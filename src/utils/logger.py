"""
로깅 시스템

애플리케이션 전체에서 사용할 통일된 로거
"""
import logging
import logging.handlers
from pathlib import Path
from typing import Optional


class LoggerSetup:
    """로거 설정 및 초기화"""
    
    _logger_initialized = False
    
    @staticmethod
    def setup_logger(
        name: str,
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        console_output: bool = True
    ) -> logging.Logger:
        """
        로거 설정 및 반환
        
        Args:
            name: 로거 이름 (보통 __name__)
            log_level: 로그 레벨 ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
            log_file: 로그 파일 경로 (None이면 파일 출력 안 함)
            console_output: 콘솔 출력 여부
            
        Returns:
            설정된 로거 객체
        """
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, log_level.upper()))
        
        # 기존 핸들러 제거 (중복 방지)
        logger.handlers.clear()
        
        # 포매터 설정
        formatter = logging.Formatter(
            '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 콘솔 핸들러
        if console_output:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(getattr(logging, log_level.upper()))
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        # 파일 핸들러
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(getattr(logging, log_level.upper()))
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        return logger


def get_logger(name: str, log_level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """
    로거 조회 또는 생성 (유틸 함수)
    
    Args:
        name: 로거 이름
        log_level: 로그 레벨
        log_file: 로그 파일 경로
        
    Returns:
        로거 객체
    """
    return LoggerSetup.setup_logger(name, log_level, log_file)
