from serial import Serial
from roboclaw import Roboclaw

rclaw = Roboclaw(Serial('/dev/ttyS1', 38400))

rclaw.forward_m1(0)
rclaw.forward_m2(0)