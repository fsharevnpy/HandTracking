import cv2

def draw_debug(frame, hand_lms, cam_w, cam_h, debug, tap_click):
    for lm in hand_lms:
        cx, cy = int(lm.x * cam_w), int(lm.y * cam_h)
        cv2.circle(frame, (cx, cy), 2, (0, 255, 255), -1)

    tip = debug["tip"]
    pip = debug["pip"]
    sx = debug["sx"]
    sy = debug["sy"]

    cv2.circle(
        frame,
        (int(((tip.x + pip.x) * 0.5) * cam_w), int(((tip.y + pip.y) * 0.5) * cam_h)),
        6,
        (0, 255, 0),
        -1,
    )
    cv2.putText(
        frame,
        f"Left ({sx},{sy}) tap={int(tap_click)} grab={int(debug['grab'])} scroll={debug['scroll']}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def draw_roi(frame, roi_box):
    if not roi_box:
        return
    x1, y1, x2, y2 = roi_box
    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 200, 0), 2)
