# quick_diagnose.py
import pandas as pd
import re
import glob
import os
from hvdc_ontology_pipeline import EnhancedDataLoader, OntologyMapper

def diagnose_missing_events():
    """누락 이벤트 진단 스크립트"""
    print("🔍 누락 이벤트 진단 시작")
    print("=" * 50)
    
    # ① 실제 Excel 파일들 처리
    mapper = OntologyMapper("mapping_rules_v2.4.json")
    loader = EnhancedDataLoader(mapper)
    
    # 각 파일별로 컬럼 분석
    data_files = glob.glob("data/HVDC WAREHOUSE_*.xlsx")
    
    for filepath in data_files:
        if 'invoice' in filepath.lower():
            continue  # 인보이스 파일 제외
            
        filename = os.path.basename(filepath)
        print(f"\n📄 파일 분석: {filename}")
        
        try:
            # Excel 파일 읽기
            df = pd.read_excel(filepath, sheet_name=0)
            print(f"   총 컬럼 수: {len(df.columns)}")
            
            # ② 아직 창고가 지정되지 않은 ETA/ETD 열 목록 출력
            suspects = []
            unknown_mapped = []
            
            for col in df.columns:
                col_str = str(col).lower()
                # MARKAZ 관련 의심스러운 컬럼 찾기
                if re.search(r'markaz.*(eta|etd|date|time)', col_str, re.I):
                    suspects.append(str(col))
                    # 현재 매핑 결과 확인
                    mapped_result = loader._extract_warehouse_from_column_name(str(col))
                    if mapped_result == 'UNKNOWN':
                        unknown_mapped.append(str(col))
            
            if suspects:
                print(f"   🔍 MARKAZ 관련 의심 컬럼: {suspects[:10]}")
                print(f"   ❌ UNKNOWN으로 매핑된 컬럼: {unknown_mapped[:10]}")
            
            # 기타 패턴 확인
            other_suspects = []
            for col in df.columns:
                col_str = str(col).lower()
                if any(keyword in col_str for keyword in ['markaz', 'almarkaz', 'm1']) and str(col) not in suspects:
                    other_suspects.append(str(col))
                    
            if other_suspects:
                print(f"   🔍 기타 MARKAZ 관련 컬럼: {other_suspects[:10]}")
                
        except Exception as e:
            print(f"   ❌ 파일 읽기 오류: {e}")
    
    print("\n" + "=" * 50)
    
    # ③ 실제 집계 결과 분석
    print("📊 현재 집계 결과 분석")
    raw_events = loader.load_and_process_files("data")
    
    # UNKNOWN 창고 확인
    unknown_events = raw_events[raw_events['Location'] == 'UNKNOWN']
    print(f"   UNKNOWN 위치 이벤트 수: {len(unknown_events)}")
    
    if len(unknown_events) > 0:
        print(f"   UNKNOWN 이벤트 샘플:")
        print(unknown_events[['Case_No', 'Date', 'Location', 'Qty', 'Source_File']].head())
    
    # Al Markaz 관련 통계
    markaz_events = raw_events[raw_events['Location'] == 'DSV Al Markaz']
    print(f"\n   DSV Al Markaz 이벤트 수: {len(markaz_events)}")
    if len(markaz_events) > 0:
        print(f"   DSV Al Markaz 총 수량: {markaz_events['Qty'].sum()}")
        print(f"   DSV Al Markaz 파일별 분포:")
        for source, group in markaz_events.groupby('Source_File'):
            print(f"     {os.path.basename(source)}: {len(group)}건, {group['Qty'].sum()}박스")

if __name__ == "__main__":
    diagnose_missing_events() 