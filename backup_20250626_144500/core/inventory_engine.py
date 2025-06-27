"""inventory_engine.py – v0.4 (2025‑06‑24)

HVDC Warehouse 재고·금액 집계 엔진
=================================
* 주요 변경
  - **Amount 합계**를 포함한 `calculate_monthly_summary()` 구현.
  - `Incoming`·`Outgoing`·`Inventory` 집계와 함께 월간 **Total_Amount** 반환.
  - Billing month 자동 파싱(`to_datetime`) + xls 템플릿 호환 컬럼 별칭 지원.

Note
----
이 모듈은 전처리된 DataFrame(표준 컬럼: `Incoming`, `Outgoing`, `Inventory`, `Amount`, `Billing month`) 을 입력으로 받아
일/월별 KPI를 계산한다. 외부 모듈(`warehouse_loader.py`, `deduplication.py`)에서 전처리가 완료된 후 호출되는 것을 전제로 한다.
"""
from __future__ import annotations

import pandas as pd
from typing import Tuple


class InventoryEngine:
    """재고 및 금액 집계 전용 엔진."""

    def __init__(self, df: pd.DataFrame):
        # 내부 복사본 보존 – 후속 처리 안전
        self.df = df.copy()
        required_cols = {"Incoming", "Outgoing", "Amount", "Billing month"}
        missing = required_cols - set(self.df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

    # ------------------------------------------------------------------
    # Daily Inventory (단순 누적)
    # ------------------------------------------------------------------
    def calculate_daily_inventory(self) -> pd.DataFrame:
        """prev + Incoming – Outgoing 계산 후 `Inventory` 컬럼 반환."""
        self.df = self.df.sort_values("Start")  # 날짜순 보장
        self.df["Inventory"] = (self.df["Incoming"].fillna(0) - self.df["Outgoing"].fillna(0)).cumsum()
        return self.df

    # ------------------------------------------------------------------
    # Monthly Summary with Amount
    # ------------------------------------------------------------------
    def calculate_monthly_summary(self) -> pd.DataFrame:
        """Billing month 별 KPI + Total_Amount 반환."""
        # Billing month 파싱 → PeriodIndex(M)
        billing_dt = pd.to_datetime(self.df["Billing month"], errors="coerce")
        if billing_dt.isna().any():
            raise ValueError("Billing month parsing failed for some rows.")
        self.df["billing_period"] = billing_dt.dt.to_period("M")

        agg_df = (
            self.df.groupby("billing_period").agg(
                Incoming=("Incoming", "sum"),
                Outgoing=("Outgoing", "sum"),
                End_Inventory=("Inventory", "last"),
                Total_Amount=("Amount", "sum"),
            )
        )

        return agg_df.reset_index().rename(columns={"billing_period": "Billing Month"})


# ----------------------------------------------------------------------
# Demo CLI (python -m inventory_engine <excel_path>)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from warehouse_loader import load_hvdc_warehouse_file

    if len(sys.argv) != 2:
        sys.exit("Usage: python -m inventory_engine <excel_path>")

    path = sys.argv[1]
    df_original = load_hvdc_warehouse_file(path)
    engine = InventoryEngine(df_original)
    df_daily = engine.calculate_daily_inventory()
    df_monthly = engine.calculate_monthly_summary()

    print("--- Daily Inventory (tail) ---")
    print(df_daily.tail())

    print("\n--- Monthly Summary ---")
    print(df_monthly) 