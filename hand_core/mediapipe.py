import cv2
import mediapipe as mp

vision = mp.tasks.vision
HandLandmarker = vision.HandLandmarker
HandLandmarkerOptions = vision.HandLandmarkerOptions
RunningMode = vision.RunningMode
BaseOptions = mp.tasks.BaseOptions

def build_hand_landmarker_options(args):
    return HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=args.model),
        running_mode=RunningMode.VIDEO,
        num_hands=args.max_hands,
        min_hand_detection_confidence=args.det,
        min_hand_presence_confidence=args.presence,
        min_tracking_confidence=args.trk,
    )

def to_mp_image(frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
