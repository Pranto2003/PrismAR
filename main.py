"""
AR Filter Window
----------------
Real-time webcam AR system that creates a filter window between two hands.

Run locally with:
    python main.py

This file owns the main application loop. The tracking, filters, and drawing
helpers live in separate modules so the project stays easy to read and modify.
"""

import time

import cv2

from filters import FilterManager
from hand_tracking import HandTracker
from utils import (
    SmoothRectangle,
    draw_cinematic_bars,
    draw_glowing_window,
    draw_hud,
    draw_startup_animation,
    draw_waiting_prompt,
    update_fps,
)


# Camera and render settings.
CAMERA_INDEX = 0
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
MIRROR_VIEW = True
WINDOW_TITLE = "AR Filter Window"


def create_camera():
    """
    Open the default webcam and request a 720p frame.

    OpenCV may silently fall back to a smaller resolution if the webcam does
    not support the requested size. The rest of the app adapts automatically.
    """
    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, 30)
    return cap


def print_controls():
    """Show quick controls in the terminal after the app starts."""
    print("\nAR Filter Window")
    print("----------------")
    print("Raise both hands to open the floating filter window.")
    print("Controls:")
    print("  1-8       Switch filters")
    print("  N / ]     Next filter")
    print("  P / [     Previous filter")
    print("  H         Toggle HUD")
    print("  Q / ESC   Quit")
    print()


def main():
    cap = create_camera()
    if not cap.isOpened():
        print("Error: Could not open webcam. Check camera permissions or CAMERA_INDEX.")
        return

    print_controls()

    # MediaPipe is CPU-friendly, but processing a smaller copy improves FPS.
    hand_tracker = HandTracker(
        max_num_hands=2,
        detection_confidence=0.65,
        tracking_confidence=0.60,
        processing_width=640,
    )

    filter_manager = FilterManager()
    rectangle_smoother = SmoothRectangle(alpha=0.30, hold_frames=8)

    show_hud = True
    fps = 0.0
    previous_time = time.perf_counter()
    startup_time = time.perf_counter()

    try:
        while True:
            success, frame = cap.read()
            if not success:
                print("Warning: Failed to read from webcam.")
                break

            if MIRROR_VIEW:
                frame = cv2.flip(frame, 1)

            # Detect both hands and estimate the AR window between them.
            hands = hand_tracker.find_hands(frame)
            raw_rectangle = hand_tracker.get_filter_window(hands, frame.shape)
            rectangle = rectangle_smoother.update(raw_rectangle)

            # Apply the selected effect only inside the AR rectangle.
            is_window_active = rectangle is not None
            if is_window_active:
                transition_alpha = filter_manager.get_transition_alpha()
                frame = filter_manager.apply_current_filter(
                    frame,
                    rectangle,
                    alpha=transition_alpha,
                )
                draw_glowing_window(
                    frame,
                    rectangle,
                    color=filter_manager.current_color,
                    label=filter_manager.current_filter.name,
                )
            else:
                draw_waiting_prompt(frame)

            # UI polish. Kept lightweight so it does not dominate frame time.
            draw_cinematic_bars(frame)
            if show_hud:
                draw_hud(
                    frame=frame,
                    filter_manager=filter_manager,
                    fps=fps,
                    active=is_window_active,
                    hands_detected=len(hands),
                )

            elapsed_startup = time.perf_counter() - startup_time
            if elapsed_startup < 2.2:
                draw_startup_animation(frame, progress=elapsed_startup / 2.2)

            # Smoothed FPS counter.
            fps, previous_time = update_fps(fps, previous_time)

            cv2.imshow(WINDOW_TITLE, frame)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), ord("Q"), 27):
                break
            if key in (ord("h"), ord("H")):
                show_hud = not show_hud
            elif key in (ord("n"), ord("N"), ord("]")):
                filter_manager.next_filter()
            elif key in (ord("p"), ord("P"), ord("[")):
                filter_manager.previous_filter()
            else:
                filter_manager.switch_by_key(key)

    finally:
        hand_tracker.close()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
