"""
Visual filters for the AR window.

Every filter accepts a BGR OpenCV image region and returns another BGR image
with the same width and height. Keeping this contract simple makes it easy to
add new effects later.
"""

from dataclasses import dataclass
import time
from typing import Callable, List, Tuple

import cv2
import numpy as np


Color = Tuple[int, int, int]
FilterFunction = Callable[[np.ndarray], np.ndarray]


@dataclass(frozen=True)
class FilterSpec:
    """Metadata for one switchable filter."""

    key: str
    name: str
    shortcut: str
    color: Color
    function: FilterFunction


def _safe_roi(roi: np.ndarray) -> bool:
    """Return True when the ROI is large enough to process safely."""
    return roi is not None and roi.size > 0 and roi.shape[0] > 2 and roi.shape[1] > 2


def _ensure_bgr(image: np.ndarray) -> np.ndarray:
    """Convert a single-channel image back to BGR if needed."""
    if len(image.shape) == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    return image


def _boost_saturation(roi: np.ndarray, sat_scale: float = 1.25, val_scale: float = 1.06) -> np.ndarray:
    """Increase saturation and brightness in HSV color space."""
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * sat_scale, 0, 255)
    hsv[:, :, 2] = np.clip(hsv[:, :, 2] * val_scale, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def edge_detection(roi: np.ndarray) -> np.ndarray:
    """Bright cinematic edge lines over a darkened version of the ROI."""
    if not _safe_roi(roi):
        return roi

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 70, 155)
    edges = cv2.dilate(edges, np.ones((2, 2), dtype=np.uint8), iterations=1)

    edge_layer = np.zeros_like(roi)
    edge_layer[edges > 0] = (255, 245, 120)

    dimmed = cv2.convertScaleAbs(roi, alpha=0.35, beta=-5)
    return cv2.addWeighted(dimmed, 0.75, edge_layer, 1.0, 0)


def anime_black_white(roi: np.ndarray) -> np.ndarray:
    """
    Manga-inspired monochrome posterization with strong ink lines.

    Bilateral filtering keeps major surfaces smooth while adaptive thresholding
    creates bold black outlines.
    """
    if not _safe_roi(roi):
        return roi

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    smooth = cv2.bilateralFilter(gray, d=7, sigmaColor=70, sigmaSpace=70)

    # Quantize gray values into clean tone bands.
    tones = (smooth // 42) * 42
    tones = np.clip(tones + 18, 0, 255).astype(np.uint8)

    ink = cv2.adaptiveThreshold(
        smooth,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY,
        11,
        5,
    )
    anime = cv2.bitwise_and(tones, ink)
    return cv2.cvtColor(anime, cv2.COLOR_GRAY2BGR)


def thermal_vision(roi: np.ndarray) -> np.ndarray:
    """False-color heat-map look using luminance as the temperature source."""
    if not _safe_roi(roi):
        return roi

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    normalized = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)

    # TURBO is vivid and modern. Fallback to JET on older OpenCV builds.
    colormap = getattr(cv2, "COLORMAP_TURBO", cv2.COLORMAP_JET)
    thermal = cv2.applyColorMap(normalized, colormap)

    # Add a soft glow to hot regions.
    hot_mask = cv2.threshold(normalized, 185, 255, cv2.THRESH_BINARY)[1]
    glow = cv2.GaussianBlur(hot_mask, (0, 0), 8)
    glow_bgr = cv2.applyColorMap(glow, cv2.COLORMAP_HOT)
    return cv2.addWeighted(thermal, 0.82, glow_bgr, 0.25, 0)


def glow_effect(roi: np.ndarray) -> np.ndarray:
    """Soft bloom effect that makes bright details radiate light."""
    if not _safe_roi(roi):
        return roi

    boosted = _boost_saturation(roi, sat_scale=1.18, val_scale=1.08)
    gray = cv2.cvtColor(boosted, cv2.COLOR_BGR2GRAY)
    bright = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)[1]

    bloom = cv2.bitwise_and(boosted, boosted, mask=bright)
    bloom = cv2.GaussianBlur(bloom, (0, 0), 13)
    result = cv2.addWeighted(boosted, 1.0, bloom, 0.85, 8)
    return np.clip(result, 0, 255).astype(np.uint8)


def sketch_effect(roi: np.ndarray) -> np.ndarray:
    """Pencil-sketch style using color dodge blending."""
    if not _safe_roi(roi):
        return roi

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    inverted = 255 - gray
    blur = cv2.GaussianBlur(inverted, (21, 21), 0)

    # Dodge blend: gray / (255 - blurred inverse).
    denominator = 255 - blur
    sketch = cv2.divide(gray, denominator, scale=256)
    sketch = cv2.equalizeHist(sketch)
    return cv2.cvtColor(sketch, cv2.COLOR_GRAY2BGR)


def pixelation(roi: np.ndarray) -> np.ndarray:
    """Retro pixelated window with a subtle grid overlay."""
    if not _safe_roi(roi):
        return roi

    h, w = roi.shape[:2]
    pixel_size = max(6, min(w, h) // 32)
    small_w = max(1, w // pixel_size)
    small_h = max(1, h // pixel_size)

    small = cv2.resize(roi, (small_w, small_h), interpolation=cv2.INTER_LINEAR)
    pixelated = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)

    # Draw faint grid lines to emphasize the blocky look.
    grid = pixelated.copy()
    for x in range(0, w, pixel_size):
        cv2.line(grid, (x, 0), (x, h), (35, 35, 35), 1)
    for y in range(0, h, pixel_size):
        cv2.line(grid, (0, y), (w, y), (35, 35, 35), 1)

    return cv2.addWeighted(pixelated, 0.88, grid, 0.12, 0)


def cyberpunk_neon(roi: np.ndarray) -> np.ndarray:
    """High-saturation neon grade with cyan and magenta edge accents."""
    if not _safe_roi(roi):
        return roi

    neon = _boost_saturation(roi, sat_scale=1.65, val_scale=1.10)

    # Shift channels slightly to create a controlled chromatic glitch feel.
    b, g, r = cv2.split(neon)
    shift = max(1, roi.shape[1] // 140)
    cyan_shift = np.roll(b, shift, axis=1)
    magenta_shift = np.roll(r, -shift, axis=1)
    neon = cv2.merge((cyan_shift, g, magenta_shift))

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 60, 140)
    edges = cv2.dilate(edges, np.ones((2, 2), dtype=np.uint8), iterations=1)

    edge_layer = np.zeros_like(roi)
    edge_layer[edges > 0] = (255, 70, 255)

    glow = cv2.GaussianBlur(edge_layer, (0, 0), 6)
    result = cv2.addWeighted(neon, 0.92, edge_layer, 0.90, 0)
    result = cv2.addWeighted(result, 1.0, glow, 0.55, 0)
    return np.clip(result, 0, 255).astype(np.uint8)


def blur_background_window(roi: np.ndarray) -> np.ndarray:
    """
    Frosted-glass blur inside the floating window.

    The outside webcam feed remains untouched; only the selected rectangle is
    blurred and tinted.
    """
    if not _safe_roi(roi):
        return roi

    blurred = cv2.GaussianBlur(roi, (0, 0), 12)
    tint = np.full_like(roi, (40, 220, 255))
    frosted = cv2.addWeighted(blurred, 0.78, tint, 0.12, 12)

    # Preserve a little original detail so the effect feels like glass.
    return cv2.addWeighted(frosted, 0.82, roi, 0.18, 0)


class FilterManager:
    """Stores the active filter and handles keyboard switching."""

    def __init__(self, transition_seconds: float = 0.28):
        self.filters: List[FilterSpec] = [
            FilterSpec("edge", "Edge Detection", "1", (255, 235, 95), edge_detection),
            FilterSpec("anime_bw", "Anime Black & White", "2", (245, 245, 245), anime_black_white),
            FilterSpec("thermal", "Thermal Vision", "3", (0, 120, 255), thermal_vision),
            FilterSpec("glow", "Glow Effect", "4", (105, 255, 190), glow_effect),
            FilterSpec("sketch", "Sketch Effect", "5", (230, 230, 230), sketch_effect),
            FilterSpec("pixel", "Pixelation", "6", (255, 175, 60), pixelation),
            FilterSpec("cyberpunk", "Cyberpunk Neon", "7", (255, 70, 255), cyberpunk_neon),
            FilterSpec("blur_window", "Blur Background Window", "8", (255, 210, 90), blur_background_window),
        ]
        self.current_index = 0
        self.transition_seconds = transition_seconds
        self.last_switch_time = time.perf_counter()

    @property
    def current_filter(self) -> FilterSpec:
        return self.filters[self.current_index]

    @property
    def current_color(self) -> Color:
        return self.current_filter.color

    def get_transition_alpha(self) -> float:
        """Fade the selected filter in after a switch."""
        elapsed = time.perf_counter() - self.last_switch_time
        return float(np.clip(elapsed / self.transition_seconds, 0.0, 1.0))

    def switch_to(self, index: int):
        """Switch to a filter index and restart the visual transition."""
        index = index % len(self.filters)
        if index != self.current_index:
            self.current_index = index
            self.last_switch_time = time.perf_counter()

    def next_filter(self):
        self.switch_to(self.current_index + 1)

    def previous_filter(self):
        self.switch_to(self.current_index - 1)

    def switch_by_key(self, key_code: int) -> bool:
        """
        Switch filters using number keys.

        Returns True when a filter was changed. This is useful if you want to
        add sound or terminal feedback later.
        """
        if key_code == 255:
            return False

        key = chr(key_code) if 0 <= key_code <= 255 else ""
        for index, spec in enumerate(self.filters):
            if key == spec.shortcut:
                self.switch_to(index)
                return True
        return False

    def apply_current_filter(self, frame: np.ndarray, rect, alpha: float = 1.0) -> np.ndarray:
        """
        Apply the active filter only inside the given rectangle.

        rect format: (x1, y1, x2, y2)
        """
        if rect is None:
            return frame

        h, w = frame.shape[:2]
        x1, y1, x2, y2 = rect
        x1 = int(np.clip(x1, 0, w - 1))
        x2 = int(np.clip(x2, 0, w))
        y1 = int(np.clip(y1, 0, h - 1))
        y2 = int(np.clip(y2, 0, h))

        if x2 <= x1 + 2 or y2 <= y1 + 2:
            return frame

        roi = frame[y1:y2, x1:x2]
        filtered = self.current_filter.function(roi)
        filtered = _ensure_bgr(filtered)

        alpha = float(np.clip(alpha, 0.0, 1.0))
        if alpha < 1.0:
            filtered = cv2.addWeighted(roi, 1.0 - alpha, filtered, alpha, 0)

        frame[y1:y2, x1:x2] = filtered
        return frame
