import pandas as pd
import pytest
from datetime import datetime

# 클래스 import 경로
from core.inventory_engine import InventoryEngine


def _build_sample_df():
    """테스트용 샘플 DataFrame 생성."""
    data = {
        "Incoming": [100, 50, 75, 0, 25],
        "Outgoing": [0, 20, 30, 10, 5],
        "Inventory": [100, 130, 175, 165, 185],
        "Amount": [10000.0, 5000.0, 7500.0, 0.0, 2500.0],
        "Billing month": [
            "2024-01-01",
            "2024-01-01", 
            "2024-01-01",
            "2024-01-01",
            "2024-01-01"
        ]
    }
    return pd.DataFrame(data)


def test_calculate_monthly_amount():
    """월별 금액 집계 기능 테스트."""
    df = _build_sample_df()
    inv = InventoryEngine(df)
    summary = inv.calculate_monthly_summary()

    # 2024-01 합계 검증
    jan_data = summary[summary["Billing Month"].astype(str) == "2024-01"]
    
    assert len(jan_data) == 1, "2024-01 데이터가 정확히 1행이어야 함"
    
    # 금액 합계: 10000 + 5000 + 7500 + 0 + 2500 = 25000
    expected_amount = 25000.0
    actual_amount = float(jan_data["Total_Amount"].iloc[0])
    
    assert pytest.approx(actual_amount, rel=1e-6) == expected_amount, \
        f"Expected {expected_amount}, got {actual_amount}"
    
    # 입고량 합계: 100 + 50 + 75 + 0 + 25 = 250
    expected_incoming = 250
    actual_incoming = int(jan_data["Incoming"].iloc[0])
    
    assert actual_incoming == expected_incoming, \
        f"Expected {expected_incoming}, got {actual_incoming}"
    
    # 출고량 합계: 0 + 20 + 30 + 10 + 5 = 65
    expected_outgoing = 65
    actual_outgoing = int(jan_data["Outgoing"].iloc[0])
    
    assert actual_outgoing == expected_outgoing, \
        f"Expected {expected_outgoing}, got {actual_outgoing}"
    
    # 기말재고: 마지막 행의 Inventory = 185
    expected_inventory = 185
    actual_inventory = int(jan_data["End_Inventory"].iloc[0])
    
    assert actual_inventory == expected_inventory, \
        f"Expected {expected_inventory}, got {actual_inventory}" 