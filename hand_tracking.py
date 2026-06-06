"""
MediaPipe hand tracking utilities.

This module supports two MediaPipe layouts:

1. Classic MediaPipe Solutions API:
   mp.solutions.hands

2. Newer MediaPipe Tasks API:
   mediapipe.tasks.python.vision.HandLandmarker

Some newer Python environments only receive the Tasks-style MediaPipe package
from pip. The fallback keeps this project usable on those installs too.
"""

from dataclasses import dataclass
from pathlib import Path
import time
from typing import List, Optional, Tuple
from urllib.error import URLError
from urllib.request import urlretrieve

import cv2
import mediapipe as mp
import numpy as np

from packaging_utils import find_existing_asset, writable_asset_path


Point = Tuple[int, int]
Rectangle = Tuple[int, int, int, int]

DEFAULT_TASK_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)
DEFAULT_TASK_MODEL_FILENAME = "hand_landmarker.task"

# MediaPipe hand landmark connections. Defining them here lets us draw a simple
# skeleton even when mp.solutions.drawing_utils is not available.
HAND_CONNECTIONS = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (13, 17),
    (17, 18),
    (18, 19),
    (19, 20),
    (0, 17),
)


@dataclass
class TrackedHand:
    """All image-space data needed by the AR window logic."""

    label: str
    score: float
    landmarks: List[Tuple[int, int, float]]
    bbox: Rectangle
    center: Point
    size: int


def _try_load_classic_solutions():
    """Return classic MediaPipe modules when available, otherwise None."""
    try:
        return (
            mp.solutions.hands,
            mp.solutions.drawing_utils,
            mp.solutions.drawing_styles,
        )
    except AttributeError:
        return None


def _load_tasks_api():
    """Load MediaPipe Tasks modules used by newer MediaPipe packages."""
    try:
        from mediapipe.tasks import python as mp_tasks_python
        from mediapipe.tasks.python import vision as mp_tasks_vision

        return mp_tasks_python, mp_tasks_vision
    except Exception as exc:
        raise RuntimeError(
            "Could not load MediaPipe hand tracking. Your installed MediaPipe "
            "package exposes neither mp.solutions.hands nor the Tasks Vision "
            "HandLandmarker API. Reinstall with:\n\n"
            "    python -m pip install --force-reinstall -r requirements.txt\n"
        ) from exc


def _ensure_task_model(model_path: Path):
    """
    Ensure the MediaPipe Hand Landmarker .task model exists.

    Newer MediaPipe Tasks requires a local model bundle. This is a small
    pretrained MediaPipe model file, not a dataset and not training data.
    """
    if model_path.exists():
        return

    model_path.parent.mkdir(parents=True, exist_ok=True)
    print("MediaPipe Tasks model not found.")
    print(f"Downloading hand landmarker model to: {model_path}")

    try:
        urlretrieve(DEFAULT_TASK_MODEL_URL, model_path)
    except (OSError, URLError) as exc:
        raise RuntimeError(
            "Could not download the MediaPipe hand landmarker model.\n\n"
            "Manual fix:\n"
            f"1. Download this file:\n   {DEFAULT_TASK_MODEL_URL}\n"
            f"2. Save it here:\n   {model_path}\n"
            "3. Run again:\n   python main.py\n"
        ) from exc


def _build_tracked_hand(label: str, score: float, landmarks: List[Tuple[int, int, float]], frame_shape) -> TrackedHand:
    """Build a TrackedHand from image-space landmarks."""
    frame_h, frame_w = frame_shape[:2]
    x_values = [point[0] for point in landmarks]
    y_values = [point[1] for point in landmarks]

    x1, y1 = min(x_values), min(y_values)
    x2, y2 = max(x_values), max(y_values)

    padding = 10
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(frame_w - 1, x2 + padding)
    y2 = min(frame_h - 1, y2 + padding)

    center = ((x1 + x2) // 2, (y1 + y2) // 2)
    size = max(x2 - x1, y2 - y1, 1)

    return TrackedHand(
        label=label,
        score=score,
        landmarks=landmarks,
        bbox=(x1, y1, x2, y2),
        center=center,
        size=size,
    )


def _draw_simple_hand_skeleton(frame, landmarks: List[Tuple[int, int, float]]):
    """Draw a lightweight hand skeleton without MediaPipe drawing utilities."""
    for start_index, end_index in HAND_CONNECTIONS:
        start = landmarks[start_index]
        end = landmarks[end_index]
        cv2.line(frame, (start[0], start[1]), (end[0], end[1]), (80, 230, 255), 2, cv2.LINE_AA)

    for x, y, _ in landmarks:
        cv2.circle(frame, (x, y), 3, (255, 255, 255), -1, cv2.LINE_AA)


class HandTracker:
    """Small wrapper around MediaPipe Hands / HandLandmarker."""

    def __init__(
        self,
        max_num_hands: int = 2,
        detection_confidence: float = 0.65,
        tracking_confidence: float = 0.60,
        processing_width: int = 640,
        task_model_path: Optional[str] = None,
    ):
        self.max_num_hands = max_num_hands
        self.processing_width = processing_width
        self.backend = "classic"

        self.hands = None
        self.hand_landmarker = None
        self.mp_hands = None
        self.mp_drawing = None
        self.mp_styles = None
        self._last_timestamp_ms = 0
        self._start_time = time.perf_counter()

        classic_modules = _try_load_classic_solutions()
        if classic_modules is not None:
            self.mp_hands, self.mp_drawing, self.mp_styles = classic_modules

            # model_complexity=0 favors speed and is usually enough for webcam AR.
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=max_num_hands,
                model_complexity=0,
                min_detection_confidence=detection_confidence,
                min_tracking_confidence=tracking_confidence,
            )
            return

        self.backend = "tasks"
        mp_tasks_python, mp_tasks_vision = _load_tasks_api()

        if task_model_path:
            model_path = Path(task_model_path).expanduser().resolve()
        else:
            model_path = find_existing_asset(DEFAULT_TASK_MODEL_FILENAME)
            if model_path is None:
                model_path = writable_asset_path(DEFAULT_TASK_MODEL_FILENAME)

        _ensure_task_model(model_path)

        base_options = mp_tasks_python.BaseOptions(model_asset_path=str(model_path))
        options = mp_tasks_vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_tasks_vision.RunningMode.VIDEO,
            num_hands=max_num_hands,
            min_hand_detection_confidence=detection_confidence,
            min_hand_presence_confidence=tracking_confidence,
            min_tracking_confidence=tracking_confidence,
        )
        self.hand_landmarker = mp_tasks_vision.HandLandmarker.create_from_options(options)

    def close(self):
        """Release MediaPipe resources."""
        if self.hands is not None:
            self.hands.close()
        if self.hand_landmarker is not None:
            self.hand_landmarker.close()

    def _resize_for_processing(self, frame):
        """Resize a copy for MediaPipe while keeping the original for display."""
        h, w = frame.shape[:2]
        if self.processing_width <= 0 or w <= self.processing_width:
            return frame

        scale = self.processing_width / float(w)
        new_size = (self.processing_width, int(h * scale))
        return cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)

    def _next_timestamp_ms(self) -> int:
        """Return a strictly increasing timestamp for MediaPipe video mode."""
        elapsed_ms = int((time.perf_counter() - self._start_time) * 1000)
        timestamp_ms = max(elapsed_ms, self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        return timestamp_ms

    def find_hands(self, frame, draw_landmarks: bool = False) -> List[TrackedHand]:
        """
        Detect hands in a BGR frame.

        Landmarks are returned in the coordinate system of the original frame,
        even though MediaPipe may receive a smaller processing copy.
        """
        if self.backend == "classic":
            return self._find_hands_classic(frame, draw_landmarks)
        return self._find_hands_tasks(frame, draw_landmarks)

    def _find_hands_classic(self, frame, draw_landmarks: bool) -> List[TrackedHand]:
        original_h, original_w = frame.shape[:2]
        processing_frame = self._resize_for_processing(frame)

        rgb = cv2.cvtColor(processing_frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self.hands.process(rgb)

        detected_hands: List[TrackedHand] = []
        if not results.multi_hand_landmarks:
            return detected_hands

        handedness_list = results.multi_handedness or []

        for hand_index, hand_landmarks in enumerate(results.multi_hand_landmarks):
            landmarks: List[Tuple[int, int, float]] = []

            for lm in hand_landmarks.landmark:
                x = int(np.clip(lm.x * original_w, 0, original_w - 1))
                y = int(np.clip(lm.y * original_h, 0, original_h - 1))
                landmarks.append((x, y, lm.z))

            label = "Unknown"
            score = 0.0
            if hand_index < len(handedness_list):
                classification = handedness_list[hand_index].classification[0]
                label = classification.label
                score = float(classification.score)

            detected_hands.append(_build_tracked_hand(label, score, landmarks, frame.shape))

            if draw_landmarks:
                self.mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_styles.get_default_hand_landmarks_style(),
                    self.mp_styles.get_default_hand_connections_style(),
                )

        return detected_hands

    def _find_hands_tasks(self, frame, draw_landmarks: bool) -> List[TrackedHand]:
        original_h, original_w = frame.shape[:2]
        processing_frame = self._resize_for_processing(frame)

        rgb = cv2.cvtColor(processing_frame, cv2.COLOR_BGR2RGB)
        rgb = np.ascontiguousarray(rgb)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self.hand_landmarker.detect_for_video(mp_image, self._next_timestamp_ms())

        detected_hands: List[TrackedHand] = []
        if not result.hand_landmarks:
            return detected_hands

        for hand_index, hand_landmarks in enumerate(result.hand_landmarks):
            landmarks: List[Tuple[int, int, float]] = []

            for lm in hand_landmarks:
                x = int(np.clip(lm.x * original_w, 0, original_w - 1))
                y = int(np.clip(lm.y * original_h, 0, original_h - 1))
                landmarks.append((x, y, lm.z))

            label = "Unknown"
            score = 0.0
            if result.handedness and hand_index < len(result.handedness) and result.handedness[hand_index]:
                category = result.handedness[hand_index][0]
                label = (
                    getattr(category, "category_name", None)
                    or getattr(category, "display_name", None)
                    or "Unknown"
                )
                score = float(getattr(category, "score", 0.0))

            detected_hands.append(_build_tracked_hand(label, score, landmarks, frame.shape))

            if draw_landmarks:
                _draw_simple_hand_skeleton(frame, landmarks)

        return detected_hands

    def get_filter_window(
        self,
        hands: List[TrackedHand],
        frame_shape,
    ) -> Optional[Rectangle]:
        """
        Estimate the AR rectangle between two hands.

        The two hand boxes act like left and right handles. Moving the hands
        apart widens the window; raising or lowering them moves the window.
        """
        if len(hands) < 2:
            return None

        frame_h, frame_w = frame_shape[:2]
        left_hand, right_hand = sorted(hands[:2], key=lambda hand: hand.center[0])

        # Require the hands to be separated enough to form a readable window.
        distance_x = abs(right_hand.center[0] - left_hand.center[0])
        average_hand_size = (left_hand.size + right_hand.size) / 2.0
        min_distance = max(130, int(frame_w * 0.16))
        if distance_x < min_distance:
            return None

        center_x = int((left_hand.center[0] + right_hand.center[0]) / 2)
        center_y = int((left_hand.center[1] + right_hand.center[1]) / 2)

        # Use the gap between the two hand boxes when possible so the filter
        # window feels like it is floating between the hands, not over them.
        inner_left = left_hand.bbox[2] + int(average_hand_size * 0.12)
        inner_right = right_hand.bbox[0] - int(average_hand_size * 0.12)
        gap_width = inner_right - inner_left

        if gap_width > frame_w * 0.12:
            window_width = gap_width
        else:
            window_width = int(distance_x - average_hand_size * 0.65)

        # Clamp the size so the window remains cinematic and usable.
        min_width = int(frame_w * 0.22)
        max_width = int(frame_w * 0.78)
        window_width = int(np.clip(window_width, min_width, max_width))

        # A 16:9 rectangle reads like a futuristic video panel.
        window_height = int(window_width * 9 / 16)

        # If the hands are at different heights, expand vertically a bit so
        # the window still visually connects both handles.
        vertical_offset = abs(right_hand.center[1] - left_hand.center[1])
        window_height = max(window_height, int(vertical_offset + average_hand_size * 0.55))

        min_height = int(frame_h * 0.20)
        max_height = int(frame_h * 0.72)
        window_height = int(np.clip(window_height, min_height, max_height))

        x1 = center_x - window_width // 2
        y1 = center_y - window_height // 2
        x2 = x1 + window_width
        y2 = y1 + window_height

        # Keep the rectangle inside the camera frame.
        margin = 18
        if x1 < margin:
            x2 += margin - x1
            x1 = margin
        if y1 < margin:
            y2 += margin - y1
            y1 = margin
        if x2 > frame_w - margin:
            x1 -= x2 - (frame_w - margin)
            x2 = frame_w - margin
        if y2 > frame_h - margin:
            y1 -= y2 - (frame_h - margin)
            y2 = frame_h - margin

        x1 = int(np.clip(x1, 0, frame_w - 1))
        y1 = int(np.clip(y1, 0, frame_h - 1))
        x2 = int(np.clip(x2, x1 + 1, frame_w))
        y2 = int(np.clip(y2, y1 + 1, frame_h))

        return (x1, y1, x2, y2)
