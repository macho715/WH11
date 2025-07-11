# HVDC 재고 관리 시스템 (WH5)

## 📋 개요

HVDC 재고 관리 시스템은 Excel 기반의 창고 데이터를 처리하여 일별 재고를 계산하고, 기대값과 비교하며, 종합적인 Excel 리포트를 생성하는 완전한 재고 관리 솔루션입니다.

## 🏗️ 시스템 구조

```
WH5/
├── 📁 core/                    # 핵심 모듈
│   ├── deduplication.py       # 중복 제거 및 TRANSFER 보정
│   ├── inventory_engine.py    # 재고 계산 엔진
│   ├── loader.py              # 데이터 로더
│   ├── config_manager.py      # 설정 관리
│   ├── helpers.py             # 유틸리티 함수
│   └── timeline.py            # 타임라인 추적
├── 📁 data/                   # Excel 데이터 파일
├── 📁 scripts/                # 스크립트 파일들
├── 📁 tools/                  # 도구 파일들
├── 📁 tests/                  # 테스트 파일들
├── 📁 config/                 # 설정 파일들
├── 📁 docs/                   # 문서
├── main.py                    # 메인 실행 파일
├── excel_reporter.py          # Excel 리포트 생성기 ✨ NEW
├── test_excel_reporter.py     # Excel 리포트 테스트 ✨ NEW
├── expected_stock.yml         # 기대 재고 설정
├── config.py                  # 설정 로더
├── mapping_rules_v2.4.json    # 온톨로지 매핑 규칙
└── requirements.txt           # 의존성 파일
```

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# Python 3.8+ 설치 확인
python --version

# 의존성 설치
pip install -r requirements.txt
```

### 2. 데이터 준비

`data/` 폴더에 다음 Excel 파일들을 배치:
- `HVDC WAREHOUSE_HITACHI(HE).xlsx`
- `HVDC WAREHOUSE_HITACHI(HE-0214,0252).xlsx`
- `HVDC WAREHOUSE_HITACHI(HE_LOCAL).xlsx`
- `HVDC WAREHOUSE_SIMENSE(SIM).xlsx`

### 3. 기대값 설정

`expected_stock.yml` 파일에 검증 기준일과 기대 재고를 설정:

```yaml
"2025-06-24":
  DSV Al Markaz: 812
  DSV Indoor: 414
"2025-06-25":
  DSV Al Markaz: 805
  DSV Indoor: 418
"2025-07-01":
  DSV Al Markaz: 812
  DSV Indoor: 414
```

### 4. 프로그램 실행

#### 기본 재고 계산
```bash
# 기본 실행 (오늘 날짜 기준)
python main.py

# 특정 날짜 기준 실행
python main.py --asof 2025-07-01

# 다른 데이터 폴더 지정
python main.py --asof 2025-07-01 --src /path/to/data

# 디버그 모드 실행
python main.py --debug
```

#### Excel 리포트 생성 ✨ NEW
```bash
# 종합 Excel 리포트 생성
python test_excel_reporter.py

# 또는 메인 시스템과 함께 실행
python main.py --debug
```

## 🔧 핵심 기능

### 1. 데이터 처리 파이프라인

1. **데이터 로딩**: Excel 파일에서 원시 이벤트 추출
2. **트랜잭션 생성**: 이벤트를 트랜잭션 로그로 변환
3. **TRANSFER 보정**: 양방향 보정 로직으로 짝 맞춤
4. **중복 제거**: 중복 트랜잭션 제거
5. **검증**: TRANSFER 짝 및 날짜 순서 검증
6. **재고 계산**: 일별 재고 스냅샷 생성
7. **결과 비교**: 계산된 재고와 기대값 비교
8. **Excel 리포트 생성**: 종합적인 분석 리포트 생성 ✨ NEW

### 2. 양방향 TRANSFER 보정

- **문제**: TRANSFER_IN만 있고 TRANSFER_OUT이 없는 케이스 또는 그 반대
- **해결**: 자동으로 누락된 짝을 생성하여 데이터 무결성 보장
- **성과**: 559건의 TRANSFER 불일치를 완전히 해결

### 3. 재고 계산 로직

```
재고 = 초기재고 + 입고 - 출고
```

- **루프 기반 계산**: 각 트랜잭션마다 순차적으로 재고 업데이트
- **창고별 분리**: 각 창고별로 독립적인 재고 계산
- **일별 스냅샷**: 매일의 재고 상태를 기록

### 4. Excel 리포트 생성 ✨ NEW

#### 📊 생성되는 시트들
1. **01_종합대시보드** - 전체 요약 및 KPI
2. **02_창고별상세** - 창고별 입고/출고/재고
3. **03_현장별상세** - 현장 배송 현황
4. **04_공급사별상세** - 공급사별 공급 현황
5. **05_월별트렌드** - 월별 입고/출고 추이
6. **06_재고스냅샷** - 최신 재고 현황
7. **07_트랜잭션로그** - 상세 트랜잭션 기록
8. **08_원시데이터** - 디버그용 원시 데이터

#### 🎯 주요 기능
- **한글 컬럼명** 및 **한국어 시트명** 지원
- **자동 파일명 생성** (날짜/시간 포함)
- **데이터 크기 제한** (1,000건)으로 성능 최적화
- **디버그 모드** 지원
- **오류 처리** 및 **로깅**

## 📊 실행 결과 예시

### 메인 시스템 실행
```
✅ 온톨로지 매핑 룰 로드 완료: mapping_rules_v2.4.json
📄 파일 처리 중: HVDC WAREHOUSE_HITACHI(HE).xlsx
   📅 날짜 컬럼 13개 발견
   ✅ 4038건 이벤트 추출
📊 총 5,680건의 원시 이벤트 수집
🔄 트랜잭션 로그 생성 중...
📊 트랜잭션 타입 분포:
   IN: 4,685건 (75.1%)
   TRANSFER_OUT: 559건 (9.0%)
   TRANSFER_IN: 559건 (9.0%)
   FINAL_OUT: 436건 (7.0%)
🛠️  AUTO-FIX 추가: IN→OUT 0건 / OUT→IN 559건
Rows before/after dedup: 6239 → 6239
📊 일별 재고 계산 중...
✅ 46개 일별 재고 스냅샷 생성

📊 재고 검증 결과
✅ DSV Al Markaz    813 EA | Δ +1 (기대 812)
✅ DSV Indoor       413 EA | Δ -1 (기대 414)
ℹ️ DSV Outdoor    1300 EA (기대값 없음)
```

### Excel 리포트 생성 ✨ NEW
```
📊 Excel 리포트 생성 시작...
📄 01_종합대시보드 시트 생성 완료
📄 02_창고별상세 시트 생성 완료
📄 03_현장별상세 시트 생성 완료
📄 04_공급사별상세 시트 생성 완료
📄 05_월별트렌드 시트 생성 완료
📄 06_재고스냅샷 시트 생성 완료
📄 07_트랜잭션로그 시트 생성 완료
📄 08_원시데이터 시트 생성 완료
✅ Excel 리포트 생성 완료: HVDC_테스트리포트_20250624_1620.xlsx
```

## 🔍 주요 모듈 설명

### `main.py` - 메인 실행 파일
- **역할**: 전체 파이프라인 조율
- **주요 함수**:
  - `main()`: 메인 실행 로직
  - `compare_stock_vs_expected()`: 재고와 기대값 비교
  - `get_latest_inventory_summary()`: 최신 재고 요약

### `excel_reporter.py` - Excel 리포트 생성기 ✨ NEW
- **역할**: 종합적인 Excel 분석 리포트 생성
- **주요 함수**:
  - `generate_excel_comprehensive_report()`: 메인 리포트 생성 함수
  - `create_dashboard_sheet()`: 종합 대시보드 생성
  - `create_warehouse_detail_sheet()`: 창고별 상세 분석
  - `create_site_detail_sheet()`: 현장별 상세 분석
  - `create_supplier_detail_sheet()`: 공급사별 상세 분석
  - `create_monthly_trend_sheet()`: 월별 트렌드 분석
  - `create_stock_snapshot_sheet()`: 재고 스냅샷 생성
  - `create_transaction_log_sheet()`: 트랜잭션 로그 생성
  - `create_raw_data_sheet()`: 원시 데이터 생성

### `test_excel_reporter.py` - Excel 리포트 테스트 ✨ NEW
- **역할**: Excel 리포트 생성 기능 테스트
- **주요 기능**:
  - 데이터 로딩 및 전처리
  - 재고 계산
  - Excel 리포트 생성
  - 결과 검증

### `core/deduplication.py` - 중복 제거 및 보정
- **역할**: 데이터 무결성 보장
- **주요 함수**:
  - `reconcile_orphan_transfers()`: TRANSFER 짝 보정
  - `drop_duplicate_transfers()`: 중복 제거
  - `DeduplicationEngine`: 종합적 중복 제거 엔진

### `core/inventory_engine.py` - 재고 계산 엔진
- **역할**: 재고 계산 및 검증
- **주요 함수**:
  - `validate_transfer_pairs()`: TRANSFER 짝 검증
  - `validate_date_sequence()`: 날짜 순서 검증
  - `InventoryEngine`: 종합적 재고 계산 엔진

### `core/loader.py` - 데이터 로더
- **역할**: Excel 파일 로딩 및 전처리
- **주요 기능**:
  - Excel 파일 자동 감지
  - 날짜 컬럼 자동 인식
  - 데이터 정규화

## ⚙️ 설정 파일

### `expected_stock.yml`
```yaml
"2025-06-24":
  DSV Al Markaz: 812
  DSV Indoor: 414
"2025-06-25":
  DSV Al Markaz: 805
  DSV Indoor: 418
```

### `mapping_rules_v2.4.json`
- 온톨로지 매핑 규칙
- 창고명, 트랜잭션 타입 매핑
- 데이터 정규화 규칙

## 🛠️ 문제 해결

### 1. TRANSFER 불일치 오류
```
ValueError: TRANSFER 짝 불일치: 559 케이스
```
- **원인**: TRANSFER_IN과 TRANSFER_OUT의 짝이 맞지 않음
- **해결**: 양방향 보정 로직이 자동으로 처리

### 2. 날짜 역순 오류
```
ValueError: 날짜 역순 Case 559개
```
- **원인**: AUTO_FIX 레코드의 날짜가 부적절
- **해결**: 기존 Case의 날짜를 참조하여 설정

### 3. 기대값 없음
```
ℹ️ dsv al markaz: 0 EA (기대값 없음)
```
- **원인**: `expected_stock.yml`에 해당 날짜의 기대값이 없음
- **해결**: 기대값 파일에 해당 날짜 추가

### 4. Excel 리포트 생성 오류 ✨ NEW
```
ValueError: Excel 파일 크기 제한 초과
```
- **원인**: 데이터가 1,000건을 초과함
- **해결**: 자동으로 데이터를 1,000건으로 제한하여 처리

## 📈 성능 지표

### 데이터 처리 성과
- **원시 데이터**: 5,680건 이벤트
- **전처리 완료**: 6,239건 트랜잭션
- **고유 케이스**: 3,688건
- **총 창고**: 10개소
- **총 재고**: 3,690 EA

### 트랜잭션 타입별 분포
- **IN**: 4,685건 (75.1%)
- **TRANSFER_OUT**: 559건 (9.0%)
- **TRANSFER_IN**: 559건 (9.0%)
- **FINAL_OUT**: 436건 (7.0%)

### 상위 창고별 재고 현황
1. **DSV Indoor**: 1,416 EA
2. **DSV Outdoor**: 826 EA
3. **DAS**: 703 EA
4. **DSV Al Markaz**: 341 EA
5. **SHU**: 264 EA

### 시스템 성능
- **TRANSFER 보정**: 559건 불일치 → 0건 (100% 해결)
- **재고 계산**: 46개 일별 스냅샷 생성
- **검증 정확도**: 기대값 대비 ±2 EA 이내
- **Excel 리포트**: 8개 시트 자동 생성

## 🔄 업데이트 내역

### v2.4 (최신) ✨ NEW
- ✅ **Excel Reporter 시스템** 완전 구현
- ✅ **8개 시트 종합 리포트** 자동 생성
- ✅ **한글 컬럼명** 및 **한국어 시트명** 지원
- ✅ **양방향 TRANSFER 보정** 로직 구현
- ✅ **559건 TRANSFER 불일치** 완전 해결
- ✅ **안정적인 재고 계산** 파이프라인 구축
- ✅ **종합적인 데이터 검증** 시스템
- ✅ **디버그 모드** 및 **오류 처리** 완료

### v2.3
- ✅ 양방향 TRANSFER 보정 로직 구현
- ✅ 692건 TRANSFER 불일치 완전 해결
- ✅ 안정적인 재고 계산 파이프라인 구축
- ✅ 종합적인 데이터 검증 시스템

## 📞 지원

문제가 발생하거나 추가 기능이 필요한 경우:

### 1. 기본 문제 해결
1. 로그 파일 확인
2. 설정 파일 검증
3. 데이터 형식 확인
4. 기대값 설정 확인

### 2. Excel 리포트 관련 ✨ NEW
1. `test_excel_reporter.py` 실행 확인
2. Excel 파일 크기 제한 확인 (1,000건)
3. 한글 컬럼명 지원 확인
4. 디버그 모드 활성화

### 3. 시스템 테스트
```bash
# 전체 시스템 테스트
python test_system.py

# Excel 리포트 테스트
python test_excel_reporter.py

# 메인 시스템 디버그 모드
python main.py --debug
```

---

## 🚀 Usage – Full Pipeline 예제

### 1) CLI 한 번에 실행

```bash
python main.py \
  --warehouse-file HVDC_WAREHOUSE_2024Q1.xlsx \
  --mapping-rules mapping_rules_v2.5.json \
  --output reports/HVDC_Q1_Dashboard.xlsx
```

위 명령은 다음을 수행합니다.

1. **`warehouse_loader`** 로 Excel → 표준 DataFrame 파싱
2. **`ontology_mapper`** 로 RDF 트리플(`hasAmount` 포함) 생성
3. **`inventory_engine`** 으로 월별 `Total_Amount` 집계
4. **`excel_reporter`** 로 KPI + FinancialSummary 시트를 포함한 Dashboard 출력

### 2) 파이썬 스크립트 예시

```python
from warehouse_loader import load_hvdc_warehouse_file
from inventory_engine import calculate_monthly_summary
from excel_reporter import generate_full_dashboard

# 1. 데이터 로드
raw_df = load_hvdc_warehouse_file("HVDC_WAREHOUSE_2024Q1.xlsx")

# 2. 월별 재고·금액 요약 계산
monthly_df = calculate_monthly_summary(raw_df)
print(monthly_df.head())

# 3. 대시보드 리포트 생성
generate_full_dashboard(raw_df, "reports/HVDC_Q1_Dashboard.xlsx")
```

---

## 🗒️ CHANGELOG

| 날짜         | 버전     | 주요 변경                                                                                   |
| ---------- | ------ | --------------------------------------------------------------------------------------- |
| 2025‑06‑24 | v0.5   | **excel_reporter**: FinancialSummary 시트, `Total_Amount` 콤마 및 Conditional Formatting 추가 |
| 2025‑06‑24 | v0.4   | **inventory_engine**: `calculate_monthly_summary()` 에 Amount 합계 지원                     |
| 2025‑06‑24 | v0.3.1 | **ontology_mapper**: `hasAmount` 데이터타입 프로퍼티 및 매핑 로직 추가                                 |
| 2025‑06‑24 | v0.3   | **mapping_rules_v2.5.json**: `hasAmount` 필드 정의, 규칙 버전업                                |
| 2025‑06‑24 | v0.2   | **warehouse_loader**: HVDC 전용 Excel 파서 초기 구현                                           |

---

## 📄 라이선스

MIT

---

**HVDC 재고 관리 시스템 v2.4** - 안정적이고 정확한 재고 관리 솔루션 + 종합 Excel 리포트 생성 기능 🚀
