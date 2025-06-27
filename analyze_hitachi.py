#!/usr/bin/env python3
"""
HITACHI 파일 Pkg 컬럼 상세 분석
목표: 5,346개 vs 5,347개 차이 원인 분석
"""

import pandas as pd
import numpy as np

def analyze_hitachi_pkg():
    """
    HITACHI 파일의 Pkg 컬럼 상세 분석
    """
    print("🔍 HITACHI 파일 Pkg 컬럼 상세 분석")
    print("목표: 5,346개 vs 5,347개 차이 원인 분석")
    print("=" * 60)
    
    try:
        # 파일 로드
        df = pd.read_excel('data/HVDC WAREHOUSE_HITACHI(HE).xlsx')
        print(f"📋 총 행 수: {len(df):,}")
        print(f"📦 Pkg 컬럼 총합: {df['Pkg'].sum():,}")
        
        # Pkg 컬럼 통계
        print("\n📊 Pkg 컬럼 통계:")
        print(df['Pkg'].describe())
        
        # 누락/이상 데이터 확인
        print("\n🔍 누락/이상 데이터 확인:")
        print(f"   Pkg가 0인 행: {(df['Pkg'] == 0).sum():,}")
        print(f"   Pkg가 null인 행: {df['Pkg'].isnull().sum():,}")
        print(f"   Pkg가 1이 아닌 행: {(df['Pkg'] != 1).sum():,}")
        
        # Pkg가 1이 아닌 행들 확인
        non_one_rows = df[df['Pkg'] != 1]
        if len(non_one_rows) > 0:
            print(f"\n⚠️ Pkg가 1이 아닌 행들 ({len(non_one_rows)}개):")
            for idx, row in non_one_rows.head(10).iterrows():
                print(f"   행 {idx}: HVDC CODE = {row['HVDC CODE']}, Pkg = {row['Pkg']}")
        
        # HVDC CODE별 Pkg 합계
        print("\n📦 HVDC CODE별 Pkg 합계:")
        code_pkg_sum = df.groupby('HVDC CODE')['Pkg'].sum()
        print(f"   고유 HVDC CODE 수: {len(code_pkg_sum):,}")
        print(f"   HVDC CODE별 Pkg 총합: {code_pkg_sum.sum():,}")
        
        # Pkg가 1이 아닌 HVDC CODE들
        non_one_codes = code_pkg_sum[code_pkg_sum != 1]
        if len(non_one_codes) > 0:
            print(f"\n⚠️ HVDC CODE별 Pkg가 1이 아닌 케이스들 ({len(non_one_codes)}개):")
            for code, pkg_sum in non_one_codes.head(10).items():
                print(f"   {code}: Pkg 합계 = {pkg_sum}")
        
        # 차이 분석
        target_qty = 5347
        actual_qty = df['Pkg'].sum()
        difference = target_qty - actual_qty
        
        print(f"\n📊 차이 분석:")
        print(f"   목표 수량: {target_qty:,}")
        print(f"   실제 수량: {actual_qty:,}")
        print(f"   차이: {difference:,}")
        
        if difference == 1:
            print("   🔍 차이가 1개 - 누락된 행이나 Pkg 값이 0인 행이 있을 가능성")
        elif difference > 0:
            print(f"   🔍 차이가 {difference}개 - 누락된 데이터 존재")
        else:
            print(f"   🔍 차이가 {abs(difference)}개 - 중복 또는 잘못된 데이터 존재")
            
        # 창고별 분포 확인
        print("\n🏢 창고별 분포 확인:")
        warehouse_cols = [col for col in df.columns if any(warehouse in str(col) for warehouse in 
                        ['DSV Indoor', 'DSV Al Markaz', 'DSV Outdoor', 'Hauler Indoor', 'MOSB', 'MIR', 'SHU', 'DAS', 'AGI'])]
        
        for col in warehouse_cols:
            non_null_count = df[col].notna().sum()
            if non_null_count > 0:
                print(f"   {col}: {non_null_count}건 (Pkg 합계: {df[df[col].notna()]['Pkg'].sum():,})")
        
    except Exception as e:
        print(f"❌ 분석 실패: {e}")

if __name__ == "__main__":
    analyze_hitachi_pkg()
    print("\n" + "=" * 60) 