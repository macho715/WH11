#!/usr/bin/env python3
"""
HVDC Warehouse Management System - 표준화된 로깅 시스템
모든 모듈에서 일관된 로깅을 제공합니다.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from datetime import datetime
import os

class HVDCLogger:
    """HVDC 시스템 전용 로거"""
    
    def __init__(self, name: str = "HVDC", level: str = "INFO"):
        self.name = name
        self.level = getattr(logging, level.upper())
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(self.name)
        logger.setLevel(self.level)
        
        # 이미 핸들러가 설정되어 있으면 중복 방지
        if logger.handlers:
            return logger
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.level)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # 파일 핸들러 (logs 디렉토리에 저장)
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"hvdc_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(self.level)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        return logger
    
    def debug(self, message: str):
        """디버그 로그"""
        self.logger.debug(message)
    
    def info(self, message: str):
        """정보 로그"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """경고 로그"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """오류 로그"""
        self.logger.error(message)
    
    def critical(self, message: str):
        """치명적 오류 로그"""
        self.logger.critical(message)
    
    def exception(self, message: str):
        """예외 로그 (스택 트레이스 포함)"""
        self.logger.exception(message)

# 전역 로거 인스턴스
_hvdc_logger = None

def get_logger(name: str = "HVDC", level: str = None) -> HVDCLogger:
    """
    로거 인스턴스 반환 (싱글톤 패턴)
    
    Args:
        name: 로거 이름
        level: 로그 레벨 (환경변수 HVDC_LOG_LEVEL에서 읽어옴)
    
    Returns:
        HVDCLogger: 로거 인스턴스
    """
    global _hvdc_logger
    
    if level is None:
        level = os.getenv("HVDC_LOG_LEVEL", "INFO")
    
    if _hvdc_logger is None:
        _hvdc_logger = HVDCLogger(name, level)
    
    return _hvdc_logger

def setup_logging(level: str = "INFO", log_file: str = None):
    """
    로깅 시스템 초기화
    
    Args:
        level: 로그 레벨
        log_file: 로그 파일 경로 (선택사항)
    """
    logger = get_logger(level=level)
    logger.info(f"HVDC 로깅 시스템 초기화 완료 (레벨: {level})")
    
    if log_file:
        logger.info(f"로그 파일: {log_file}")

# 편의 함수들
def log_transaction_processing(module: str, count: int, duration: float):
    """트랜잭션 처리 로그"""
    logger = get_logger()
    logger.info(f"📊 {module}: {count:,}건 처리 완료 ({duration:.2f}초)")

def log_mapping_validation(validation_result: dict):
    """매핑 검증 로그"""
    logger = get_logger()
    for storage_type, info in validation_result.items():
        logger.info(f"🏷️ {storage_type}: {info['count']}건 - {info['locations']}")

def log_deduplication_result(before: int, after: int):
    """중복 제거 결과 로그"""
    logger = get_logger()
    removed = before - after
    if removed > 0:
        logger.info(f"🗑️ 중복 제거: {before:,} → {after:,}건 ({removed:,}건 제거)")

def log_inventory_calculation(warehouse: str, expected: int, actual: int, variance: float):
    """재고 계산 결과 로그"""
    logger = get_logger()
    status = "✅" if abs(variance) <= 2 else "⚠️"
    logger.info(f"{status} {warehouse}: 기대 {expected:,} / 실제 {actual:,} (오차: {variance:+.1f}%)")

def log_system_error(error: Exception, context: str = ""):
    """시스템 오류 로그"""
    logger = get_logger()
    logger.error(f"❌ 시스템 오류 {context}: {str(error)}")
    logger.exception(f"상세 오류 정보 {context}")

def log_performance_metric(metric: str, value: float, unit: str = ""):
    """성능 메트릭 로그"""
    logger = get_logger()
    logger.info(f"⚡ {metric}: {value:.2f}{unit}")

# 모듈별 로거 생성 함수
def get_module_logger(module_name: str) -> HVDCLogger:
    """모듈별 로거 생성"""
    return get_logger(f"HVDC.{module_name}")

# 사용 예시:
# from core.logger import get_module_logger
# logger = get_module_logger("loader")
# logger.info("데이터 로딩 시작") 