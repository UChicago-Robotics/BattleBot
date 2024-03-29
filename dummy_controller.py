import zmq
import json

ip = "192.168.8.233"
port = 5555

context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect(f"tcp://{ip}:{port}")
print(f"Attempting to connect to {ip}:{port}...")

controls = {
    "type": "controller",
    "data": {
        "invert_button": False,
        "left_stick_y": 0,
        "right_stick_y": 0,
        "left_trigger": 0,
        "right_trigger": 0
    }
}

while True:
    controls_json = json.dumps(controls)
    socket.send_json(controls_json)

    message = socket.recv_string()
    print(f"Server replied: {message}\n")