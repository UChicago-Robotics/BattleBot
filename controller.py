import zmq
import can
import serial
import json
import logging

from typing import *
from roboclaw import Roboclaw
from math import copysign
from time import perf_counter
from threading import Lock

logging.basicConfig(format="[{asctime:<8}] {levelname:<10} {message}", style='{', datefmt='%H:%M:%S')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def clamp(mn, mx, n):
    return min(max(n, mn), mx)

# Checks if a specified delta was exceeded when calling `notify`. Thread-safe.
class Watchdog:
    def __init__(self, expires: float):
        # The last time the watchdog was notified.
        self.prev_check = perf_counter()
        self.expires = expires
        self.lock = Lock()

    # Update the watchdog to keep it alive.
    def notify(self):
        with self.lock:
            curr_time = perf_counter()
            delta = curr_time - self.prev_check
            self.prev_check = curr_time

    # Check if the watchdog is alive.
    @property
    def alive(self) -> bool:
        with self.lock:
            curr_time = perf_counter()
            delta = curr_time - self.prev_check

            return delta < self.expires

class Spinner:
    def __init__(self, uart_address: str = "/dev/ttyS1", uart_baud: int = 38400):
        self.roboclaw = Roboclaw(serial.Serial(uart_address, uart_baud))

    def spin(self, vel: float):
        self.roboclaw.forward_backward_m1(min(64 + int(64 * vel), 127))

# Utility class to calculate wheel outputs for differential driving.
class DifferentialDrive:
    # Shamelessly ripped from WPILib's differential drive
    @staticmethod
    def differential_ik(x_vel: float, z_rot: float) -> Tuple[float, float]:
        x_vel = clamp(-1.0, 1.0, x_vel)
        z_rot = clamp(-1.0, 1.0, z_rot)

        # Square the inputs to make it less sensitive at low speed
        x_vel = copysign(x_vel * x_vel, x_vel)
        z_rot = copysign(z_rot * z_rot, z_rot)

        speed_l = x_vel - z_rot
        speed_r = x_vel + z_rot

        greater = max(abs(x_vel), abs(z_rot))
        lesser = min(abs(x_vel), abs(z_rot))

        if greater == 0.0:
            return (0.0, 0.0)
        else:
            saturated = (greater + lesser) / greater

            speed_l /= saturated
            speed_r /= saturated

            return (speed_l, speed_r)

    def __init__(self):
        self.prev_time = perf_counter()
        self.prev_wheels = (0.0, 0.0)
        self.ramp = 1.0

    def drive(self, x_vel: float, z_rot: float) -> (float, float):
        delta = perf_counter() - self.prev_time # seconds

        target = DifferentialDrive.differential_ik(x_vel, z_rot)
        target_diff = (
            min(target[0] - self.prev_wheels[0], delta * self.ramp),
            min(target[1] - self.prev_wheels[1], delta * self.ramp),
        )

        out = (
            clamp(-1.0, 1.0, self.prev_wheels[0] + target_diff[0]),
            clamp(-1.0, 1.0, self.prev_wheels[1] + target_diff[1]),
        )

        self.prev_wheels = out

        return out

class Drivetrain(DifferentialDrive):
    def __init__(
        self,
        controller_id_l: int,
        controller_id_r: int,
        can_channel: str = "can0",
        can_bitrate: int = 125_000
    ):
        super().__init__()

        self.controller_id_l = controller_id_l
        self.controller_id_r = controller_id_r

        self.can = can.Bus(bustype="socketcan", channel=can_channel, bitrate=can_bitrate)

        # Track the last time a CAN command was sent to avoid saturating the CAN bus queue.
        self.can_command_prev = perf_counter()
        self.can_bitrate = 125_000

    # Move the drivetrain. Skips sending CAN commands when called faster than 125kbits/s.
    def drive(self, x_vel: float, z_rot: float) -> (float, float):
        curr_time = perf_counter()

        can_command_delta = curr_time - self.can_command_prev

        if can_command_delta > 5.0:
            logger.info("Sending CAN message.")

            (l_duty, r_duty) = super().drive(x_vel, z_rot)

            self.can.send(
                can.Message(
                    arbitration_id=self.controller_id_l,
                    data=int(l_duty * 100_000).to_bytes(4, byteorder="big", signed=True),
                    is_extended_id=True
                )
            )
            self.can.send(
                can.Message(
                    arbitration_id=self.controller_id_r,
                    data=(-int(r_duty * 100_000)).to_bytes(4, byteorder="big", signed=True),
                    is_extended_id=True
                )
            )

            self.can_command_prev = curr_time

            return (l_duty, r_duty)
        else:
            return self.prev_wheels

class Controller:
    HEART_ATTACK_THRESHOLD = 1.0

    def __init__(self):
        # Movement stuff
        self.drivetrain = Drivetrain(0x00000000, 0x00000001)
        self.spinner = Spinner()

        # Networking
        self.context = zmq.Context()

        self.receiver = self.context.socket(zmq.PULL)
        self.receiver.bind(f"tcp://*:5555")

        logger.info("Socket bound.")

        self.watchdog = Watchdog(Controller.HEART_ATTACK_THRESHOLD)

        self.curr_command = None # dictionary

    # Get the current controller command. If a new command is available, the current command is
    # updated.
    def command(self) -> Optional[dict]:
        packet = None

        # Consume all received packets until we get the latest one.
        while True:
            try:
                packet = self.receiver.recv_string(flags=zmq.NOBLOCK)
                self.watchdog.notify() # Make sure we notify the watchdog to keep it alive.
                packet = packet.replace("\\", "").strip('"')
                packet = json.loads(packet)
            except zmq.Again as e:
                break

        if packet is not None:
            self.curr_command = {k: v for (k, v) in dict(packet).items()}
            logger.info(f"Received: \n{self.curr_command}")

        return self.curr_command

    # Run the main controller loop.
    def update(self):
        command_prev = None
        command = self.command()

        if self.watchdog.alive:
            if command is not None:
                right_stick = command["right_stick_y"]
                left_stick = command["left_stick_y"]
                right_trigger = command["right_trigger"]
                left_trigger = command["left_trigger"]
                #inverted = 1.0 if not command["invert_button"] else -1.0

                self.drivetrain.drive(left_stick, right_stick)
                self.spinner.spin(left_trigger - right_trigger)

                command_prev = command
        else:
            logger.info("Controller not connected.")

            self.drivetrain.drive(0.0, 0.0)
            self.spinner.spin(0.0)

            if command_prev != command:
                # Reset the watchdog because the connection is back!
                self.watchdog = Watchdog(Controller.HEART_ATTACK_THRESHOLD)

if __name__ == "__main__":
    controller = Controller()

    logger.info("Controller configured.")

    while True:
        controller.update()
