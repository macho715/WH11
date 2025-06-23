# check_data_loading.py
import pandas as pd
from hvdc_ontology_pipeline import EnhancedDataLoader, OntologyMapper

def analyze_data_loading_process():
    """데이터 로딩 과정에서 누락되는 원인 분석"""
    print("🔍 데이터 로딩 과정 분석")
    print("=" * 60)
    
    filepath = "data/HVDC WAREHOUSE_HITACHI(HE).xlsx"
    
    # 1. 원본 Excel 파일 직접 읽기
    print("📄 1단계: 원본 Excel 파일 직접 분석")
    df_raw = pd.read_excel(filepath, sheet_name=0)
    print(f"   원본 파일 총 행 수: {len(df_raw)}")
    
    # Al Markaz 컬럼 확인
    markaz_col = None
    for col in df_raw.columns:
        if 'markaz' in str(col).lower():
            markaz_col = col
            break
    
    if markaz_col:
        print(f"   Al Markaz 컬럼: '{markaz_col}'")
        
        # 전체 데이터에서 Al Markaz 값 개수
        total_markaz = df_raw[markaz_col].count()
        print(f"   전체 Al Markaz 데이터: {total_markaz}개")
        
        # 3691 이전과 이후 분리
        before_3691 = df_raw.iloc[:3690][markaz_col].count()
        after_3691 = df_raw.iloc[3690:][markaz_col].count()
        
        print(f"   3691 이전: {before_3691}개")
        print(f"   3691 이후: {after_3691}개")
        print(f"   3691 이후 비율: {after_3691/total_markaz*100:.1f}%")
        
        # 3691 이후 데이터 샘플
        after_data = df_raw.iloc[3690:][markaz_col].dropna()
        if len(after_data) > 0:
            print(f"   3691 이후 샘플: {after_data.head().tolist()}")
    
    # 2. EnhancedDataLoader로 처리한 결과와 비교
    print(f"\n📊 2단계: EnhancedDataLoader 처리 결과 비교")
    
    mapper = OntologyMapper("mapping_rules_v2.4.json")
    loader = EnhancedDataLoader(mapper)
    
    # _process_warehouse_file 메서드 직접 호출하여 중간 과정 확인
    try:
        processed_df = loader._process_warehouse_file(filepath)
        print(f"   처리 후 총 이벤트: {len(processed_df)}")
        
        # DSV Al Markaz 이벤트 개수
        markaz_events = processed_df[processed_df['Location'] == 'DSV Al Markaz']
        print(f"   DSV Al Markaz 이벤트: {len(markaz_events)}")
        
        # 날짜 범위 확인
        if len(markaz_events) > 0:
            print(f"   Al Markaz 날짜 범위: {markaz_events['Date'].min()} ~ {markaz_events['Date'].max()}")
            
            # 날짜별 이벤트 분포
            date_counts = markaz_events['Date'].value_counts().sort_index()
            print(f"   날짜별 이벤트 (마지막 5일):")
            for date, count in date_counts.tail().items():
                print(f"     {date}: {count}건")
        
        # 3. 원본과 처리 후 비교
        print(f"\n🔍 3단계: 데이터 손실 분석")
        print(f"   원본 Al Markaz 데이터: {total_markaz}개")
        print(f"   처리 후 Al Markaz 이벤트: {len(markaz_events)}개")
        print(f"   손실률: {(total_markaz - len(markaz_events))/total_markaz*100:.1f}%")
        
        if total_markaz != len(markaz_events):
            print(f"   ⚠️ {total_markaz - len(markaz_events)}개 데이터 손실 발생!")
            
            # 손실 원인 추정
            if after_3691 > 0 and len(markaz_events) < total_markaz:
                print(f"   💡 추정 원인: 3691번 이후 {after_3691}개 데이터 처리 누락")
        
    except Exception as e:
        print(f"   ❌ 처리 중 오류: {e}")

if __name__ == "__main__":
    analyze_data_loading_process() 