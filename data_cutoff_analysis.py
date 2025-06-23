# data_cutoff_analysis.py
import pandas as pd
from hvdc_ontology_pipeline import OntologyMapper, EnhancedDataLoader, EnhancedTransactionEngine, EnhancedAnalysisEngine

def analyze_data_cutoff_timing():
    """기대값과 집계 시점 일치 여부 확인"""
    print("🕐 데이터 Cut-off 시점 분석")
    print("=" * 60)
    
    # 데이터 로드
    mapper = OntologyMapper("mapping_rules_v2.4.json")
    loader = EnhancedDataLoader(mapper)
    raw_events = loader.load_and_process_files("data")
    
    # 트랜잭션 로그 생성
    tx_engine = EnhancedTransactionEngine(mapper)
    transaction_log = tx_engine.create_transaction_log(raw_events)
    
    # DSV Al Markaz & DSV Indoor 분석
    markaz_tx = transaction_log[transaction_log['Location'] == 'DSV Al Markaz']
    indoor_tx = transaction_log[transaction_log['Location'] == 'DSV Indoor']
    
    print("📊 데이터 범위 분석:")
    print(f"   전체 데이터 기간: {transaction_log['Date'].min()} ~ {transaction_log['Date'].max()}")
    
    if len(markaz_tx) > 0:
        print(f"   DSV Al Markaz 기간: {markaz_tx['Date'].min()} ~ {markaz_tx['Date'].max()}")
        print(f"   DSV Al Markaz 마지막 트랜잭션: {markaz_tx['Date'].max()}")
    
    if len(indoor_tx) > 0:
        print(f"   DSV Indoor 기간: {indoor_tx['Date'].min()} ~ {indoor_tx['Date'].max()}")
        print(f"   DSV Indoor 마지막 트랜잭션: {indoor_tx['Date'].max()}")
    
    # 특정 날짜까지 누적 계산 (예: 2024-06-23까지)
    cutoff_dates = ['2024-06-23', '2024-06-24', '2024-12-31']
    
    for cutoff_date in cutoff_dates:
        print(f"\n📅 {cutoff_date} 기준 재고 계산:")
        
        # 해당 날짜까지만 필터링
        filtered_tx = transaction_log[transaction_log['Date'] <= cutoff_date]
        
        # DSV Al Markaz
        markaz_filtered = filtered_tx[filtered_tx['Location'] == 'DSV Al Markaz']
        if len(markaz_filtered) > 0:
            markaz_in = markaz_filtered[markaz_filtered['TxType_Refined'] == 'IN']['Qty'].sum()
            markaz_transfer_out = markaz_filtered[markaz_filtered['TxType_Refined'] == 'TRANSFER_OUT']['Qty'].sum()
            markaz_final_out = markaz_filtered[markaz_filtered['TxType_Refined'] == 'FINAL_OUT']['Qty'].sum()
            markaz_stock = markaz_in - markaz_transfer_out - markaz_final_out
            
            print(f"   DSV Al Markaz: 입고 {markaz_in}, 출고 {markaz_transfer_out + markaz_final_out}, 재고 {markaz_stock}")
            
            # 기대값과 비교
            if abs(markaz_stock - 812) <= 10:  # 10박스 오차 허용
                print(f"   🎯 DSV Al Markaz: {markaz_stock}박스 ≈ 812박스 (목표 달성!)")
        
        # DSV Indoor
        indoor_filtered = filtered_tx[filtered_tx['Location'] == 'DSV Indoor']
        if len(indoor_filtered) > 0:
            indoor_in = indoor_filtered[indoor_filtered['TxType_Refined'] == 'IN']['Qty'].sum()
            indoor_transfer_out = indoor_filtered[indoor_filtered['TxType_Refined'] == 'TRANSFER_OUT']['Qty'].sum()
            indoor_final_out = indoor_filtered[indoor_filtered['TxType_Refined'] == 'FINAL_OUT']['Qty'].sum()
            indoor_stock = indoor_in - indoor_transfer_out - indoor_final_out
            
            print(f"   DSV Indoor: 입고 {indoor_in}, 출고 {indoor_transfer_out + indoor_final_out}, 재고 {indoor_stock}")
            
            # 기대값과 비교
            if abs(indoor_stock - 414) <= 10:  # 10박스 오차 허용
                print(f"   🎯 DSV Indoor: {indoor_stock}박스 ≈ 414박스 (목표 달성!)")

if __name__ == "__main__":
    analyze_data_cutoff_timing() 