import zmq
import json
import sys

from serial import Serial
from time import sleep, perf_counter
from math import copysign
from typing import Tuple
from threading import Thread, Timer

def clamp(mn, mx, n): return min(max(n, mn), mx)

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
    def __init__(self, host, port):
        print(f"Listening on {host} : {port}")

        context = zmq.Context()
        self.socket = context.socket(zmq.REP)
        self.socket.bind(f"tcp://{host}:{port}")
        
        # serial_kick = Serial('/dev/ttyS1', 38400)
        # serial_wheels = Serial('/dev/ttyUSB0', 38400)

        #self.rclaw_kick = Roboclaw(serial_kick)
        #self.rclaw_wheels = Roboclaw(serial_wheels)
        
        self.prev_command = None
        # Prev wheels speed (python_roboclaw had some issues about reporting speeds)
        self.prev_wheels = (0.0, 0.0)
        # Linear acceleration rate (in percent output/s)
        self.ramp = 1.0
        # Last frame time
        self.prev_time = 0.0 # seconds

        # check when most recent heartbeat packet was received, terminate if 
        # it has been more than 1 second without a packet
        self.heartbeat_time = 0.0 # time until last heartbeat
        self.heart_attack_threshold = 10.0 # latency after which robot will shut down
        self.dead = False
        
        Timer(0.5, self.heartbeat).start()

    def execute(self, cjson: json):

        right_stick = cjson["right_stick_y"]
        left_stick = cjson["left_stick_y"]
        right_trigger = cjson["right_trigger"]
        left_trigger = cjson["left_trigger"]

        # this code is all paurticular to the roboclaw motordriver API,
        # so it needs to be changed
        """
        # Differential driving
        delta = perf_counter() - self.prev_time # seconds

        target_wheels = differential_ik(left_stick, right_stick)
        target_diff = ( min(target_wheels[0] - self.prev_wheels[0], delta * self.ramp)
                      , min(target_wheels[1] - self.prev_wheels[1], delta * self.ramp)
                      )
        self.rclaw_wheels.forward_backward_m1(
            clamp(-1.0, 1.0, self.prev_wheels[0] + target_diff[0])
        )
        self.rclaw_wheels.forward_backward_m2(
            clamp(-1.0, 1.0, self.prev_wheels[1] + target_diff[1])
        )

        ## power the wheels based on tank controls
        # self.rclaw_wheels.forward_backward_m1(right_stick)
        # self.rclaw_wheels.forward_backward_m2(left_stick)
        
        # Check if trigger state has changed because running commands over the 
        # USB bus is expensive
        if (right_trigger, left_trigger) != (self.prev_command["right_trigger"], self.prev_command["left_trigger"]):
           rclaw_kick_target = min(64 + 64 * (left_trigger - right_trigger), 127)
           self.rclaw_kick.forward_backward_m1(rclaw_kick_target)
           self.rclaw_kick.forward_backward_m1(rclaw_kick_target)
        """

        if self.prev_command == None: self.prev_command = cjson

        print(cjson)

    # main loo for robot controller
    def listen(self):
        self.prev_time = perf_counter()

        try:
            while not self.dead:
                # load control packets into json object
                controller_state = self.socket.recv_string()
                cs = controller_state.replace("\\", "").strip("\"")
                controller_json = {k: int(v) for (k, v) in dict(json.loads(cs)).items()}

                # check for packet type
                if controller_json["type"] == "heartbeat":
                    self.heartbeat_time = 0.0
                elif controller_json["tye"] == "controller":
                    self.execute(controller_json)
                    self.socket.send_string(f"Done")
                    self.heartbeat_time = 0.0

                self.prev_time = perf_counter()

        except BaseException as e:
            print(e)
            self.motor_kill()
            sys.exit()

    # check the time from the last heartbeat packet, kill the robot if threshold has passed
    def heartbeat(self):
        if self.heartbeat_time > self.heart_attack_threshold:
            self.motor_kill()
            self.dead = True

    # kill the robot
    def motor_kill(self):
        print("robot is dead")
        self.dead = True

def main():
    r = RobotController("*", 5555)
    r.listen()

if __name__ == "__main__":
    main()
