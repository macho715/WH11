"""
HVDC 시스템용 헬퍼 함수들
main.py에서 사용할 유틸리티 함수들
"""

import pandas as pd
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def get_latest_inventory_summary(expected_values=None, tolerance=2):
    """
    최신 데이터 기준 DSV Al Markaz, DSV Indoor의 최신 재고 집계
    main.py의 로직을 단순화한 버전
    """
    from config import load_expected_stock
    from core.loader import DataLoader
    from core.deduplication import reconcile_orphan_transfers, drop_duplicate_transfers
    from core.inventory_engine import validate_transfer_pairs, validate_date_sequence
    
    try:
        print("🚀 재고 요약 생성 중...")
        
        # 1. 데이터 로딩
        loader = DataLoader()
        excel_files = loader.load_excel_files("data")
        
        if not excel_files:
            print("❌ Excel 파일이 없습니다!")
            return None
        
        raw_transactions = loader.extract_transactions(excel_files)
        print(f"📊 총 {len(raw_transactions):,}건의 원시 트랜잭션 수집")
        
        # 2. DataFrame 변환
        transaction_df = transactions_to_dataframe_simple(raw_transactions)
        
        # 3. TRANSFER 보정
        transaction_df = reconcile_orphan_transfers(transaction_df)
        
        # 4. 중복 제거
        transaction_df = drop_duplicate_transfers(transaction_df)
        
        # 5. 검증
        validate_transfer_pairs(transaction_df)
        validate_date_sequence(transaction_df)
        
        # 6. 재고 계산
        daily_stock = calculate_simple_inventory(transaction_df)
        
        # 7. 기대값 비교
        today = datetime.now().strftime("%Y-%m-%d")
        expected = load_expected_stock(today)
        
        if daily_stock is not None and not daily_stock.empty:
            compare_with_expected_simple(daily_stock, expected, tolerance)
            return daily_stock
        else:
            print("❌ 재고 계산 실패")
            return None
            
    except Exception as e:
        print(f"❌ 재고 요약 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        return None

def transactions_to_dataframe_simple(transactions):
    """단순화된 트랜잭션 → DataFrame 변환"""
    data = []
    
    for tx in transactions:
        tx_data = tx.get('data', {})
        
        # 기본 정보 추출
        case_id = str(tx_data.get('case', f"CASE_{len(data)}"))
        warehouse = normalize_warehouse_simple(tx_data.get('warehouse', 'UNKNOWN'))
        date_val = tx_data.get('date', datetime.now())
        
        # 수량 처리
        incoming = tx_data.get('incoming', 0) or 0
        outgoing = tx_data.get('outgoing', 0) or 0
        
        # IN 트랜잭션
        if incoming > 0:
            data.append({
                'Case_No': case_id,
                'Date': pd.to_datetime(date_val),
                'Qty': int(incoming),
                'TxType_Refined': 'IN',
                'Location': warehouse,
                'Loc_From': 'SOURCE',
                'Target_Warehouse': warehouse,
                'Source_File': tx.get('source_file', '')
            })
        
        # OUT 트랜잭션
        if outgoing > 0:
            # 사이트 구분
            site = extract_site_simple(warehouse)
            tx_type = 'FINAL_OUT' if site in ['AGI', 'DAS', 'MIR', 'SHU'] else 'TRANSFER_OUT'
            
            data.append({
                'Case_No': case_id,
                'Date': pd.to_datetime(date_val),
                'Qty': int(outgoing),
                'TxType_Refined': tx_type,
                'Location': warehouse,
                'Loc_From': warehouse,
                'Target_Warehouse': 'DESTINATION',
                'Source_File': tx.get('source_file', '')
            })
    
    return pd.DataFrame(data)

def normalize_warehouse_simple(raw_name):
    """간단한 창고명 정규화"""
    if pd.isna(raw_name):
        return 'UNKNOWN'
        
    name_lower = str(raw_name).lower().strip()
    
    if any(x in name_lower for x in ['markaz', 'm1', 'al markaz']):
        return 'DSV Al Markaz'
    elif any(x in name_lower for x in ['indoor', 'm44']):
        return 'DSV Indoor'
    elif any(x in name_lower for x in ['outdoor', 'out']):
        return 'DSV Outdoor'
    elif 'mosb' in name_lower:
        return 'MOSB'
    elif 'mzp' in name_lower:
        return 'DSV MZP'
    elif 'dhl' in name_lower:
        return 'DHL WH'
    elif 'aaa' in name_lower:
        return 'AAA Storage'
    
    return str(raw_name).strip()

def extract_site_simple(warehouse_name):
    """간단한 사이트명 추출"""
    name_upper = str(warehouse_name).upper()
    
    if 'AGI' in name_upper:
        return 'AGI'
    elif 'DAS' in name_upper:
        return 'DAS'
    elif 'MIR' in name_upper:
        return 'MIR'
    elif 'SHU' in name_upper:
        return 'SHU'
    
    return 'UNK'

def calculate_simple_inventory(transaction_df):
    """간단한 재고 계산"""
    if transaction_df.empty:
        return pd.DataFrame()
    
    print("📊 간단 재고 계산 중...")
    
    # 날짜 정규화
    transaction_df['Date'] = pd.to_datetime(transaction_df['Date']).dt.date
    
    # 트랜잭션 타입별 집계
    daily_summary = transaction_df.groupby(['Location', 'Date', 'TxType_Refined']).agg({
        'Qty': 'sum'
    }).reset_index()
    
    # 피벗
    daily_pivot = daily_summary.pivot_table(
        index=['Location', 'Date'],
        columns='TxType_Refined', 
        values='Qty',
        fill_value=0
    ).reset_index()
    
    daily_pivot.columns.name = None
    
    # 필요한 컬럼 확보
    for col in ['IN', 'TRANSFER_OUT', 'FINAL_OUT']:
        if col not in daily_pivot.columns:
            daily_pivot[col] = 0
    
    # 재고 계산
    stock_records = []
    
    for location in daily_pivot['Location'].unique():
        if location in ['UNKNOWN', 'UNK']:
            continue
            
        loc_data = daily_pivot[daily_pivot['Location'] == location].sort_values('Date')
        current_stock = 0
        
        for _, row in loc_data.iterrows():
            inbound = row.get('IN', 0)
            transfer_out = row.get('TRANSFER_OUT', 0)
            final_out = row.get('FINAL_OUT', 0)
            total_outbound = transfer_out + final_out
            
            opening_stock = current_stock
            closing_stock = opening_stock + inbound - total_outbound
            current_stock = closing_stock
            
            stock_records.append({
                'Location': location,
                'Date': row['Date'],
                'Opening_Stock': opening_stock,
                'Inbound': inbound,
                'Transfer_Out': transfer_out,
                'Final_Out': final_out,
                'Total_Outbound': total_outbound,
                'Closing_Stock': closing_stock
            })
    
    result_df = pd.DataFrame(stock_records)
    
    if not result_df.empty:
        print(f"✅ {len(result_df)}개 재고 스냅샷 생성")
    
    return result_df

def compare_with_expected_simple(daily_stock, expected, tolerance=2):
    """간단한 기대값 비교"""
    if daily_stock.empty:
        print("❌ 비교할 재고 데이터가 없습니다")
        return
    
    # 최신 재고 추출
    latest = (daily_stock.sort_values("Date")
                        .groupby("Location")
                        .tail(1)
                        .set_index("Location"))
    
    print("\n📊 재고 검증 결과")
    
    for location, row in latest.iterrows():
        actual = int(row["Closing_Stock"])
        
        # 기대값 찾기 (대소문자 무시)
        expected_value = None
        for exp_key, exp_val in expected.items():
            if str(exp_key).lower().strip() == str(location).lower().strip():
                expected_value = exp_val
                break
        
        if expected_value is None:
            print(f"ℹ️ {location:<15} {actual:>4} EA (기대값 없음)")
        else:
            diff = actual - expected_value
            mark = "✅" if abs(diff) <= tolerance else "❌"
            print(f"{mark} {location:<15} {actual:>4} EA | Δ {diff:+}")

def debug_transaction_flow(transaction_df, case_sample=5):
    """트랜잭션 플로우 디버깅"""
    if transaction_df.empty:
        return
    
    print(f"\n🔍 트랜잭션 플로우 디버깅 (샘플 {case_sample}개)")
    
    # 트랜잭션 타입 분포
    type_counts = transaction_df['TxType_Refined'].value_counts()
    print("\n📊 트랜잭션 타입 분포:")
    for tx_type, count in type_counts.items():
        percentage = (count / len(transaction_df)) * 100
        print(f"   {tx_type}: {count:,}건 ({percentage:.1f}%)")
    
    # 창고별 분포
    location_counts = transaction_df['Location'].value_counts()
    print(f"\n🏭 창고별 분포:")
    for location, count in location_counts.head(10).items():
        print(f"   {location}: {count:,}건")
    
    # 케이스별 샘플
    sample_cases = transaction_df['Case_No'].unique()[:case_sample]
    print(f"\n📦 케이스별 샘플 ({len(sample_cases)}개):")
    
    for case_no in sample_cases:
        case_data = transaction_df[transaction_df['Case_No'] == case_no].sort_values('Date')
        print(f"\n   📋 {case_no}:")
        for _, row in case_data.iterrows():
            date_str = row['Date'].strftime('%Y-%m-%d') if hasattr(row['Date'], 'strftime') else str(row['Date'])
            print(f"      {date_str} | {row['TxType_Refined']:<12} | {row['Location']:<15} | {row['Qty']:>3} EA")

def validate_final_results(daily_stock, expected_results):
    """최종 결과 검증"""
    print("\n🔍 최종 결과 검증")
    
    if daily_stock.empty:
        print("❌ 검증할 재고 데이터가 없습니다")
        return False
    
    # 최신 재고
    latest_stock = (daily_stock.sort_values("Date")
                              .groupby("Location")
                              .tail(1))
    
    print(f"📊 계산된 최종 재고:")
    total_calculated = 0
    
    for _, row in latest_stock.iterrows():
        stock_value = int(row["Closing_Stock"])
        total_calculated += stock_value
        print(f"   {row['Location']:<15}: {stock_value:>4} EA")
    
    print(f"   {'총계':<15}: {total_calculated:>4} EA")
    
    # 기대 결과와 비교
    expected_total = sum(expected_results.values())
    print(f"\n📋 기대 결과:")
    print(f"   DSV Al Markaz: 813 EA")
    print(f"   DSV Indoor   : 413 EA")
    print(f"   DSV Outdoor  : 1300 EA (기대값 없음)")
    
    # 주요 창고 검증
    markaz_actual = latest_stock[latest_stock['Location'] == 'DSV Al Markaz']['Closing_Stock'].iloc[0] if len(latest_stock[latest_stock['Location'] == 'DSV Al Markaz']) > 0 else 0
    indoor_actual = latest_stock[latest_stock['Location'] == 'DSV Indoor']['Closing_Stock'].iloc[0] if len(latest_stock[latest_stock['Location'] == 'DSV Indoor']) > 0 else 0
    
    markaz_expected = 813
    indoor_expected = 413
    
    markaz_diff = abs(markaz_actual - markaz_expected)
    indoor_diff = abs(indoor_actual - indoor_expected)
    
    success = markaz_diff <= 2 and indoor_diff <= 2
    
    print(f"\n✅ 검증 결과:")
    print(f"   DSV Al Markaz: {'PASS' if markaz_diff <= 2 else 'FAIL'} (오차: {markaz_diff})")
    print(f"   DSV Indoor:    {'PASS' if indoor_diff <= 2 else 'FAIL'} (오차: {indoor_diff})")
    print(f"   전체:          {'PASS' if success else 'FAIL'}")
    
    return success

def print_system_info():
    """시스템 정보 출력"""
    print("🚀 HVDC 재고 관리 시스템 v2.4")
    print("=" * 60)
    print("📁 처리 대상 파일:")
    print("   - HVDC WAREHOUSE_HITACHI(HE).xlsx")
    print("   - HVDC WAREHOUSE_HITACHI(HE-0214,0252).xlsx")
    print("   - HVDC WAREHOUSE_HITACHI(HE_LOCAL).xlsx")
    print("   - HVDC WAREHOUSE_SIMENSE(SIM).xlsx")
    print("\n🎯 기대 결과:")
    print("   - DSV Al Markaz: 813 EA (오차 ±1)")
    print("   - DSV Indoor:    413 EA (오차 ±1)")
    print("   - DSV Outdoor:   1300 EA (기대값 없음)")
    print("=" * 60)

def run_diagnostic_check():
    """진단 체크 실행"""
    print("\n🔧 시스템 진단 체크")
    
    import os
    from pathlib import Path
    
    # 1. 파일 존재 확인
    required_files = [
        "data/HVDC WAREHOUSE_HITACHI(HE).xlsx",
        "data/HVDC WAREHOUSE_SIMENSE(SIM).xlsx",
        "expected_stock.yml",
        "config.py"
    ]
    
    print("📁 필수 파일 확인:")
    all_files_exist = True
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} (없음)")
            all_files_exist = False
    
    # 2. 모듈 임포트 확인
    print("\n📦 모듈 임포트 확인:")
    modules_to_test = [
        "core.loader",
        "core.deduplication", 
        "core.inventory_engine",
        "config"
    ]
    
    all_modules_ok = True
    
    for module_name in modules_to_test:
        try:
            __import__(module_name)
            print(f"   ✅ {module_name}")
        except ImportError as e:
            print(f"   ❌ {module_name}: {e}")
            all_modules_ok = False
    
    # 3. 전체 상태
    system_ready = all_files_exist and all_modules_ok
    
    print(f"\n🚦 시스템 상태: {'준비 완료' if system_ready else '문제 있음'}")
    
    return system_ready 