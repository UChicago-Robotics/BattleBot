import sys
import zmq

host, port = "192.168.8.245", "5555"
if len(sys.argv) > 1:
    port =  sys.argv[1]
    int(port)

if len(sys.argv) > 2:
    port1 =  sys.argv[2]
    int(port1)

# Socket to talk to server
context = zmq.Context()
socket = context.socket(zmq.SUB)

print("Collecting updates from weather server...")
socket.connect(f"tcp://{host}:{port}")

# Subscribe to zipcode, default is NYC, 10001
#topicfilter = "10001"
socket.setsockopt_string(zmq.SUBSCRIBE, "")

# Process 5 updates
total_value = 0
for update_nbr in range (5):
    string = socket.recv_string()
    topic, messagedata = string.split()
    total_value += int(messagedata)
    print(topic, messagedata)

