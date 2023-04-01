import time
import zmq
context = zmq.Context()
socket = context.socket(zmq.PUB)

host, port = "*", "5555"
socket.bind(f'tcp://{host}:{port}')

# Allow clients to connect before sending data
i = 0
while True:
    print(f"Sending packet {i}...")
    socket.send_string(f"test {i}")
    time.sleep(1)
    i += 1
    