# detailed_diagnose.py
import pandas as pd
from hvdc_ontology_pipeline import OntologyMapper, EnhancedDataLoader, EnhancedTransactionEngine, EnhancedAnalysisEngine

def analyze_markaz_transactions():
    """DSV Al Markaz 트랜잭션 상세 분석"""
    print("🔍 DSV Al Markaz 트랜잭션 상세 분석")
    print("=" * 60)
    
    # 데이터 로드
    mapper = OntologyMapper("mapping_rules_v2.4.json")
    loader = EnhancedDataLoader(mapper)
    raw_events = loader.load_and_process_files("data")
    
    # 트랜잭션 로그 생성
    tx_engine = EnhancedTransactionEngine(mapper)
    transaction_log = tx_engine.create_transaction_log(raw_events)
    
    # DSV Al Markaz 관련 트랜잭션만 필터링
    markaz_tx = transaction_log[transaction_log['Location'] == 'DSV Al Markaz']
    
    print(f"📊 DSV Al Markaz 트랜잭션 통계:")
    print(f"   총 트랜잭션: {len(markaz_tx)}건")
    
    if len(markaz_tx) > 0:
        # 트랜잭션 타입별 집계
        tx_summary = markaz_tx.groupby('TxType_Refined').agg({
            'Qty': ['count', 'sum']
        }).round(2)
        print(f"\n   트랜잭션 타입별 집계:")
        print(tx_summary)
        
        # 날짜별 누적 분석
        markaz_daily = markaz_tx.groupby(['Date', 'TxType_Refined']).agg({
            'Qty': 'sum'
        }).reset_index()
        
        markaz_pivot = markaz_daily.pivot_table(
            index='Date', 
            columns='TxType_Refined', 
            values='Qty', 
            fill_value=0
        )
        
        # 필요한 컬럼 추가
        for col in ['IN', 'TRANSFER_OUT', 'FINAL_OUT']:
            if col not in markaz_pivot.columns:
                markaz_pivot[col] = 0
        
        # 누적 재고 계산
        markaz_pivot['Net_Change'] = markaz_pivot['IN'] - markaz_pivot['TRANSFER_OUT'] - markaz_pivot['FINAL_OUT']
        markaz_pivot['Cumulative_Stock'] = markaz_pivot['Net_Change'].cumsum()
        
        print(f"\n   📅 일별 재고 변화 (최근 10일):")
        print(markaz_pivot.tail(10))
        
        print(f"\n   📈 최종 재고: {markaz_pivot['Cumulative_Stock'].iloc[-1]}박스")
        print(f"   📊 총 입고: {markaz_pivot['IN'].sum()}박스")
        print(f"   📊 총 이동출고: {markaz_pivot['TRANSFER_OUT'].sum()}박스")
        print(f"   📊 총 최종출고: {markaz_pivot['FINAL_OUT'].sum()}박스")
        
        # 기대값과 비교
        expected_stock = 812
        actual_stock = markaz_pivot['Cumulative_Stock'].iloc[-1]
        difference = actual_stock - expected_stock
        
        print(f"\n   🎯 기대값 비교:")
        print(f"   기대값: {expected_stock}박스")
        print(f"   실제값: {actual_stock}박스")
        print(f"   차이: {difference:+}박스")
        
        if difference < 0:
            print(f"   💡 분석: {abs(difference)}박스 부족 → 입고 이벤트 누락 가능성")
        else:
            print(f"   💡 분석: {difference}박스 초과 → 출고 이벤트 누락 가능성")

if __name__ == "__main__":
    analyze_markaz_transactions() 