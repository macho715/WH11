#!/usr/bin/env python3
"""
HVDC Warehouse 통합 매핑 유틸리티 v2.6

매핑 규칙 파일을 기반으로 일관된 Storage Type 분류를 제공합니다.
최신 실전 예제 및 확장 자동화 기능 포함.
"""

import json
import pandas as pd
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# 최신 mapping_rules 불러오기
try:
    with open('mapping_rules_v2.6.json', encoding='utf-8') as f:
        RULES = json.load(f)
    VENDOR_MAP = RULES['vendor_mappings']
    CONTAINER_GROUPS = RULES['container_column_groups']
    WAREHOUSE_CLASS = RULES['warehouse_classification']
    FIELD_MAP = RULES['field_map']
    PROPERTY_MAPPINGS = RULES['property_mappings']
except Exception as e:
    logger.warning(f"mapping_rules_v2.6.json 로드 실패, 기본값 사용: {e}")
    VENDOR_MAP = {}
    CONTAINER_GROUPS = {}
    WAREHOUSE_CLASS = {}
    FIELD_MAP = {}
    PROPERTY_MAPPINGS = {}

class MappingManager:
    """통합 매핑 관리자"""
    
    def __init__(self, mapping_file: str = "mapping_rules_v2.6.json"):
        self.mapping_file = mapping_file
        self.mapping_rules = self._load_mapping_rules()
        self.warehouse_classification = self.mapping_rules.get("warehouse_classification", {})
        
    def _load_mapping_rules(self):
        """매핑 규칙 파일 로드"""
        try:
            rule_path = Path(self.mapping_file)
            if not rule_path.exists():
                logger.error(f"매핑 규칙 파일 없음: {self.mapping_file}")
                return {}
                
            with open(rule_path, "r", encoding="utf-8") as f:
                rules = json.load(f)
                logger.info(f"✅ 매핑 규칙 로드 완료: {self.mapping_file}")
                return rules
        except Exception as e:
            logger.error(f"매핑 규칙 로드 실패: {e}")
            return {}
    
    def classify_storage_type(self, location: str) -> str:
        """
        Location을 Storage Type으로 분류
        
        Args:
            location: 창고/현장명
            
        Returns:
            str: Storage Type (Indoor, Outdoor, Site, dangerous_cargo, Unknown)
        """
        if not location or pd.isna(location):
            return "Unknown"
            
        loc = str(location).strip()
        
        # 매핑 규칙에 따른 분류
        for storage_type, locations in self.warehouse_classification.items():
            if loc in locations:
                return storage_type
                
        # 추가 패턴 매칭 (부분 문자열)
        loc_lower = loc.lower()
        for storage_type, locations in self.warehouse_classification.items():
            for pattern in locations:
                if pattern.lower() in loc_lower or loc_lower in pattern.lower():
                    return storage_type
        
        logger.warning(f"⚠️ 매핑되지 않은 Location: {location}")
        return "Unknown"
    
    def add_storage_type_to_dataframe(self, df: pd.DataFrame, location_col: str = "Location") -> pd.DataFrame:
        """
        DataFrame에 Storage_Type 컬럼 추가
        
        Args:
            df: 대상 DataFrame
            location_col: Location 컬럼명
            
        Returns:
            pd.DataFrame: Storage_Type 컬럼이 추가된 DataFrame
        """
        if location_col not in df.columns:
            logger.error(f"Location 컬럼 없음: {location_col}")
            df['Storage_Type'] = 'Unknown'
            return df
            
        # ✅ Location 기준으로 Storage_Type 새로 생성 (기존 값 무시)
        df['Storage_Type'] = df[location_col].apply(self.classify_storage_type)
        
        # 검증 로그
        storage_counts = df['Storage_Type'].value_counts()
        logger.info(f"🏷️ Storage Type 분류 결과: {dict(storage_counts)}")
        
        return df
    
    def validate_mapping(self, df: pd.DataFrame, location_col: str = "Location") -> dict:
        """
        매핑 검증 및 통계
        
        Args:
            df: 검증할 DataFrame
            location_col: Location 컬럼명
            
        Returns:
            dict: 검증 결과
        """
        if location_col not in df.columns:
            return {"error": f"Location 컬럼 없음: {location_col}"}
            
        # Storage Type별 고유 Location 목록
        validation_result = {}
        
        for storage_type in self.warehouse_classification.keys():
            locations = df[df['Storage_Type'] == storage_type][location_col].unique()
            validation_result[storage_type] = {
                'count': len(df[df['Storage_Type'] == storage_type]),
                'locations': sorted(locations.tolist())
            }
        
        # Unknown 타입 검증
        unknown_locations = df[df['Storage_Type'] == 'Unknown'][location_col].unique()
        validation_result['Unknown'] = {
            'count': len(df[df['Storage_Type'] == 'Unknown']),
            'locations': sorted(unknown_locations.tolist())
        }
        
        return validation_result
    
    def get_warehouse_locations(self) -> list:
        """창고 Location 목록 반환"""
        warehouse_types = ['Indoor', 'Outdoor', 'dangerous_cargo']
        warehouse_locations = []
        
        for storage_type in warehouse_types:
            if storage_type in self.warehouse_classification:
                warehouse_locations.extend(self.warehouse_classification[storage_type])
                
        return warehouse_locations
    
    def get_site_locations(self) -> list:
        """현장 Location 목록 반환"""
        return self.warehouse_classification.get('Site', [])

# 전역 매핑 매니저 인스턴스
mapping_manager = MappingManager()

def classify_storage_type(location: str) -> str:
    """편의 함수: Location을 Storage Type으로 분류"""
    return mapping_manager.classify_storage_type(location)

def add_storage_type_to_dataframe(df: pd.DataFrame, location_col: str = "Location") -> pd.DataFrame:
    """편의 함수: DataFrame에 Storage_Type 컬럼 추가"""
    return mapping_manager.add_storage_type_to_dataframe(df, location_col)

def normalize_vendor(vendor_name):
    """
    벤더명 정규화 (mapping_rules의 vendor_mappings 적용)
    
    Args:
        vendor_name: 원본 벤더명
        
    Returns:
        str: 정규화된 벤더명
    """
    if pd.isna(vendor_name) or not vendor_name:
        return 'UNKNOWN'
    
    vendor_mappings = mapping_manager.mapping_rules.get('vendor_mappings', {})
    vendor_str = str(vendor_name).strip().upper()
    
    # 매핑 규칙에 따른 정규화
    for original, normalized in vendor_mappings.items():
        if vendor_str == original.upper() or vendor_str in original.upper():
            return normalized
    
    return vendor_str

def standardize_container_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    컨테이너 컬럼 표준화 (mapping_rules의 container_column_groups 적용)
    
    Args:
        df: 대상 DataFrame
        
    Returns:
        pd.DataFrame: 표준화된 DataFrame
    """
    container_groups = mapping_manager.mapping_rules.get('container_column_groups', {})
    
    # 각 컨테이너 그룹별로 표준화
    for standard_name, variations in container_groups.items():
        # 해당 그룹의 모든 변형을 찾아서 표준명으로 통합
        for variation in variations:
            if variation in df.columns:
                # 표준명 컬럼이 없으면 생성
                if standard_name not in df.columns:
                    df[standard_name] = 0
                
                # 기존 값들을 표준명 컬럼에 추가
                df[standard_name] = df[standard_name] + df[variation].fillna(0)
                
                # 원본 컬럼 삭제 (선택사항)
                # df = df.drop(columns=[variation])
    
    return df

# 최신 실전 예제 함수들 추가
def normalize_vendor_enhanced(val):
    """벤더명 표준화: SIMENSE→SIM 등 (최신 실전 예제)"""
    if pd.isna(val): 
        return 'Unknown'
    sval = str(val).upper()
    return VENDOR_MAP.get(sval, sval)

def standardize_container_columns_enhanced(df):
    """컨테이너 컬럼(20FT/40FT 등) 그룹화 (최신 실전 예제)"""
    for std_col, variants in CONTAINER_GROUPS.items():
        df[std_col] = 0
        for var in variants:
            for col in df.columns:
                if col.replace(" ", "").replace("-", "").upper() == var.replace(" ", "").replace("-", "").upper():
                    df[std_col] += pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

def add_storage_type_to_dataframe_enhanced(df, col="Category"):
    """창고/현장/위험물 자동 분류 (Storage_Type 부여) (최신 실전 예제)"""
    def map_type(loc):
        for k, vlist in WAREHOUSE_CLASS.items():
            if str(loc).strip() in vlist:
                return k
        return "Unknown"
    df["Storage_Type"] = df[col].apply(map_type)
    return df

def normalize_location_column(df, location_col='Location'):
    """Location 컬럼 정규화 (최신 실전 예제)"""
    df[location_col] = df[location_col].astype(str).str.strip()
    return df

def get_numeric_fields_from_mapping():
    """mapping_rules에서 숫자형 필드 목록 반환"""
    numeric_fields = []
    for field, props in PROPERTY_MAPPINGS.items():
        if props.get('datatype') in ['xsd:decimal', 'xsd:integer']:
            numeric_fields.append(field)
    return numeric_fields

def get_field_predicate(field_name):
    """필드명에 해당하는 predicate 반환"""
    return FIELD_MAP.get(field_name, f"has{field_name.replace(' ', '')}")

def validate_dataframe_against_mapping(df):
    """DataFrame이 mapping_rules와 일치하는지 검증"""
    missing_fields = []
    extra_fields = []
    
    # mapping_rules에 정의된 필드가 DataFrame에 없는지 확인
    for field in FIELD_MAP.keys():
        if field not in df.columns:
            missing_fields.append(field)
    
    # DataFrame에 있지만 mapping_rules에 정의되지 않은 필드 확인
    for col in df.columns:
        if col not in FIELD_MAP:
            extra_fields.append(col)
    
    return {
        'missing_fields': missing_fields,
        'extra_fields': extra_fields,
        'is_valid': len(missing_fields) == 0
    } 