# main.py

# 1. 데이터 정규화 및 온톨로지 파이프라인
from hvdc_ontology_pipeline import OntologyMapper, EnhancedDataLoader, EnhancedTransactionEngine, EnhancedAnalysisEngine

# 2. 검증 및 리포트 생성 엔진
from enhanced_inventory_validator import EnhancedInventoryValidator
from hvdc_korean_excel_report import create_korean_excel_report

# 3. 비용/인보이스/통합 분석 엔진
from hvdc_cost_enhanced_analysis import CostAnalysisEngine
from hvdc_integrated_invoice_analysis import IntegratedAnalyzer

def main():
    print("\n[1] 온톨로지/정규화 및 데이터 로드")
    mapper = OntologyMapper("mapping_rules_v2.4.json")
    loader = EnhancedDataLoader(mapper)
    raw_events = loader.load_and_process_files("data")
    
    print("\n[2] 트랜잭션 생성 및 월별 집계/검증")
    tx_engine = EnhancedTransactionEngine(mapper)
    transaction_log = tx_engine.create_transaction_log(raw_events)
    analysis_engine = EnhancedAnalysisEngine(mapper)
    daily_stock = analysis_engine.calculate_daily_stock(transaction_log)
    monthly_summary = analysis_engine.create_monthly_summary(transaction_log, daily_stock)
    validation_result = analysis_engine.validate_stock_integrity(daily_stock)
    
    print("\n[3] 고급 재고 검증(추가로 필요시)")
    validator = EnhancedInventoryValidator()
    # 예시: validator.validate_user_inventory_logic(...), validator.run_comprehensive_validation(...)
    # (원하면 주석 해제 후 활용)
    
    print("\n[4] 한국어 리포트 생성")
    create_korean_excel_report()
    
    print("\n[5] (선택) 인보이스/비용/통합 분석 리포트")
    # 비용 분석 등은 실무에서 필요할 때만 호출
    # 예시:
    # cost_engine = CostAnalysisEngine(mapper)
    # cost_engine.load_invoice_cost_data('data/HVDC WAREHOUSE_INVOICE.xlsx')
    # 통합분석
    analyzer = IntegratedAnalyzer()
    analyzer.load_all_data()
    analyzer.perform_integrated_analysis()
    
    print("\n🎉 전체 메인 실행 완료!")

if __name__ == "__main__":
    main() 