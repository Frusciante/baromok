"""
홍채 거리 측정 실험 공통 모듈

촬영 스크립트(iris_distance_capture.py)와 평가 스크립트(iris_distance_evaluation.py)가
같은 파일명 규칙과 이미지 입출력 방식을 사용하도록 공통 기능을 모아 둔다.

파일명 규칙: d{실측거리cm 3자리}_{순번 2자리}_{glasses|bare}.jpg
예) d060_03_glasses.jpg
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIRECTORY = PROJECT_ROOT / "data_test" / "iris_distance"

CONDITION_GLASSES = "glasses"
CONDITION_BARE = "bare"
CONDITIONS = (CONDITION_BARE, CONDITION_GLASSES)

IMAGE_EXTENSION = ".jpg"
JPEG_QUALITY = 95

_FILE_NAME_PATTERN = re.compile(
    r"^d(?P<distance>\d{3})_(?P<sequence>\d{2})_(?P<condition>glasses|bare)\.(?:jpg|jpeg|png)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SampleInformation:
    """파일명에서 해석한 촬영 정보"""

    distance_cm: int
    sequence: int
    condition: str


def build_sample_file_name(distance_cm: int, sequence: int, condition: str) -> str:
    """촬영 정보로 규칙에 맞는 파일명을 만든다."""
    if condition not in CONDITIONS:
        raise ValueError(f"알 수 없는 촬영 조건: {condition} (허용: {CONDITIONS})")
    return f"d{distance_cm:03d}_{sequence:02d}_{condition}{IMAGE_EXTENSION}"


def parse_sample_file_name(file_name: str) -> Optional[SampleInformation]:
    """파일명을 해석한다. 규칙에 맞지 않으면 None을 반환한다."""
    match = _FILE_NAME_PATTERN.match(file_name)
    if match is None:
        return None
    return SampleInformation(
        distance_cm=int(match.group("distance")),
        sequence=int(match.group("sequence")),
        condition=match.group("condition").lower(),
    )


def find_next_sequence(directory: Path, distance_cm: int, condition: str) -> int:
    """같은 거리/조건에서 아직 사용하지 않은 다음 순번을 찾는다."""
    used_sequences = set()
    if directory.exists():
        for path in directory.iterdir():
            information = parse_sample_file_name(path.name)
            if information and information.distance_cm == distance_cm and information.condition == condition:
                used_sequences.add(information.sequence)
    sequence = 1
    while sequence in used_sequences:
        sequence += 1
    return sequence


def read_image_unicode_safe(path: Path) -> Optional[np.ndarray]:
    """한글 경로에서도 동작하도록 이미지를 읽는다 (cv2.imread는 비ASCII 경로 실패)."""
    try:
        buffer = np.fromfile(str(path), dtype=np.uint8)
        return cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    except OSError:
        return None


def write_image_unicode_safe(path: Path, image: np.ndarray) -> bool:
    """한글 경로에서도 동작하도록 이미지를 저장한다 (cv2.imwrite는 비ASCII 경로 실패)."""
    success, encoded = cv2.imencode(path.suffix, image, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not success:
        return False
    encoded.tofile(str(path))
    return True
