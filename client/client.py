import sys
import threading
import queue
import time

import grpc
from chat_proto import chat_pb2, chat_pb2_grpc
import os, sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def fmt(ts):
    try:
        return time.strftime("%H:%M:%S", time.localtime(int(ts)/1000))
    except Exception:
        return ""

def input_thread(send_q: queue.Queue):
    try:
        while True:
            line = input()
            if line.strip().lower() == "/quit":
                send_q.put(None)
                break
            send_q.put(line.rstrip("\n"))
    except EOFError:
        send_q.put(None)

def request_iter(user, room, send_q: queue.Queue):
    # Primer mensaje: configura sender/room
    yield chat_pb2.ChatMessage(sender=user, room=room, text="", timestamp=0)
    while True:
        item = send_q.get()
        if item is None:
            break
        yield chat_pb2.ChatMessage(sender=user, room=room, text=item, timestamp=0)

def main():
    if len(sys.argv) < 3:
        print("Uso: python client.py <user> <room> [host:port]")
        sys.exit(1)

    user = sys.argv[1]
    room = sys.argv[2]
    target = sys.argv[3] if len(sys.argv) > 3 else "localhost:50051"

    channel = grpc.insecure_channel(target)
    stub = chat_pb2_grpc.ChatServiceStub(channel)

    # 1) Unario: Join
    reply = stub.Join(chat_pb2.JoinRequest(user=user, room=room))
    if not reply.ok:
        print("[JOIN] Rechazado:", reply.message)
        sys.exit(1)
    print("[JOIN]", reply.message)

    # 2) Server-streaming: History
    print(f"[HISTORY] Últimos 20 mensajes de #{room}:")
    for msg in stub.History(chat_pb2.HistoryRequest(room=room, limit=20)):
        print(f"[{fmt(msg.timestamp)}] {msg.sender}@{msg.room}: {msg.text}")

    # 3) Bidireccional: Chat
    send_q = queue.Queue()
    th_in = threading.Thread(target=input_thread, args=(send_q,), daemon=True)
    th_in.start()

    responses = stub.Chat(request_iter(user, room, send_q))
    try:
        for msg in responses:
            print(f"[{fmt(msg.timestamp)}] {msg.sender}@{msg.room}: {msg.text}")
    except grpc.RpcError as e:
        print("Conexión cerrada:", e)
    finally:
        th_in.join(timeout=0.2)

if __name__ == "__main__":
    main()
