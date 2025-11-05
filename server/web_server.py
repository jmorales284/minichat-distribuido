"""
Servidor Web FastAPI que actúa como puente entre el frontend web
y el servidor gRPC existente
"""
import asyncio
import json
import time
import queue as sync_queue
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import grpc
from chat_proto import chat_pb2, chat_pb2_grpc
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

app = FastAPI(title="Mini-Chat Web Interface")

# Montar archivos estáticos
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "client", "web")), name="static")

# Conexiones WebSocket activas
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.user_connections: dict = {}  # user@room -> WebSocket

    async def connect(self, websocket: WebSocket, user: str, room: str):
        # El websocket ya debe estar aceptado antes de llamar a este método
        self.active_connections.add(websocket)
        key = f"{user}@{room}"
        self.user_connections[key] = websocket

    def disconnect(self, websocket: WebSocket, user: str = None, room: str = None):
        self.active_connections.discard(websocket)
        if user and room:
            key = f"{user}@{room}"
            self.user_connections.pop(key, None)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

manager = ConnectionManager()

# Cliente gRPC asíncrono
class GRPCChatClient:
    def __init__(self, host: str = "localhost", port: int = 50051):
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = chat_pb2_grpc.ChatServiceStub(self.channel)
        self.send_queue = asyncio.Queue()
        self.sync_send_queue = sync_queue.Queue()  # Queue síncrona para el iterator
        self.running = False

    async def join(self, user: str, room: str) -> dict:
        """Unirse a una sala"""
        try:
            reply = self.stub.Join(chat_pb2.JoinRequest(user=user, room=room))
            return {"ok": reply.ok, "message": reply.message}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    async def get_history(self, room: str, limit: int = 50) -> list:
        """Obtener historial de mensajes"""
        messages = []
        try:
            for msg in self.stub.History(chat_pb2.HistoryRequest(room=room, limit=limit)):
                messages.append({
                    "sender": msg.sender,
                    "room": msg.room,
                    "text": msg.text,
                    "timestamp": msg.timestamp
                })
        except Exception as e:
            print(f"Error obteniendo historial: {e}")
        return messages

    async def send_message(self, user: str, room: str, text: str):
        """Enviar un mensaje"""
        # Poner en la queue síncrona (la async es solo para compatibilidad)
        self.sync_send_queue.put({
            "sender": user,
            "room": room,
            "text": text
        })

    def create_request_iterator(self, user: str, room: str):
        """Generador para el stream bidireccional"""
        # Primer mensaje: configuración
        yield chat_pb2.ChatMessage(sender=user, room=room, text="", timestamp=0)
        
        # Mensajes del usuario
        while self.running:
            try:
                msg = self.sync_send_queue.get(timeout=0.1)
                yield chat_pb2.ChatMessage(
                    sender=msg["sender"],
                    room=msg["room"],
                    text=msg["text"],
                    timestamp=0
                )
            except:
                continue

    async def start_chat_stream(self, user: str, room: str, websocket: WebSocket):
        """Iniciar stream bidireccional y enviar mensajes al WebSocket"""
        self.running = True
        
        # Ejecutar el stream en un thread pool para no bloquear
        loop = asyncio.get_event_loop()
        
        def run_stream():
            try:
                responses = self.stub.Chat(self.create_request_iterator(user, room))
                for msg in responses:
                    # Enviar al WebSocket de forma asíncrona
                    asyncio.run_coroutine_threadsafe(
                        websocket.send_json({
                            "type": "message",
                            "sender": msg.sender,
                            "room": msg.room,
                            "text": msg.text,
                            "timestamp": msg.timestamp
                        }),
                        loop
                    )
            except Exception as e:
                print(f"Error en stream: {e}")
                try:
                    asyncio.run_coroutine_threadsafe(
                        websocket.send_json({
                            "type": "error",
                            "message": str(e)
                        }),
                        loop
                    )
                except:
                    pass
            finally:
                self.running = False
        
        # Ejecutar en thread separado
        await loop.run_in_executor(None, run_stream)

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Servir la página principal"""
    html_path = os.path.join(BASE_DIR, "client", "web", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Endpoint WebSocket para comunicación en tiempo real"""
    user = None
    room = None
    grpc_client = None
    
    # Aceptar conexión primero
    await websocket.accept()
    
    try:
        # Esperar mensaje de inicialización
        init_data = await websocket.receive_json()
        
        if init_data.get("type") != "init":
            await websocket.send_json({"type": "error", "message": "Se requiere mensaje de inicialización"})
            await websocket.close()
            return
        
        user = init_data.get("user", "").strip()
        room = init_data.get("room", "").strip()
        grpc_host = init_data.get("host", "localhost")
        grpc_port = int(init_data.get("port", 50051))
        
        if not user or not room:
            await websocket.send_json({"type": "error", "message": "Usuario y sala son obligatorios"})
            await websocket.close()
            return
        
        # Conectar al manager
        await manager.connect(websocket, user, room)
        
        # Crear cliente gRPC
        grpc_client = GRPCChatClient(host=grpc_host, port=grpc_port)
        
        # Unirse a la sala
        join_result = await grpc_client.join(user, room)
        if not join_result["ok"]:
            await websocket.send_json({
                "type": "error",
                "message": join_result["message"]
            })
            await websocket.close()
            return
        
        await websocket.send_json({
            "type": "joined",
            "message": join_result["message"]
        })
        
        # Obtener historial
        history = await grpc_client.get_history(room, limit=50)
        await websocket.send_json({
            "type": "history",
            "messages": history
        })
        
        # Iniciar stream de chat en background
        stream_task = asyncio.create_task(
            grpc_client.start_chat_stream(user, room, websocket)
        )
        
        # Escuchar mensajes del cliente
        while True:
            try:
                data = await websocket.receive_json()
                
                if data.get("type") == "message":
                    text = data.get("text", "").strip()
                    if text:
                        await grpc_client.send_message(user, room, text)
                
                elif data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"Error procesando mensaje: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
        
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Error en WebSocket: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        if grpc_client:
            grpc_client.running = False
        if user and room:
            manager.disconnect(websocket, user, room)
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading
    
    def open_browser():
        """Abrir el navegador después de un breve delay"""
        import time
        time.sleep(1.5)  # Esperar a que el servidor inicie
        webbrowser.open("http://localhost:8000")
    
    # Iniciar thread para abrir navegador
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    print("=" * 60)
    print("Servidor Web FastAPI iniciando...")
    print("Accede a: http://localhost:8000")
    print("El navegador se abrirá automáticamente...")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)

