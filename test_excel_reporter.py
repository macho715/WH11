#!/usr/bin/env python3
"""
HVDC Excel Reporter 테스트 스크립트

이 스크립트는 Excel 리포트 생성 기능을 테스트합니다.
통합 매핑 시스템을 사용하여 storage_type 기반 창고/현장 분리를 구현합니다.
"""

import pandas as pd
from datetime import datetime
import sys
import os

# 핵심 모듈 임포트
try:
    from config import load_expected_stock
except Exception as e:
    print(f"⚠️ 설정 로드 실패: {e}")
    # 빈 함수로 대체
    def load_expected_stock(as_of=None):
        return {}
        
from core.deduplication import drop_duplicate_transfers, reconcile_orphan_transfers
from core.loader import DataLoader
from excel_reporter import (
    generate_monthly_in_out_stock_report,
    generate_monthly_in_report,
    generate_monthly_trend_and_cumulative,
    validate_transaction_data,
    create_test_out_transaction,
    print_transaction_analysis,
    normalize_location_column,
    visualize_out_transactions,
    generate_excel_comprehensive_report
)
from mapping_utils import mapping_manager, add_storage_type_to_dataframe

def main():
    """Excel Reporter 테스트 메인 함수"""
    print("🚀 HVDC Excel Reporter 테스트 시작 (통합 매핑 시스템)")
    print("=" * 70)
    
    try:
        # 1. 데이터 로딩
        print("📄 데이터 로딩 중...")
        loader = DataLoader()
        excel_files = loader.load_excel_files("data")
        
        if not excel_files:
            print("❌ Excel 파일이 없습니다!")
            return False
            
        raw_transactions = loader.extract_transactions(excel_files)
        print(f"📊 총 {len(raw_transactions):,}건의 원시 트랜잭션 수집")

        # 2. 트랜잭션 DataFrame 변환
        print("🔄 트랜잭션 변환 중...")
        transaction_df = transactions_to_dataframe(raw_transactions)
        print(f"✅ {len(transaction_df)}건 트랜잭션 생성")
        
        # ✅ 통합 매핑으로 Storage Type 재검증 및 강제 적용
        print("\n🔄 통합 매핑 검증 및 적용:")
        transaction_df = add_storage_type_to_dataframe(transaction_df, "Location")
        
        # 매핑 검증 결과 출력
        validation_result = mapping_manager.validate_mapping(transaction_df)
        for storage_type, info in validation_result.items():
            print(f"   {storage_type}: {info['count']}건 - {info['locations']}")

        # ✅ 트랜잭션 데이터 상세 분석 추가
        print_transaction_analysis(transaction_df)
        
        # ✅ 데이터 진단 및 권장사항
        diagnosis = validate_transaction_data(transaction_df)
        print("\n📋 **데이터 진단 결과**:")
        print(diagnosis['recommendation'])

        # 3. 전처리
        print("🛠️ 데이터 전처리 중...")
        transaction_df = reconcile_orphan_transfers(transaction_df)
        transaction_df = drop_duplicate_transfers(transaction_df)
        print("✅ 데이터 검증 완료")
        
        # 4. 일별 재고 계산
        print("📊 일별 재고 계산 중...")
        daily_stock = calculate_daily_inventory(transaction_df)
        print(f"✅ {len(daily_stock)}개 일별 재고 스냅샷 생성")
        
        # --- [핵심 방어 코드: '월', 'Handling Fee' 컬럼 보장] ---
        if '월' not in transaction_df.columns:
            transaction_df['월'] = pd.to_datetime(transaction_df['Date'], errors='coerce').dt.strftime('%Y-%m')
        if 'Handling Fee' not in transaction_df.columns:
            transaction_df['Handling Fee'] = 0
        # ------------------------------------------------------

        # 모든 리포트 함수는 DataFrame만 반환
        in_df, out_df, stock_df = generate_monthly_in_out_stock_report(transaction_df)
        monthly_in_df = generate_monthly_in_report(transaction_df)
        trend_df, cumulative_df = generate_monthly_trend_and_cumulative(transaction_df)
        
        # ✅ OUT 트랜잭션 테스트 추가
        print("\n🧪 OUT 트랜잭션 테스트 시작...")
        
        # 1. OUT 트랜잭션 강제 생성
        out_row = {
            'Case_No': 'CASE_OUT_001',
            'Date': pd.Timestamp('2025-07-15'),
            'Location': 'DSV Indoor',          # 실제 존재하는 창고명 사용
            'TxType_Refined': 'TRANSFER_OUT',  # 또는 'FINAL_OUT' (Site 출고시)
            'Qty': 40,                         # 임의 수량
            'Source_File': '테스트',
            'Loc_From': 'DSV Indoor',
            'Target_Warehouse': 'AGI',
            'Storage_Type': 'Indoor',
            'storage_type': 'Indoor'
        }
        
        # 2. DataFrame에 추가
        transaction_df_with_out = pd.concat(
            [transaction_df, pd.DataFrame([out_row])],
            ignore_index=True
        )
        print(f"✅ OUT 트랜잭션 추가: {out_row['Location']}에서 {out_row['Qty']}개 출고")
        
        # 3. OUT 포함 집계 함수 재호출
        in_df_with_out, out_df_with_out, stock_df_with_out = generate_monthly_in_out_stock_report(transaction_df_with_out)
        
        # 4. 결과 검증
        print("\n📊 OUT 트랜잭션 집계 결과 검증:")
        print("OUT 시트 (마지막 3행):")
        print(out_df_with_out.tail(3))
        
        print("\n재고 시트 (마지막 3행):")
        print(stock_df_with_out.tail(3))
        
        # 5. 엑셀로 저장 (테스트)
        with pd.ExcelWriter("HVDC_최종통합리포트_OUT테스트.xlsx", engine='xlsxwriter') as writer:
            in_df_with_out.to_excel(writer, sheet_name='01_월별IN_창고현장', index=False)
            out_df_with_out.to_excel(writer, sheet_name='02_월별OUT_창고현장', index=False)
            stock_df_with_out.to_excel(writer, sheet_name='03_월별재고_창고현장', index=False)
        print("✅ OUT 트랜잭션 집계 테스트 리포트 생성 완료: HVDC_최종통합리포트_OUT테스트.xlsx")
        
        # 6. 기존 리포트도 함께 저장
        with pd.ExcelWriter("HVDC_최종통합리포트.xlsx", engine='xlsxwriter') as writer:
            in_df.to_excel(writer, sheet_name='01_월별IN_창고현장', index=False)
            out_df.to_excel(writer, sheet_name='02_월별OUT_창고현장', index=False)
            stock_df.to_excel(writer, sheet_name='03_월별재고_창고현장', index=False)
            monthly_in_df.to_excel(writer, sheet_name='04_월별IN_집계', index=False)
            trend_df.to_excel(writer, sheet_name='05_월별INOUT_트렌드', index=False)
            cumulative_df.to_excel(writer, sheet_name='06_월별누적재고', index=False)
        print("✅ 한 파일에 모든 리포트 시트 저장 완료!")
        
        # 예시: OUT 트랜잭션 시각화
        visualize_out_transactions(transaction_df)
        
        # 🧪 Handling Fee 집계 테스트
        print("\n🧪 Handling Fee 집계 테스트 시작...")
        
        # Handling Fee 컬럼이 있는지 확인
        if 'Handling Fee' in transaction_df.columns:
            handling_fee_sum = transaction_df['Handling Fee'].sum()
            if handling_fee_sum > 0:
                print(f"✅ Handling Fee 컬럼 발견: {len(transaction_df[transaction_df['Handling Fee'].notna()])}건의 데이터")
                
                # Handling Fee 통계 출력
                handling_stats = {
                    '총합': transaction_df['Handling Fee'].sum(),
                    '평균': transaction_df['Handling Fee'].mean(),
                    '최대값': transaction_df['Handling Fee'].max(),
                    '최소값': transaction_df['Handling Fee'].min(),
                    '표준편차': transaction_df['Handling Fee'].std()
                }
                print("📊 Handling Fee 통계:")
                for key, value in handling_stats.items():
                    print(f"   {key}: {value:,.2f}")
                
                # 월별 Handling Fee 집계 확인
                handling_by_month = transaction_df.groupby('월')['Handling Fee'].sum().reset_index()
                print(f"📅 월별 Handling Fee 집계: {len(handling_by_month)}개월")
                print(f"   최고 월: {handling_by_month.loc[handling_by_month['Handling Fee'].idxmax(), '월']} ({handling_by_month['Handling Fee'].max():,.2f})")
                print(f"   최저 월: {handling_by_month.loc[handling_by_month['Handling Fee'].idxmin(), '월']} ({handling_by_month['Handling Fee'].min():,.2f})")
                
                # 창고별 Handling Fee 집계 확인
                location_handling = transaction_df.groupby('Location')['Handling Fee'].sum().sort_values(ascending=False)
                print(f"🏢 창고별 Handling Fee 집계: {len(location_handling)}개 창고/현장")
                print(f"   최고 창고: {location_handling.index[0]} ({location_handling.iloc[0]:,.2f})")
                print(f"   최저 창고: {location_handling.index[-1]} ({location_handling.iloc[-1]:,.2f})")
            else:
                print("⚠️ Handling Fee 컬럼은 있지만 모든 값이 0입니다!")
                print("   → 원본 Excel 파일에 Handling Fee 데이터가 없습니다.")
                print("   → 테스트용 데이터를 추가하여 기능을 검증합니다.")
                
                # 테스트용 Handling Fee 데이터 추가
                import random
                transaction_df['Handling Fee'] = [random.uniform(100, 1000) for _ in range(len(transaction_df))]
                print(f"✅ 테스트용 Handling Fee 데이터 추가: {len(transaction_df)}건")
                
                # Handling Fee 통계 출력
                handling_stats = {
                    '총합': transaction_df['Handling Fee'].sum(),
                    '평균': transaction_df['Handling Fee'].mean(),
                    '최대값': transaction_df['Handling Fee'].max(),
                    '최소값': transaction_df['Handling Fee'].min(),
                    '표준편차': transaction_df['Handling Fee'].std()
                }
                print("📊 테스트 Handling Fee 통계:")
                for key, value in handling_stats.items():
                    print(f"   {key}: {value:,.2f}")
        else:
            print("ℹ️ Handling Fee 컬럼이 없습니다. 테스트용 데이터를 추가합니다.")
            
            # 테스트용 Handling Fee 데이터 추가
            import random
            transaction_df['Handling Fee'] = [random.uniform(100, 1000) for _ in range(len(transaction_df))]
            print(f"✅ 테스트용 Handling Fee 데이터 추가: {len(transaction_df)}건")
            
            # Handling Fee 통계 출력
            handling_stats = {
                '총합': transaction_df['Handling Fee'].sum(),
                '평균': transaction_df['Handling Fee'].mean(),
                '최대값': transaction_df['Handling Fee'].max(),
                '최소값': transaction_df['Handling Fee'].min(),
                '표준편차': transaction_df['Handling Fee'].std()
            }
            print("📊 테스트 Handling Fee 통계:")
            for key, value in handling_stats.items():
                print(f"   {key}: {value:,.2f}")
        
        # Handling Fee 포함한 최종 리포트 생성
        print("\n📊 Handling Fee 포함 최종 리포트 생성 중...")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        final_report_path = f"HVDC_최종통합리포트_HandlingFee포함_{timestamp}.xlsx"
        
        # 🆕 NEW: 가이드에 따라 generate_excel_comprehensive_report 함수 호출
        generate_excel_comprehensive_report(transaction_df, daily_stock=None, output_file=final_report_path, debug=True)
        
        print(f"✅ Handling Fee 포함 최종 리포트 생성 완료: {final_report_path}")
        
        return True
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def transactions_to_dataframe(transactions):
    """트랜잭션 리스트를 DataFrame으로 변환 (통합 매핑 적용)"""
    data = []
    
    for tx in transactions:
        tx_data = tx.get('data', {})
        
        # 기본 정보 추출
        case_id = extract_case_id(tx_data)
        warehouse = extract_warehouse(tx_data)
        date_val = extract_datetime(tx_data)
        
        # ✅ 통합 매핑으로 storage_type 분류 (기존 값 무시하고 새로 생성)
        storage_type = tx_data.get('storage_type', 'Unknown')
        
        # 🆕 NEW: Vendor 정보 추출 (가이드 A 적용)
        vendor = extract_vendor_from_data(tx_data, tx.get('source_file', ''))
        
        # 수량 처리
        incoming = tx_data.get('incoming', 0) or 0
        outgoing = tx_data.get('outgoing', 0) or 0
        
        # 기본 레코드 템플릿
        base_record = {
            'Case_No': case_id,
            'Date': date_val,
            'Location': warehouse,
            'Source_File': tx.get('source_file', ''),
            'Loc_From': 'SOURCE',
            'Target_Warehouse': warehouse,
            'Amount': tx_data.get('amount', 0),
            'Storage_Type': storage_type,
            'storage_type': storage_type,
            'Vendor': vendor  # 🆕 NEW: Vendor 컬럼 추가
        }
        
        # IN 트랜잭션 생성
        if incoming > 0:
            record = base_record.copy()
            record.update({
                'TxType_Refined': 'IN',
                'Qty': int(incoming),
                'Incoming': int(incoming),
                'Outgoing': 0
            })
            data.append(record)
            
        # OUT 트랜잭션 생성
        if outgoing > 0:
            record = base_record.copy()
            
            # 사이트 구분하여 FINAL_OUT vs TRANSFER_OUT 결정
            site = extract_site(warehouse)
            tx_type = 'FINAL_OUT' if site in ['AGI', 'DAS', 'MIR', 'SHU'] else 'TRANSFER_OUT'
                
            record.update({
                'TxType_Refined': tx_type,
                'Qty': int(outgoing),
                'Loc_From': warehouse,
                'Target_Warehouse': 'DESTINATION',
                'Incoming': 0,
                'Outgoing': int(outgoing)
            })
            data.append(record)
    
    df = pd.DataFrame(data)
    if not df.empty:
        # ✅ Location 정규화 적용 (가이드 필수 코드)
        df = normalize_location_column(df)
        
        # 🆕 NEW: Vendor 컬럼 강제 정규화 (가이드 A 적용)
        if 'Vendor' in df.columns:
            from mapping_utils import normalize_vendor
            df['Vendor'] = df['Vendor'].apply(normalize_vendor)
        else:
            df['Vendor'] = 'UNKNOWN'
        
        # 🆕 NEW: Vendor 컬럼 자체를 upper()로 정규화 (가이드 B 적용)
        df['Vendor'] = df['Vendor'].astype(str).str.strip().str.upper()
        
        # 날짜가 비어있거나 파싱 불가한 경우 현재 날짜로 대체
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['Date'] = df['Date'].fillna(pd.Timestamp.now())
        df['Billing month'] = df['Date'].dt.strftime('%Y-%m')
        df['Category'] = 'General'
        
        # ✅ 통합 매핑 검증 출력
        print("   창고만:", df[df["Storage_Type"].isin(["Indoor", "Outdoor", "dangerous_cargo"])]["Location"].unique())
        print("   현장만:", df[df["Storage_Type"] == "Site"]["Location"].unique())
        
        # 🆕 NEW: Vendor 검증 출력 (가이드 E 적용)
        vendors_found = sorted(df['Vendor'].dropna().unique().tolist())
        print(f"   발견된 Vendor: {vendors_found}")
        
    return df

def extract_case_id(data):
    """케이스 ID 추출"""
    case_fields = ['case', 'Case', 'case_id', 'CaseID', 'ID', 'carton', 'box', 'mr#']
    
    for field in case_fields:
        if field in data and data[field]:
            case_value = str(data[field]).strip()
            if case_value and case_value.lower() not in ['nan', 'none', '']:
                return case_value
    
    return f"CASE_{abs(hash(str(data))) % 100000}"

def extract_warehouse(data):
    """창고명 추출 및 정규화"""
    warehouse_fields = ['warehouse', 'Warehouse', 'site', 'Site', 'location', 'Location']
    
    for field in warehouse_fields:
        if field in data and data[field]:
            raw_warehouse = str(data[field]).strip()
            if raw_warehouse and raw_warehouse.lower() not in ['nan', 'none', '']:
                return normalize_warehouse_name(raw_warehouse)
    
    return 'UNKNOWN'

def extract_datetime(data):
    """날짜/시간 추출"""
    date_fields = ['date', 'Date', 'timestamp', 'Timestamp', 'datetime']
    
    for field in date_fields:
        if field in data and data[field]:
            try:
                date_value = data[field]
                if isinstance(date_value, str) and date_value.lower() in ['nan', 'none', '']:
                    continue
                return pd.to_datetime(date_value)
            except:
                continue
    
    return pd.Timestamp.now()

def normalize_warehouse_name(raw_name):
    """창고명 정규화 (매핑 규칙 기반)"""
    if pd.isna(raw_name) or not raw_name:
        return 'UNKNOWN'
    
    # ✅ 매핑 규칙의 모든 Location으로 정규화
    all_locations = []
    for locations in mapping_manager.warehouse_classification.values():
        all_locations.extend(locations)
    
    name_lower = str(raw_name).lower().strip()
    
    for location in all_locations:
        if location.lower() in name_lower or name_lower in location.lower():
            return location
    
    return str(raw_name).strip()

def extract_site(warehouse_name):
    """사이트명 추출 (매핑 규칙 기반)"""
    if pd.isna(warehouse_name):
        return 'UNK'
    
    # ✅ Site 타입인지 확인
    if mapping_manager.classify_storage_type(warehouse_name) == 'Site':
        return warehouse_name
    
    return 'UNK'

def extract_vendor_from_data(tx_data, source_file):
    """Vendor 정보 추출 (원본 데이터 기반) - 가이드 B 적용"""
    # HVDC CODE 3에서 벤더 추출
    if 'HVDC CODE 3' in tx_data:
        code3 = str(tx_data['HVDC CODE 3']).strip().upper()
        if code3 in ['HE', 'SIM']:
            return code3
    
    # 파일명에서 벤더 추출
    if 'HITACHI' in source_file.upper():
        return 'HE'
    elif 'SIM' in source_file.upper():
        return 'SIM'
    
    return 'UNKNOWN'

def calculate_daily_inventory(transaction_df):
    """일별 재고 계산"""
    if transaction_df.empty:
        return pd.DataFrame()
    
    # 날짜별로 그룹화하여 재고 계산
    daily_inventory = []
    
    # 창고별로 분리하여 계산
    for warehouse in transaction_df['Location'].unique():
        warehouse_data = transaction_df[transaction_df['Location'] == warehouse].copy()
        warehouse_data = warehouse_data.sort_values('Date')
        
        current_inventory = 0
        
        for _, row in warehouse_data.iterrows():
            # 입고/출고에 따라 재고 업데이트
            if row['TxType_Refined'] == 'IN':
                current_inventory += row['Qty']
            elif row['TxType_Refined'] in ['TRANSFER_OUT', 'FINAL_OUT']:
                current_inventory -= row['Qty']
            
            # 일별 스냅샷 기록
            daily_inventory.append({
                'Date': row['Date'],
                'Location': warehouse,
                'Inventory': current_inventory,
                'Transaction_Type': row['TxType_Refined'],
                'Qty': row['Qty']
            })
    
    return pd.DataFrame(daily_inventory)

if __name__ == "__main__":
    success = main()
    if success:
        print("\n모든 테스트가 성공적으로 완료되었습니다!")
        sys.exit(0)
    else:
        print("\n❌ 테스트가 실패했습니다.")
        sys.exit(1) 