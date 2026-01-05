import os
os.system('cls')

import ctypes
import socket
import time

user32 = ctypes.windll.user32

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP   = 0x0004

def set_cursor(x: int, y: int):
    user32.SetCursorPos(int(x), int(y))

def left_click():
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_LEFTUP,   0, 0, 0, 0)

def double_click():
    left_click()
    time.sleep(0.02)
    left_click()

def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

def get_screen_size():
    w = user32.GetSystemMetrics(0)
    h = user32.GetSystemMetrics(1)
    return w, h

if __name__ == "__main__":
    HOST = "127.0.0.1"
    PORT = 5005

    w, h = get_screen_size()
    print(f"Listening UDP on {HOST}:{PORT}")
    print(f"Screen: {w}x{h}")
    print("Expected message: 'x,y,p' (e.g. 960,820,1). Ctrl+C to stop.")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    sock.settimeout(1.0)

    cur_x, cur_y = w // 2, h // 2
    alpha = 0.35

    prev_p = 0
    cooldown_ms = 20
    double_click_ms = 300
    last_click = 0.0
    pending_click_time = None
    
    try:
        while True:
            try:
                data, _ = sock.recvfrom(256)
            except socket.timeout:
                continue

            s = data.decode("utf-8", errors="ignore").strip()
            if not s:
                continue

            try:
                xs, ys, ps = (t.strip() for t in s.split(",", 2))
                x = int(float(xs))
                y = int(float(ys))
                p = int(float(ps))  # 0/1
            except ValueError:
                continue

            x = clamp(x, 0, w - 1)
            y = clamp(y, 0, h - 1)

            cur_x = int(cur_x + alpha * (x - cur_x))
            cur_y = int(cur_y + alpha * (y - cur_y))
            set_cursor(cur_x, cur_y)

            now = time.monotonic()
            if p == 1 and prev_p == 0:
                if pending_click_time is not None and (now - pending_click_time) * 1000.0 <= double_click_ms:
                    if (now - last_click) * 1000.0 >= cooldown_ms:
                        double_click()
                        last_click = now
                    pending_click_time = None
                else:
                    pending_click_time = now

            if pending_click_time is not None and (now - pending_click_time) * 1000.0 > double_click_ms:
                if (now - last_click) * 1000.0 >= cooldown_ms:
                    left_click()
                    last_click = now
                pending_click_time = None
                
            prev_p = 1 if p else 0

            time.sleep(0.001)

    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        sock.close()
