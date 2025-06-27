# import pandas as pd
# import matplotlib.pyplot as plt
# import seaborn as sns
from excel_reporter import normalize_location_column

def visualize_out_transactions(transaction_df, threshold_std=2.0):
    """
    OUT 트랜잭션 월별/창고별 시각화 및 이상치 탐지
    Args:
        transaction_df: 트랜잭션 DataFrame (Location, Date, TxType_Refined, Qty 필수)
        threshold_std: 이상치 탐지 표준편차 기준 (default=2.0)
    Returns:
        None (그래프 출력 및 이상치 로그)
    """
    import matplotlib.pyplot as plt
    import seaborn as sns
    # 1. Location 정규화
    df = normalize_location_column(transaction_df.copy())
    df['월'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m')
    out_df = df[df['TxType_Refined'].isin(['TRANSFER_OUT', 'FINAL_OUT'])]

    if out_df.empty:
        print("❗ OUT 트랜잭션 데이터가 없습니다.")
        return

    # 2. 월별/창고별 OUT 집계
    pivot = (
        out_df.groupby(['월', 'Location'])['Qty']
        .sum()
        .unstack(fill_value=0)
    )

    # 3. 시각화
    plt.figure(figsize=(12, 6))
    sns.heatmap(pivot, annot=True, fmt=".0f", cmap="Reds")
    plt.title("월별·창고별 OUT 트랜잭션 집계")
    plt.ylabel("월")
    plt.xlabel("창고명")
    plt.tight_layout()
    plt.show()

    # 4. 이상치 탐지 (월별 합계 기준)
    out_monthly = out_df.groupby(['월', 'Location'])['Qty'].sum().reset_index()
    for location in out_monthly['Location'].unique():
        vals = out_monthly[out_monthly['Location'] == location]['Qty']
        mean = vals.mean()
        std = vals.std()
        for idx, qty in vals.iteritems():
            if std > 0 and abs(qty - mean) > threshold_std * std:
                print(f"⚠️ 이상치 감지: {location} {out_monthly.iloc[idx]['월']} - OUT {qty} (평균 {mean:.1f}, std {std:.1f})")

    # 5. OUT 트랜잭션 상위 TOP5 창고/월 출력
    top_out = out_monthly.sort_values('Qty', ascending=False).head(5)
    print("\n📈 OUT 트랜잭션 상위 TOP5:")
    print(top_out) 