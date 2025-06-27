import os
import pandas as pd
import pytest

# 단계별 엔진 import
from core.inventory_engine import InventoryEngine
from excel_reporter import generate_financial_report
from ontology_mapper import dataframe_to_rdf  # 가정: DataFrame→RDF 함수


def _sample_df():
    """파이프라인 통합 테스트용 6행 샘플."""
    data = {
        "Incoming": [7, 2, 10, 0, 1, 1],
        "Outgoing": [0, 0, 5, 3, 0, 0],
        "Inventory": [7, 9, 14, 11, 12, 13],
        "Amount": [58782.5, 5770.0, 45131.1, 29160.28, 3030.0, 515.0],
        "Billing month": [
            "2024-01-01",
            "2024-01-01",
            "2024-01-01",
            "2024-01-01",
            "2024-01-01",
            "2024-01-01",
        ],
        "Shipment No": [
            "HVDC-ADOPT-HE-0001",
            "HVDC-ADOPT-HE-0002",
            "HVDC-ADOPT-HE-0003",
            "HVDC-ADOPT-HE-0003",
            "HVDC-ADOPT-HE-0012",
            "HVDC-ADOPT-HE-0013",
        ],
        "Category": [
            "Outdoor",
            "Outdoor",
            "Outdoor",
            "Indoor(M44)",
            "Outdoor",
            "Outdoor",
        ],
    }
    return pd.DataFrame(data)


@pytest.fixture
def df():
    return _sample_df()


def test_end_to_end(tmp_path, df):
    """DataFrame → Ontology → Summary → Excel 리포트 End‑to‑End."""
    # 1) Ontology 변환 (유효성만 체크)
    rdf_path = dataframe_to_rdf(df, tmp_path / "test_output.ttl")  # Path 반환
    assert rdf_path.exists(), "RDF 파일이 생성되지 않음"
    assert rdf_path.stat().st_size > 0, "RDF 파일이 비어있음"

    # 2) 월별 합계 계산
    engine = InventoryEngine(df)
    summary = engine.calculate_monthly_summary()
    assert "Total_Amount" in summary.columns, "Total_Amount 컬럼 누락"
    jan_total = float(summary.loc[summary["Billing Month"].astype(str) == "2024-01", "Total_Amount"].iloc[0])
    assert pytest.approx(jan_total, rel=1e-6) == 142388.88, "샘플 합계 오류"  # 58,782.5+5,770+45,131.1+29,160.28+3,030+515 → 142,388.88

    # 3) Excel 리포트 생성
    out_file = tmp_path / "financial_report.xlsx"
    generate_financial_report(df, out_file)
    assert out_file.exists(), "Excel 리포트 파일이 생성되지 않음"

    # 4) 파일 크기 최소 확인 (>1 KB 예상)
    assert os.path.getsize(out_file) > 1 * 1024, "리포트 파일 크기가 비정상적으로 작음" 