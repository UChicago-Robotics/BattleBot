import json
import zmq
import json

ip = "192.168.56.1"
port = 5555

context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect(f"tcp://{ip}:{port}")
print(f"Connected to {ip} {port}")


controls = {
    "type": "controller",
    "data": {
        "left_stick_y": 0,
        "right_stick_y": 0,
        "left_trigger": 0,
        "right_trigger": 0
    }
}

while True:
    controls_json = json.dumps(controls)
    socket.send_string(controls_json)

    message = socket.recv_string()
    print(f"Server replied: {message}\n")