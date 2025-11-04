import time
import threading
import queue
from concurrent import futures

import grpc
from chat_proto import chat_pb2, chat_pb2_grpc
import os, sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Estado en memoria: room -> set de suscriptores
_rooms = {}     # str -> set[Subscriber]
_history = {}   # str -> list[ChatMessage]
_lock = threading.RLock()

MAX_HISTORY = 500

class Subscriber:
    def __init__(self, user, room):
        self.user = user
        self.room = room
        self.out_q = queue.Queue()
        self.active = True

    def send(self, msg):
        if self.active:
            try:
                self.out_q.put_nowait(msg)
            except Exception:
                pass

def ensure_room(room: str):
    with _lock:
        _rooms.setdefault(room, set())
        _history.setdefault(room, [])

def push_history(room: str, msg: chat_pb2.ChatMessage):
    with _lock:
        ensure_room(room)
        _history[room].append(msg)
        if len(_history[room]) > MAX_HISTORY:
            _history[room] = _history[room][-MAX_HISTORY:]

def broadcast(room: str, msg: chat_pb2.ChatMessage):
    with _lock:
        subs = list(_rooms.get(room, []))
    for s in subs:
        s.send(msg)

class ChatService(chat_pb2_grpc.ChatServiceServicer):
    def Join(self, request, context):
        user, room = request.user.strip(), request.room.strip()
        if not user or not room:
            return chat_pb2.JoinReply(ok=False, message="user y room son obligatorios")
        ensure_room(room)
        return chat_pb2.JoinReply(ok=True, message=f"Usuario {user} unido a {room}")

    def History(self, request, context):
        room = request.room.strip()
        limit = max(1, request.limit or 20)
        ensure_room(room)
        with _lock:
            last = _history[room][-limit:]
        for msg in last:
            yield msg

    def Chat(self, request_iterator, context):
        """
        Bidireccional: cada cliente mantiene una Queue de salida. Un hilo recibe,
        este generador drena la Queue y va emitiendo los mensajes al cliente.
        """
        sub = None
        recv_done = threading.Event()

        def recv_loop():
            nonlocal sub
            first = True
            try:
                for incoming in request_iterator:
                    user = incoming.sender.strip()
                    room = incoming.room.strip()

                    if first:
                        first = False
                        if not user or not room:
                            break
                        ensure_room(room)
                        sub = Subscriber(user=user, room=room)
                        with _lock:
                            _rooms[room].add(sub)

                        # Mensaje de sistema: join
                        join_msg = chat_pb2.ChatMessage(
                            sender="system",
                            room=room,
                            text=f"{user} se ha unido a la sala.",
                            timestamp=int(time.time() * 1000),
                        )
                        push_history(room, join_msg)
                        broadcast(room, join_msg)
                        continue

                    # Mensaje normal
                    text = (incoming.text or "").strip()
                    if text:
                        server_msg = chat_pb2.ChatMessage(
                            sender=user,
                            room=room,
                            text=text,
                            timestamp=int(time.time() * 1000),
                        )
                        push_history(room, server_msg)
                        broadcast(room, server_msg)
            finally:
                recv_done.set()

        t = threading.Thread(target=recv_loop, daemon=True)
        t.start()

        try:
            while True:
                if not context.is_active():
                    break
                if sub is None:
                    if recv_done.is_set():
                        break
                    time.sleep(0.01)
                    continue
                try:
                    msg = sub.out_q.get(timeout=0.2)
                    yield msg
                except queue.Empty:
                    if recv_done.is_set() and sub.out_q.empty():
                        break
                    continue
        finally:
            if sub:
                sub.active = False
                with _lock:
                    if sub.room in _rooms and sub in _rooms[sub.room]:
                        _rooms[sub.room].remove(sub)
                leave = chat_pb2.ChatMessage(
                    sender="system",
                    room=sub.room,
                    text=f"{sub.user} salió de la sala.",
                    timestamp=int(time.time() * 1000),
                )
                push_history(sub.room, leave)
                broadcast(sub.room, leave)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=32))
    chat_pb2_grpc.add_ChatServiceServicer_to_server(ChatService(), server)
    addr = "0.0.0.0:50051"
    server.add_insecure_port(addr)
    print(f"gRPC Chat server escuchando en {addr} (HTTP/2 sobre TCP/IP)")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
