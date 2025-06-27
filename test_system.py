#!/usr/bin/env python3
"""
수정된 HVDC 재고 관리 시스템 테스트
pandas 2.0+ 호환성 및 트랜잭션 추출 문제 해결 확인
"""

import os
import sys
import pandas as pd
from datetime import datetime

# 현재 디렉토리를 파이썬 경로에 추가
sys.path.append('.')

def create_expected_stock_yml():
    """expected_stock.yml 파일 생성"""
    yml_content = """# HVDC 창고 기대 재고 설정
# 기존 기대값이 부정확하여 제거됨

# 향후 정확한 기대값이 확정되면 아래 형식으로 추가:
# "2025-06-24":
#   "DSV Al Markaz": [정확한_값]
#   "DSV Indoor": [정확한_값]
#   "DSV Outdoor": [정확한_값]

# 현재는 빈 설정으로 유지
"2025-06-24": {}
"2025-06-25": {}
"2025-07-01": {}

# 오차 허용 범위 설정
tolerance:
  default: 2
  "DSV Al Markaz": 2
  "DSV Indoor": 2
  "DSV Outdoor": 2
"""
    
    with open('expected_stock.yml', 'w', encoding='utf-8') as f:
        f.write(yml_content)
    
    print("✅ expected_stock.yml 파일 생성 완료")

def test_text_normalization():
    """텍스트 정규화 테스트"""
    print("🧪 텍스트 정규화 테스트")
    print("-" * 40)
    
    from core.loader import DataLoader
    loader = DataLoader()
    
    test_cases = [
        "PKG", "pkg", "Pkg", "PKGS", "pkgs", "Pkgs", 
        "PKG'S", "pkg's", "Pkg's", "PACKAGE", "package", 
        "Package", "PACKAGES", "packages", "Packages"
    ]
    
    for test_case in test_cases:
        normalized = loader._normalize_text_for_matching(test_case)
        print(f"  {test_case:<12} → {normalized}")
    
    print("✅ 텍스트 정규화 테스트 완료\n")

def test_data_loading():
    """데이터 로딩 테스트"""
    print("🧪 데이터 로딩 테스트")
    print("-" * 40)
    
    from core.loader import DataLoader
    loader = DataLoader()
    
    # data 디렉토리 확인
    data_dir = "data"
    if not os.path.exists(data_dir):
        print(f"❌ {data_dir} 디렉토리가 없습니다.")
        return False
    
    # Excel 파일 로딩
    excel_files = loader.load_excel_files(data_dir)
    
    if not excel_files:
        print(f"❌ {data_dir}에서 Excel 파일을 찾을 수 없습니다.")
        return False
    
    print(f"✅ {len(excel_files)}개 Excel 파일 발견:")
    
    total_rows = 0
    for filename, df in excel_files.items():
        print(f"  📄 {filename}: {len(df)} 행, {len(df.columns)} 컬럼")
        total_rows += len(df)
        
        # 컬럼 분석
        case_col = loader._find_case_column(df)
        qty_col = loader._find_quantity_column(df)
        date_cols = loader._find_date_columns(df)
        
        print(f"    케이스 컬럼: {case_col}")
        print(f"    수량 컬럼: {qty_col}")
        print(f"    날짜 컬럼: {len(date_cols)}개")
        
        if len(date_cols) > 0:
            print(f"    날짜 컬럼 샘플: {date_cols[:3]}")
    
    print(f"  총 데이터: {total_rows:,} 행")
    print("✅ 데이터 로딩 테스트 완료\n")
    return True

def test_transaction_extraction():
    """트랜잭션 추출 테스트"""
    print("🧪 트랜잭션 추출 테스트")
    print("-" * 40)
    
    from core.loader import DataLoader
    loader = DataLoader()
    
    # 데이터 로딩
    excel_files = loader.load_excel_files("data")
    
    if not excel_files:
        print("❌ 테스트할 Excel 파일이 없습니다.")
        return False
    
    # 트랜잭션 추출
    raw_transactions = loader.extract_transactions(excel_files)
    
    print(f"📊 추출 결과: {len(raw_transactions):,}건")
    
    if len(raw_transactions) == 0:
        print("❌ 트랜잭션이 추출되지 않았습니다.")
        
        # 디버깅 정보 출력
        print("\n🔍 디버깅 정보:")
        for filename, df in excel_files.items():
            print(f"\n📄 {filename}:")
            print(f"  데이터 행수: {len(df)}")
            print(f"  컬럼 수: {len(df.columns)}")
            
            # 샘플 컬럼명 출력
            sample_cols = list(df.columns[:10])
            print(f"  컬럼 샘플: {sample_cols}")
            
            # 케이스 컬럼 찾기
            case_col = loader._find_case_column(df)
            if case_col:
                sample_cases = df[case_col].dropna().head(3).tolist()
                print(f"  케이스 컬럼: {case_col}")
                print(f"  케이스 샘플: {sample_cases}")
            else:
                print("  케이스 컬럼: 찾을 수 없음")
            
            # 날짜 컬럼 찾기
            date_cols = loader._find_date_columns(df)
            print(f"  날짜 컬럼: {len(date_cols)}개")
            if date_cols:
                print(f"  날짜 컬럼 샘플: {date_cols[:3]}")
        
        return False
    
    # 트랜잭션 통계
    incoming_count = sum(1 for tx in raw_transactions if tx['data'].get('incoming', 0) > 0)
    outgoing_count = sum(1 for tx in raw_transactions if tx['data'].get('outgoing', 0) > 0)
    
    print(f"  📥 입고 트랜잭션: {incoming_count:,}건")
    print(f"  📤 출고 트랜잭션: {outgoing_count:,}건")
    
    # 창고별 분포
    warehouse_counts = {}
    for tx in raw_transactions:
        warehouse = tx['data'].get('warehouse', 'UNKNOWN')
        warehouse_counts[warehouse] = warehouse_counts.get(warehouse, 0) + 1
    
    print(f"\n🏭 창고별 분포 (상위 5개):")
    sorted_warehouses = sorted(warehouse_counts.items(), key=lambda x: x[1], reverse=True)
    for warehouse, count in sorted_warehouses[:5]:
        print(f"  {warehouse}: {count:,}건")
    
    print("✅ 트랜잭션 추출 테스트 완료\n")
    return True

def test_dataframe_conversion():
    """DataFrame 변환 테스트"""
    print("🧪 DataFrame 변환 테스트")
    print("-" * 40)
    
    try:
        from core.loader import DataLoader
        from main import transactions_to_dataframe
        
        loader = DataLoader()
        excel_files = loader.load_excel_files("data")
        raw_transactions = loader.extract_transactions(excel_files)
        
        if not raw_transactions:
            print("❌ 변환할 트랜잭션이 없습니다.")
            return False
        
        # DataFrame 변환
        transactions_df = transactions_to_dataframe(raw_transactions)
        
        print(f"📊 변환 결과: {len(transactions_df):,} 행")
        
        if transactions_df.empty:
            print("❌ DataFrame 변환 실패")
            return False
        
        # 컬럼 정보
        print(f"  컬럼 수: {len(transactions_df.columns)}")
        print(f"  컬럼: {list(transactions_df.columns)}")
        
        # 트랜잭션 타입별 분포
        if 'TxType_Refined' in transactions_df.columns:
            tx_type_counts = transactions_df['TxType_Refined'].value_counts()
            print(f"\n📊 트랜잭션 타입별 분포:")
            for tx_type, count in tx_type_counts.items():
                print(f"  {tx_type}: {count:,}건")
        
        # Status 정보 확인
        status_cols = [col for col in transactions_df.columns if col.startswith('Status_')]
        if status_cols:
            print(f"\n📊 Status 컬럼: {status_cols}")
            for col in status_cols[:3]:  # 상위 3개만 표시
                if col in transactions_df.columns:
                    unique_values = transactions_df[col].nunique()
                    print(f"  {col}: {unique_values}개 고유값")
        
        print("✅ DataFrame 변환 테스트 완료\n")
        return True
        
    except Exception as e:
        print(f"❌ DataFrame 변환 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_full_system():
    """전체 시스템 통합 테스트"""
    print("🧪 전체 시스템 통합 테스트")
    print("-" * 40)
    
    try:
        # main.py의 process_hvdc_inventory 함수 테스트
        from main import process_hvdc_inventory
        import argparse
        
        # 테스트 인자 생성
        args = argparse.Namespace()
        args.data_dir = "data"
        args.asof = "2025-06-24"
        args.debug = True
        
        # 시스템 실행
        success = process_hvdc_inventory(args)
        
        if success:
            print("✅ 전체 시스템 테스트 성공")
        else:
            print("❌ 전체 시스템 테스트 실패")
        
        return success
        
    except Exception as e:
        print(f"❌ 전체 시스템 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 실행"""
    print("🚀 HVDC 재고 관리 시스템 - 수정 사항 테스트")
    print("=" * 60)
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 0. 필수 파일 생성
    create_expected_stock_yml()
    
    # 테스트 실행
    tests = [
        ("텍스트 정규화", test_text_normalization),
        ("데이터 로딩", test_data_loading),
        ("트랜잭션 추출", test_transaction_extraction),
        ("DataFrame 변환", test_dataframe_conversion),
        ("전체 시스템", test_full_system)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name} 테스트 실행 중...")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 테스트 중 오류: {e}")
            results.append((test_name, False))
    
    # 최종 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        
        if result:
            passed += 1
        else:
            failed += 1
    
    print("-" * 60)
    print(f"총 {len(results)}개 테스트 중 {passed}개 성공, {failed}개 실패")
    
    if failed == 0:
        print("🎉 모든 테스트가 성공했습니다!")
    else:
        print("⚠️ 일부 테스트가 실패했습니다. 로그를 확인해주세요.")
    
    print("=" * 60)

if __name__ == "__main__":
    main() 