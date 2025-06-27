#!/usr/bin/env python3
"""
YAML 온톨로지 정합성 검증 스크립트
expected_stock.yml의 창고 ID가 온톨로지와 일치하는지 검증합니다.
"""

import json
import yaml
import sys
from pathlib import Path
from typing import Dict, List, Set

def load_valid_warehouse_ids() -> Set[str]:
    """유효한 창고 ID 목록 로드"""
    try:
        with open("valid_warehouse_ids.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data["valid_warehouse_ids"])
    except FileNotFoundError:
        print("❌ valid_warehouse_ids.json 파일을 찾을 수 없습니다.")
        return set()

def load_expected_stock_yaml() -> Dict:
    """expected_stock.yml 파일 로드"""
    try:
        with open("expected_stock.yml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("❌ expected_stock.yml 파일을 찾을 수 없습니다.")
        return {}
    except yaml.YAMLError as e:
        print(f"❌ YAML 파싱 오류: {e}")
        return {}

def validate_warehouse_ids(yaml_data: Dict, valid_ids: Set[str]) -> Dict:
    """창고 ID 검증"""
    validation_result = {
        "is_valid": True,
        "errors": [],
        "warnings": [],
        "summary": {
            "total_warehouses": 0,
            "valid_warehouses": 0,
            "invalid_warehouses": 0,
            "missing_warehouses": []
        }
    }
    
    if "expected" not in yaml_data:
        validation_result["errors"].append("'expected' 섹션이 없습니다.")
        validation_result["is_valid"] = False
        return validation_result
    
    # 모든 날짜에서 사용된 창고 ID 수집
    used_warehouse_ids = set()
    for date_str, warehouses in yaml_data["expected"].items():
        if isinstance(warehouses, dict):
            used_warehouse_ids.update(warehouses.keys())
    
    validation_result["summary"]["total_warehouses"] = len(used_warehouse_ids)
    
    # 유효하지 않은 창고 ID 검사
    invalid_ids = used_warehouse_ids - valid_ids
    if invalid_ids:
        validation_result["errors"].append(f"유효하지 않은 창고 ID: {sorted(invalid_ids)}")
        validation_result["is_valid"] = False
        validation_result["summary"]["invalid_warehouses"] = len(invalid_ids)
    
    # 누락된 창고 ID 검사
    missing_ids = valid_ids - used_warehouse_ids
    if missing_ids:
        validation_result["warnings"].append(f"누락된 창고 ID: {sorted(missing_ids)}")
        validation_result["summary"]["missing_warehouses"] = sorted(missing_ids)
    
    validation_result["summary"]["valid_warehouses"] = len(used_warehouse_ids - invalid_ids)
    
    return validation_result

def validate_tolerance_structure(yaml_data: Dict) -> Dict:
    """Tolerance 구조 검증"""
    validation_result = {
        "is_valid": True,
        "errors": [],
        "warnings": []
    }
    
    # tolerance_pct 확인
    if "tolerance_pct" not in yaml_data:
        validation_result["warnings"].append("tolerance_pct가 정의되지 않았습니다.")
    
    # tolerance 섹션 확인
    if "tolerance" not in yaml_data:
        validation_result["warnings"].append("tolerance 섹션이 없습니다.")
    else:
        tolerance = yaml_data["tolerance"]
        if "default" not in tolerance:
            validation_result["warnings"].append("tolerance에 default 값이 없습니다.")
    
    return validation_result

def validate_date_format(yaml_data: Dict) -> Dict:
    """날짜 형식 검증"""
    validation_result = {
        "is_valid": True,
        "errors": [],
        "warnings": []
    }
    
    if "expected" not in yaml_data:
        return validation_result
    
    for date_str in yaml_data["expected"].keys():
        try:
            # YYYY-MM-DD 형식 검증
            if not isinstance(date_str, str) or len(date_str) != 10:
                validation_result["errors"].append(f"잘못된 날짜 형식: {date_str}")
                validation_result["is_valid"] = False
                continue
            
            year, month, day = date_str.split("-")
            if not (year.isdigit() and month.isdigit() and day.isdigit()):
                validation_result["errors"].append(f"날짜에 숫자가 아닌 문자가 포함됨: {date_str}")
                validation_result["is_valid"] = False
                continue
            
            # 실제 날짜 유효성 검사
            from datetime import datetime
            datetime.strptime(date_str, "%Y-%m-%d")
            
        except ValueError as e:
            validation_result["errors"].append(f"잘못된 날짜: {date_str} - {e}")
            validation_result["is_valid"] = False
    
    return validation_result

def main():
    """메인 검증 함수"""
    print("🔍 YAML 온톨로지 정합성 검증 시작")
    print("=" * 50)
    
    # 유효한 창고 ID 로드
    valid_ids = load_valid_warehouse_ids()
    if not valid_ids:
        print("❌ 유효한 창고 ID를 로드할 수 없습니다.")
        sys.exit(1)
    
    print(f"✅ 유효한 창고 ID {len(valid_ids)}개 로드됨")
    
    # YAML 파일 로드
    yaml_data = load_expected_stock_yaml()
    if not yaml_data:
        print("❌ YAML 파일을 로드할 수 없습니다.")
        sys.exit(1)
    
    print("✅ expected_stock.yml 로드됨")
    
    # 검증 실행
    warehouse_validation = validate_warehouse_ids(yaml_data, valid_ids)
    tolerance_validation = validate_tolerance_structure(yaml_data)
    date_validation = validate_date_format(yaml_data)
    
    # 결과 출력
    print("\n📊 검증 결과:")
    print("-" * 30)
    
    # 창고 ID 검증 결과
    if warehouse_validation["is_valid"]:
        print("✅ 창고 ID 검증 통과")
    else:
        print("❌ 창고 ID 검증 실패")
        for error in warehouse_validation["errors"]:
            print(f"   - {error}")
    
    for warning in warehouse_validation["warnings"]:
        print(f"⚠️  {warning}")
    
    # Tolerance 검증 결과
    if tolerance_validation["is_valid"]:
        print("✅ Tolerance 구조 검증 통과")
    else:
        print("❌ Tolerance 구조 검증 실패")
        for error in tolerance_validation["errors"]:
            print(f"   - {error}")
    
    for warning in tolerance_validation["warnings"]:
        print(f"⚠️  {warning}")
    
    # 날짜 형식 검증 결과
    if date_validation["is_valid"]:
        print("✅ 날짜 형식 검증 통과")
    else:
        print("❌ 날짜 형식 검증 실패")
        for error in date_validation["errors"]:
            print(f"   - {error}")
    
    # 요약 정보
    if warehouse_validation["summary"]:
        summary = warehouse_validation["summary"]
        print(f"\n📈 요약:")
        print(f"   - 총 창고 수: {summary['total_warehouses']}")
        print(f"   - 유효한 창고: {summary['valid_warehouses']}")
        print(f"   - 유효하지 않은 창고: {summary['invalid_warehouses']}")
        if summary['missing_warehouses']:
            print(f"   - 누락된 창고: {len(summary['missing_warehouses'])}개")
    
    # 최종 결과
    overall_valid = (
        warehouse_validation["is_valid"] and 
        tolerance_validation["is_valid"] and 
        date_validation["is_valid"]
    )
    
    print("\n" + "=" * 50)
    if overall_valid:
        print("🎉 모든 검증 통과!")
        sys.exit(0)
    else:
        print("❌ 검증 실패 - 수정이 필요합니다.")
        sys.exit(1)

if __name__ == "__main__":
    main() 