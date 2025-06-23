# check_missing_data.py
import pandas as pd
import numpy as np

def check_hitachi_he_missing_data():
    """HVDC WAREHOUSE_HITACHI(HE) 파일의 누락 데이터 분석"""
    print("🔍 HITACHI(HE) 파일 누락 데이터 분석")
    print("=" * 60)
    
    filepath = "data/HVDC WAREHOUSE_HITACHI(HE).xlsx"
    
    try:
        # Excel 파일 읽기
        df = pd.read_excel(filepath, sheet_name=0)
        print(f"📄 파일: {filepath}")
        print(f"📊 총 행 수: {len(df)}")
        print(f"📊 총 컬럼 수: {len(df.columns)}")
        
        # 3691번째 행 주변 데이터 확인
        print(f"\n🔍 3691번째 행 주변 데이터 확인:")
        
        if len(df) >= 3691:
            # 3685~3695행 확인 (3691 주변)
            start_idx = max(0, 3690-5)  # 3685번째 행 (0-based이므로 3684)
            end_idx = min(len(df), 3690+5)  # 3695번째 행
            
            print(f"   행 범위: {start_idx+1}~{end_idx}번째 행 확인")
            
            sample_df = df.iloc[start_idx:end_idx].copy()
            
            # 주요 컬럼들 확인
            key_columns = []
            for col in df.columns:
                col_str = str(col).lower()
                if any(keyword in col_str for keyword in ['case', 'markaz', 'indoor', 'date', 'qty']):
                    key_columns.append(col)
            
            if key_columns:
                print(f"   주요 컬럼: {key_columns[:5]}")
                for idx, row in sample_df.iterrows():
                    print(f"   행 {idx+1}: ", end="")
                    for col in key_columns[:3]:  # 처음 3개 컬럼만 표시
                        value = row[col] if pd.notna(row[col]) else 'NaN'
                        print(f"{col}={value} ", end="")
                    print()
            
            # 빈 행 확인
            print(f"\n📋 빈 행 분석:")
            empty_rows = []
            for i in range(3685, min(len(df), 3700)):
                row = df.iloc[i]
                non_null_count = row.count()
                if non_null_count == 0:
                    empty_rows.append(i+1)
                elif non_null_count < 5:  # 5개 미만의 값만 있는 행
                    print(f"   행 {i+1}: {non_null_count}개 값만 존재")
            
            if empty_rows:
                print(f"   완전히 빈 행: {empty_rows}")
            
            # 3691번째 행 이후 데이터 통계
            print(f"\n📊 3691번째 행 이후 데이터 통계:")
            after_3691 = df.iloc[3690:]  # 3691번째 행부터 (0-based)
            
            print(f"   3691번 이후 행 수: {len(after_3691)}")
            
            # DSV Al Markaz 관련 데이터 확인
            markaz_columns = []
            for col in df.columns:
                col_str = str(col).lower()
                if 'markaz' in col_str or 'al markaz' in col_str:
                    markaz_columns.append(col)
            
            if markaz_columns:
                print(f"   Al Markaz 관련 컬럼: {markaz_columns}")
                
                for col in markaz_columns:
                    # 3691 이전 vs 이후 비교
                    before_3691 = df.iloc[:3690][col].count()
                    after_3691_count = after_3691[col].count()
                    
                    print(f"   {col}:")
                    print(f"     3691 이전: {before_3691}개 값")
                    print(f"     3691 이후: {after_3691_count}개 값")
                    
                    # 3691 이후에 데이터가 있는지 확인
                    if after_3691_count > 0:
                        non_null_values = after_3691[col].dropna()
                        if len(non_null_values) > 0:
                            print(f"     3691 이후 샘플: {non_null_values.head().tolist()}")
                            total_qty = non_null_values.sum() if non_null_values.dtype in ['int64', 'float64'] else len(non_null_values)
                            print(f"     3691 이후 총량: {total_qty}")
            
        else:
            print(f"   ❌ 파일에 3691행이 없음 (총 {len(df)}행)")
            
    except Exception as e:
        print(f"❌ 파일 읽기 오류: {e}")

if __name__ == "__main__":
    check_hitachi_he_missing_data() 