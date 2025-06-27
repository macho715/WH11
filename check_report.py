#!/usr/bin/env python3
import pandas as pd
import os

# 최신 리포트 파일 찾기
report_files = [f for f in os.listdir('.') if f.startswith('HVDC_최종통합리포트') and f.endswith('.xlsx')]
latest_report = max(report_files, key=os.path.getctime)

print(f"📊 최신 리포트 파일: {latest_report}")
print("=" * 50)

# 시트 목록 확인
xl = pd.ExcelFile(latest_report)
print("📋 시트 목록:")
for i, sheet in enumerate(xl.sheet_names, 1):
    print(f"  {i:2d}. {sheet}")

print("\n" + "=" * 50)

# 공급사별 시트 확인
vendor_sheets = [sheet for sheet in xl.sheet_names if sheet.endswith('_월별집계')]
if vendor_sheets:
    print("🏢 공급사별 월별집계 시트:")
    for sheet in vendor_sheets:
        print(f"  ✅ {sheet}")
else:
    print("⚠️ 공급사별 월별집계 시트가 없습니다.")

# ALL 시트 확인
if 'ALL_월별집계' in xl.sheet_names:
    print("✅ ALL_월별집계 시트 존재")
else:
    print("⚠️ ALL_월별집계 시트가 없습니다.")

print("\n" + "=" * 50)

# 샘플 데이터 확인
if 'ALL_월별집계' in xl.sheet_names:
    df = pd.read_excel(latest_report, sheet_name='ALL_월별집계')
    print("📊 ALL_월별집계 샘플 데이터 (처음 3행):")
    print(df.head(3))
    
    print(f"\n📈 컬럼 목록: {list(df.columns)}")
    
    if '합계' in df['월'].values:
        print("✅ 합계 행이 포함되어 있습니다.")
    else:
        print("⚠️ 합계 행이 없습니다.") 