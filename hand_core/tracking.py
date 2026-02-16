from collections import deque
from .config import INDEX_PIP_ID, INDEX_TIP_ID

class TrackerState:
    def __init__(self):
        self.ema_x = None
        self.ema_y = None
        self.prev_palm_px = None
        self.grab_active = False
        self.grab_last_palm_y = None
        # Pinch-click state (thumb tip touching index tip)
        self.pinch_active = False
        self.pinch_cooldown_until = 0
        self.pinch_armed_ts = None


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

    #####PINCH (THUMB-INDEX) CLICK LOGIC#####
    click = False
    scroll_delta = 0
    hold_down = False

    wrist = hand_lms[0]
    index_mcp = hand_lms[5]
    middle_mcp = hand_lms[9]
    ring_mcp = hand_lms[13]
    pinky_mcp = hand_lms[17]

    palm_x = (wrist.x + index_mcp.x + middle_mcp.x + ring_mcp.x + pinky_mcp.x) / 5.0
    palm_y = (wrist.y + index_mcp.y + middle_mcp.y + ring_mcp.y + pinky_mcp.y) / 5.0

    palm_px = (int(palm_x * cam_w), int(palm_y * cam_h))
    # tip-relative speed no longer used (tap logic removed)

    palm_speed = 0.0
    if state.prev_palm_px is not None:
        dxp = palm_px[0] - state.prev_palm_px[0]
        dyp = palm_px[1] - state.prev_palm_px[1]
        palm_speed = float((dxp * dxp + dyp * dyp) ** 0.5)

    # Compute thumb-index pinch based on scaled distance
    thumb_tip = hand_lms[4]
    index_tip = hand_lms[8]
    # Use wrist-middle MCP distance as scale
    mid_scale_sq = (middle_mcp.x - wrist.x) ** 2 + (middle_mcp.y - wrist.y) ** 2
    scale_sq = mid_scale_sq if mid_scale_sq > 1e-12 else 1e-12
    # Hysteresis: separate close/open thresholds to reduce false positives
    pinch_ratio_close = float(getattr(args, "pinch_ratio", 0.3))
    pinch_ratio_open = float(getattr(args, "pinch_open_ratio", 0.45))
    pinch_close_thresh_sq = scale_sq * (pinch_ratio_close ** 2)
    pinch_open_thresh_sq = scale_sq * (pinch_ratio_open ** 2)
    pinch_dist_sq = (thumb_tip.x - index_tip.x) ** 2 + (thumb_tip.y - index_tip.y) ** 2
    pinch_closed = pinch_dist_sq <= pinch_close_thresh_sq
    pinch_open = pinch_dist_sq >= pinch_open_thresh_sq

    pinch_cooldown_ms = int(getattr(args, "pinch_cooldown_ms", 250))
    pinch_min_hold_ms = int(getattr(args, "pinch_min_hold_ms", 25))
    pinch_palm_speed = float(getattr(args, "pinch_palm_speed", getattr(args, "palm_speed", 12.0)))

    if not state.pinch_active:
        if pinch_closed:
            if state.pinch_armed_ts is None:
                state.pinch_armed_ts = ts_ms
            else:
                held_long_enough = (ts_ms - state.pinch_armed_ts) >= pinch_min_hold_ms
                palm_stable = palm_speed <= pinch_palm_speed
                if held_long_enough and palm_stable and ts_ms >= state.pinch_cooldown_until:
                    click = True
                    state.pinch_active = True
                    state.pinch_cooldown_until = ts_ms + pinch_cooldown_ms
        else:
            state.pinch_armed_ts = None
    else:
        if pinch_open:
            state.pinch_active = False
            state.pinch_armed_ts = None

    # Tap logic removed: pinch is the sole trigger for clicks.

    #####GRAB / SCROLL LOGIC#####
    # Use squared distances to avoid expensive sqrt operations
    mid_scale_sq = (middle_mcp.x - wrist.x) ** 2 + (middle_mcp.y - wrist.y) ** 2
    scale_sq = mid_scale_sq if mid_scale_sq > 1e-12 else 1e-12
    index_tip = hand_lms[8]
    other_tips = [hand_lms[12], hand_lms[16], hand_lms[20]]
    curled_other = 0
    grab_thresh_sq = scale_sq * (args.grab_ratio ** 2)
    for tip_lm in other_tips:
        dist_sq = (tip_lm.x - palm_x) ** 2 + (tip_lm.y - palm_y) ** 2
        if dist_sq <= grab_thresh_sq:
            curled_other += 1

    index_dist_sq = (index_tip.x - palm_x) ** 2 + (index_tip.y - palm_y) ** 2
    index_curled = index_dist_sq <= scale_sq * (args.grab_index_ratio ** 2)

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

    if bool(getattr(args, "fist_hold", False)):
        hold_down = state.grab_active

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
        "pinch": state.pinch_active,
        "pinch_dist_sq": pinch_dist_sq,
    }
    return target_px, click, scroll_delta, hold_down, debug
