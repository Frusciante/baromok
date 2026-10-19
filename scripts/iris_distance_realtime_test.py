#!/usr/bin/env python3
"""
Iris distance realtime test

Compares the current production algorithm (production_app, -20cm offset)
with the improved algorithm (horizontal_mean + k=0.896) in real time.

RED  = distance <= 45 cm (too close warning)
BLUE = current (old) algorithm value
GREEN= improved algorithm value

Keys (preview window must be active):
  Q / Esc : quit
  + / =   : increase k by 0.005
  -       : decrease k by 0.005
  R       : reset k to default (0.896)

Run: python scripts/iris_distance_realtime_test.py
"""

import math
import shutil
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# ── algorithm parameters ─────────────────────────────────────────────
DEFAULT_CORRECTION_SCALE = 0.896   # measured k for horizontal_mean method
HFOV_DEG = 60.0                    # camera horizontal FOV (fixed, same as production)
IRIS_DIAMETER_MM = 11.7            # from posture_definition_criteria.json

# FaceMesh iris indices: 468 = left center, 469-472 = left contour
#                        473 = right center, 474-477 = right contour
LEFT_IRIS_INDICES  = (468, 469, 470, 471, 472)
RIGHT_IRIS_INDICES = (473, 474, 475, 476, 477)

# ── layout ───────────────────────────────────────────────────────────
WINDOW_NAME = "iris distance realtime test"
BAR_HEIGHT = 220
FONT = cv2.FONT_HERSHEY_SIMPLEX

# ── colors (BGR) ─────────────────────────────────────────────────────
COLOR_BACKGROUND = (30,  30,  30)
COLOR_LABEL      = (180, 180, 180)
COLOR_OLD        = (80,  180, 255)   # blue  : current (old) algorithm
COLOR_NEW        = (80,  255, 140)   # green : improved algorithm
COLOR_WARNING    = (60,  60,  240)   # red   : too close (<=45 cm)
COLOR_KEY        = (140, 140, 140)
COLOR_IRIS_MARK  = (0,   255, 255)   # cyan  : iris contour overlay
COLOR_SCALE      = (220, 220,  80)

WARNING_DISTANCE_CM = 45.0


# ════════════════════════════════════════════════════════════════
# model path workaround (non-ASCII path -> ASCII temp path)
# ════════════════════════════════════════════════════════════════
def prepare_ascii_model_directory() -> str:
    from src.utils.paths import MODELS_DIR
    models_directory = Path(MODELS_DIR)
    if str(models_directory).isascii():
        return str(models_directory)
    ascii_directory = Path(tempfile.gettempdir()) / "baromok_iris_evaluation_models"
    ascii_directory.mkdir(parents=True, exist_ok=True)
    for task_file in models_directory.glob("*.task"):
        target = ascii_directory / task_file.name
        if not target.exists() or target.stat().st_size != task_file.stat().st_size:
            shutil.copy2(task_file, target)
    print(f"[info] model files copied to ASCII temp path: {ascii_directory}")
    return str(ascii_directory)


# ════════════════════════════════════════════════════════════════
# improved distance calculation
# ════════════════════════════════════════════════════════════════
def extract_horizontal_diameter_px(face_landmarks, indices, frame_width, frame_height):
    """Compute iris horizontal diameter (px) from 4 contour points.
    indices[0] is the center point and is excluded."""
    if face_landmarks is None or len(face_landmarks) <= max(indices):
        return None
    contour = np.array(
        [(face_landmarks[i][0] * frame_width, face_landmarks[i][1] * frame_height)
         for i in indices[1:]],   # skip center point
        dtype=np.float64,
    )
    pair_a = np.linalg.norm(contour[0] - contour[2])
    pair_b = np.linalg.norm(contour[1] - contour[3])
    return float(max(pair_a, pair_b))


def calculate_new_distance_cm(face_landmarks, frame_width, frame_height, correction_scale):
    """Estimate eye-to-camera distance using horizontal_mean + k method."""
    focal_px = frame_width / (2.0 * math.tan(math.radians(HFOV_DEG) / 2.0))

    diameters = []
    for indices in (LEFT_IRIS_INDICES, RIGHT_IRIS_INDICES):
        diam = extract_horizontal_diameter_px(face_landmarks, indices, frame_width, frame_height)
        if diam and diam > 0:
            diameters.append(diam)

    if not diameters:
        return None

    mean_diam = sum(diameters) / len(diameters)
    raw_cm = (IRIS_DIAMETER_MM * focal_px / mean_diam) / 10.0
    return max(0.0, raw_cm * correction_scale)


# ════════════════════════════════════════════════════════════════
# rendering
# ════════════════════════════════════════════════════════════════
def draw_iris_overlay(frame, face_landmarks, left_indices, right_indices):
    """Draw iris contour dots and horizontal diameter line on frame."""
    h, w = frame.shape[:2]
    if face_landmarks is None or len(face_landmarks) <= max(right_indices):
        return
    for indices in (left_indices, right_indices):
        contour = [
            (int(face_landmarks[i][0] * w), int(face_landmarks[i][1] * h))
            for i in indices[1:]
        ]
        for pt in contour:
            cv2.circle(frame, pt, 2, COLOR_IRIS_MARK, -1)
        a = np.linalg.norm(np.array(contour[0]) - np.array(contour[2]))
        b = np.linalg.norm(np.array(contour[1]) - np.array(contour[3]))
        p1, p2 = (contour[0], contour[2]) if a >= b else (contour[1], contour[3])
        cv2.line(frame, p1, p2, COLOR_IRIS_MARK, 1, cv2.LINE_AA)


def put_text_shadow(img, text, pos, font_scale, color, thickness=2):
    x, y = pos
    cv2.putText(img, text, (x + 1, y + 1), FONT, font_scale, (0, 0, 0), thickness + 1, cv2.LINE_AA)
    cv2.putText(img, text, pos, FONT, font_scale, color, thickness, cv2.LINE_AA)


def draw_distance_bar(panel, label, value_cm, color, y_offset, bar_max_cm=150.0, bar_width=400):
    cv2.putText(panel, label, (10, y_offset - 4), FONT, 0.55, COLOR_LABEL, 1, cv2.LINE_AA)
    if value_cm is None:
        cv2.putText(panel, "-- (not detected)", (10, y_offset + 22), FONT, 0.65, COLOR_WARNING, 2, cv2.LINE_AA)
        return
    text = f"{value_cm:.1f} cm"
    color_final = COLOR_WARNING if value_cm <= WARNING_DISTANCE_CM else color
    cv2.putText(panel, text, (10, y_offset + 22), FONT, 0.85, color_final, 2, cv2.LINE_AA)
    ratio = min(value_cm / bar_max_cm, 1.0)
    bar_x = 200
    cv2.rectangle(panel, (bar_x, y_offset + 4), (bar_x + bar_width, y_offset + 20), (60, 60, 60), -1)
    cv2.rectangle(panel, (bar_x, y_offset + 4), (bar_x + int(bar_width * ratio), y_offset + 20), color_final, -1)
    # warning threshold line
    warn_x = bar_x + int(bar_width * (WARNING_DISTANCE_CM / bar_max_cm))
    cv2.line(panel, (warn_x, y_offset + 2), (warn_x, y_offset + 22), (0, 60, 200), 1)


def build_info_panel(width, old_cm, new_cm, correction_scale, fps, detected):
    panel = np.full((BAR_HEIGHT, width, 3), COLOR_BACKGROUND, dtype=np.uint8)
    cv2.line(panel, (0, 0), (width, 0), (70, 70, 70), 1)

    # old algorithm row
    cv2.putText(panel, "[ current  (production_app, -20 cm offset) ]",
                (10, 22), FONT, 0.52, COLOR_OLD, 1, cv2.LINE_AA)
    draw_distance_bar(panel, "old algorithm", old_cm, COLOR_OLD, y_offset=35)

    # new algorithm row
    cv2.putText(panel, "[ improved (horizontal_mean x k) ]",
                (10, 97), FONT, 0.52, COLOR_NEW, 1, cv2.LINE_AA)
    draw_distance_bar(panel, "new algorithm", new_cm, COLOR_NEW, y_offset=110)

    # right info block
    rx = width - 340
    cv2.putText(panel, f"k = {correction_scale:.3f}", (rx, 30), FONT, 0.7, COLOR_SCALE, 2, cv2.LINE_AA)
    cv2.putText(panel, "+/- : adjust k    R : reset", (rx, 56), FONT, 0.44, COLOR_KEY, 1, cv2.LINE_AA)

    status_color = COLOR_NEW if detected else COLOR_WARNING
    status_text = "iris detected" if detected else "iris NOT detected"
    cv2.putText(panel, status_text, (rx, 88), FONT, 0.62, status_color, 2, cv2.LINE_AA)

    cv2.putText(panel, f"FPS {fps:4.1f}", (rx, 116), FONT, 0.55, COLOR_LABEL, 1, cv2.LINE_AA)
    cv2.putText(panel, f"RED = distance <= {WARNING_DISTANCE_CM:.0f} cm (too close)", (rx, 144), FONT, 0.44, COLOR_WARNING, 1, cv2.LINE_AA)

    cv2.putText(panel, "Q / Esc : quit", (10, BAR_HEIGHT - 10), FONT, 0.42, COLOR_KEY, 1, cv2.LINE_AA)
    return panel


# ════════════════════════════════════════════════════════════════
# main loop
# ════════════════════════════════════════════════════════════════
def main():
    camera_index, frame_width, frame_height = 0, 1280, 720
    try:
        from src.config import get_config
        config = get_config()
        camera_index = int(config.get_app_setting("camera_index", 0) or 0)
        frame_width  = int(config.get_app_setting("camera_resolution_width",  1280) or 1280)
        frame_height = int(config.get_app_setting("camera_resolution_height", 720)  or 720)
    except Exception as e:
        print(f"[warning] could not read app settings, using defaults: {e}")

    print("Loading models...")
    from src.core.landmark_extractor import LandmarkExtractor
    extractor = LandmarkExtractor(model_base_path=prepare_ascii_model_directory())
    if extractor.face_landmarker is None:
        print("[error] Face Landmarker failed to load. Check model files.")
        sys.exit(1)

    from src.core.indicator_calculator import IndicatorCalculator
    try:
        from src.config import get_config
        indicator_calc = IndicatorCalculator(get_config())
    except Exception:
        indicator_calc = IndicatorCalculator()

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"[error] cannot open camera {camera_index}")
        sys.exit(1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  frame_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_height)
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Camera resolution: {actual_w}x{actual_h}  (requested: {frame_width}x{frame_height})")
    print("Ready. Press Q or Esc in the preview window to quit.")

    correction_scale = DEFAULT_CORRECTION_SCALE
    prev_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[error] failed to read frame")
                break

            fh, fw = frame.shape[:2]

            extracted = extractor.extract_landmarks(frame)
            face_landmarks = extracted.face.landmarks if extracted.face is not None else None

            relevant = extractor.get_relevant_landmarks(extracted, frame_width=fw, frame_height=fh)
            normalized = extractor.normalize_landmarks(
                relevant, frame_width=fw, frame_height=fh,
                timestamp_ms=extracted.frame_timestamp_ms, baseline_mode=True
            )
            indicators = indicator_calc.calculate_all_indicators(
                normalized, timestamp=time.time(), baseline_mode=True
            )

            old_cm = indicators.eye_screen_distance_cm if indicators else None
            new_cm = calculate_new_distance_cm(face_landmarks, fw, fh, correction_scale)
            detected = new_cm is not None

            draw_iris_overlay(frame, face_landmarks, LEFT_IRIS_INDICES, RIGHT_IRIS_INDICES)

            if new_cm is not None:
                color = COLOR_WARNING if new_cm <= WARNING_DISTANCE_CM else COLOR_NEW
                put_text_shadow(frame, f"new: {new_cm:.1f} cm", (16, 48), 1.1, color, 2)
            else:
                put_text_shadow(frame, "iris not detected", (16, 48), 1.0, COLOR_WARNING, 2)
            if old_cm is not None:
                put_text_shadow(frame, f"old: {old_cm:.1f} cm", (16, 96), 0.8, COLOR_OLD, 2)

            now = time.time()
            fps = 1.0 / max(now - prev_time, 1e-6)
            prev_time = now
            panel = build_info_panel(fw, old_cm, new_cm, correction_scale, fps, detected)
            display = np.vstack([frame, panel])
            cv2.imshow(WINDOW_NAME, display)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                break
            elif key == ord("+") or key == ord("="):
                correction_scale = round(min(correction_scale + 0.005, 2.0), 3)
                print(f"k -> {correction_scale:.3f}")
            elif key == ord("-"):
                correction_scale = round(max(correction_scale - 0.005, 0.1), 3)
                print(f"k -> {correction_scale:.3f}")
            elif key in (ord("r"), ord("R")):
                correction_scale = DEFAULT_CORRECTION_SCALE
                print(f"k reset -> {correction_scale:.3f}")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("Quit.")


if __name__ == "__main__":
    main()
