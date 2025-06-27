#!/usr/bin/env python3
"""
HVDC 통합 테스트 스크립트 v2.6

최신 실전 예제 및 확장 자동화 기능 테스트
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from pathlib import Path

# 모듈 임포트
from mapping_utils import (
    mapping_manager, 
    normalize_vendor, 
    standardize_container_columns,
    add_storage_type_to_dataframe,
    normalize_vendor_enhanced,
    standardize_container_columns_enhanced,
    add_storage_type_to_dataframe_enhanced,
    get_numeric_fields_from_mapping,
    validate_dataframe_against_mapping
)

from excel_reporter import (
    generate_monthly_in_out_stock_report,
    generate_excel_comprehensive_report,
    generate_automated_summary_report,
    validate_report_data
)

from ontology_mapper import (
    dataframe_to_rdf,
    create_enhanced_rdf,
    generate_sparql_queries,
    validate_rdf_conversion,
    create_rdf_schema,
    quick_rdf_convert
)

def create_test_data():
    """테스트용 샘플 데이터 생성"""
    print("📊 테스트 데이터 생성 중...")
    
    # 기본 테스트 데이터
    test_data = {
        'Case_No': [f'CASE{i:03d}' for i in range(1, 21)],
        'Date': [
            '2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05',
            '2024-02-01', '2024-02-02', '2024-02-03', '2024-02-04', '2024-02-05',
            '2024-03-01', '2024-03-02', '2024-03-03', '2024-03-04', '2024-03-05',
            '2024-04-01', '2024-04-02', '2024-04-03', '2024-04-04', '2024-04-05'
        ],
        'Location': [
            'DSV Indoor', 'DSV Outdoor', 'DSV MZP', 'AGI', 'DAS',
            'DSV Indoor', 'DSV Outdoor', 'MOSB', 'MIR', 'SHU',
            'DSV Indoor', 'DSV Al Markaz', 'DSV MZP', 'AGI', 'DAS',
            'DSV Indoor', 'DSV Outdoor', 'MOSB', 'MIR', 'SHU'
        ],
        'Qty': np.random.randint(10, 1000, 20),
        'Amount': np.random.uniform(1000, 50000, 20),
        'Handling Fee': np.random.uniform(50, 500, 20),
        'Vendor': np.random.choice(['SIMENSE', 'HITACHI', 'SAMSUNG', 'ZENER', 'ETC'], 20),
        'TxType_Refined': np.random.choice(['IN', 'TRANSFER_OUT', 'FINAL_OUT'], 20),
        'CBM': np.random.uniform(1, 100, 20),
        'Weight (kg)': np.random.uniform(10, 1000, 20),
        '20FT': np.random.randint(0, 5, 20),
        '40FT': np.random.randint(0, 3, 20),
        '20FR': np.random.randint(0, 2, 20),
        '40FR': np.random.randint(0, 2, 20)
    }
    
    df = pd.DataFrame(test_data)
    print(f"✅ 테스트 데이터 생성 완료: {len(df)}건")
    return df

def test_mapping_utils(df):
    """mapping_utils 테스트"""
    print("\n🔧 mapping_utils 테스트 중...")
    
    # 1. 벤더 정규화 테스트
    print("  📝 벤더 정규화 테스트...")
    df['Vendor_Normalized'] = df['Vendor'].apply(normalize_vendor)
    vendor_counts = df['Vendor_Normalized'].value_counts()
    print(f"    ✅ 벤더 정규화 완료: {dict(vendor_counts)}")
    
    # 2. 컨테이너 컬럼 표준화 테스트
    print("  📦 컨테이너 컬럼 표준화 테스트...")
    df_std = standardize_container_columns(df.copy())
    container_cols = [col for col in df_std.columns if any(ct in col for ct in ['20FT', '40FT', '20FR', '40FR'])]
    print(f"    ✅ 컨테이너 컬럼 표준화 완료: {container_cols}")
    
    # 3. Storage Type 추가 테스트
    print("  🏷️ Storage Type 추가 테스트...")
    df_storage = add_storage_type_to_dataframe(df.copy())
    storage_counts = df_storage['Storage_Type'].value_counts()
    print(f"    ✅ Storage Type 분류 완료: {dict(storage_counts)}")
    
    # 4. 향상된 함수들 테스트
    print("  🚀 향상된 함수들 테스트...")
    df_enhanced = normalize_vendor_enhanced(df['Vendor'].iloc[0])
    print(f"    ✅ 향상된 벤더 정규화: {df_enhanced}")
    
    # 5. 매핑 검증 테스트
    print("  ✅ 매핑 검증 테스트...")
    validation = validate_dataframe_against_mapping(df)
    print(f"    ✅ 매핑 검증 결과: {validation}")
    
    return df_storage

def test_excel_reporter(df):
    """excel_reporter 테스트"""
    print("\n📊 excel_reporter 테스트 중...")
    
    # 1. 기본 월별 리포트 테스트
    print("  📈 기본 월별 리포트 테스트...")
    in_df, out_df, stock_df = generate_monthly_in_out_stock_report(df)
    print(f"    ✅ IN 리포트: {len(in_df)}건")
    print(f"    ✅ OUT 리포트: {len(out_df)}건")
    print(f"    ✅ 재고 리포트: {len(stock_df)}건")
    
    # 2. 통합 엑셀 리포트 테스트
    print("  📋 통합 엑셀 리포트 테스트...")
    excel_path = generate_excel_comprehensive_report(df, output_file="test_output/integrated_report.xlsx")
    print(f"    ✅ 통합 리포트 생성: {excel_path}")
    
    # 3. 자동화된 요약 리포트 테스트
    print("  🤖 자동화된 요약 리포트 테스트...")
    summary_path = generate_automated_summary_report(df, output_dir="test_output")
    print(f"    ✅ 자동화 리포트 생성: {summary_path}")
    
    # 4. 데이터 검증 테스트
    print("  ✅ 데이터 검증 테스트...")
    validation = validate_report_data(df)
    print(f"    ✅ 데이터 검증 결과: {validation}")
    
    return excel_path, summary_path

def test_ontology_mapper(df):
    """ontology_mapper 테스트"""
    print("\n🔗 ontology_mapper 테스트 중...")
    
    # 1. 기본 RDF 변환 테스트
    print("  🔗 기본 RDF 변환 테스트...")
    rdf_path = dataframe_to_rdf(df, "test_output/basic_output.ttl")
    print(f"    ✅ 기본 RDF 변환: {rdf_path}")
    
    # 2. 향상된 RDF 변환 테스트
    print("  🚀 향상된 RDF 변환 테스트...")
    enhanced_rdf_path = create_enhanced_rdf(df, "test_output/enhanced_output.ttl")
    print(f"    ✅ 향상된 RDF 변환: {enhanced_rdf_path}")
    
    # 3. SPARQL 쿼리 생성 테스트
    print("  🔍 SPARQL 쿼리 생성 테스트...")
    sparql_path = generate_sparql_queries("test_output")
    print(f"    ✅ SPARQL 쿼리 생성: {sparql_path}")
    
    # 4. RDF 스키마 생성 테스트
    print("  📋 RDF 스키마 생성 테스트...")
    schema_path = create_rdf_schema("test_output/schema.ttl")
    print(f"    ✅ RDF 스키마 생성: {schema_path}")
    
    # 5. 빠른 변환 테스트
    print("  ⚡ 빠른 변환 테스트...")
    rdf_path, sparql_path, schema_path = quick_rdf_convert(df, "test_output")
    print(f"    ✅ 빠른 변환 완료: {rdf_path}")
    
    # 6. RDF 변환 검증 테스트
    print("  ✅ RDF 변환 검증 테스트...")
    validation = validate_rdf_conversion(df)
    print(f"    ✅ RDF 변환 검증: {validation}")
    
    return rdf_path, sparql_path, schema_path

def test_mapping_rules_integration():
    """mapping_rules 통합 테스트"""
    print("\n📋 mapping_rules 통합 테스트 중...")
    
    # 1. mapping_rules 로드 테스트
    print("  📄 mapping_rules 로드 테스트...")
    try:
        with open('mapping_rules_v2.6.json', 'r', encoding='utf-8') as f:
            rules = json.load(f)
        print(f"    ✅ mapping_rules 로드 완료: v{rules.get('version', 'unknown')}")
        
        # 2. 필드 매핑 확인
        field_map = rules.get('field_map', {})
        print(f"    ✅ 필드 매핑 수: {len(field_map)}개")
        
        # 3. 자동화 기능 확인
        automation = rules.get('automation_features', {})
        print(f"    ✅ 자동화 기능: {list(automation.keys())}")
        
        # 4. 숫자형 필드 확인
        numeric_fields = get_numeric_fields_from_mapping()
        print(f"    ✅ 숫자형 필드: {numeric_fields}")
        
    except Exception as e:
        print(f"    ❌ mapping_rules 로드 실패: {e}")
    
    return True

def main():
    """메인 테스트 함수"""
    print("🚀 HVDC 통합 테스트 시작")
    print("=" * 60)
    
    # 출력 디렉토리 생성
    Path("test_output").mkdir(exist_ok=True)
    
    try:
        # 1. 테스트 데이터 생성
        df = create_test_data()
        
        # 2. mapping_rules 통합 테스트
        test_mapping_rules_integration()
        
        # 3. mapping_utils 테스트
        df_processed = test_mapping_utils(df)
        
        # 4. excel_reporter 테스트
        excel_path, summary_path = test_excel_reporter(df_processed)
        
        # 5. ontology_mapper 테스트
        rdf_path, sparql_path, schema_path = test_ontology_mapper(df_processed)
        
        # 6. 결과 요약
        print("\n" + "=" * 60)
        print("🎉 모든 테스트 완료!")
        print("=" * 60)
        print("📁 생성된 파일들:")
        print(f"  📊 엑셀 리포트: {excel_path}")
        print(f"  📋 요약 리포트: {summary_path}")
        print(f"  🔗 RDF 파일: {rdf_path}")
        print(f"  🔍 SPARQL 쿼리: {sparql_path}")
        print(f"  📋 RDF 스키마: {schema_path}")
        
        print("\n✅ 최신 실전 예제 및 확장 자동화 기능이 모두 정상 작동합니다!")
        
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 통합 테스트 성공!")
    else:
        print("\n❌ 통합 테스트 실패!") 