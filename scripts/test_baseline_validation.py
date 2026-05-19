#!/usr/bin/env python3
"""
Baseline 유효성 검증 테스트

변경사항: BaselineManager.is_baseline_valid() 강화된 검증 로직 테스트
"""

import sys
import json
from pathlib import Path

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ConfigManager
from src.core.baseline_manager import BaselineManager
from src.utils.logger import get_logger

logger = get_logger(__name__, "DEBUG")


def test_case_1_no_baseline_file():
    """테스트 1: Baseline 파일이 없을 때"""
    logger.info("=" * 70)
    logger.info("테스트 1: Baseline 파일이 없을 때")
    logger.info("=" * 70)

    config = ConfigManager()
    bm = BaselineManager(config, data_dir="test_baseline_data")

    # 기존 파일 제거
    baseline_file = Path("test_baseline_data/baseline.json")
    if baseline_file.exists():
        baseline_file.unlink()
        logger.info("기존 baseline.json 파일 제거")

    # 로드 시도
    loaded = bm.load_baseline_from_file(str(baseline_file))
    logger.info(f"로드 결과: {loaded}")

    # 유효성 검증
    is_valid = bm.is_baseline_valid()
    logger.info(f"유효성 검증: {is_valid}")
    assert not is_valid, "baseline 파일이 없으면 유효하지 않아야 함"
    logger.info("✓ 테스트 1 통과: 파일 없음 -> 유효하지 않음\n")


def test_case_2_existing_baseline():
    """테스트 2: 유효한 Baseline 파일이 있을 때"""
    logger.info("=" * 70)
    logger.info("테스트 2: 유효한 Baseline 파일이 있을 때")
    logger.info("=" * 70)

    config = ConfigManager()
    bm = BaselineManager(config, data_dir="data")

    # 저장된 baseline 로드
    loaded = bm.load_baseline_from_file()
    logger.info(f"로드 결과: {loaded}")

    if loaded:
        # 유효성 검증
        is_valid = bm.is_baseline_valid()
        logger.info(f"유효성 검증: {is_valid}")
        logger.info(f"Baseline 메트릭: {bm.baseline_metrics}")
        logger.info(f"Frame count: {bm.baseline_metrics.frame_count}")
        logger.info(f"Metrics 키: {list(bm.baseline_metrics.metrics.keys())}")
        if is_valid:
            logger.info("✓ 테스트 2 통과: baseline 로드 및 검증 성공\n")
        else:
            logger.warning("⚠ 테스트 2: baseline 파일은 로드되었으나 유효성 검증 실패")
            logger.warning("  (상세 로그는 위 참고)\n")
    else:
        logger.warning("⚠ 테스트 2: 저장된 baseline.json이 없음 (스킵)\n")


def test_case_3_corrupted_baseline():
    """테스트 3: 손상된 Baseline 파일"""
    logger.info("=" * 70)
    logger.info("테스트 3: 손상된 Baseline 파일 (필수 필드 부재)")
    logger.info("=" * 70)

    config = ConfigManager()
    bm = BaselineManager(config, data_dir="test_baseline_data")

    # 손상된 baseline.json 생성
    corrupted_data = {
        "timestamp": "2026-05-19T00:00:00",
        "collection_duration_seconds": 10,
        "frame_count": 50,  # 너무 적음 (최소 120)
        "metrics": {
            "cheek_distance": 0.5,
            # shoulder_width 부재 (필수 필드)
        }
    }

    baseline_file = Path("test_baseline_data/baseline.json")
    baseline_file.parent.mkdir(parents=True, exist_ok=True)
    with open(baseline_file, "w") as f:
        json.dump(corrupted_data, f)
    logger.info("손상된 baseline.json 생성 (shoulder_width 부재, frame_count 부족)")

    # 로드
    loaded = bm.load_baseline_from_file(str(baseline_file))
    logger.info(f"로드 결과: {loaded}")

    if loaded:
        # 유효성 검증
        is_valid = bm.is_baseline_valid()
        logger.info(f"유효성 검증: {is_valid}")
        assert not is_valid, "손상된 baseline은 유효하지 않아야 함"
        logger.info("✓ 테스트 3 통과: 손상된 파일 감지\n")
    else:
        logger.warning("⚠ 테스트 3: 파일 로드 실패 (또는 파싱 오류)\n")


def test_case_4_invalid_metrics():
    """테스트 4: 메트릭 값 유효성 검증 (NaN/Inf/범위 초과)"""
    logger.info("=" * 70)
    logger.info("테스트 4: 메트릭 값 유효성 검증")
    logger.info("=" * 70)

    config = ConfigManager()
    bm = BaselineManager(config, data_dir="test_baseline_data")

    # 범위 초과 baseline 생성
    invalid_data = {
        "timestamp": "2026-05-19T00:00:00",
        "collection_duration_seconds": 30,
        "frame_count": 150,
        "metrics": {
            "cheek_distance": 1.5,  # 범위 초과 (0 < x <= 1)
            "shoulder_width": 0.5,
            "ransac_x_samples": [0.3, 0.4, 0.5],
            "ransac_y_samples": [0.4, 0.5, 0.6],
        }
    }

    baseline_file = Path("test_baseline_data/baseline.json")
    with open(baseline_file, "w") as f:
        json.dump(invalid_data, f)
    logger.info("범위 초과 메트릭 baseline.json 생성 (cheek_distance=1.5)")

    # 로드
    loaded = bm.load_baseline_from_file(str(baseline_file))
    logger.info(f"로드 결과: {loaded}")

    if loaded:
        # 유효성 검증
        is_valid = bm.is_baseline_valid()
        logger.info(f"유효성 검증: {is_valid}")
        assert not is_valid, "범위 초과 메트릭은 유효하지 않아야 함"
        logger.info("✓ 테스트 4 통과: 메트릭 범위 검증\n")
    else:
        logger.warning("⚠ 테스트 4: 파일 로드 실패\n")


def main():
    """메인 테스트 실행"""
    logger.info("Baseline 유효성 검증 테스트 시작\n")

    try:
        test_case_1_no_baseline_file()
        test_case_2_existing_baseline()
        test_case_3_corrupted_baseline()
        test_case_4_invalid_metrics()

        logger.info("=" * 70)
        logger.info("모든 테스트 완료")
        logger.info("=" * 70)

    except AssertionError as e:
        logger.error(f"✗ 테스트 실패: {e}")
        return 1
    except Exception as e:
        logger.error(f"✗ 예상치 못한 오류: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
