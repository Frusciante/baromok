#!/usr/bin/env python3
"""
홍채 거리 실측 데이터셋 촬영 스크립트

줄자로 잰 실제 거리(눈 ~ 카메라 렌즈)를 입력하고 웹캠 사진을 저장한다.
앱과 같은 카메라/해상도 설정(camera_index, camera_resolution_width/height)을 사용한다.

조작 (미리보기 창이 활성화된 상태에서):
  숫자 키 + Enter : 실측 거리(cm) 설정
  Backspace       : 입력 중인 숫자 지우기
  G               : 촬영 조건 전환 (bare <-> glasses)
  Space           : 1장 저장
  B               : 연속 저장 (BURST_COUNT장, BURST_INTERVAL_SECONDS 간격)
  Q / Esc         : 종료

실행: python scripts/iris_distance_capture.py [--camera-index N] [--width W] [--height H]
"""

import argparse
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from iris_distance_common import (  # noqa: E402
    CONDITION_BARE,
    CONDITION_GLASSES,
    DATASET_DIRECTORY,
    build_sample_file_name,
    find_next_sequence,
    write_image_unicode_safe,
)

BURST_COUNT = 5
BURST_INTERVAL_SECONDS = 0.4
MINIMUM_DISTANCE_CM = 10
MAXIMUM_DISTANCE_CM = 300
WINDOW_NAME = "iris distance capture"

KEY_ENTER_CODES = (13, 10)
KEY_BACKSPACE_CODE = 8
KEY_ESCAPE_CODE = 27

TEXT_COLOR = (80, 255, 80)
WARNING_COLOR = (60, 60, 255)
GUIDE_COLOR = (200, 200, 200)


def load_default_camera_settings() -> dict:
    """앱 설정에서 카메라 기본값을 읽는다. 실패하면 앱 기본값을 사용한다."""
    defaults = {"camera_index": 0, "width": 1280, "height": 720}
    try:
        from src.config import get_config

        config = get_config()
        defaults["camera_index"] = int(config.get_app_setting("camera_index", 0) or 0)
        defaults["width"] = int(config.get_app_setting("camera_resolution_width", 1280) or 1280)
        defaults["height"] = int(config.get_app_setting("camera_resolution_height", 720) or 720)
    except Exception as error:
        print(f"[경고] 앱 설정을 읽지 못해 기본값을 사용합니다: {error}")
    return defaults


def parse_arguments() -> argparse.Namespace:
    defaults = load_default_camera_settings()
    parser = argparse.ArgumentParser(description="홍채 거리 실측 데이터셋 촬영")
    parser.add_argument("--camera-index", type=int, default=defaults["camera_index"])
    parser.add_argument("--width", type=int, default=defaults["width"])
    parser.add_argument("--height", type=int, default=defaults["height"])
    parser.add_argument("--output-directory", type=Path, default=DATASET_DIRECTORY)
    return parser.parse_args()


def open_camera(camera_index: int, width: int, height: int) -> cv2.VideoCapture:
    """앱의 CameraWorker와 같은 방식으로 카메라를 연다."""
    capture = cv2.VideoCapture(camera_index)
    if not capture.isOpened():
        raise RuntimeError(f"카메라 {camera_index}를 열 수 없습니다")
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return capture


def save_sample(frame, output_directory: Path, distance_cm: int, condition: str) -> Path:
    """규칙에 맞는 파일명으로 프레임을 저장하고 경로를 반환한다."""
    sequence = find_next_sequence(output_directory, distance_cm, condition)
    path = output_directory / build_sample_file_name(distance_cm, sequence, condition)
    if not write_image_unicode_safe(path, frame):
        raise IOError(f"이미지 저장 실패: {path}")
    return path


def draw_overlay(frame, distance_cm, condition, typed_digits, saved_count, message):
    """미리보기 화면에 상태와 안내를 그린다 (저장 이미지에는 그리지 않음)."""
    preview = frame.copy()
    height, width = preview.shape[:2]

    cv2.line(preview, (width // 2, 0), (width // 2, height), GUIDE_COLOR, 1)
    cv2.line(preview, (0, height // 2), (width, height // 2), GUIDE_COLOR, 1)

    distance_text = f"{distance_cm} cm" if distance_cm else "NOT SET"
    lines = [
        (f"distance: {distance_text}", TEXT_COLOR if distance_cm else WARNING_COLOR),
        (f"condition: {condition}", TEXT_COLOR),
        (f"input: {typed_digits}_", GUIDE_COLOR),
        (f"saved this session: {saved_count}", TEXT_COLOR),
        (f"resolution: {width}x{height}", GUIDE_COLOR),
        ("[0-9]+Enter distance | G condition | Space save | B burst | Q quit", GUIDE_COLOR),
    ]
    if message:
        lines.append((message, WARNING_COLOR))

    for line_index, (text, color) in enumerate(lines):
        cv2.putText(preview, text, (12, 28 + line_index * 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2, cv2.LINE_AA)
    return preview


def main():
    arguments = parse_arguments()
    output_directory: Path = arguments.output_directory
    output_directory.mkdir(parents=True, exist_ok=True)

    capture = open_camera(arguments.camera_index, arguments.width, arguments.height)
    actual_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"요청 해상도: {arguments.width}x{arguments.height} / 실제 해상도: {actual_width}x{actual_height}")
    if (actual_width, actual_height) != (arguments.width, arguments.height):
        print("[경고] 카메라가 요청 해상도를 지원하지 않습니다. 평가 시 이 차이가 기록됩니다.")
    print(f"저장 위치: {output_directory}")

    distance_cm = None
    condition = CONDITION_BARE
    typed_digits = ""
    saved_count = 0
    message = ""

    try:
        while True:
            success, frame = capture.read()
            if not success:
                print("[오류] 프레임을 읽지 못했습니다.")
                break

            cv2.imshow(WINDOW_NAME, draw_overlay(frame, distance_cm, condition, typed_digits, saved_count, message))
            key = cv2.waitKey(1) & 0xFF
            if key == 255:
                continue

            message = ""
            if key in (ord("q"), ord("Q"), KEY_ESCAPE_CODE):
                break
            elif ord("0") <= key <= ord("9"):
                typed_digits = (typed_digits + chr(key))[-3:]
            elif key == KEY_BACKSPACE_CODE:
                typed_digits = typed_digits[:-1]
            elif key in KEY_ENTER_CODES:
                if typed_digits and MINIMUM_DISTANCE_CM <= int(typed_digits) <= MAXIMUM_DISTANCE_CM:
                    distance_cm = int(typed_digits)
                    print(f"실측 거리 설정: {distance_cm}cm")
                else:
                    message = f"distance must be {MINIMUM_DISTANCE_CM}-{MAXIMUM_DISTANCE_CM} cm"
                typed_digits = ""
            elif key in (ord("g"), ord("G")):
                condition = CONDITION_GLASSES if condition == CONDITION_BARE else CONDITION_BARE
                print(f"촬영 조건: {condition}")
            elif key in (ord(" "), ord("b"), ord("B")):
                if distance_cm is None:
                    message = "set distance first"
                    continue
                shot_count = 1 if key == ord(" ") else BURST_COUNT
                for shot_index in range(shot_count):
                    if shot_index > 0:
                        time.sleep(BURST_INTERVAL_SECONDS)
                        success, frame = capture.read()
                        if not success:
                            break
                    path = save_sample(frame, output_directory, distance_cm, condition)
                    saved_count += 1
                    print(f"저장: {path.name}")
    finally:
        capture.release()
        cv2.destroyAllWindows()

    print(f"촬영 종료. 이번 세션 저장 수: {saved_count}")


if __name__ == "__main__":
    main()
