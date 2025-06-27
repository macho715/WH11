# main.py - 최종 수정된 버전

import argparse
import pandas as pd
import pathlib as pl

# 핵심 모듈 임포트
from config import load_expected_stock
from core.deduplication import drop_duplicate_transfers, reconcile_orphan_transfers, validate_transfer_pairs_fixed, validate_date_sequence_fixed
from core.loader import DataLoader

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", help="스냅샷 기준일 (YYYY-MM-DD)")
    ap.add_argument("--src",  default="data", help="Excel 폴더 경로")
    ap.add_argument("--debug", action="store_true", help="디버그 모드")
    args = ap.parse_args()

    # 시스템 정보 출력
    print_system_info()
    
    # 진단 체크
    if not run_diagnostic_check():
        print("❌ 시스템 진단 실패 - 필수 파일이나 모듈을 확인하세요")
        return False

    try:
        print("\n🚀 메인 처리 시작")
        
        # ① 데이터 로딩
        loader = DataLoader()
        print("📄 데이터 파일 로딩 중...")
        
        excel_files = loader.load_excel_files(args.src)
        if not excel_files:
            print("❌ 로딩할 Excel 파일이 없습니다!")
            return False
            
        raw_transactions = loader.extract_transactions(excel_files)
        print(f"📊 총 {len(raw_transactions):,}건의 원시 트랜잭션 수집")

        # ② 트랜잭션 DataFrame 변환
        transaction_df = transactions_to_dataframe(raw_transactions)
        
        if args.debug:
            debug_transaction_flow(transaction_df)
        
        # 필수 컬럼 확인 및 추가
        required_columns = ['Case_No', 'Date', 'Qty', 'TxType_Refined', 'Location', 'Loc_From', 'Target_Warehouse']
        for col in required_columns:
            if col not in transaction_df.columns:
                if col == 'Loc_From':
                    transaction_df[col] = 'SOURCE'
                elif col == 'Target_Warehouse':
                    transaction_df[col] = transaction_df.get('Location', 'UNKNOWN')
                else:
                    transaction_df[col] = 'UNKNOWN'

        print(f"🔄 트랜잭션 로그 생성 완료: {len(transaction_df)}건")
        
        # ③ TRANSFER 보정 (한 번만 실행)
        print("🛠️ TRANSFER 짝 보정 중...")
        transaction_df = reconcile_orphan_transfers(transaction_df)
        
        # ④ 중복 제거
        before_dedup = len(transaction_df)
        transaction_df = drop_duplicate_transfers(transaction_df)
        after_dedup = len(transaction_df)
        print(f"🗑️ 중복 제거: {before_dedup} → {after_dedup}건")
        
        # ⑤ 검증
        validate_transfer_pairs_fixed(transaction_df)
        validate_date_sequence_fixed(transaction_df)
        print("✅ TRANSFER 짝 모두 일치")
        
        # ⑥ 일별 재고 계산
        daily_stock = calculate_daily_inventory(transaction_df)
        
        # ⑦ 기대값과 비교 (기대값 제거)
        expected = load_expected_stock(args.asof)
        compare_stock_vs_expected(daily_stock, expected)
        
        # ⑧ 최종 결과 출력 및 엑셀 생성
        print_final_inventory_summary(daily_stock)
        
        return True
        
    except Exception as e:
        print(f"❌ 실행 실패: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return False

def transactions_to_dataframe(transactions):
    """트랜잭션 리스트를 DataFrame으로 변환 - 개선된 버전"""
    data = []
    
    print("🔄 트랜잭션 변환 중...")
    
    for tx in transactions:
        tx_data = tx.get('data', {})
        
        # 기본 정보 추출
        case_id = extract_case_id(tx_data)
        warehouse = extract_warehouse(tx_data)
        date_val = extract_datetime(tx_data)
        
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
            'Target_Warehouse': warehouse
        }
        
        # IN 트랜잭션 생성
        if incoming > 0:
            record = base_record.copy()
            record.update({
                'TxType_Refined': 'IN',
                'Qty': int(incoming)
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
                'Loc_From': warehouse,  # 출고는 해당 창고에서
                'Target_Warehouse': 'DESTINATION'
            })
            data.append(record)
    
    result_df = pd.DataFrame(data)
    print(f"✅ {len(result_df)}건 트랜잭션 생성")
    
    return result_df

def extract_case_id(data):
    """케이스 ID 추출 - 개선된 버전"""
    case_fields = ['case', 'Case', 'case_id', 'CaseID', 'ID', 'carton', 'box', 'mr#']
    
    for field in case_fields:
        if field in data and data[field]:
            case_value = str(data[field]).strip()
            if case_value and case_value.lower() not in ['nan', 'none', '']:
                return case_value
    
    # 백업: 해시 기반 ID
    return f"CASE_{abs(hash(str(data))) % 100000}"

def extract_warehouse(data):
    """창고명 추출 및 정규화 - 개선된 버전"""
    warehouse_fields = ['warehouse', 'Warehouse', 'site', 'Site', 'location', 'Location']
    
    for field in warehouse_fields:
        if field in data and data[field]:
            raw_warehouse = str(data[field]).strip()
            if raw_warehouse and raw_warehouse.lower() not in ['nan', 'none', '']:
                return normalize_warehouse_name(raw_warehouse)
    
    return 'UNKNOWN'

def extract_datetime(data):
    """날짜/시간 추출 - 개선된 버전"""
    import pandas as pd
    from datetime import datetime
    
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
    
    # 기본값: 현재 시간
    return pd.Timestamp.now()

def extract_quantity(data):
    """수량 추출 - 개선된 버전"""
    qty_fields = ['incoming', 'outgoing', 'inventory', 'quantity', 'qty', 'pieces']
    total_qty = 0
    
    for field in qty_fields:
        if field in data and data[field]:
            try:
                qty = pd.to_numeric(data[field], errors='coerce')
                if not pd.isna(qty) and qty > 0:
                    total_qty += qty
            except:
                continue
                
    return max(int(total_qty), 1)  # 최소 1개

def normalize_warehouse_name(raw_name):
    """창고명 표준화 - 개선된 버전"""
    if pd.isna(raw_name) or not raw_name:
        return 'UNKNOWN'
        
    name_lower = str(raw_name).lower().strip()
    
    # 정확한 매핑 테이블
    warehouse_rules = {
        'DSV Al Markaz': ['markaz', 'm1', 'al markaz', 'almarkaz', 'al_markaz', 'dsv al markaz'],
        'DSV Indoor': ['indoor', 'm44', 'hauler indoor', 'hauler_indoor', 'dsv indoor'],
        'DSV Outdoor': ['outdoor', 'out', 'dsv outdoor'],
        'MOSB': ['mosb'],
        'DSV MZP': ['mzp', 'dsv mzp'],
        'DHL WH': ['dhl', 'dhl wh'],
        'AAA Storage': ['aaa', 'aaa storage']
    }
    
    for canonical, patterns in warehouse_rules.items():
        if any(pattern in name_lower for pattern in patterns):
            return canonical
    
    return str(raw_name).strip()

def extract_site(warehouse_name):
    """사이트명 추출 - 개선된 버전"""
    if pd.isna(warehouse_name) or not warehouse_name:
        return 'UNK'
        
    name_upper = str(warehouse_name).upper()
    
    site_patterns = {
        'AGI': ['AGI'],
        'DAS': ['DAS'], 
        'MIR': ['MIR'],
        'SHU': ['SHU']
    }
    
    for site, patterns in site_patterns.items():
        if any(pattern in name_upper for pattern in patterns):
            return site
    
    return 'UNK'

def calculate_daily_inventory(transaction_df):
    """일별 재고 계산 - 사용자 검증된 로직"""
    print("📊 일별 재고 계산 중...")
    
    if transaction_df.empty:
        print("❌ 계산할 트랜잭션이 없습니다")
        return pd.DataFrame()
    
    # 날짜별, 위치별 집계
    transaction_df['Date'] = pd.to_datetime(transaction_df['Date']).dt.date
    
    daily_summary = transaction_df.groupby(['Location', 'Date', 'TxType_Refined']).agg({
        'Qty': 'sum'
    }).reset_index()
    
    # 피벗으로 입고/출고 분리
    daily_pivot = daily_summary.pivot_table(
        index=['Location', 'Date'],
        columns='TxType_Refined', 
        values='Qty',
        fill_value=0
    ).reset_index()
    
    # 컬럼명 정리
    daily_pivot.columns.name = None
    expected_cols = ['IN', 'TRANSFER_OUT', 'FINAL_OUT']
    for col in expected_cols:
        if col not in daily_pivot.columns:
            daily_pivot[col] = 0
    
    # 재고 계산 (위치별 누적)
    stock_records = []
    
    for location in daily_pivot['Location'].unique():
        if location in ['UNKNOWN', 'UNK', '']:
            continue
            
        loc_data = daily_pivot[daily_pivot['Location'] == location].copy()
        loc_data = loc_data.sort_values('Date')
        
        opening_stock = 0
        
        for _, row in loc_data.iterrows():
            inbound = row.get('IN', 0)
            transfer_out = row.get('TRANSFER_OUT', 0) 
            final_out = row.get('FINAL_OUT', 0)
            total_outbound = transfer_out + final_out
            
            closing_stock = opening_stock + inbound - total_outbound
            
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
            
            opening_stock = closing_stock
    
    daily_stock_df = pd.DataFrame(stock_records)
    print(f"✅ {len(daily_stock_df)}개 일별 재고 스냅샷 생성")
    
    return daily_stock_df

def compare_stock_vs_expected(daily_stock, expected, tol=2):
    """재고와 기대값 비교 - 기대값 없어도 정상 동작"""
    if daily_stock.empty:
        print("❌ 계산된 재고 데이터가 없습니다!")
        return
        
    latest = (daily_stock.sort_values("Date")
                        .groupby("Location")
                        .tail(1)
                        .set_index("Location"))
    
    print("\n📊 재고 검증 결과")
    
    has_expected = any(expected.values()) if expected else False
    
    if not has_expected:
        print("ℹ️ 설정된 기대값이 없습니다. 계산된 재고만 표시합니다.")
        print("-" * 50)
        
        for location, row in latest.iterrows():
            actual = int(row["Closing_Stock"])
            print(f"📦 {location:<20}: {actual:>6} EA")
        return
    
    # 기대값이 있는 경우
    for wh, row in latest.iterrows():
        actual = int(row["Closing_Stock"])
        
        # 대소문자 무시하고 기대값 찾기
        exp = None
        for exp_key, exp_val in expected.items():
            if str(exp_key).lower().strip() == str(wh).lower().strip():
                exp = exp_val
                break
        
        if exp is None:
            print(f"ℹ️ {wh:<15} {actual:>4} EA (기대값 없음)")
        else:
            diff = actual - exp
            mark = "✅" if abs(diff) <= tol else "❌"
            print(f"{mark} {wh:<15} {actual:>4} EA | Δ {diff:+}")

# 헬퍼 함수들 임포트
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
    
    # 필수 파일 확인
    required_files = [
        "data/HVDC WAREHOUSE_HITACHI(HE).xlsx",
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
    
    return all_files_exist

def debug_transaction_flow(transaction_df, case_sample=3):
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
    for location, count in location_counts.head(5).items():
        print(f"   {location}: {count:,}건")

def validate_final_results(daily_stock, expected_results):
    """최종 결과 검증"""
    if daily_stock.empty:
        return False
    
    # 최신 재고
    latest_stock = (daily_stock.sort_values("Date")
                              .groupby("Location")
                              .tail(1))
    
    # 주요 창고 검증
    markaz_actual = 0
    indoor_actual = 0
    
    for _, row in latest_stock.iterrows():
        if 'markaz' in row['Location'].lower():
            markaz_actual = int(row['Closing_Stock'])
        elif 'indoor' in row['Location'].lower():
            indoor_actual = int(row['Closing_Stock'])
    
    markaz_expected = 813
    indoor_expected = 413
    
    markaz_diff = abs(markaz_actual - markaz_expected)
    indoor_diff = abs(indoor_actual - indoor_expected)
    
    success = markaz_diff <= 2 and indoor_diff <= 2
    
    return success

def print_final_inventory_summary(daily_stock):
    """최종 재고 요약 출력"""
    if daily_stock.empty:
        print("❌ 계산된 재고 데이터가 없습니다!")
        return
    
    latest = (daily_stock.sort_values("Date")
                        .groupby("Location")
                        .tail(1)
                        .sort_values("Closing_Stock", ascending=False))
    
    print("\n🎉 최종 재고 요약")
    print("=" * 50)
    
    total_stock = 0
    for _, row in latest.iterrows():
        location = row['Location']
        stock = int(row['Closing_Stock'])
        total_stock += stock
        print(f"📦 {location:<20}: {stock:>6} EA")
    
    print("-" * 50)
    print(f"📊 총 재고: {total_stock:,} EA")
    print("✅ 재고 계산 완료!")

if __name__ == "__main__":
    success = main()
    if not success:
        exit(1) 