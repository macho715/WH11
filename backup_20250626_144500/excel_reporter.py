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

logger = logging.getLogger(__name__)

# 최신 mapping_rules 불러오기
try:
    with open('mapping_rules_v2.6.json', encoding='utf-8') as f:
        RULES = json.load(f)
    FIELD_MAP = RULES['field_map']
    PROPERTY_MAPPINGS = RULES['property_mappings']
except Exception as e:
    logger.warning(f"mapping_rules_v2.6.json 로드 실패, 기본값 사용: {e}")
    FIELD_MAP = {}
    PROPERTY_MAPPINGS = {}

def normalize_location_column(df, location_col='Location'):
    """Location 컬럼 정규화"""
    if location_col in df.columns:
        df[location_col] = df[location_col].astype(str).str.strip()
    return df

def generate_monthly_in_out_stock_report(df):
    """
    월별 IN/OUT/재고 리포트 생성 (기존 기능 유지)
    
    Args:
        df: 트랜잭션 DataFrame
        
    Returns:
        tuple: (in_df, out_df, stock_df)
    """
    print("📊 월별 IN/OUT/재고 리포트 생성 중...")
    
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

def generate_excel_comprehensive_report(transaction_df, daily_stock=None, output_file=None, debug=False):
    """
    통합 엑셀 리포트 생성 (최신 실전 자동 리포트 예제)
    
    Args:
        transaction_df: 트랜잭션 DataFrame
        daily_stock: 일별 재고 데이터 (선택사항)
        output_file: 출력 파일 경로
        debug: 디버그 모드
        
    Returns:
        str: 생성된 파일 경로
    """
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"HVDC_통합자동화리포트_{timestamp}.xlsx"
    
    print(f"📊 통합 엑셀 리포트 생성 중: {output_file}")
    
    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        # 1. 월별 IN 집계
        transaction_df['월'] = pd.to_datetime(transaction_df['Date'], errors='coerce').dt.strftime('%Y-%m')
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
    
    if debug:
        print(f"✅ 통합 리포트 저장: {output_file}")
    
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
    
    out_df = df[df['TxType_Refined'].isin(['TRANSFER_OUT', 'FINAL_OUT'])].copy()
    
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