import os
import sys
import time

import cv2

from hand_core import capture, config, mediapipe, net, render, tracking

os.system("cls")

def main():
    args = config.parse_args()

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

    options = mediapipe.build_hand_landmarker_options(args)
    state = tracking.TrackerState()

    last_ts = -1  # ensure monotonic

    with mediapipe.HandLandmarker.create_from_options(options) as landmarker:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue

            mp_image = mediapipe.to_mp_image(frame)

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

            if result and result.hand_landmarks:
                for i, hand_lms in enumerate(result.hand_landmarks):
                    hand_label = None
                    if result.handedness and i < len(result.handedness) and result.handedness[i]:
                        cat0 = result.handedness[i][0]
                        hand_label = getattr(cat0, "category_name", None) or getattr(cat0, "display_name", None)

                    if hand_label != "Right":
                        continue

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

                    break  # only 1 left hand

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
