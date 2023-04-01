import json
import time
from threading import Thread
import zmq

def worker_thread():
    cxt = zmq.Context.instance()
    worker = cxt.socket(zmq.DEALER)
    worker.setsockopt(zmq.IDENTITY, b'A')
    worker.connect("tcp://127.0.0.1:5559")

    for _ in range(10):
        request = worker.recv_multipart()
        response = request[0].decode()
        packet = response.replace("\\", "").strip('"')
        packet = json.loads(packet)
        response_json = {
            k: v for (k, v) in dict(packet).items()
        }
        print(response_json['key_' + str(_)])

        response_json['key_' + str(_)] = "data_received_" + str(_)
        # worker.send_multipart([bytes(json.dumps(response_json), 'utf-8')])

cxt = zmq.Context.instance()
client = cxt.socket(zmq.ROUTER)
client.bind('tcp://127.0.0.1:5559')

Thread(target=worker_thread).start()
time.sleep(2)

# str_request = client.recv_string()
# print(str_request)

for _ in range(10):
    request = {
        "key_" + str(_) : "data_sent_" + str(_)
    }
    client.send_multipart([b'A', bytes(json.dumps(request), 'utf-8')])

    # request = client.recv_multipart()
    # response = request[1].decode()
    # packet = response.replace("\\", "").strip('"')
    # packet = json.loads(packet)
    # response_json = {
    #     k: v for (k, v) in dict(packet).items()
    # }
    # print(response_json)
