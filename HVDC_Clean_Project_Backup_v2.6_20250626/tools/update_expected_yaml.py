import yaml, datetime as dt, sys
from pathlib import Path
import pandas as pd

CFG = Path(__file__).resolve().parent.parent / "config" / "expected_stock.yml"

def main(csv_path: str):
    df = pd.read_csv(csv_path)            # WMS Snapshot
    today = dt.date.today().isoformat()

    # 창고별 박스 합계 계산 (컬럼명은 상황에 맞게)
    expected = (
        df.groupby("Warehouse")["Box_Count"]
          .sum()
          .astype(int)
          .to_dict()
    )
    # YAML read-modify-write
    if CFG.exists():
        data = yaml.safe_load(open(CFG, "r", encoding="utf-8")) or {}
    else:
        data = {}

    data[today] = {k.lower(): int(v) for k, v in expected.items()}

    with open(CFG, "w", encoding="utf-8") as fp:
        yaml.safe_dump(data, fp, allow_unicode=True)
    print(f"[OK] {today} 기대값 업데이트 완료")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("사용법: python update_expected_yaml.py snapshot.csv")
    main(sys.argv[1]) 