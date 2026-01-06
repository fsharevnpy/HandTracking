import cv2

def open_cap(idx, w, h, fps):
    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            return None

    # Smaller buffer reduces latency by avoiding old frames.
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    # On Windows webcams, using MJPG often yields higher FPS at given resolutions
    try:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    except Exception:
        pass

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    cap.set(cv2.CAP_PROP_FPS, fps)
    for _ in range(5):
        cap.read()
    ok, _ = cap.read()
    if not ok:
        cap.release()
        return None
    return cap
