import pandas as pd
import json

# (전역, 파일 상단에서)
try:
    with open('mapping_rules_v2.6.json', encoding='utf-8') as f:
        RULES = json.load(f)
    WAREHOUSE_CLASS = RULES.get('warehouse_classification', {})
except Exception as e:
    print(f"⚠️ 매핑룰 로드 실패: {e}")
    WAREHOUSE_CLASS = {}

def normalize_str(val):
    """모든 주요 key(벤더, 스토리지, 현장명 등) 소문자·공백 표준화"""
    if pd.isna(val): return ""
    return str(val).strip().lower().replace("  ", " ").replace("_", " ").replace("-", " ")

def normalize_all_keys(df):
    """Vendor, Storage_Type, Status_Location, Status_Current 등 일괄 정규화"""
    for col in ['Vendor', 'Storage_Type', 'Status_Location', 'Status_Current']:
        if col in df.columns:
            df[col] = df[col].apply(normalize_str)
    return df 

def classify_storage_type(location):
    """
    동적 매핑룰 기반 Storage Type 분류 (Indoor/Outdoor/Site/위험물/Unknown 자동)
    - mapping_rules_v2.6.json warehouse_classification 기준
    """
    if pd.isna(location) or not location:
        return "Unknown"
    loc = str(location).strip()
    # 1. 룰에서 직접 매칭
    for storage_type, locations in WAREHOUSE_CLASS.items():
        if loc in locations:
            return storage_type
    # 2. 부분 매칭(확장): 예) "DSV Outdoor" in "Outdoor" 등
    loc_lower = loc.lower()
    for storage_type, locations in WAREHOUSE_CLASS.items():
        for pattern in locations:
            if pattern.lower() in loc_lower or loc_lower in pattern.lower():
                return storage_type
    return "Unknown" 