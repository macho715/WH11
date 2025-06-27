#!/usr/bin/env python3
"""
Handling Fee 집계 문제 진단 스크립트
"""

import pandas as pd
from datetime import datetime
import sys

# 핵심 모듈 임포트
try:
    from config import load_expected_stock
except Exception as e:
    print(f"⚠️ 설정 로드 실패: {e}")
    def load_expected_stock(as_of=None):
        return {}
        
from core.deduplication import drop_duplicate_transfers, reconcile_orphan_transfers
from core.loader import DataLoader
from excel_reporter import (
    generate_monthly_in_out_stock_report,
    normalize_location_column
)
from mapping_utils import mapping_manager, add_storage_type_to_dataframe

def transactions_to_dataframe(transactions):
    """트랜잭션 리스트를 DataFrame으로 변환"""
    data = []
    
    for tx in transactions:
        tx_data = tx.get('data', {})
        
        # 기본 정보 추출
        case_id = extract_case_id(tx_data)
        warehouse = extract_warehouse(tx_data)
        date_val = extract_datetime(tx_data)
        
        # 수량 처리
        incoming = tx_data.get('incoming', 0) or 0
        outgoing = tx_data.get('outgoing', 0) or 0
        
        # Handling Fee 추출 (여러 가능한 필드명 확인)
        handling_fee = 0
        fee_fields = ['handling_fee', 'Handling Fee', 'handling_fee_amount', 'fee', 'Fee']
        for field in fee_fields:
            if field in tx_data and tx_data[field] is not None:
                try:
                    handling_fee = float(tx_data[field])
                    break
                except (ValueError, TypeError):
                    continue
        
        # 기본 레코드 템플릿
        base_record = {
            'Case_No': case_id,
            'Date': date_val,
            'Location': warehouse,
            'Source_File': tx.get('source_file', ''),
            'Loc_From': 'SOURCE',
            'Target_Warehouse': warehouse,
            'Amount': tx_data.get('amount', 0),
            'Handling Fee': handling_fee,  # Handling Fee 추가
            'Storage_Type': tx_data.get('storage_type', 'Unknown'),
            'storage_type': tx_data.get('storage_type', 'Unknown')
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
        df = normalize_location_column(df)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['Date'] = df['Date'].fillna(pd.Timestamp.now())
        df['Billing month'] = df['Date'].dt.strftime('%Y-%m')
        df['Category'] = 'General'
        
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
    """창고명 정규화"""
    if pd.isna(raw_name) or not raw_name:
        return 'UNKNOWN'
    
    all_locations = []
    for locations in mapping_manager.warehouse_classification.values():
        all_locations.extend(locations)
    
    name_lower = str(raw_name).lower().strip()
    
    for location in all_locations:
        if location.lower() in name_lower or name_lower in location.lower():
            return location
    
    return str(raw_name).strip()

def extract_site(warehouse_name):
    """사이트명 추출"""
    if pd.isna(warehouse_name):
        return 'UNK'
    
    if mapping_manager.classify_storage_type(warehouse_name) == 'Site':
        return warehouse_name
    
    return 'UNK'

def main():
    """Handling Fee 진단 메인 함수"""
    print("🔍 Handling Fee 집계 문제 진단 시작")
    print("=" * 50)
    
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

        # 2. 원시 데이터에서 Handling Fee 필드 확인
        print("\n🔍 원시 데이터 Handling Fee 필드 확인:")
        handling_fee_found = False
        for i, tx in enumerate(raw_transactions[:10]):  # 처음 10개만 확인
            tx_data = tx.get('data', {})
            fee_fields = ['handling_fee', 'Handling Fee', 'handling_fee_amount', 'fee', 'Fee']
            found_fields = [field for field in fee_fields if field in tx_data]
            if found_fields:
                print(f"  트랜잭션 {i}: {found_fields} = {[tx_data[field] for field in found_fields]}")
                handling_fee_found = True
        
        if not handling_fee_found:
            print("  ❌ 원시 데이터에 Handling Fee 관련 필드가 없습니다!")
            print("  📋 사용 가능한 필드들:")
            if raw_transactions:
                sample_data = raw_transactions[0].get('data', {})
                for key, value in sample_data.items():
                    print(f"    - {key}: {value}")

        # 3. DataFrame 변환
        print("\n🔄 DataFrame 변환 중...")
        transaction_df = transactions_to_dataframe(raw_transactions)
        print(f"✅ {len(transaction_df)}건 트랜잭션 생성")
        
        # 4. Handling Fee 컬럼 상태 확인
        print("\n📊 DataFrame Handling Fee 컬럼 상태:")
        if 'Handling Fee' in transaction_df.columns:
            handling_fee_stats = {
                '총합': transaction_df['Handling Fee'].sum(),
                '평균': transaction_df['Handling Fee'].mean(),
                '최대값': transaction_df['Handling Fee'].max(),
                '최소값': transaction_df['Handling Fee'].min(),
                '0이 아닌 값 개수': (transaction_df['Handling Fee'] != 0).sum(),
                'NaN 개수': transaction_df['Handling Fee'].isna().sum()
            }
            print("  Handling Fee 통계:")
            for key, value in handling_fee_stats.items():
                print(f"    {key}: {value}")
            
            # 0이 아닌 값들 확인
            non_zero_handling = transaction_df[transaction_df['Handling Fee'] != 0]
            if not non_zero_handling.empty:
                print(f"  📋 0이 아닌 Handling Fee 값들 (처음 5개):")
                for _, row in non_zero_handling.head().iterrows():
                    print(f"    {row['Case_No']}: {row['Handling Fee']} ({row['Location']})")
            else:
                print("  ⚠️ 모든 Handling Fee 값이 0입니다!")
        else:
            print("  ❌ DataFrame에 'Handling Fee' 컬럼이 없습니다!")
            print(f"  📋 사용 가능한 컬럼들: {list(transaction_df.columns)}")

        # 5. 테스트용 Handling Fee 데이터 추가
        print("\n🧪 테스트용 Handling Fee 데이터 추가...")
        import random
        transaction_df['Handling Fee'] = [random.uniform(100, 1000) for _ in range(len(transaction_df))]
        
        # 6. Handling Fee 집계 테스트
        print("\n📊 Handling Fee 집계 테스트:")
        
        # 월별 집계
        transaction_df['월'] = pd.to_datetime(transaction_df['Date'], errors='coerce').dt.strftime('%Y-%m')
        handling_by_month = transaction_df.groupby('월')['Handling Fee'].sum().reset_index()
        print(f"  월별 집계: {len(handling_by_month)}개월")
        print(f"  총 Handling Fee: {handling_by_month['Handling Fee'].sum():,.2f}")
        
        # 창고별 집계
        handling_by_location = transaction_df.groupby('Location')['Handling Fee'].sum().reset_index()
        print(f"  창고별 집계: {len(handling_by_location)}개 창고/현장")
        print(f"  최고 창고: {handling_by_location.loc[handling_by_location['Handling Fee'].idxmax(), 'Location']} ({handling_by_location['Handling Fee'].max():,.2f})")
        
        # 7. 리포트 생성 테스트
        print("\n📄 Handling Fee 포함 리포트 생성 테스트...")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        test_report_path = f"HVDC_HandlingFee_테스트_{timestamp}.xlsx"
        
        with pd.ExcelWriter(test_report_path, engine='xlsxwriter') as writer:
            # 월별 Handling Fee
            handling_by_month.to_excel(writer, sheet_name='월별HandlingFee', index=False)
            
            # 창고별 Handling Fee
            handling_by_location = handling_by_location.sort_values('Handling Fee', ascending=False)
            handling_by_location.to_excel(writer, sheet_name='창고별HandlingFee', index=False)
            
            # Handling Fee 통계
            handling_stats = {
                '지표': ['총 Handling Fee', '평균 Handling Fee', '최대 Handling Fee', '최소 Handling Fee', '표준편차'],
                '값': [
                    transaction_df['Handling Fee'].sum(),
                    transaction_df['Handling Fee'].mean(),
                    transaction_df['Handling Fee'].max(),
                    transaction_df['Handling Fee'].min(),
                    transaction_df['Handling Fee'].std()
                ]
            }
            handling_stats_df = pd.DataFrame(handling_stats)
            handling_stats_df.to_excel(writer, sheet_name='HandlingFee통계', index=False)
        
        print(f"✅ 테스트 리포트 생성 완료: {test_report_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ 진단 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 Handling Fee 진단 완료!")
        sys.exit(0)
    else:
        print("\n❌ 진단 실패!")
        sys.exit(1) 