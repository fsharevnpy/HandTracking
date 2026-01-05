import argparse

INDEX_PIP_ID = 6
INDEX_TIP_ID = 8

def get_screen_size_fallback():
    try:
        import ctypes

        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        return 1920, 1080

def parse_args():
    sw, sh = get_screen_size_fallback()
    ap = argparse.ArgumentParser()

    ap.add_argument("--dev", type=int, default=0, help="Camera index (0,1,2,...)")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--input-scale", type=float, default=2.5)

    ap.add_argument("--fps", type=int, default=30)

    ap.add_argument("--mirror", action="store_true")

    ap.add_argument("--screen-w", type=int, default=sw)
    ap.add_argument("--screen-h", type=int, default=sh)
    ap.add_argument("--screen-scale", type=float, default=0.8)

    ap.add_argument("--send-host", default="127.0.0.1")
    ap.add_argument("--send-port", type=int, default=5005)

    # MediaPipe Tasks model
    ap.add_argument(
        "--model",
        default=r".\model\hand_landmarker.task",
        help="Path to hand_landmarker.task",
    )

    # Task options
    ap.add_argument("--max-hands", type=int, default=1)
    ap.add_argument("--det", type=float, default=0.6, help="min_hand_detection_confidence")
    ap.add_argument("--presence", type=float, default=0.6, help="min_hand_presence_confidence")
    ap.add_argument("--trk", type=float, default=0.8, help="min_tracking_confidence")

    ap.add_argument("--ema-alpha", type=float, default=0.2)
    ap.add_argument("--draw", action="store_true")

    # Tap click (tip speed relative to palm)
    ap.add_argument("--tap-speed", type=float, default=14.0, help="tip speed threshold (px/frame)")
    ap.add_argument("--tap-release", type=float, default=12.0, help="speed to release tap arm")
    ap.add_argument("--palm-speed", type=float, default=6.0, help="max palm speed to allow tap")
    ap.add_argument("--tap-window-ms", type=int, default=200, help="max ms between arm and release")
    ap.add_argument("--tap-cooldown-ms", type=int, default=20, help="cooldown after click")

    # Grab-and-drag scrolling
    ap.add_argument("--grab-ratio", type=float, default=0.55, help="fingertip distance ratio to palm")
    ap.add_argument("--grab-index-ratio", type=float, default=0.45, help="index tip ratio to palm")
    ap.add_argument("--grab-count", type=int, default=3, help="curled fingers to start grab")
    ap.add_argument("--grab-release-count", type=int, default=1, help="curled fingers to release grab")
    ap.add_argument("--scroll-gain", type=float, default=8.0, help="wheel units per pixel")
    ap.add_argument("--scroll-deadzone", type=int, default=2, help="min palm delta for scroll")
    ap.add_argument("--scroll-max", type=int, default=600, help="max wheel units per frame")
    return ap.parse_args()
