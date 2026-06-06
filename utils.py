"""
Drawing, smoothing, and small utility helpers for AR Filter Window.
"""

import math
import time
from typing import Optional, Tuple

import cv2
import numpy as np


Rectangle = Tuple[int, int, int, int]
Color = Tuple[int, int, int]


class SmoothRectangle:
    """
    Exponential moving average for rectangle coordinates.

    Hand tracking boxes can jitter frame to frame. Smoothing makes the filter
    window feel physically anchored instead of noisy.
    """

    def __init__(self, alpha: float = 0.30, hold_frames: int = 8):
        self.alpha = float(np.clip(alpha, 0.01, 1.0))
        self.hold_frames = max(0, hold_frames)
        self.current: Optional[np.ndarray] = None
        self.missed_frames = 0

    def update(self, rect: Optional[Rectangle]) -> Optional[Rectangle]:
        if rect is None:
            self.missed_frames += 1
            if self.current is not None and self.missed_frames <= self.hold_frames:
                return tuple(np.round(self.current).astype(int))
            self.current = None
            return None

        self.missed_frames = 0
        new_rect = np.array(rect, dtype=np.float32)

        if self.current is None:
            self.current = new_rect
        else:
            self.current = (1.0 - self.alpha) * self.current + self.alpha * new_rect

        return tuple(np.round(self.current).astype(int))


def update_fps(current_fps: float, previous_time: float):
    """
    Return a smoothed FPS value and the new timestamp.

    Smoothing prevents the HUD from flickering between rapidly changing values.
    """
    now = time.perf_counter()
    delta = max(now - previous_time, 1e-6)
    instant_fps = 1.0 / delta

    if current_fps <= 0:
        smoothed = instant_fps
    else:
        smoothed = current_fps * 0.88 + instant_fps * 0.12

    return smoothed, now


def _alpha_blend(frame, overlay, alpha: float):
    """Blend an overlay onto frame in-place."""
    cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)


def _draw_text(
    frame,
    text: str,
    origin: Tuple[int, int],
    scale: float = 0.55,
    color: Color = (230, 245, 255),
    thickness: int = 1,
):
    """Draw crisp HUD text with a subtle dark shadow."""
    x, y = origin
    cv2.putText(frame, text, (x + 1, y + 1), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def _draw_panel(frame, rect: Rectangle, alpha: float = 0.36):
    """Draw a translucent dark HUD panel."""
    x1, y1, x2, y2 = rect
    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (8, 12, 18), -1)
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (90, 225, 255), 1)
    _alpha_blend(frame, overlay, alpha)


def draw_cinematic_bars(frame):
    """Add subtle letterbox bars for a cinematic look."""
    h, w = frame.shape[:2]
    bar_h = max(18, int(h * 0.055))
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, bar_h), (0, 0, 0), -1)
    cv2.rectangle(overlay, (0, h - bar_h), (w, h), (0, 0, 0), -1)
    _alpha_blend(frame, overlay, 0.28)


def draw_glowing_window(frame, rect: Rectangle, color: Color, label: str = ""):
    """
    Draw a glowing rectangle with bracket corners and small scan lines.

    This function only draws UI. The filter itself is applied in filters.py.
    """
    x1, y1, x2, y2 = rect
    h, w = frame.shape[:2]
    x1 = int(np.clip(x1, 0, w - 1))
    y1 = int(np.clip(y1, 0, h - 1))
    x2 = int(np.clip(x2, 0, w - 1))
    y2 = int(np.clip(y2, 0, h - 1))

    # Glow layers.
    for i, alpha in enumerate((0.10, 0.08, 0.06)):
        overlay = frame.copy()
        thickness = 10 + i * 8
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, thickness)
        _alpha_blend(frame, overlay, alpha)

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)
    cv2.rectangle(frame, (x1 + 4, y1 + 4), (x2 - 4, y2 - 4), (255, 255, 255), 1, cv2.LINE_AA)

    # Corner brackets.
    length = max(28, min(x2 - x1, y2 - y1) // 8)
    thickness = 3
    corners = [
        ((x1, y1), (x1 + length, y1), (x1, y1 + length)),
        ((x2, y1), (x2 - length, y1), (x2, y1 + length)),
        ((x1, y2), (x1 + length, y2), (x1, y2 - length)),
        ((x2, y2), (x2 - length, y2), (x2, y2 - length)),
    ]
    for start, end_a, end_b in corners:
        cv2.line(frame, start, end_a, color, thickness, cv2.LINE_AA)
        cv2.line(frame, start, end_b, color, thickness, cv2.LINE_AA)

    # Internal horizontal scan lines.
    overlay = frame.copy()
    for y in range(y1 + 12, y2, 18):
        cv2.line(overlay, (x1 + 8, y), (x2 - 8, y), color, 1, cv2.LINE_AA)
    _alpha_blend(frame, overlay, 0.07)

    if label:
        label_y = max(24, y1 - 12)
        _draw_text(frame, f"[ {label.upper()} ]", (x1, label_y), scale=0.55, color=color, thickness=1)


def draw_waiting_prompt(frame):
    """Draw the center prompt shown when two hands are not detected."""
    h, w = frame.shape[:2]
    center = (w // 2, h // 2)
    color = (90, 220, 255)

    overlay = frame.copy()
    cv2.circle(overlay, center, 72, color, 1, cv2.LINE_AA)
    cv2.circle(overlay, center, 42, color, 1, cv2.LINE_AA)
    cv2.line(overlay, (center[0] - 96, center[1]), (center[0] - 28, center[1]), color, 1, cv2.LINE_AA)
    cv2.line(overlay, (center[0] + 28, center[1]), (center[0] + 96, center[1]), color, 1, cv2.LINE_AA)
    cv2.line(overlay, (center[0], center[1] - 96), (center[0], center[1] - 28), color, 1, cv2.LINE_AA)
    cv2.line(overlay, (center[0], center[1] + 28), (center[0], center[1] + 96), color, 1, cv2.LINE_AA)
    _alpha_blend(frame, overlay, 0.42)

    message = "RAISE BOTH HANDS TO OPEN FILTER WINDOW"
    text_size = cv2.getTextSize(message, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 1)[0]
    text_x = center[0] - text_size[0] // 2
    _draw_text(frame, message, (text_x, center[1] + 130), scale=0.65, color=(210, 245, 255), thickness=1)


def draw_hud(frame, filter_manager, fps: float, active: bool, hands_detected: int):
    """Draw the top HUD, FPS counter, and filter list."""
    h, w = frame.shape[:2]

    # Top-left status panel.
    panel_w = min(390, w - 30)
    _draw_panel(frame, (16, 18, panel_w, 138), alpha=0.42)

    status = "WINDOW LOCKED" if active else "SEARCHING FOR HANDS"
    status_color = (95, 255, 170) if active else (90, 220, 255)
    _draw_text(frame, "AR FILTER WINDOW", (32, 48), scale=0.72, color=(235, 250, 255), thickness=2)
    _draw_text(frame, f"STATUS: {status}", (32, 78), scale=0.50, color=status_color, thickness=1)
    _draw_text(frame, f"HANDS: {hands_detected}/2", (32, 104), scale=0.50, color=(210, 230, 240), thickness=1)
    _draw_text(frame, f"FPS: {fps:05.1f}", (210, 104), scale=0.50, color=(210, 230, 240), thickness=1)

    # Right filter selector panel.
    list_w = 270
    list_x1 = max(16, w - list_w - 16)
    list_y1 = 18
    list_y2 = min(h - 20, list_y1 + 42 + len(filter_manager.filters) * 29)
    _draw_panel(frame, (list_x1, list_y1, w - 16, list_y2), alpha=0.34)
    _draw_text(frame, "FILTER STACK", (list_x1 + 16, list_y1 + 30), scale=0.55, color=(235, 250, 255), thickness=1)

    y = list_y1 + 60
    for index, spec in enumerate(filter_manager.filters):
        is_current = index == filter_manager.current_index
        text_color = spec.color if is_current else (160, 178, 190)
        prefix = ">" if is_current else " "
        _draw_text(frame, f"{prefix} {spec.shortcut}. {spec.name}", (list_x1 + 16, y), scale=0.43, color=text_color, thickness=1)
        y += 29

    # Bottom controls strip.
    controls = "1-8 SWITCH FILTERS   N/P NEXT/PREV   H HUD   Q QUIT"
    text_size = cv2.getTextSize(controls, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)[0]
    x = max(16, (w - text_size[0]) // 2)
    y = h - 24
    _draw_text(frame, controls, (x, y), scale=0.48, color=(190, 220, 235), thickness=1)


def draw_startup_animation(frame, progress: float):
    """
    Draw a brief boot animation during the first seconds of the app.

    progress should be from 0.0 to 1.0.
    """
    progress = float(np.clip(progress, 0.0, 1.0))
    h, w = frame.shape[:2]
    center = (w // 2, h // 2)

    fade_out = 1.0 - max(0.0, (progress - 0.72) / 0.28)
    overlay_alpha = 0.52 * fade_out
    if overlay_alpha <= 0:
        return

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), (3, 8, 14), -1)

    color = (90, 225, 255)
    radius = int(40 + progress * min(w, h) * 0.28)
    cv2.circle(overlay, center, radius, color, 2, cv2.LINE_AA)
    cv2.circle(overlay, center, max(18, radius // 2), (255, 255, 255), 1, cv2.LINE_AA)

    sweep_angle = progress * math.tau * 2.0
    sweep_end = (
        int(center[0] + math.cos(sweep_angle) * radius),
        int(center[1] + math.sin(sweep_angle) * radius),
    )
    cv2.line(overlay, center, sweep_end, color, 2, cv2.LINE_AA)

    # Moving grid lines.
    spacing = 42
    offset = int(progress * spacing)
    for x in range(-spacing + offset, w, spacing):
        cv2.line(overlay, (x, 0), (x, h), (30, 80, 95), 1)
    for y in range(-spacing + offset, h, spacing):
        cv2.line(overlay, (0, y), (w, y), (30, 80, 95), 1)

    _alpha_blend(frame, overlay, overlay_alpha)

    title = "AR FILTER WINDOW"
    subtitle = "INITIALIZING HAND TRACKING"
    title_size = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
    sub_size = cv2.getTextSize(subtitle, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)[0]
    _draw_text(frame, title, (center[0] - title_size[0] // 2, center[1] - 10), scale=1.0, color=(235, 250, 255), thickness=2)
    _draw_text(frame, subtitle, (center[0] - sub_size[0] // 2, center[1] + 28), scale=0.55, color=color, thickness=1)
