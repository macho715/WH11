#!/usr/bin/env python3
"""
데이터 및 컬럼 정합성 사전 점검 스크립트
"""

import pandas as pd
import numpy as np
from datetime import datetime

def check_data_integrity(df):
    """DataFrame의 데이터 및 컬럼 정합성 점검"""
    print("🔍 데이터 및 컬럼 정합성 점검 시작")
    print("=" * 50)
    
    # 1. 필수 컬럼 존재 여부 확인
    required_columns = ['Location', '월', 'TxType_Refined', 'Qty', 'Amount']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        print(f"❌ 누락된 필수 컬럼: {missing_columns}")
        return False
    else:
        print("✅ 모든 필수 컬럼 존재")
    
    # 2. Location 정규화 확인
    print(f"\n🏢 Location 컬럼 분석:")
    print(f"   고유 Location 수: {df['Location'].nunique()}")
    print(f"   Location 목록: {sorted(df['Location'].unique())}")
    
    # 3. 월 컬럼 확인
    print(f"\n📅 월 컬럼 분석:")
    print(f"   고유 월 수: {df['월'].nunique()}")
    print(f"   월 범위: {df['월'].min()} ~ {df['월'].max()}")
    print(f"   월 목록: {sorted(df['월'].unique())}")
    
    # 4. TxType_Refined 확인
    print(f"\n🔄 TxType_Refined 분석:")
    tx_counts = df['TxType_Refined'].value_counts()
    for tx_type, count in tx_counts.items():
        print(f"   {tx_type}: {count:,}건")
    
    # 5. Qty 컬럼 확인
    print(f"\n📦 Qty 컬럼 분석:")
    print(f"   총 수량: {df['Qty'].sum():,}")
    print(f"   평균 수량: {df['Qty'].mean():.2f}")
    print(f"   최대 수량: {df['Qty'].max():,}")
    print(f"   최소 수량: {df['Qty'].min():,}")
    print(f"   NaN 개수: {df['Qty'].isna().sum()}")
    
    # 6. Amount 컬럼 확인
    print(f"\n💰 Amount 컬럼 분석:")
    print(f"   총 금액: {df['Amount'].sum():,.2f}")
    print(f"   평균 금액: {df['Amount'].mean():.2f}")
    print(f"   최대 금액: {df['Amount'].max():,.2f}")
    print(f"   최소 금액: {df['Amount'].min():,.2f}")
    print(f"   NaN 개수: {df['Amount'].isna().sum()}")
    print(f"   0 값 개수: {(df['Amount'] == 0).sum()}")
    
    # 7. 입고/출고별 분석
    print(f"\n📊 입고/출고별 분석:")
    in_df = df[df['TxType_Refined'] == 'IN']
    out_df = df[df['TxType_Refined'].isin(['TRANSFER_OUT', 'FINAL_OUT'])]
    
    print(f"   입고(IN): {len(in_df):,}건, 수량: {in_df['Qty'].sum():,}, 금액: {in_df['Amount'].sum():,.2f}")
    print(f"   출고(OUT): {len(out_df):,}건, 수량: {out_df['Qty'].sum():,}, 금액: {out_df['Amount'].sum():,.2f}")
    
    # 8. 창고별 입고/출고 분석
    print(f"\n🏢 창고별 입고/출고 분석:")
    for location in sorted(df['Location'].unique()):
        loc_in = in_df[in_df['Location'] == location]
        loc_out = out_df[out_df['Location'] == location]
        print(f"   {location}:")
        print(f"     입고: {len(loc_in):,}건, 수량: {loc_in['Qty'].sum():,}, 금액: {loc_in['Amount'].sum():,.2f}")
        print(f"     출고: {len(loc_out):,}건, 수량: {loc_out['Qty'].sum():,}, 금액: {loc_out['Amount'].sum():,.2f}")
    
    print("\n" + "=" * 50)
    return True

if __name__ == "__main__":
    # 테스트용 데이터 로드
    from test_excel_reporter import main as test_main
    print("테스트 데이터로 정합성 점검을 실행합니다...")
    # 실제로는 test_excel_reporter에서 생성된 DataFrame을 사용해야 함 