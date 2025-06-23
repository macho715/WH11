# detailed_row_analysis.py
import pandas as pd

def analyze_3691_after_rows():
    """3691번 이후 행의 상세 분석"""
    print("🔍 3691번 이후 행 상세 분석")
    print("=" * 60)
    
    filepath = "data/HVDC WAREHOUSE_HITACHI(HE).xlsx"
    df = pd.read_excel(filepath, sheet_name=0)
    
    print(f"📄 파일: {filepath}")
    print(f"📊 총 행 수: {len(df)}")
    
    # 3691번 이후 데이터 추출
    after_3691 = df.iloc[3690:].copy()  # 3691번째 행부터
    print(f"📊 3691번 이후 행 수: {len(after_3691)}")
    
    # Al Markaz 컬럼 찾기
    markaz_col = None
    for col in df.columns:
        if 'markaz' in str(col).lower():
            markaz_col = col
            break
    
    if markaz_col:
        print(f"\n🎯 '{markaz_col}' 컬럼 분석:")
        
        # 3691 이후 Al Markaz 컬럼의 데이터 타입과 내용
        markaz_data = after_3691[markaz_col].dropna()
        print(f"   3691 이후 Non-null 값: {len(markaz_data)}개")
        
        if len(markaz_data) > 0:
            print(f"   데이터 타입: {markaz_data.dtype}")
            print(f"   첫 5개 값: {markaz_data.head(5).tolist()}")
            
            # 날짜인지 숫자인지 확인
            sample_value = markaz_data.iloc[0]
            print(f"   샘플 값: {sample_value} (타입: {type(sample_value)})")
            
            # 숫자인지 확인
            if pd.api.types.is_numeric_dtype(markaz_data):
                print(f"   📊 숫자 데이터 통계:")
                print(f"     합계: {markaz_data.sum()}")
                print(f"     평균: {markaz_data.mean():.2f}")
                print(f"     최대값: {markaz_data.max()}")
                print(f"     최소값: {markaz_data.min()}")
            elif pd.api.types.is_datetime64_any_dtype(markaz_data):
                print(f"   📅 날짜 데이터:")
                print(f"     최소 날짜: {markaz_data.min()}")
                print(f"     최대 날짜: {markaz_data.max()}")
                print(f"     유니크 날짜 수: {markaz_data.nunique()}")
                
                # 날짜별 카운트
                date_counts = markaz_data.value_counts().sort_index()
                print(f"     날짜별 분포:")
                for date, count in date_counts.items():
                    print(f"       {date.date()}: {count}건")
            else:
                print(f"   📝 기타 데이터 타입:")
                print(f"     유니크 값: {markaz_data.unique()[:10]}")
    
    # Case No. 컬럼과의 관계 확인
    case_col = None
    for col in df.columns:
        if 'case' in str(col).lower():
            case_col = col
            break
    
    if case_col:
        print(f"\n📦 '{case_col}' 컬럼 분석:")
        case_data = after_3691[case_col].dropna()
        print(f"   3691 이후 Case 수: {len(case_data)}개")
        
        if len(case_data) > 0:
            # 숫자형으로 변환 가능한지 확인
            try:
                case_numeric = pd.to_numeric(case_data, errors='coerce').dropna()
                if len(case_numeric) > 0:
                    print(f"   Case 번호 범위: {case_numeric.min()} ~ {case_numeric.max()}")
                else:
                    print(f"   Case 데이터가 숫자가 아님")
                    print(f"   샘플 값: {case_data.head(3).tolist()}")
            except:
                print(f"   Case 데이터 변환 오류")
                print(f"   샘플 값: {case_data.head(3).tolist()}")
            
            # Al Markaz와 Case가 모두 있는 행 확인
            if markaz_col:
                both_present = after_3691[(after_3691[case_col].notna()) & (after_3691[markaz_col].notna())]
                print(f"   Case와 Al Markaz 둘 다 있는 행: {len(both_present)}개")
                
                if len(both_present) > 0:
                    print(f"   샘플 행 (첫 3개):")
                    for idx, (_, row) in enumerate(both_present.head(3).iterrows()):
                        actual_row_num = row.name + 1  # 1-based 행 번호
                        case_val = row[case_col]
                        markaz_val = row[markaz_col]
                        print(f"     행 {actual_row_num}: Case={case_val}, Al Markaz={markaz_val}")

    print(f"\n💡 결론:")
    print(f"   3691번 이후 Al Markaz 컬럼에는 날짜 데이터만 있음")
    print(f"   이는 입고/출고 수량이 아닌 날짜 정보임")
    print(f"   따라서 388박스 부족의 원인은 다른 곳에 있을 수 있음")

if __name__ == "__main__":
    analyze_3691_after_rows() 