import os
import sys
import time

import cv2

from hand_core import capture, config, mediapipe, net, render, tracking

os.system("cls")

class SimpleLandmark:
    __slots__ = ("x", "y", "z")

    def __init__(self, x, y, z=0.0):
        self.x = x
        self.y = y
        self.z = z


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def remap_landmarks(hand_lms, roi_params, cam_w, cam_h):
    x1, y1, roi_w, roi_h = roi_params
    remapped = []
    for lm in hand_lms:
        x = (lm.x * roi_w + x1) / cam_w
        y = (lm.y * roi_h + y1) / cam_h
        z = getattr(lm, "z", 0.0)
        remapped.append(SimpleLandmark(x, y, z))
    return remapped


def compute_palm_center_px(hand_lms, cam_w, cam_h):
    wrist = hand_lms[0]
    index_mcp = hand_lms[5]
    middle_mcp = hand_lms[9]
    ring_mcp = hand_lms[13]
    pinky_mcp = hand_lms[17]
    palm_x = (wrist.x + index_mcp.x + middle_mcp.x + ring_mcp.x + pinky_mcp.x) / 5.0
    palm_y = (wrist.y + index_mcp.y + middle_mcp.y + ring_mcp.y + pinky_mcp.y) / 5.0
    return palm_x * cam_w, palm_y * cam_h


def update_roi_from_landmarks(hand_lms, cam_w, cam_h, args, last_center, last_ts, ts_ms):
    xs = [lm.x for lm in hand_lms]
    ys = [lm.y for lm in hand_lms]
    min_x = max(0.0, min(xs))
    max_x = min(1.0, max(xs))
    min_y = max(0.0, min(ys))
    max_y = min(1.0, max(ys))

    bbox_w = max((max_x - min_x) * cam_w, args.roi_min_size)
    bbox_h = max((max_y - min_y) * cam_h, args.roi_min_size)

    palm_px = compute_palm_center_px(hand_lms, cam_w, cam_h)
    vel_x = 0.0
    vel_y = 0.0
    if last_center is not None and last_ts is not None:
        dt = max((ts_ms - last_ts) / 1000.0, 1e-3)
        vel_x = (palm_px[0] - last_center[0]) / dt
        vel_y = (palm_px[1] - last_center[1]) / dt

    pred_ms = max(0, args.roi_predict_ms)
    pred_x = palm_px[0] + vel_x * (pred_ms / 1000.0)
    pred_y = palm_px[1] + vel_y * (pred_ms / 1000.0)

    speed = (vel_x * vel_x + vel_y * vel_y) ** 0.5
    extra = 0.0
    if args.roi_vel_scale > 0:
        extra = min(args.roi_vel_margin, speed / args.roi_vel_scale)
    margin = args.roi_margin + extra

    box_w = bbox_w * (1.0 + 2.0 * margin)
    box_h = bbox_h * (1.0 + 2.0 * margin)

    x1 = int(pred_x - box_w / 2.0)
    y1 = int(pred_y - box_h / 2.0)
    x2 = int(pred_x + box_w / 2.0)
    y2 = int(pred_y + box_h / 2.0)

    x1 = clamp(x1, 0, cam_w - 1)
    y1 = clamp(y1, 0, cam_h - 1)
    x2 = clamp(x2, 1, cam_w)
    y2 = clamp(y2, 1, cam_h)

    if x2 <= x1 + 1 or y2 <= y1 + 1:
        return None, palm_px

    return (x1, y1, x2, y2), palm_px


def main():
    args = config.parse_args()

    input_scale = args.input_scale if args.input_scale > 0 else 1
    screen_scale = args.screen_scale if args.screen_scale > 0 else 1
    args.width = max(1, int(args.width / input_scale))
    args.height = max(1, int(args.height / input_scale))
    args.screen_w = max(1, int(args.screen_w / screen_scale))
    args.screen_h = max(1, int(args.screen_h / screen_scale))

    # Enable OpenCV optimizations for better performance
    cv2.setUseOptimized(True)
    cap = capture.open_cap(args.dev, args.width, args.height, args.fps)
    if cap is None:
        sys.exit(f"Can not open camera index {args.dev}")

    cam_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cam_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cam_fps = int(cap.get(cv2.CAP_PROP_FPS)) or args.fps

    print(f"Camera index: {args.dev} @ {cam_w}x{cam_h} {cam_fps}fps")
    print(f"Send cursor to: {args.send_host}:{args.send_port} | Screen map: {args.screen_w}x{args.screen_h}")
    print(f"Model: {args.model}")
    print("Press q to quit")

    sock = net.create_udp_sender()
    # Connect the UDP socket once to avoid per-send address resolution overhead
    try:
        sock.connect((args.send_host, args.send_port))
    except OSError:
        pass

    options = mediapipe.build_hand_landmarker_options(args)
    state = tracking.TrackerState()

    last_ts = -1  # ensure monotonic
    roi_box = None
    roi_miss = 0
    roi_last_center = None
    roi_last_ts = None

    with mediapipe.HandLandmarker.create_from_options(options) as landmarker:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue

            roi_params = None
            roi_frame = frame
            if args.roi and roi_box is not None:
                x1, y1, x2, y2 = roi_box
                if x2 > x1 and y2 > y1:
                    roi_frame = frame[y1:y2, x1:x2]
                    roi_params = (x1, y1, x2 - x1, y2 - y1)
                else:
                    roi_box = None

            mp_image = mediapipe.to_mp_image(roi_frame)

            # timestamp ms must be monotonically increasing
            ts = int(time.monotonic() * 1000)
            if ts <= last_ts:
                ts = last_ts + 1
            last_ts = ts

            result = landmarker.detect_for_video(mp_image, ts)

            target_px = None
            tap_click = False
            scroll_delta = 0
            debug = None
            found_hand = False

            if result and result.hand_landmarks:
                for i, hand_lms in enumerate(result.hand_landmarks):
                    hand_label = None
                    if result.handedness and i < len(result.handedness) and result.handedness[i]:
                        cat0 = result.handedness[i][0]
                        hand_label = getattr(cat0, "category_name", None) or getattr(cat0, "display_name", None)

                    if hand_label != "Right":
                        continue

                    found_hand = True
                    if roi_params is not None:
                        hand_lms = remap_landmarks(hand_lms, roi_params, cam_w, cam_h)

                    target_px, tap_click, scroll_delta, debug = tracking.process_hand(
                        hand_lms,
                        args,
                        cam_w,
                        cam_h,
                        args.mirror,
                        args.screen_w,
                        args.screen_h,
                        state,
                        ts,
                    )

                    if args.draw:
                        render.draw_debug(frame, hand_lms, cam_w, cam_h, debug, tap_click)

                    if args.roi:
                        roi_box, roi_last_center = update_roi_from_landmarks(
                            hand_lms, cam_w, cam_h, args, roi_last_center, roi_last_ts, ts
                        )
                        roi_last_ts = ts
                        roi_miss = 0

                    break  # only 1 right hand
            if args.roi and roi_box is not None and not found_hand:
                roi_miss += 1
                if roi_miss >= args.roi_fail:
                    roi_box = None
                    roi_miss = 0

            if args.draw and args.roi and roi_box is not None:
                render.draw_roi(frame, roi_box)

            if target_px is not None:
                net.send_cursor(sock, args.send_host, args.send_port, target_px, tap_click, scroll_delta)

            show = cv2.flip(frame, 1) if args.mirror else frame
            cv2.imshow("Hands -> Mouse (Tasks) (press q)", show)
            if (cv2.waitKey(1) & 0xFF) == ord('q'):
                break

    sock.close()
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
