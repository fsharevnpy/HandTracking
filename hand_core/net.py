import socket

def create_udp_sender():
    return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def send_cursor(sock, host, port, target_px, tap_click, scroll_delta=0):
    # If the socket is connected, use send for lower overhead; otherwise fallback to sendto
    msg = f"{target_px[0]},{target_px[1]},{1 if tap_click else 0},{scroll_delta}".encode("utf-8")
    try:
        sock.send(msg)
    except (OSError, AttributeError):
        sock.sendto(msg, (host, port))
