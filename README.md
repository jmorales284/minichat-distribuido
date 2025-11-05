# Mini-Chat Distribuido en gRPC

Sistema de chat en tiempo real usando gRPC con streaming bidireccional (full-duplex).

## 📋 Especificaciones Implementadas

### ✅ Cobertura de Temas

- **gRPC bidireccional (streaming full duplex)**: El método `Chat()` implementa `stream ChatMessage returns stream ChatMessage`
- **Mensajes asíncronos**: Usa threading y queues para manejo asíncrono
- **Modelo Cliente-Servidor**: Servidor actúa como broker de mensajes
- **Protocolos en capas**:
  - **Capa Aplicación**: Chat (mensajes de texto)
  - **RPC**: gRPC
  - **Transporte**: HTTP/2
  - **Red**: TCP/IP

## 🏗️ Arquitectura y Flujo

### Diagrama de Streaming Bidireccional

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  Cliente 1  │         │  Servidor   │         │  Cliente 2  │
│   (Juan)    │         │  (Broker)   │         │   (María)   │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │
       │  1. Join Request      │                       │
       ├──────────────────────>│                       │
       │  2. Join Reply        │                       │
       │<──────────────────────┤                       │
       │                       │                       │
       │  3. History Request   │                       │
       ├──────────────────────>│                       │
       │  4. History Stream    │                       │
       │<──────────────────────┤                       │
       │                       │                       │
       │  5. Chat Stream       │                       │
       ├──────────────────────>│                       │
       │  6. Chat Stream       │                       │
       │<──────────────────────┤                       │
       │                       │                       │
       │                       │  7. Chat Stream       │
       │                       │<──────────────────────┤
       │                       │                       │
       │  8. Mensaje "Hola"    │                       │
       ├──────────────────────>│                       │
       │                       │ [RECIBIDO]            │
       │                       │ [RETRANSMITIENDO]    │
       │                       │                       │
       │  9. Mensaje "Hola"    │  9. Mensaje "Hola"   │
       │<──────────────────────┤──────────────────────>│
       │                       │                       │
       │                       │  10. Mensaje "Adiós"  │
       │                       │<──────────────────────┤
       │                       │ [RECIBIDO]            │
       │                       │ [RETRANSMITIENDO]    │
       │                       │                       │
       │  11. Mensaje "Adiós"  │                       │
       │<──────────────────────┤                       │
```

### Flujo de Hilos en el Servidor

```
┌─────────────────────────────────────────────────────────┐
│                    Servidor gRPC                        │
│  ThreadPoolExecutor (max_workers=32)                    │
└─────────────────────────────────────────────────────────┘
                          │
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
   ┌─────────┐      ┌─────────┐      ┌─────────┐
   │ Cliente │      │ Cliente │      │ Cliente │
   │    1    │      │    2    │      │    3    │
   └────┬────┘      └────┬────┘      └────┬────┘
        │                │                 │
        │                │                 │
   ┌────▼────────────────▼─────────────────▼────┐
   │         ChatService.Chat()                 │
   │  ┌──────────────────────────────────────┐  │
   │  │  recv_loop() [Thread]                │  │
   │  │  - Recibe mensajes del cliente       │  │
   │  │  - Crea Subscriber                   │  │
   │  │  - Guarda en _history                │  │
   │  │  - Llama broadcast()                 │  │
   │  └──────────────────────────────────────┘  │
   │                │                            │
   │                ▼                            │
   │  ┌──────────────────────────────────────┐  │
   │  │  Generator (yield)                   │  │
   │  │  - Lee de sub.out_q                  │  │
   │  │  - Envía mensajes al cliente         │  │
   │  └──────────────────────────────────────┘  │
   │                │                            │
   │                ▼                            │
   │  ┌──────────────────────────────────────┐  │
   │  │  broadcast(room, msg)               │  │
   │  │  - Itera sobre _rooms[room]          │  │
   │  │  - Envía a todos los Subscriber      │  │
   │  └──────────────────────────────────────┘  │
   └────────────────────────────────────────────┘
```

### Estructura de Datos en Memoria

```
_rooms = {
    "general": {Subscriber(user="Juan", room="general"), 
                Subscriber(user="María", room="general")},
    "privado": {Subscriber(user="Pedro", room="privado")}
}

_history = {
    "general": [ChatMessage(...), ChatMessage(...), ...],
    "privado": [ChatMessage(...)]
}
```

## 🚀 Cómo Usar

### 1. Instalar Dependencias

```powershell
pip install -r requirements.txt
```

### 2. Iniciar el Servidor

```powershell
cd minichat-distribuido
$env:PYTHONPATH="C:\Users\andre\Desktop\Distribuidos\Minichat\minichat-distribuido"
python server/server.py
```

El servidor mostrará logs de todos los mensajes recibidos y retransmitidos:
```
[14:30:15] [SERVIDOR] ✓ Juan se unió a #general
[14:30:20] [SERVIDOR] ← RECIBIDO de Juan@general: Hola
[14:30:20] [SERVIDOR] → RETRANSMITIENDO a 2 cliente(s) en #general: Hola
```

### 3. Conectar Clientes

En terminales separadas:

**Terminal 2 - Cliente 1:**
```powershell
cd minichat-distribuido
$env:PYTHONPATH="C:\Users\andre\Desktop\Distribuidos\Minichat\minichat-distribuido"
python client/client.py Juan general
```

**Terminal 3 - Cliente 2:**
```powershell
cd minichat-distribuido
$env:PYTHONPATH="C:\Users\andre\Desktop\Distribuidos\Minichat\minichat-distribuido"
python client/client.py María general
```

### 4. Enviar Mensajes

Simplemente escribe mensajes y presiona Enter. Los mensajes se enviarán en tiempo real a todos los clientes en la misma sala.

Para salir, escribe `/quit`.

## 🔍 Sniffing HTTP/2

Para demostrar los frames HTTP/2 que gRPC utiliza, puedes usar las siguientes herramientas:

### Opción 1: Wireshark (Recomendado)

1. **Instalar Wireshark**: https://www.wireshark.org/download.html

2. **Configurar Wireshark**:
   - Abre Wireshark
   - Selecciona la interfaz de red (ej: "Ethernet" o "Wi-Fi")
   - En el filtro, escribe: `tcp.port == 50051`

3. **Capturar tráfico**:
   - Inicia la captura antes de ejecutar el servidor
   - Ejecuta el servidor y los clientes
   - Los frames HTTP/2 aparecerán como:
     - `SETTINGS` (configuración inicial)
     - `HEADERS` (headers de gRPC)
     - `DATA` (mensajes serializados con protobuf)
     - `WINDOW_UPDATE` (control de flujo)

4. **Ver detalles HTTP/2**:
   - Click derecho en un paquete → "Follow" → "HTTP2 Stream"
   - Verás los frames HTTP/2 en detalle

### Opción 2: tcpdump (Linux/Mac)

```bash
# Capturar tráfico en el puerto 50051
sudo tcpdump -i any -A -s 0 'tcp port 50051' -w grpc_capture.pcap

# Ver con Wireshark después
wireshark grpc_capture.pcap
```

### Opción 3: Script Python con scapy (Opcional)

Ver `tools/sniff_grpc.py` para un script básico de sniffing (requiere permisos de administrador).

## 📊 Tipos de Comunicación gRPC Implementados

1. **Unario** (`Join`): Cliente → Servidor (request/response simple)
2. **Server-streaming** (`History`): Cliente → Servidor → Cliente (stream de respuestas)
3. **Bidirectional streaming** (`Chat`): Cliente ↔ Servidor (stream bidireccional simultáneo)

## 🎯 Evidencias de Cumplimiento

### ✅ Streaming Bidireccional
- El método `Chat()` usa `stream ChatMessage returns stream ChatMessage`
- Múltiples clientes pueden enviar y recibir simultáneamente

### ✅ Mensajes Asíncronos
- Threading: `recv_loop()` corre en un hilo separado
- Queues: `sub.out_q` para comunicación entre hilos
- Generator: `yield` para streaming de salida

### ✅ Servidor como Broker
- `_rooms` mantiene lista de suscriptores por sala
- `broadcast()` retransmite a todos los clientes
- `_history` mantiene historial de mensajes

### ✅ Logs del Servidor
- Muestra cada mensaje recibido
- Muestra cada retransmisión con conteo de clientes
- Logs de join/leave de usuarios

## 📝 Notas Técnicas

- **Puerto**: 50051 (puerto estándar de gRPC)
- **Protocolo**: HTTP/2 sobre TCP/IP
- **Serialización**: Protocol Buffers (protobuf)
- **Concurrencia**: ThreadPoolExecutor con 32 workers
- **Historial**: Máximo 500 mensajes por sala en memoria

## 🔧 Troubleshooting

**Error: "ModuleNotFoundError: No module named 'chat_proto'"**
- Asegúrate de establecer PYTHONPATH antes de ejecutar
- O ejecuta desde el directorio raíz del proyecto

**Error: "Address already in use"**
- El puerto 50051 está ocupado
- Cambia el puerto en `server/server.py` línea 156

**Los mensajes no se reciben en tiempo real**
- Verifica que el servidor esté corriendo
- Verifica que los clientes estén en la misma sala
- Revisa los logs del servidor para ver errores

