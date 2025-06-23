# main.py

# 1. 데이터 정규화 및 온톨로지 파이프라인
from hvdc_ontology_pipeline import OntologyMapper, EnhancedDataLoader, EnhancedTransactionEngine, EnhancedAnalysisEngine

# 2. 검증 및 리포트 생성 엔진
from enhanced_inventory_validator import EnhancedInventoryValidator
from hvdc_korean_excel_report import create_korean_excel_report

# 3. 비용/인보이스/통합 분석 엔진
from hvdc_cost_enhanced_analysis import CostAnalysisEngine
from hvdc_integrated_invoice_analysis import IntegratedAnalyzer

def get_latest_inventory_summary(expected_values=None, tolerance=2):
    """
    최신 데이터 기준 DSV Al Markaz, DSV Indoor의 최신 재고 집계 및 기대값과의 비교 자동 리포트
    """
    if expected_values is None:
        # 기본값을 None으로 두어 하드코딩 방지 - 실제 운영에서는 DB/API에서 가져와야 함
        expected_values = None  # {"DSV Al Markaz": 812, "DSV Indoor": 414} - 하드코딩 제거
    mapper = OntologyMapper("mapping_rules_v2.4.json")
    loader = EnhancedDataLoader(mapper)
    raw_events = loader.load_and_process_files("data")
    tx_engine = EnhancedTransactionEngine(mapper)
    transaction_log = tx_engine.create_transaction_log(raw_events)
    analysis_engine = EnhancedAnalysisEngine(mapper)
    daily_stock = analysis_engine.calculate_daily_stock(transaction_log)
    print("\n🔎 **창고별 재고 검증 결과**")
    result = {}
    if "Location" in daily_stock.columns and "Closing_Stock" in daily_stock.columns and "Date" in daily_stock.columns:
        latest = daily_stock.sort_values("Date").groupby("Location").tail(1)
        if expected_values:  # expected_values가 None이 아닌 경우에만 실행
            for wh, expected in expected_values.items():
                row = latest[latest["Location"] == wh]
                if not row.empty:
                    actual = int(round(row["Closing_Stock"].values[0]))
                    diff = actual - expected
                    ratio = 0
                    if expected:
                        ratio = diff / expected * 100
                    # 근사/불일치 메시지
                    if abs(diff) <= tolerance:
                        msg = "✅"
                        explain = f"{actual}박스 (근사치, 기대 {expected})"
                    else:
                        msg = "❌"
                        explain = f"실제 재고: {actual}박스 | 기대값: {expected}박스 | 차이: {diff:+}박스 ({ratio:+.1f}% {'초과' if diff>0 else '부족'})"
                    print(f"{msg} **{wh}**: {explain}")
                    result[wh] = {"actual": actual, "expected": expected, "diff": diff, "diff_ratio": ratio}
                else:
                    print(f"❌ **{wh}**: 데이터 없음")
                    result[wh] = None
        else:
            # expected_values가 None인 경우 실제 재고만 출력
            print("📊 **실제 재고 현황** (기대값 없음 - 하드코딩 제거됨)")
            for _, row in latest.iterrows():
                location = row["Location"]
                actual = int(round(row["Closing_Stock"]))
                print(f"📦 **{location}**: {actual}박스")
                result[location] = {"actual": actual, "expected": None, "diff": None, "diff_ratio": None}
    else:
        print("❌ 재고 집계 DataFrame 구조 오류")
    return result

def main():
    # 1. 데이터 적재 및 검증/집계 자동 실행
    get_latest_inventory_summary()
    # 2. 추가 리포트/자동화 등...
    # create_korean_excel_report(), 통합 분석 등 필요시 추가

if __name__ == "__main__":
    main() 