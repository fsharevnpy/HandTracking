import socket

def create_udp_sender():
    return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def send_cursor(sock, host, port, target_px, outlier):
    msg = f"{target_px[0]},{target_px[1]},{1 if outlier else 0}".encode("utf-8")
    sock.sendto(msg, (host, port))
