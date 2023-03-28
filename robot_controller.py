import can
import zmq
import json
import sys
import traceback

from serial import Serial
from time import sleep, perf_counter
from math import copysign
from typing import Tuple
rpm

def clamp(mn, mx, n):
    return min(max(n, mn), mx)


# Shamelessly ripped from WPILib's differential drive
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


class RobotController:
    # Explanation of VESC (i.e. the protocol our drivetrain motor controllers use) CAN bus messages
    # -----------------------------------------------------------------------
    #
    # Each CAN bus message has two parts (for our purposes):
    #
    # (1) An "arbitration ID" that uniquely identifies the type of message being sent (i.e. setting
    #     the duty cycle) and the target controller ID
    # (2) A data segment that contains a command payload (if any) of up to 8 bytes
    #
    # Example
    # -------
    #
    # To set the duty cycle to 10% for controller 0,
    #
    # - The arbitration ID is: 0x00000000
    #                                  ^^ Controller ID 0 (up to 256 IDs available)
    #                            ^^^^^^   VESC message type (0x000000 corresponds to "set duty cycle")
    # - The payload/data is:   0x00002710
    #                            ^^^^^^^^ "set duty cyle" expects a number from 0 to 100_000, where
    #                                     50_000 is a 50% duty cycle. So, 0x2710 corresponds to
    #                                     0.1 * 100_000.
    CAN_ADDRESS = "can0"
    # How often the CAN bus is transmitting/receiving messages
    CAN_BITRATE = 125000  # Hz

    ZMQ_HOST = "*"
    ZMQ_PORT = 5555

    CONTROLLER_ID_L = 0x00000000
    CONTROLLER_ID_R = 0x00000001

    # Construct a byte array containing a duty cycle payload for CAN transmission.
    @staticmethod
    def duty_cycle_can(cycle: float) -> bytes:
        int(cycle * 100000).to_bytes(4, byteorder="big")

    # TODO Not tested. Not sure what current unit is.
    # # Convert a STATUS_1 CAN message to a tuple of (rpm, current, and duty cycle)
    # @staticmethod
    # def status_1_can(data: bytes) -> Optional[Tuple[int, float, float]]:
    #     if len(data) != 8:
    #         return None

    #     rpm = int.from_bytes(data[0:4], byteorder='big')
    #     current = int.from_bytes(data[4:6], byteorder='big')
    #     duty = int.from_bytes(data[6:8], byteorder='big')

    #     return (rpm, float(current) / 10.0, float(duty) / 1000.0)

    def __init__(self):
        context = zmq.Context()

        self.socket = context.socket(zmq.REP)
        self.socket.bind(f"tcp://{ZMQ_HOST}:{ZMQ_PORT}")

        print(f"Listening on {ZMQ_HOST}:{ZMQ_PORT}.")

        # Drivetrain CAN bus socket
        self.can = can.Bus(
            bustype="socketcan", channel=CAN_ADDRESS, bitrate=CAN_BITRATE
        )

        # Spinner roboclaw controller
        self.rclaw_spinner = Roboclaw(Serial("/dev/ttyS1", 38400))

        self.prev_command = None
        # Prev wheels speed
        self.prev_wheels = (0.0, 0.0)
        # Linear acceleration rate (in percent output/s)
        self.ramp = 1.0
        # Last frame time
        self.prev_time = 0.0  # seconds

        # Check when most recent heartbeat packet was received, terminate if
        # it has been more than 1 second without a packet.
        self.heartbeat_time = 0.0  # time until last heartbeat
        self.heart_attack_threshold = 10.0  # latency after which robot will shut down
        self.heartbeat_delta = 0.5
        self.dead = False

    # Command the drivetrain ESC duty cycle to the specified x velocity and z rotation.
    #
    # Parameters
    # ----------
    # x_vel:
    #   forward velociy value from -1.0 to 1.0
    # z_rot:
    #   rotation value from -1.0 to 1.0
    def drive(self, x_vel: float, z_rot: float):
        delta = perf_counter() - self.prev_time  # seconds

        target_wheels = differential_ik(l, r)
        target_diff = (
            min(target_wheels[0] - self.prev_wheels[0], delta * self.ramp),
            min(target_wheels[1] - self.prev_wheels[1], delta * self.ramp),
        )

        self.can.send(
            can.Message(
                arbitration_id=CONTROLLER_ID_L,
                data=RobotController.duty_cycle_can(
                    clamp(-1.0, 1.0, self.prev_wheels[0] + target_diff[0])
                ),
                is_extended_id=True,
            )
        )
        self.can.send(
            can.Message(
                arbitration_id=CONTROLLER_ID_R,
                data=RobotController.duty_cycle_can(
                    clamp(-1.0, 1.0, self.prev_wheels[1] + target_diff[1])
                ),
                is_extended_id=True,
            )
        )

    # Command the spinner
    #
    # Parameters
    # ----------
    # vel:
    #   velociy value from -1.0 to 1.0
    def spin(self, vel: float):
        self.rclaw_spinner.forward_backward_m1(min(64 + 64 * vel, 127))

    def execute(self, cjson: json):
        pause = cjson["pause"]
        right_stick = cjson["right_stick_y"]
        left_stick = cjson["left_stick_y"]
        right_trigger = cjson["right_trigger"]
        left_trigger = cjson["left_trigger"]

        self.drive(stick_l, stick_r)

        if (right_trigger, left_trigger) != (
            self.prev_command["right_trigger"],
            self.prev_command["left_trigger"],
        ):
            self.spin(left_trigger - right_trigger)

        if self.prev_command == None:
            self.prev_command = cjson

        print(cjson)

    # main loo for robot controller
    def listen(self):
        self.prev_time = perf_counter()
        receiving_data = False

        try:
            while not self.dead:
                # load control packets into json object
                packet = self.socket.recv_string()
                packet = packet.replace("\\", "").strip('"')
                packet = json.loads(packet)

                if packet["pause"]:
                    self.motor_kill()

                # start hearbeat protocol if this is our first packet
                if not receiving_data:
                    self.heartbeat(self.heartbeat_delta)
                    receiving_data = True

                # check for packet type
                if packet["type"] == "heartbeat":
                    self.heartbeat_time = 0.0
                elif packet["type"] == "controller":
                    controller_json = {
                        k: int(v) for (k, v) in dict(packet["data"]).items()
                    }
                    self.execute(controller_json)
                    self.socket.send_string(f"Done")
                    self.heartbeat_time = 0.0

                self.prev_time = perf_counter()
        except BaseException:
            print(traceback.format_exc())
            self.motor_kill()
            sys.exit()

    # check the time from the last heartbeat packet, kill the robot if threshold has passed
    def heartbeat(self, delta: float):
        self.heartbeat_time += delta
        print("Checking heartbeat...")

        if self.heartbeat_time > self.heart_attack_threshold:
            print(
                f"Heartbeat not found after threshold time of {self.heart_attack_threshold} seconds, terminating..."
            )
            self.motor_kill()
            self.dead = True

        Timer(delta, self.heartbeat, args=(delta,)).start()

    # kill the robot
    def motor_kill(self):
        print("Robot is dead.")

if __name__ == "__main__":
    RobotController().listen()
