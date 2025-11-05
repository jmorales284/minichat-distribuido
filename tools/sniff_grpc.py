"""
Script básico para sniffing de tráfico gRPC/HTTP/2
Requiere permisos de administrador y la librería scapy

Instalación:
    pip install scapy

Uso (Windows como administrador):
    python tools/sniff_grpc.py

Nota: En Windows, scapy puede requerir instalación de WinPcap o Npcap
"""

try:
    from scapy.all import sniff, IP, TCP, Raw
    import sys
except ImportError:
    print("ERROR: Requiere scapy. Instálalo con: pip install scapy")
    sys.exit(1)

def analyze_grpc_packet(packet):
    """Analiza paquetes TCP en el puerto 50051 (gRPC)"""
    if packet.haslayer(TCP):
        tcp = packet[TCP]
        
        # Verificar si es el puerto 50051
        if tcp.dport == 50051 or tcp.sport == 50051:
            direction = "→ SERVIDOR" if tcp.dport == 50051 else "← CLIENTE"
            
            # Intentar leer datos de la capa TCP
            if packet.haslayer(Raw):
                data = packet[Raw].load
                print(f"[{direction}] Puerto: {tcp.dport if tcp.dport == 50051 else tcp.sport}")
                print(f"    Tamaño: {len(data)} bytes")
                print(f"    Datos (hex): {data[:50].hex()}")
                print(f"    Datos (ascii): {data[:50]}")
                print()
            
            # Información de flags TCP
            flags = []
            if tcp.flags & 0x02: flags.append("SYN")
            if tcp.flags & 0x10: flags.append("ACK")
            if tcp.flags & 0x01: flags.append("FIN")
            if tcp.flags & 0x08: flags.append("PSH")
            
            if flags:
                print(f"    Flags: {', '.join(flags)}")
                print()

def main():
    print("=" * 60)
    print("Sniffer gRPC/HTTP/2 - Puerto 50051")
    print("=" * 60)
    print("Presiona Ctrl+C para detener")
    print()
    
    try:
        # Filtrar solo tráfico TCP en puerto 50051
        sniff(
            filter="tcp port 50051",
            prn=analyze_grpc_packet,
            store=False
        )
    except PermissionError:
        print("ERROR: Se requieren permisos de administrador")
        print("Ejecuta este script como administrador")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nSniffing detenido por el usuario")
        sys.exit(0)

if __name__ == "__main__":
    main()

