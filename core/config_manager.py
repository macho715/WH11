"""
[주의] Tolerance 적용 우선순위:
  1. 창고별 값(tolerance["WAREHOUSE_NAME"])
  2. default 값(tolerance["default"])
  3. 전역 tolerance_pct
(실제 적용은 위 순서대로 찾음. 온톨로지와 창고명 완전 일치 필수)

설정 관리 모듈
TOML 설정 파일 로드 및 환경변수 처리
"""

import os
import tomllib
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """설정 관리자 - TOML 파일 및 환경변수 처리"""
    
    def __init__(self, config_path: str = "config/settings.toml"):
        self.config_path = config_path
        self.config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'rb') as f:
                    config = tomllib.load(f)
                logger.info(f"✅ 설정 파일 로드 완료: {self.config_path}")
            else:
                logger.warning(f"⚠️ 설정 파일 없음: {self.config_path}, 기본값 사용")
                config = self._get_default_config()
            
            # 환경변수 오버라이드
            config = self._override_with_env_vars(config)
            return config
            
        except Exception as e:
            logger.error(f"❌ 설정 로드 실패: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """기본 설정값"""
        return {
            "validation": {
                "mode": "reference",
                "missing_reference_action": "warn",
                "tolerance": 1.0,
                "pass_rate_threshold": 95.0
            },
            "warehouses": {
                "expected_stock": {}
            },
            "data_processing": {
                "quantity_policy": {
                    "fill_na_with_zero": True,
                    "minimum_unit": 1,
                    "maximum_unit": 10000
                }
            },
            "deduplication": {
                "time_window_minutes": 5,
                "quantity_tolerance": 0.1,
                "enable_deduplication": True,
                "internal_transfer_handling": {
                    "single_deduction": True,
                    "internal_warehouses": ["Shifting", "Internal Transfer"]
                }
            },
            "logging": {
                "level": "INFO",
                "enable_data_loss_logging": True,
                "enable_duplicate_logging": True
            },
            "performance": {
                "use_vectorized_operations": True,
                "enable_groupby_optimization": True,
                "batch_size": 1000
            },
            "paths": {
                "data_directory": "data",
                "mapping_rules_file": "mapping_rules_v2.4.json",
                "output_directory": "reports",
                "warehouse_file_patterns": [
                    "HVDC WAREHOUSE_HITACHI*.xlsx",
                    "HVDC WAREHOUSE_SIMENSE*.xlsx"
                ],
                "exclude_patterns": ["*invoice*", "*~$*"]
            }
        }
    
    def _override_with_env_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """환경변수로 설정 오버라이드"""
        env_mappings = {
            "HVDC_DATA_DIR": ("paths", "data_directory"),
            "HVDC_LOG_LEVEL": ("logging", "level"),
            "HVDC_VALIDATION_MODE": ("validation", "mode"),
            "HVDC_TOLERANCE": ("validation", "tolerance"),
        }
        
        for env_var, config_path in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value:
                section, key = config_path
                if section not in config:
                    config[section] = {}
                
                # 타입 변환
                if key == "tolerance":
                    config[section][key] = float(env_value)
                elif key in ["fill_na_with_zero", "enable_deduplication", "single_deduction"]:
                    config[section][key] = env_value.lower() in ["true", "1", "yes"]
                else:
                    config[section][key] = env_value
                
                logger.info(f"환경변수 오버라이드: {env_var}={env_value}")
        
        return config
    
    def _validate_config(self):
        """설정 유효성 검증"""
        required_sections = ["validation", "data_processing", "deduplication", "logging", "paths"]
        
        for section in required_sections:
            if section not in self.config:
                logger.warning(f"⚠️ 필수 설정 섹션 누락: {section}")
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """설정값 조회"""
        try:
            return self.config[section][key]
        except KeyError:
            logger.debug(f"설정값 없음: {section}.{key}, 기본값 사용: {default}")
            return default
    
    def get_validation_config(self) -> Dict[str, Any]:
        """검증 설정 조회"""
        return self.config.get("validation", {})
    
    def get_warehouse_expected_stock(self, warehouse_name: str) -> Optional[int]:
        """창고별 기대 재고값 조회"""
        expected_stocks = self.config.get("warehouses", {}).get("expected_stock", {})
        return expected_stocks.get(warehouse_name)
    
    def get_quantity_policy(self) -> Dict[str, Any]:
        """수량 처리 정책 조회"""
        return self.config.get("data_processing", {}).get("quantity_policy", {})
    
    def get_deduplication_config(self) -> Dict[str, Any]:
        """중복 제거 설정 조회"""
        return self.config.get("deduplication", {})
    
    def get_paths_config(self) -> Dict[str, Any]:
        """경로 설정 조회"""
        return self.config.get("paths", {})
    
    def is_internal_warehouse(self, warehouse_name: str) -> bool:
        """내부 창고 여부 확인"""
        internal_warehouses = self.get_deduplication_config().get("internal_transfer_handling", {}).get("internal_warehouses", [])
        return warehouse_name in internal_warehouses
    
    def should_skip_validation(self, warehouse_name: str) -> bool:
        """검증 스킵 여부 확인"""
        mode = self.get("validation", "mode", "reference")
        if mode == "none":
            return True
        
        if mode == "reference":
            expected_stock = self.get_warehouse_expected_stock(warehouse_name)
            return expected_stock is None
        
        return False
    
    def get_missing_reference_action(self) -> str:
        """참조값 없을 때 동작 조회"""
        return self.get("validation", "missing_reference_action", "warn")

# 전역 설정 인스턴스
config_manager = ConfigManager() 