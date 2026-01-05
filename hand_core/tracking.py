from collections import deque
import numpy as np
from .config import INDEX_PIP_ID, INDEX_TIP_ID

class TrackerState:
    def __init__(self):
        self.ema_x = None
        self.ema_y = None
        self.prev_rel_px = None
        self.prev_palm_px = None
        self.speed_hist = deque(maxlen=60)
        self.tap_armed_ts = None
        self.tap_cooldown_until = 0
        self.grab_active = False
        self.grab_last_palm_y = None


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def process_hand(hand_lms, args, cam_w, cam_h, mirror, screen_w, screen_h, state, ts_ms):
    tip = hand_lms[INDEX_TIP_ID]
    pip = hand_lms[INDEX_PIP_ID]

    x_norm = (tip.x + pip.x) * 0.5
    y_norm = (tip.y + pip.y) * 0.5

    if mirror:
        x_norm = 1.0 - x_norm

    sx = int(x_norm * screen_w)
    sy = int(y_norm * screen_h)
    sx = clamp(sx, 0, screen_w - 1)
    sy = clamp(sy, 0, screen_h - 1)

    if state.ema_x is None:
        state.ema_x, state.ema_y = sx, sy
    else:
        a = args.ema_alpha
        state.ema_x = a * sx + (1.0 - a) * state.ema_x
        state.ema_y = a * sy + (1.0 - a) * state.ema_y

    target_px = (int(state.ema_x), int(state.ema_y))

    #####TAP LOGIC#####
    tap_click = False
    scroll_delta = 0

    wrist = hand_lms[0]
    index_mcp = hand_lms[5]
    middle_mcp = hand_lms[9]
    ring_mcp = hand_lms[13]
    pinky_mcp = hand_lms[17]

    palm_x = (wrist.x + index_mcp.x + middle_mcp.x + ring_mcp.x + pinky_mcp.x) / 5.0
    palm_y = (wrist.y + index_mcp.y + middle_mcp.y + ring_mcp.y + pinky_mcp.y) / 5.0

    palm_px = (int(palm_x * cam_w), int(palm_y * cam_h))
    tip_px = (int(tip.x * cam_w), int(tip.y * cam_h))
    rel_px = (tip_px[0] - palm_px[0], tip_px[1] - palm_px[1])

    speed = 0.0
    if state.prev_rel_px is not None:
        dx = rel_px[0] - state.prev_rel_px[0]
        dy = rel_px[1] - state.prev_rel_px[1]
        speed = float((dx * dx + dy * dy) ** 0.5)
        state.speed_hist.append(speed)

    palm_speed = 0.0
    if state.prev_palm_px is not None:
        dxp = palm_px[0] - state.prev_palm_px[0]
        dyp = palm_px[1] - state.prev_palm_px[1]
        palm_speed = float((dxp * dxp + dyp * dyp) ** 0.5)

    if ts_ms >= state.tap_cooldown_until:
        if state.tap_armed_ts is None:
            if speed >= args.tap_speed and palm_speed <= args.palm_speed:
                state.tap_armed_ts = ts_ms
        else:
            if speed <= args.tap_release:
                tap_click = True
                state.tap_armed_ts = None
                state.tap_cooldown_until = ts_ms + args.tap_cooldown_ms
            elif ts_ms - state.tap_armed_ts > args.tap_window_ms:
                state.tap_armed_ts = None

    #####GRAB / SCROLL LOGIC#####
    mid_scale = ((middle_mcp.x - wrist.x) ** 2 + (middle_mcp.y - wrist.y) ** 2) ** 0.5
    scale = mid_scale if mid_scale > 1e-6 else 1e-6
    index_tip = hand_lms[8]
    other_tips = [hand_lms[12], hand_lms[16], hand_lms[20]]
    curled_other = 0
    for tip_lm in other_tips:
        dist = ((tip_lm.x - palm_x) ** 2 + (tip_lm.y - palm_y) ** 2) ** 0.5
        if dist <= scale * args.grab_ratio:
            curled_other += 1

    index_dist = ((index_tip.x - palm_x) ** 2 + (index_tip.y - palm_y) ** 2) ** 0.5
    index_curled = index_dist <= scale * args.grab_index_ratio

    all_curled = index_curled and curled_other == 3

    if not state.grab_active and all_curled:
        state.grab_active = True
        state.grab_last_palm_y = palm_px[1]
    elif state.grab_active and not all_curled:
        state.grab_active = False
        state.grab_last_palm_y = None

    if state.grab_active:
        if state.grab_last_palm_y is None:
            state.grab_last_palm_y = palm_px[1]
        dy = palm_px[1] - state.grab_last_palm_y
        if abs(dy) >= args.scroll_deadzone:
            scroll_delta = int(-dy * args.scroll_gain)
            scroll_delta = clamp(scroll_delta, -args.scroll_max, args.scroll_max)
        state.grab_last_palm_y = palm_px[1]

    state.prev_rel_px = rel_px
    state.prev_palm_px = palm_px

    debug = {
        "x_norm": x_norm,
        "y_norm": y_norm,
        "sx": sx,
        "sy": sy,
        "tip": tip,
        "pip": pip,
        "grab": state.grab_active,
        "scroll": scroll_delta,
    }
    return target_px, tap_click, scroll_delta, debug
