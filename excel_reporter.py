#!/usr/bin/env python3
"""
HVDC Excel Reporter v2.6 - 최신 실전 자동 리포트 예제

월별 IN/OUT/재고 리포트 생성 및 통합 자동화 기능
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from pathlib import Path
import logging

# 🆕 NEW: mapping_utils에서 새로운 함수들 import
from core.mapping_utils import classify_storage_type, normalize_all_keys, normalize_str

logger = logging.getLogger(__name__)

# 최신 mapping_rules 불러오기
try:
    with open('mapping_rules_v2.6.json', encoding='utf-8') as f:
        RULES = json.load(f)
    FIELD_MAP = RULES['field_map']
    PROPERTY_MAPPINGS = RULES['property_mappings']
    # 🆕 NEW: 새로운 설정들 로드
    HVDC_CODE3_VALID = RULES.get('hvdc_code3_valid', ['HE', 'SIM'])
    WAREHOUSE_CODES = RULES.get('warehouse_codes', ['DSV Outdoor', 'DSV Indoor', 'DSV Al Markaz', 'DSV MZP'])
    MONTH_MATCHING = RULES.get('month_matching', 'operation_month_eq_eta_month')
except Exception as e:
    logger.warning(f"mapping_rules_v2.6.json 로드 실패, 기본값 사용: {e}")
    FIELD_MAP = {}
    PROPERTY_MAPPINGS = {}
    HVDC_CODE3_VALID = ['HE', 'SIM']
    WAREHOUSE_CODES = ['DSV Outdoor', 'DSV Indoor', 'DSV Al Markaz', 'DSV MZP']
    MONTH_MATCHING = 'operation_month_eq_eta_month'

def apply_hvdc_filters(df):
    """
    🆕 NEW: HVDC CODE 정규화, 벤더/창고 필터, 월 매칭 로직 적용
    
    Args:
        df: 원본 DataFrame
        
    Returns:
        pd.DataFrame: 필터링된 DataFrame
    """
    print("🔧 HVDC 필터 적용 중...")
    
    # A. HVDC CODE 정규화 적용
    if 'HVDC CODE' in df.columns and 'HVDC CODE 4' in df.columns:
        df['HVDC_CODE_NORMALIZED'] = df['HVDC CODE'].apply(normalize_code_num)
        df['HVDC_CODE4_NORMALIZED'] = df['HVDC CODE 4'].apply(normalize_code_num)
        
        # 코드 매칭 검증
        df['CODE_MATCH'] = df.apply(
            lambda row: codes_match(row['HVDC CODE'], row['HVDC CODE 4']), axis=1
        )
        
        # 매칭되지 않는 행 필터링
        original_count = len(df)
        df = df[df['CODE_MATCH'] == True]
        filtered_count = len(df)
        print(f"  ✅ HVDC CODE 매칭: {original_count} → {filtered_count} (필터링: {original_count - filtered_count}건)")
    
    # B. CODE 3 필터 (HE, SIM만 처리)
    if 'HVDC CODE 3' in df.columns:
        original_count = len(df)
        df = df[df['HVDC CODE 3'].apply(lambda x: is_valid_hvdc_vendor(x, HVDC_CODE3_VALID))]
        filtered_count = len(df)
        print(f"  ✅ 벤더 필터 (HE/SIM): {original_count} → {filtered_count} (필터링: {original_count - filtered_count}건)")
    
    # C. 창고명(임대료) 필터 & SQM 적용
    if 'HVDC CODE' in df.columns:
        warehouse_mask = df['HVDC CODE'].apply(lambda x: is_warehouse_code(x, WAREHOUSE_CODES))
        warehouse_df = df[warehouse_mask].copy()
        
        if 'SQM' in warehouse_df.columns:
            warehouse_df['SQM'] = warehouse_df['SQM'].apply(lambda x: float(x) if pd.notna(x) else 0)
            print(f"  ✅ 창고 임대료 집계: {len(warehouse_df)}건 (SQM 포함)")
    
    # D. Operation Month(월) 매칭
    if 'Operation Month' in df.columns and 'ETA' in df.columns:
        # INVOICE 데이터: invoice_month
        # WAREHOUSE 데이터: warehouse_month (ETA)
        df['INVOICE_MONTH'] = pd.to_datetime(df['Operation Month'], errors='coerce').dt.strftime('%Y-%m')
        df['WAREHOUSE_MONTH'] = pd.to_datetime(df['ETA'], errors='coerce').dt.strftime('%Y-%m')
        
        original_count = len(df)
        df = df[df['INVOICE_MONTH'] == df['WAREHOUSE_MONTH']]
        filtered_count = len(df)
        print(f"  ✅ 월 매칭: {original_count} → {filtered_count} (필터링: {original_count - filtered_count}건)")
    
    # E. Handling IN/OUT 필드 집계
    handling_fields = ['Handling In freight ton', 'Handling out Freight Ton']
    for field in handling_fields:
        if field in df.columns:
            df[field] = df[field].apply(lambda x: float(x) if pd.notna(x) else 0)
            print(f"  ✅ {field} 처리 완료")
    
    return df

def normalize_location_column(df, location_col='Location'):
    """Location 컬럼 정규화"""
    if location_col in df.columns:
        df[location_col] = df[location_col].astype(str).str.strip()
    return df

def generate_monthly_in_out_stock_report(df):
    """
    월별 IN/OUT/재고 리포트 생성 (기존 기능 유지 + 🆕 NEW: HVDC 필터 적용)
    
    Args:
        df: 트랜잭션 DataFrame
        
    Returns:
        tuple: (in_df, out_df, stock_df)
    """
    print("📊 월별 IN/OUT/재고 리포트 생성 중...")
    
    # 🆕 NEW: HVDC 필터 적용
    df = apply_hvdc_filters(df)
    
    # Location 컬럼 정규화
    df = normalize_location_column(df)
    
    # 날짜 처리
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['월'] = df['Date'].dt.strftime('%Y-%m')
    else:
        df['월'] = 'Unknown'
    
    # IN 트랜잭션 집계
    in_df = df[df['TxType_Refined'] == 'IN'].copy()
    if not in_df.empty:
        in_summary = in_df.groupby(['월', 'Location']).agg({
            'Qty': 'sum',
            'Amount': 'sum',
            'Handling Fee': 'sum' if 'Handling Fee' in in_df.columns else lambda x: 0
        }).reset_index()
        in_summary.columns = ['월', '창고/현장', 'IN수량', 'IN금액', 'IN하역비']
    else:
        in_summary = pd.DataFrame(columns=['월', '창고/현장', 'IN수량', 'IN금액', 'IN하역비'])
    
    # OUT 트랜잭션 집계
    out_df = df[df['TxType_Refined'].isin(['TRANSFER_OUT', 'FINAL_OUT'])].copy()
    if not out_df.empty:
        out_summary = out_df.groupby(['월', 'Location']).agg({
            'Qty': 'sum',
            'Amount': 'sum',
            'Handling Fee': 'sum' if 'Handling Fee' in out_df.columns else lambda x: 0
        }).reset_index()
        out_summary.columns = ['월', '창고/현장', 'OUT수량', 'OUT금액', 'OUT하역비']
    else:
        out_summary = pd.DataFrame(columns=['월', '창고/현장', 'OUT수량', 'OUT금액', 'OUT하역비'])
    
    # 재고 계산
    stock_df = calculate_stock_levels(df)
    
    print(f"✅ 리포트 생성 완료: IN={len(in_summary)}건, OUT={len(out_summary)}건, 재고={len(stock_df)}건")
    
    return in_summary, out_summary, stock_df

def calculate_stock_levels(df):
    """재고 수준 계산"""
    print("📦 재고 수준 계산 중...")
    
    # 날짜별로 정렬
    df_sorted = df.sort_values('Date')
    
    # 각 Location별로 누적 재고 계산
    stock_data = []
    
    for location in df_sorted['Location'].unique():
        location_data = df_sorted[df_sorted['Location'] == location].copy()
        
        # 월별로 그룹화
        for month in location_data['월'].unique():
            month_data = location_data[location_data['월'] == month]
            
            # IN/OUT 계산
            in_qty = month_data[month_data['TxType_Refined'] == 'IN']['Qty'].sum()
            out_qty = month_data[month_data['TxType_Refined'].isin(['TRANSFER_OUT', 'FINAL_OUT'])]['Qty'].sum()
            
            # 재고 = IN - OUT
            stock_qty = in_qty - out_qty
            
            stock_data.append({
                '월': month,
                '창고/현장': location,
                'IN수량': in_qty,
                'OUT수량': out_qty,
                '재고수량': stock_qty,
                '재고상태': '양호' if stock_qty >= 0 else '부족'
            })
    
    stock_df = pd.DataFrame(stock_data)
    return stock_df

def mark_rent_fee(row, warehouse_list=None):
    if warehouse_list is None:
        warehouse_list = ["DSV OUTDOOR", "DSV INDOOR", "DSV AL MARKAZ", "DSV MZP"]
    if str(row.get('HVDC CODE 1', '')).upper() in [w.upper() for w in warehouse_list]:
        return "RENT FEE"
    return ""

def generate_excel_comprehensive_report(transaction_df, daily_stock=None, output_file=None, debug=False):
    """
    통합 엑셀 리포트 생성 (최신 실전 자동 리포트 예제 + 미매핑/RENT FEE 반영)
    """
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"HVDC_통합자동화리포트_{timestamp}.xlsx"
    print(f"📊 통합 엑셀 리포트 생성 중: {output_file}")

    # 🆕 NEW: Vendor 컬럼 강제 정규화 (가이드 C 적용)
    if 'Vendor' in transaction_df.columns:
        transaction_df['Vendor'] = transaction_df['Vendor'].apply(normalize_str)
    else:
        transaction_df['Vendor'] = 'UNKNOWN'
    
    # 🆕 NEW: Vendor 컬럼 자체를 upper()로 정규화 (가이드 B 적용)
    transaction_df['Vendor'] = transaction_df['Vendor'].astype(str).str.strip().str.upper()

    # 🆕 NEW: 가이드 D - 시트 생성 전 데이터 준비
    vendors = sorted(transaction_df['Vendor'].dropna().unique().tolist())
    print(f"🔍 발견된 Vendor: {vendors}")
    all_months = get_all_months(transaction_df)
    wh_list = transaction_df['Location'].dropna().unique().tolist()

    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        # 🆕 NEW: 가이드 D - 공급사별 집계 반복 (개선된 로직)
        for vendor in vendors:
            vendor_df = transaction_df[transaction_df['Vendor'] == vendor].copy()
            vendor_report = aggregate_vendor_monthly(vendor_df, all_months, wh_list)
            vendor_report['금액오차'] = vendor_report['총금액'] - vendor_report['총입고'] * 1
            vendor_report = append_summary_row(vendor_report)
            # [패치] 실제합계 행 추가 (가장 마지막에)
            if 'TOTAL' in vendor_df.columns:
                real_total = vendor_df['TOTAL'].sum()
            elif 'Qty' in vendor_df.columns:
                real_total = vendor_df['Qty'].sum()
            else:
                real_total = vendor_report['총입고'].sum()
            real_total_row = {col: '' for col in vendor_report.columns}
            real_total_row['월'] = '실제합계'
            real_total_row['총입고'] = real_total
            vendor_report = pd.concat([vendor_report, pd.DataFrame([real_total_row])], ignore_index=True)
            vendor_report.to_excel(writer, sheet_name=f"{vendor}_월별집계", index=False)
        
        # 🆕 NEW: 가이드 D - 전체(ALL) 집계
        all_report = aggregate_vendor_monthly(transaction_df, all_months, wh_list)
        all_report['금액오차'] = all_report['총금액'] - all_report['총입고'] * 1
        all_report = append_summary_row(all_report)
        if 'TOTAL' in transaction_df.columns:
            real_total_all = transaction_df['TOTAL'].sum()
        elif 'Qty' in transaction_df.columns:
            real_total_all = transaction_df['Qty'].sum()
        else:
            real_total_all = all_report['총입고'].sum()
        real_total_row_all = {col: '' for col in all_report.columns}
        real_total_row_all['월'] = '실제합계'
        real_total_row_all['총입고'] = real_total_all
        all_report = pd.concat([all_report, pd.DataFrame([real_total_row_all])], ignore_index=True)
        all_report.to_excel(writer, sheet_name="ALL_월별집계", index=False)

        # 1. [월별 IN/OUT/재고 시트] - 이미 금액 포함
        # 2. [월별 Amount 합계 시트] - "월별 실제 청구 금액" 별도 표
        transaction_df['월'] = pd.to_datetime(transaction_df['Date'], errors='coerce').dt.strftime('%Y-%m')
        
        # --- 월별 Amount 합계 ---
        monthly_amount = transaction_df.groupby('월')['Amount'].sum().reset_index()
        monthly_amount.columns = ['월', '월별청구금액(합계)']
        monthly_amount.to_excel(writer, sheet_name='월별청구금액', index=False)
        
        # --- 창고별/월별 Amount 합계 ---
        by_wh_month = transaction_df.groupby(['월', 'Location'])['Amount'].sum().reset_index()
        by_wh_month.columns = ['월', '창고명', '월별청구금액']
        by_wh_month.to_excel(writer, sheet_name='창고별월별청구금액', index=False)

        # --- 현장별/월별 Amount 합계 (Site 구분) ---
        site_list = ['AGI', 'DAS', 'MIR', 'SHU']
        is_site = transaction_df['Location'].isin(site_list)
        by_site_month = transaction_df[is_site].groupby(['월', 'Location'])['Amount'].sum().reset_index()
        by_site_month.columns = ['월', '현장명', '월별청구금액']
        by_site_month.to_excel(writer, sheet_name='현장별월별청구금액', index=False)
        
        # --- 벤더별/월별 Amount 합계 ---
        if 'Vendor' in transaction_df.columns:
            by_vendor_month = transaction_df.groupby(['월', 'Vendor'])['Amount'].sum().reset_index()
            by_vendor_month.columns = ['월', '공급사명', '월별청구금액']
            by_vendor_month.to_excel(writer, sheet_name='공급사별월별청구금액', index=False)

        # 1. 월별 IN 집계
        in_df = transaction_df[transaction_df['TxType_Refined'] == 'IN']
        if not in_df.empty:
            monthly_in = in_df.groupby(['월', 'Location'])['Qty'].sum().reset_index()
            monthly_in.to_excel(writer, sheet_name='01_월별IN_창고현장', index=False)
            print("  ✅ 월별 IN 집계 완료")
        
        # 2. 월별 OUT 집계
        out_df = transaction_df[transaction_df['TxType_Refined'].isin(['TRANSFER_OUT', 'FINAL_OUT'])]
        if not out_df.empty:
            monthly_out = out_df.groupby(['월', 'Location'])['Qty'].sum().reset_index()
            monthly_out.to_excel(writer, sheet_name='02_월별OUT_창고현장', index=False)
            print("  ✅ 월별 OUT 집계 완료")
        
        # 3. 비용 집계 (mapping_rules 기반 자동 확장)
        numeric_fields = get_numeric_fields_from_mapping()
        sheet_counter = 3
        
        for field in numeric_fields:
            if field in transaction_df.columns and transaction_df[field].sum() > 0:
                # 월별 집계
                monthly_agg = transaction_df.groupby('월')[field].sum().reset_index()
                monthly_agg.columns = ['월', f'월별{field}합계']
                sheet_name = f'{sheet_counter:02d}_월별{field}'
                monthly_agg.to_excel(writer, sheet_name=sheet_name, index=False)
                sheet_counter += 1
                print(f"  ✅ {field} 월별 집계 완료")
                
                # 창고별 집계
                location_agg = transaction_df.groupby('Location')[field].sum().reset_index()
                location_agg.columns = ['창고/현장', f'총{field}합계']
                location_agg = location_agg.sort_values(f'총{field}합계', ascending=False)
                sheet_name = f'{sheet_counter:02d}_창고별{field}'
                location_agg.to_excel(writer, sheet_name=sheet_name, index=False)
                sheet_counter += 1
                print(f"  ✅ {field} 창고별 집계 완료")
        
        # 4. 통계 요약 시트
        stats_data = []
        for field in numeric_fields:
            if field in transaction_df.columns:
                stats_data.append({
                    '필드명': field,
                    '총합': transaction_df[field].sum(),
                    '평균': transaction_df[field].mean(),
                    '최대값': transaction_df[field].max(),
                    '최소값': transaction_df[field].min(),
                    '표준편차': transaction_df[field].std()
                })
        
        if stats_data:
            stats_df = pd.DataFrame(stats_data)
            stats_df.to_excel(writer, sheet_name=f'{sheet_counter:02d}_통계요약', index=False)
            print(f"  ✅ 통계 요약 완료")
        
        # 5. 재고 데이터가 있으면 추가
        if daily_stock is not None and not daily_stock.empty:
            daily_stock.to_excel(writer, sheet_name=f'{sheet_counter+1:02d}_일별재고', index=False)
            print(f"  ✅ 일별 재고 데이터 추가")

        # === [미매핑/RENT FEE 시트 추가] ===
        # 1. 매칭 성공/실패 구분 (MATCHED 컬럼이 있다고 가정, 없으면 전체 matched)
        if 'MATCHED' in transaction_df.columns:
            matched_df = transaction_df[transaction_df['MATCHED'] == True].copy()
            unmatched_df = transaction_df[transaction_df['MATCHED'] == False].copy()
        else:
            matched_df = transaction_df.copy()
            unmatched_df = pd.DataFrame(columns=transaction_df.columns)

        if not unmatched_df.empty:
            # RENT FEE 자동 분류
            warehouse_list = ["DSV OUTDOOR", "DSV INDOOR", "DSV AL MARKAZ", "DSV MZP"]
            unmatched_df['Remark'] = unmatched_df.apply(lambda row: mark_rent_fee(row, warehouse_list), axis=1)
            # GROUP BY HVDC CODE 1, 2
            group_cols = [col for col in ['HVDC CODE 1', 'HVDC CODE 2'] if col in unmatched_df.columns]
            agg_dict = {}
            for col in ['Amount', 'Qty', 'SQM', 'Handling In freight ton', 'Handling out Freight Ton']:
                if col in unmatched_df.columns:
                    agg_dict[col] = 'sum'
            unmatched_group = unmatched_df.groupby(group_cols).agg(agg_dict).reset_index() if group_cols else pd.DataFrame()
            # RENT FEE 시트
            rent_fee_df = unmatched_df[unmatched_df['Remark'] == "RENT FEE"].copy()
        else:
            unmatched_group = pd.DataFrame()
            rent_fee_df = pd.DataFrame()

        # 시트 저장
        if not unmatched_group.empty:
            unmatched_group.to_excel(writer, sheet_name='미매핑항목(코드1_2별)', index=False)
        if not unmatched_df.empty:
            unmatched_df.to_excel(writer, sheet_name='미매핑항목_RAW', index=False)
        if not rent_fee_df.empty:
            rent_fee_df.to_excel(writer, sheet_name='RENT FEE', index=False)

        # ==== FULL_매핑집계(원본+매핑+분류+정규화 컬럼 전체 저장) ====
        transaction_df_cp = transaction_df.copy()
        transaction_df_cp['Location_Normalized'] = transaction_df_cp['Location'].astype(str).str.strip()
        transaction_df_cp['Vendor_Normalized'] = transaction_df_cp['Vendor'].astype(str).str.strip() if 'Vendor' in transaction_df_cp.columns else ''
        transaction_df_cp['Storage_Type'] = transaction_df_cp['Location'].apply(classify_storage_type)

        # 코드 정규화 등 추가 (있는 경우)
        if 'HVDC CODE' in transaction_df_cp.columns and 'HVDC CODE 4' in transaction_df_cp.columns:
            transaction_df_cp['CODE_MATCH'] = transaction_df_cp.apply(
                lambda row: codes_match(row['HVDC CODE'], row['HVDC CODE 4']), axis=1
            )
        else:
            transaction_df_cp['CODE_MATCH'] = ''

        # 미매핑, Remark 등 컬럼 추가
        if 'MATCHED' not in transaction_df_cp.columns:
            transaction_df_cp['MATCHED'] = True
        if '미매핑사유' not in transaction_df_cp.columns:
            transaction_df_cp['미매핑사유'] = ''

        # 표기/컬럼 순서(엑셀 피벗에 편리한 형태)
        main_cols = [
            'Date', '월', 'Case_No', 'Vendor', 'Vendor_Normalized', 'Location', 'Location_Normalized',
            'Storage_Type', 'TxType_Refined', 'Qty', 'Amount', 'SQM', 'Handling Fee',
            'HVDC CODE', 'HVDC CODE 1', 'HVDC CODE 2', 'HVDC CODE 3', 'HVDC CODE 4',
            'CODE_MATCH', 'MATCHED', '미매핑사유', 'Remark'
        ]
        # 실제 존재하는 컬럼만 필터링
        existing_cols = [col for col in main_cols if col in transaction_df_cp.columns]
        remaining_cols = [col for col in transaction_df_cp.columns if col not in main_cols]
        final_cols = existing_cols + remaining_cols
        
        # FULL_매핑집계 시트 sum 추가 (아래 예시)
        if 'TOTAL' in transaction_df_cp.columns:
            total_sum = transaction_df_cp['TOTAL'].sum()
            sum_row = pd.DataFrame([{col: total_sum if col == 'TOTAL' else '' for col in transaction_df_cp.columns}])
            transaction_df_cp = pd.concat([transaction_df_cp, sum_row], ignore_index=True)
        transaction_df_cp[final_cols].to_excel(writer, sheet_name='FULL_매핑집계', index=False)
        print(f"✅ FULL_매핑집계 시트 저장 ({len(transaction_df_cp)}건)")

        # === [실제수입합계_검증 시트 추가] ===
        real_table = calc_real_imported_stock(transaction_df)
        real_table.to_excel(writer, sheet_name='실제수입합계_검증', index=False)

        # 🆕 NEW: 월별정산집계 시트 추가 (가이드 적용)
        monthly_summary_df = generate_monthly_summary_report(transaction_df)
        monthly_summary_df.to_excel(writer, sheet_name='월별정산집계', index=False)
        print(f"✅ 월별정산집계 시트 저장 ({len(monthly_summary_df)}개월)")

        # === [실제_최종재고 시트 추가] ===
        real_inventory_table = calc_actual_inventory_precise(transaction_df)
        real_inventory_table.to_excel(writer, sheet_name='실제_최종재고', index=False)

    if debug:
        print(f"✅ 통합 리포트 저장: {output_file}")
    print(f"✅ 미매핑/RENT FEE 시트 추가 완료: {output_file}")
    return output_file

def get_numeric_fields_from_mapping():
    """mapping_rules에서 숫자형 필드 목록 반환"""
    numeric_fields = []
    for field, props in PROPERTY_MAPPINGS.items():
        if props.get('datatype') in ['xsd:decimal', 'xsd:integer']:
            numeric_fields.append(field)
    return numeric_fields

def generate_automated_summary_report(df, output_dir="reports"):
    """
    자동화된 요약 리포트 생성 (mapping_rules 기반)
    
    Args:
        df: 트랜잭션 DataFrame
        output_dir: 출력 디렉토리
        
    Returns:
        str: 생성된 파일 경로
    """
    print("🤖 자동화된 요약 리포트 생성 중...")
    
    # 출력 디렉토리 생성
    Path(output_dir).mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"{output_dir}/HVDC_자동요약리포트_{timestamp}.xlsx"
    
    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        sheet_counter = 1
        
        # 1. 기본 트랜잭션 요약
        if not df.empty:
            # 월별 트랜잭션 수
            monthly_tx_count = df.groupby('월').size().reset_index(name='트랜잭션수')
            monthly_tx_count.to_excel(writer, sheet_name=f'{sheet_counter:02d}_월별트랜잭션수', index=False)
            sheet_counter += 1
            
            # 창고별 트랜잭션 수
            location_tx_count = df.groupby('Location').size().reset_index(name='트랜잭션수')
            location_tx_count = location_tx_count.sort_values('트랜잭션수', ascending=False)
            location_tx_count.to_excel(writer, sheet_name=f'{sheet_counter:02d}_창고별트랜잭션수', index=False)
            sheet_counter += 1
        
        # 2. mapping_rules 기반 자동 집계
        numeric_fields = get_numeric_fields_from_mapping()
        
        for field in numeric_fields:
            if field in df.columns and df[field].sum() > 0:
                # 월별 집계
                monthly_agg = df.groupby('월')[field].agg(['sum', 'mean', 'count']).reset_index()
                monthly_agg.columns = ['월', f'{field}_총합', f'{field}_평균', f'{field}_건수']
                sheet_name = f'{sheet_counter:02d}_월별{field}상세'
                monthly_agg.to_excel(writer, sheet_name=sheet_name, index=False)
                sheet_counter += 1
        
        # 3. 벤더별 집계 (Vendor 컬럼이 있는 경우)
        if 'Vendor' in df.columns:
            vendor_agg = df.groupby('Vendor').agg({
                'Qty': 'sum',
                'Amount': 'sum'
            }).reset_index()
            vendor_agg = vendor_agg.sort_values('Amount', ascending=False)
            vendor_agg.to_excel(writer, sheet_name=f'{sheet_counter:02d}_벤더별집계', index=False)
            sheet_counter += 1
    
    print(f"✅ 자동화된 요약 리포트 생성 완료: {output_file}")
    return output_file

def validate_report_data(df):
    """
    리포트 데이터 검증
    
    Args:
        df: 검증할 DataFrame
        
    Returns:
        dict: 검증 결과
    """
    validation_result = {
        'total_records': len(df),
        'missing_dates': df['Date'].isna().sum() if 'Date' in df.columns else 0,
        'missing_locations': df['Location'].isna().sum() if 'Location' in df.columns else 0,
        'missing_quantities': df['Qty'].isna().sum() if 'Qty' in df.columns else 0,
        'negative_quantities': (df['Qty'] < 0).sum() if 'Qty' in df.columns else 0,
        'unique_locations': df['Location'].nunique() if 'Location' in df.columns else 0,
        'date_range': {
            'start': df['Date'].min() if 'Date' in df.columns else None,
            'end': df['Date'].max() if 'Date' in df.columns else None
        }
    }
    
    return validation_result

# 기존 함수들 유지 (하위 호환성)
def generate_monthly_report(df, output_file=None):
    """기존 월별 리포트 생성 함수 (하위 호환성)"""
    return generate_monthly_in_out_stock_report(df)

def create_excel_report(df, output_path):
    """기존 엑셀 리포트 생성 함수 (하위 호환성)"""
    return generate_excel_comprehensive_report(df, output_file=output_path)

# test_excel_reporter.py에서 필요한 추가 함수들
def generate_monthly_in_report(df):
    """월별 IN 리포트 생성"""
    print("📈 월별 IN 리포트 생성 중...")
    
    # Location 컬럼 정규화
    df = normalize_location_column(df)
    
    # 날짜 처리
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['월'] = df['Date'].dt.strftime('%Y-%m')
    else:
        df['월'] = 'Unknown'
    
    # IN 트랜잭션만 필터링
    in_df = df[df['TxType_Refined'] == 'IN'].copy()
    
    if not in_df.empty:
        # 월별 집계
        monthly_in = in_df.groupby('월').agg({
            'Qty': 'sum',
            'Amount': 'sum',
            'Handling Fee': 'sum' if 'Handling Fee' in in_df.columns else lambda x: 0
        }).reset_index()
        monthly_in.columns = ['월', '총IN수량', '총IN금액', '총IN하역비']
    else:
        monthly_in = pd.DataFrame(columns=['월', '총IN수량', '총IN금액', '총IN하역비'])
    
    print(f"✅ 월별 IN 리포트 생성 완료: {len(monthly_in)}건")
    return monthly_in

def generate_monthly_trend_and_cumulative(df):
    """월별 트렌드 및 누적 재고 계산"""
    print("📊 월별 트렌드 및 누적 재고 계산 중...")
    
    # Location 컬럼 정규화
    df = normalize_location_column(df)
    
    # 날짜 처리
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['월'] = df['Date'].dt.strftime('%Y-%m')
    else:
        df['월'] = 'Unknown'
    
    # 월별 IN/OUT 집계
    monthly_data = []
    
    for month in df['월'].unique():
        month_data = df[df['월'] == month]
        
        in_qty = month_data[month_data['TxType_Refined'] == 'IN']['Qty'].sum()
        out_qty = month_data[month_data['TxType_Refined'].isin(['TRANSFER_OUT', 'FINAL_OUT'])]['Qty'].sum()
        
        monthly_data.append({
            '월': month,
            'IN수량': in_qty,
            'OUT수량': out_qty,
            '순증감': in_qty - out_qty
        })
    
    trend_df = pd.DataFrame(monthly_data)
    
    # 누적 재고 계산
    cumulative_df = trend_df.copy()
    cumulative_df['누적재고'] = cumulative_df['순증감'].cumsum()
    
    print(f"✅ 트렌드 및 누적 재고 계산 완료: {len(trend_df)}개월")
    return trend_df, cumulative_df

def validate_transaction_data(df):
    """트랜잭션 데이터 검증 및 진단"""
    print("🔍 트랜잭션 데이터 검증 중...")
    
    diagnosis = {
        'total_records': len(df),
        'missing_dates': df['Date'].isna().sum() if 'Date' in df.columns else 0,
        'missing_locations': df['Location'].isna().sum() if 'Location' in df.columns else 0,
        'missing_quantities': df['Qty'].isna().sum() if 'Qty' in df.columns else 0,
        'negative_quantities': (df['Qty'] < 0).sum() if 'Qty' in df.columns else 0,
        'unique_locations': df['Location'].nunique() if 'Location' in df.columns else 0,
        'date_range': {
            'start': df['Date'].min() if 'Date' in df.columns else None,
            'end': df['Date'].max() if 'Date' in df.columns else None
        },
        'recommendation': ''
    }
    
    # 권장사항 생성
    recommendations = []
    
    if diagnosis['missing_dates'] > 0:
        recommendations.append(f"⚠️ 날짜 누락: {diagnosis['missing_dates']}건")
    
    if diagnosis['missing_locations'] > 0:
        recommendations.append(f"⚠️ 위치 누락: {diagnosis['missing_locations']}건")
    
    if diagnosis['missing_quantities'] > 0:
        recommendations.append(f"⚠️ 수량 누락: {diagnosis['missing_quantities']}건")
    
    if diagnosis['negative_quantities'] > 0:
        recommendations.append(f"⚠️ 음수 수량: {diagnosis['negative_quantities']}건")
    
    if len(recommendations) == 0:
        recommendations.append("✅ 데이터 품질 양호")
    
    diagnosis['recommendation'] = " | ".join(recommendations)
    
    print(f"✅ 데이터 검증 완료: {diagnosis['total_records']}건")
    return diagnosis

def create_test_out_transaction():
    """테스트용 OUT 트랜잭션 생성"""
    return {
        'Case_No': 'CASE_OUT_001',
        'Date': pd.Timestamp('2025-07-15'),
        'Location': 'DSV Indoor',
        'TxType_Refined': 'TRANSFER_OUT',
        'Qty': 40,
        'Source_File': '테스트',
        'Loc_From': 'DSV Indoor',
        'Target_Warehouse': 'AGI',
        'Storage_Type': 'Indoor',
        'storage_type': 'Indoor'
    }

def print_transaction_analysis(df):
    """트랜잭션 데이터 상세 분석 출력"""
    print("\n📊 **트랜잭션 데이터 상세 분석**:")
    
    if df.empty:
        print("   ❌ 데이터가 비어있습니다!")
        return
    
    # 기본 통계
    print(f"   📈 총 트랜잭션: {len(df):,}건")
    print(f"   📅 기간: {df['Date'].min().strftime('%Y-%m-%d')} ~ {df['Date'].max().strftime('%Y-%m-%d')}")
    print(f"   🏢 창고/현장 수: {df['Location'].nunique()}개")
    
    # 트랜잭션 타입별 분석
    if 'TxType_Refined' in df.columns:
        tx_counts = df['TxType_Refined'].value_counts()
        print("   🔄 트랜잭션 타입별:")
        for tx_type, count in tx_counts.items():
            print(f"      {tx_type}: {count:,}건")
    
    # 창고별 분석
    location_counts = df['Location'].value_counts().head(5)
    print("   🏢 상위 5개 창고/현장:")
    for location, count in location_counts.items():
        print(f"      {location}: {count:,}건")
    
    # 수량 분석
    if 'Qty' in df.columns:
        print(f"   📦 수량 통계:")
        print(f"      총 수량: {df['Qty'].sum():,}")
        print(f"      평균 수량: {df['Qty'].mean():.2f}")
        print(f"      최대 수량: {df['Qty'].max():,}")
        print(f"      최소 수량: {df['Qty'].min():,}")

def visualize_out_transactions(df):
    """OUT 트랜잭션 시각화 (텍스트 기반)"""
    print("\n📊 **OUT 트랜잭션 분석**:")
    
    out_df = df[df['TxType_Refined'].isin(['TRANSFER_OUT', 'FINAL_OUT'])]
    
    if out_df.empty:
        print("   ℹ️ OUT 트랜잭션이 없습니다.")
        return
    
    print(f"   📤 총 OUT 트랜잭션: {len(out_df):,}건")
    
    # OUT 타입별 분석
    out_type_counts = out_df['TxType_Refined'].value_counts()
    for out_type, count in out_type_counts.items():
        print(f"      {out_type}: {count:,}건")
    
    # 창고별 OUT 분석
    location_out = out_df.groupby('Location')['Qty'].sum().sort_values(ascending=False)
    print("   🏢 창고별 OUT 수량:")
    for location, qty in location_out.head(5).items():
        print(f"      {location}: {qty:,}")
    
    # 월별 OUT 트렌드
    if 'Date' in out_df.columns:
        out_df['월'] = pd.to_datetime(out_df['Date']).dt.strftime('%Y-%m')
        monthly_out = out_df.groupby('월')['Qty'].sum()
        print("   📅 월별 OUT 수량:")
        for month, qty in monthly_out.items():
            print(f"      {month}: {qty:,}")

# 🆕 NEW: 가이드 요구사항 [A] - 월별 집계 함수들
def get_all_months(df, date_col='Date'):
    """전체 월(YYYY-MM) 목록 추출, 누락월 없이 정렬"""
    min_month = pd.to_datetime(df[date_col].min()).to_period('M')
    max_month = pd.to_datetime(df[date_col].max()).to_period('M')
    months = pd.period_range(min_month, max_month, freq='M').strftime('%Y-%m')
    return list(months)

def aggregate_vendor_monthly(df, all_months, wh_list):
    """
    공급사별 월별/창고별/누적재고/금액 집계 (누적합 방식, 복붙)
    """
    records = []
    # 각 창고별 IN/OUT 월별 테이블 생성 (모든 월, 모든 창고 포함)
    for m in all_months:
        row = {'월': m}
        total_in = total_out = total_stock = total_amount = 0
        for wh in wh_list:
            # 월별 IN
            in_qty = df[(df['월'] == m) & (df['Location'] == wh) & (df['TxType_Refined'] == 'IN')]['Qty'].sum()
            # 월별 OUT
            out_qty = df[(df['월'] == m) & (df['Location'] == wh) & (df['TxType_Refined'].isin(['TRANSFER_OUT','FINAL_OUT']))]['Qty'].sum()
            # 월별 금액(입고 기준, 필요시 OUT 포함/분리)
            amount = df[(df['월'] == m) & (df['Location'] == wh) & (df['TxType_Refined'] == 'IN')]['Amount'].sum()
            row[f"{wh}_입고"] = in_qty
            row[f"{wh}_출고"] = out_qty
            row[f"{wh}_금액"] = amount
            total_in += in_qty
            total_out += out_qty
            total_amount += amount
        row['총입고'] = total_in
        row['총출고'] = total_out
        row['총금액'] = total_amount
        records.append(row)

    df_monthly = pd.DataFrame(records)

    # === [누적재고 계산] ===
    # 각 창고별 누적: cumsum(입고) - cumsum(출고)
    for wh in wh_list:
        in_col = f"{wh}_입고"
        out_col = f"{wh}_출고"
        stock_col = f"{wh}_누적재고"
        if in_col in df_monthly.columns and out_col in df_monthly.columns:
            df_monthly[stock_col] = (df_monthly[in_col].cumsum() - df_monthly[out_col].cumsum())
        else:
            df_monthly[stock_col] = 0

    # 전체 누적재고(합산)
    stock_cols = [f"{wh}_누적재고" for wh in wh_list]
    df_monthly['총누적재고'] = df_monthly[stock_cols].sum(axis=1)

    return df_monthly

def append_summary_row(df):
    """요약 행 추가"""
    summary_row = {
        '월': '합계',
        '총입고': df['총입고'].sum(),
        '총출고': df['총출고'].sum(),
        '총금액': df['총금액'].sum(),
        '총누적재고': df['총누적재고'].iloc[-1] if len(df) > 0 else 0,
        '금액오차': df['금액오차'].sum()
    }
    
    # 각 창고/현장별 합계 추가
    for col in df.columns:
        if col.endswith('_입고') or col.endswith('_출고') or col.endswith('_금액') or col.endswith('_누적재고'):
            if col in df.columns:
                summary_row[col] = df[col].sum()
    
    return pd.concat([df, pd.DataFrame([summary_row])], ignore_index=True)

def generate_monthly_summary_report(df):
    # 1. Billing month 기준 월 컬럼 생성 (YYYY-MM)
    if 'Billing month' in df.columns:
        df['집계월'] = pd.to_datetime(df['Billing month'], errors='coerce').dt.strftime('%Y-%m')
        month_col = '집계월'
    else:
        df['집계월'] = pd.to_datetime(df['Operation Month'], errors='coerce').dt.strftime('%Y-%m')
        month_col = '집계월'

    # 2. Location, Vendor 모두 대문자/strip 정규화
    df['Location'] = df['Location'].astype(str).str.strip().str.upper()
    if 'Vendor' in df.columns:
        df['Vendor'] = df['Vendor'].astype(str).str.strip().str.upper()

    # 3. 창고(warehouse_codes) 집합 정의
    warehouse_codes = ['DSV OUTDOOR', 'DSV INDOOR', 'DSV AL MARKAZ', 'DSV MZP', 'MOSB', 'HAULER INDOOR']

    # 4. Handling Fee (HE/SIM/HITACHI/SIMENS)
    he_sim_keywords = ['HE', 'HITACHI', 'SIM', 'SIMENS']
    he_sim_mask = df['Vendor'].isin(he_sim_keywords)
    handling_by_month = df[he_sim_mask].groupby(month_col)['Handling Fee'].sum().rename('HandlingFee_HE_SIM').reset_index()

    # 5. RENT FEE 집계: Location이 창고코드 & Amount 값 (X컬럼)
    rent_mask = df['Location'].isin(warehouse_codes)
    rent_by_month = df[rent_mask].groupby(month_col)['Amount'].sum().rename('RENT_FEE').reset_index()

    # 6. OTHERS 집계: 위 둘 모두 제외, Amount 값
    others_mask = ~(he_sim_mask | rent_mask)
    others_by_month = df[others_mask].groupby(month_col)['Amount'].sum().rename('OTHERS').reset_index()

    # 7. 병합 및 fillna(0)
    all_months = sorted(set(df[month_col]))
    result = pd.DataFrame({month_col: all_months})
    result = result.merge(handling_by_month, on=month_col, how='left')
    result = result.merge(rent_by_month, on=month_col, how='left')
    result = result.merge(others_by_month, on=month_col, how='left')
    result = result.fillna(0)
    result['TOTAL'] = result['HandlingFee_HE_SIM'] + result['RENT_FEE'] + result['OTHERS']

    # 컬럼명 표준화
    result.columns = ['월', '월별Handling Fee합계(HITACHI,SIMENS)', 'RENT FEE', 'OTHERS', 'TOTAL']
    return result

def calc_real_imported_stock(df):
    """
    실무 기준: Case_No + Vendor + Storage_Type + Location별 중복 없이 Qty sum,
    AGI/DAS/MIR/SHU만 필터링하여 피벗 테이블 반환
    """
    site_list = ['AGI', 'DAS', 'MIR', 'SHU']
    df_site = df[df['Location'].isin(site_list)]
    stock_pivot = (
        df_site.groupby(['Vendor', 'Storage_Type', 'Location'], as_index=False)['Qty'].sum()
    )
    result = stock_pivot.pivot_table(index=['Vendor', 'Storage_Type'],
                                     columns='Location', values='Qty', fill_value=0).reset_index()
    for site in site_list:
        if site not in result.columns:
            result[site] = 0
    result['TOTAL'] = result[site_list].sum(axis=1)
    result = result[['Vendor', 'Storage_Type'] + site_list + ['TOTAL']]
    return result

def calc_actual_inventory_precise(df):
    site_list = ['AGI', 'DAS', 'MIR', 'SHU']
    df = df.sort_values('Date')
    last_row = df.groupby('Case_No', as_index=False).last()
    mask = (last_row['Location'].isin(site_list)) & \
           (last_row['TxType_Refined'].isin(['IN', 'TRANSFER_IN']))
    real_stock = last_row[mask]
    print(f"🎯 실제 재고(실재고) 개수(최신 상태 기준): {len(real_stock):,}")
    # 이벤트 없는/누락 케이스 진단
    event_cases = set(df['Case_No'])
    real_cases = set(real_stock['Case_No']) if 'Case_No' in real_stock.columns else set(real_stock.index)
    missing_cases = event_cases - real_cases
    print(f"실재고 집계에서 누락된 케이스 수: {len(missing_cases)}")
    print("샘플 누락 Case_No:", list(missing_cases)[:10])
    # 현장/Storage Type별 집계
    if 'Vendor' not in real_stock.columns: real_stock['Vendor'] = 'UNKNOWN'
    if 'Storage_Type' not in real_stock.columns:
        real_stock['Storage_Type'] = real_stock['Location'].apply(classify_storage_type)
    pivot = real_stock.pivot_table(
        index=['Vendor', 'Storage_Type'],
        columns='Location',
        values='Case_No',
        aggfunc='count',
        fill_value=0
    ).reset_index()
    for site in site_list:
        if site not in pivot.columns:
            pivot[site] = 0
    pivot['TOTAL'] = pivot[site_list].sum(axis=1)
    return pivot

def real_inventory_table(df):
    df = normalize_all_keys(df)
    # ... pivot, groupby, 집계 ...

    # ... rest of the function ...

    return ...  # Return the result of the function

    # ... rest of the function ...

def find_pkg_column(df):
    # 'Pkg', 'pkg', 'PKG', ' Pkg ', 등 자동 인식
    for col in df.columns:
        if col.strip().lower() == "pkg":
            return col
    return None

def get_total_pkg(df):
    pkg_col = find_pkg_column(df)
    if pkg_col:
        # NaN은 0으로 처리
        return df[pkg_col].fillna(0).sum()
    else:
        return 0

def get_grouped_pkg_sum(df, group_cols=['Location']):
    pkg_col = find_pkg_column(df)
    if not pkg_col:
        raise ValueError("Pkg 컬럼이 존재하지 않습니다.")
    return df.groupby(group_cols)[pkg_col].sum().reset_index() 