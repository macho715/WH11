# scripts/diagnose_transfer_mismatch.py
import pandas as pd
from pathlib import Path

log = pd.read_parquet("artifacts/transaction_log.parquet")   # 현재 로그

# 1. Tx 열 자동 탐지
tx_col = next(c for c in ['Transaction_Type','TxType_Refined'] if c in log.columns)

# 2. TRANSFER 짝 Pivot
pvt = (log[log[tx_col].str.contains('TRANSFER', na=False)]
       .pivot_table(index=['Case_No','Loc_From','Loc_To'],
                    columns=tx_col, values='Qty', aggfunc='sum')
       .fillna(0))

mismatch = pvt[(pvt.get('TRANSFER_IN',0) - pvt.get('TRANSFER_OUT',0)).abs() != 0]
print(f"⚠️ 짝 안 맞은 Transfer: {len(mismatch)} 건")
print(mismatch.head(10)) 