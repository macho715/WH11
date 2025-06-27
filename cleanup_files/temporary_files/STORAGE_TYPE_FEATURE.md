# 🏷️ Storage Type 분류 기능

## 📋 개요

HVDC Warehouse 프로젝트에 **Storage Type 분류 기능**이 추가되었습니다. 이 기능은 창고 위치 정보를 기반으로 저장소 유형을 자동으로 분류하여 데이터 분석과 보고서 생성 시 더 정확한 인사이트를 제공합니다.

## 🎯 주요 기능

### 1. 자동 Storage Type 분류
- **Location** 컬럼을 기반으로 자동 분류
- `mapping_rules_v2.4.json` 파일의 규칙 활용
- 4가지 주요 카테고리로 분류

### 2. 분류 카테고리
```json
{
  "Indoor": ["DSV Indoor", "DSV Al Markaz", "Hauler Indoor"],
  "Outdoor": ["DSV Outdoor", "DSV MZP", "MOSB"],
  "Site": ["AGI", "DAS", "MIR", "SHU"],
  "dangerous_cargo": ["AAA Storage", "Dangerous Storage"]
}
```

## 🔧 구현 세부사항

### 1. DataLoader 클래스 확장

#### 새로운 메서드들:
```python
def classify_storage_type(self, location):
    """위치명을 기반으로 저장소 유형 분류"""
    
def add_storage_type(self, df):
    """DataFrame에 Storage_Type 컬럼 추가"""
```

#### 초기화 시 매핑 규칙 로드:
```python
def __init__(self):
    # mapping_rules_v2.4.json 불러오기
    rule_path = Path(__file__).parent / "../mapping_rules_v2.4.json"
    with open(rule_path, "r", encoding="utf-8") as f:
        self.mapping = json.load(f)["warehouse_classification"]
```

### 2. 트랜잭션 데이터에 Storage Type 포함

#### extract_transactions 메서드 개선:
```python
def extract_transactions(self, excel_files):
    for filename, df in excel_files.items():
        # Storage_Type 컬럼 추가
        if 'Location' in df.columns:
            df = self.add_storage_type(df)
            print(f"   🏷️ Storage_Type 컬럼 추가됨")
```

#### 트랜잭션 데이터 구조:
```python
{
    'source_file': 'filename.xlsx',
    'timestamp': datetime.now(),
    'data': {
        'case': 'CASE_001',
        'date': '2024-01-01',
        'warehouse': 'DSV Indoor',
        'incoming': 10,
        'outgoing': 0,
        'inventory': 10,
        'storage_type': 'Indoor',  # ← 새로운 필드
        'status_warehouse': '',
        'status_site': '',
        'status_current': '',
        'status_location': '',
        'status_storage': ''
    }
}
```

## 📊 사용 예시

### 1. 기본 사용법
```python
from core.loader import DataLoader

# DataLoader 인스턴스 생성
loader = DataLoader()

# Excel 파일 로드
excel_files = loader.load_excel_files("data")

# 트랜잭션 추출 (자동으로 Storage_Type 추가됨)
transactions = loader.extract_transactions(excel_files)
```

### 2. 수동 Storage Type 분류
```python
import pandas as pd

# 테스트 데이터
test_data = {
    'Location': ['DSV Indoor', 'DSV Outdoor', 'AGI', 'AAA Storage']
}
df = pd.DataFrame(test_data)

# Storage_Type 컬럼 추가
df_with_storage = loader.add_storage_type(df)
print(df_with_storage)
```

### 3. 분류 결과 확인
```python
# 분류 결과 확인
for idx, row in df_with_storage.iterrows():
    location = row['Location']
    storage_type = row['Storage_Type']
    print(f"{location} → {storage_type}")
```

## 🧪 테스트

### 테스트 스크립트 실행
```bash
python test_storage_type.py
```

### 예상 출력:
```
📋 매핑 규칙 파일 테스트
==================================================
📁 로드된 매핑 규칙:
   Indoor: ['DSV Indoor', 'DSV Al Markaz', 'Hauler Indoor']
   Outdoor: ['DSV Outdoor', 'DSV MZP', 'MOSB']
   Site: ['AGI', 'DAS', 'MIR', 'SHU']
   dangerous_cargo: ['AAA Storage', 'Dangerous Storage']

✅ 매핑 규칙 로드 완료!

🧪 Storage Type 분류 기능 테스트
==================================================
📊 테스트 데이터 생성: 11행
   컬럼: ['Location']

🏷️ Storage Type 분류 결과:
------------------------------
   DSV Indoor      → Indoor
   DSV Al Markaz   → Indoor
   DSV Outdoor     → Outdoor
   DSV MZP         → Outdoor
   MOSB            → Outdoor
   AGI             → Site
   DAS             → Site
   MIR             → Site
   SHU             → Site
   AAA Storage     → dangerous_cargo
   Unknown Location → Unknown

✅ 테스트 완료!
```

## 📈 데이터 분석 활용

### 1. Storage Type별 통계
```python
# Storage Type별 트랜잭션 수 집계
storage_stats = {}
for tx in transactions:
    storage_type = tx['data'].get('storage_type', 'Unknown')
    if storage_type not in storage_stats:
        storage_stats[storage_type] = 0
    storage_stats[storage_type] += 1

print("Storage Type별 트랜잭션 수:")
for storage_type, count in storage_stats.items():
    print(f"  {storage_type}: {count}건")
```

### 2. Storage Type별 재고 분석
```python
# Storage Type별 재고 현황
storage_inventory = {}
for tx in transactions:
    storage_type = tx['data'].get('storage_type', 'Unknown')
    inventory = tx['data'].get('inventory', 0)
    
    if storage_type not in storage_inventory:
        storage_inventory[storage_type] = 0
    storage_inventory[storage_type] += inventory

print("Storage Type별 총 재고:")
for storage_type, inventory in storage_inventory.items():
    print(f"  {storage_type}: {inventory}개")
```

## 🔄 매핑 규칙 관리

### 매핑 규칙 파일 위치
- **파일**: `mapping_rules_v2.4.json`
- **경로**: 프로젝트 루트 디렉토리

### 규칙 수정 방법
```json
{
  "warehouse_classification": {
    "Indoor": [
      "DSV Indoor",
      "DSV Al Markaz",
      "Hauler Indoor"
    ],
    "Outdoor": [
      "DSV Outdoor", 
      "DSV MZP",
      "MOSB"
    ],
    "Site": [
      "AGI",
      "DAS", 
      "MIR",
      "SHU"
    ],
    "dangerous_cargo": [
      "AAA Storage",
      "Dangerous Storage"
    ]
  }
}
```

## 🚀 향후 개선 계획

### 1. 동적 매핑 규칙
- 데이터베이스 기반 매핑 규칙 관리
- 실시간 규칙 업데이트

### 2. 머신러닝 기반 분류
- 위치명 패턴 학습
- 자동 분류 정확도 향상

### 3. 다국어 지원
- 한국어/영어 위치명 지원
- 지역별 창고명 매핑

## 📝 변경 이력

### v2.4 (현재)
- ✅ Storage Type 분류 기능 추가
- ✅ 매핑 규칙 파일 통합
- ✅ 트랜잭션 데이터에 Storage Type 포함
- ✅ 테스트 스크립트 작성

### v2.3 (이전)
- 기본 데이터 로딩 기능
- 트랜잭션 추출 기능

---

**작성자**: AI Assistant  
**최종 업데이트**: 2024년 12월  
**버전**: 2.4 