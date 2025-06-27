# HVDC Warehouse Management System - 운영 안전장치 가이드

## 개요

이 문서는 HVDC Warehouse Management System의 **운영 안정성 100% 확보**를 위한 3가지 운영 안전장치 설치 및 적용 방법을 설명합니다.

## 1. Tolerance 우선순위 주석 추가

### 적용 완료 ✅
- **파일**: `core/config_manager.py`
- **위치**: 파일 최상단 (import문 위)
- **내용**: tolerance 적용 우선순위 규칙 명시

```python
"""
[주의] Tolerance 적용 우선순위:
  1. 창고별 값(tolerance["WAREHOUSE_NAME"])
  2. default 값(tolerance["default"])
  3. 전역 tolerance_pct
(실제 적용은 위 순서대로 찾음. 온톨로지와 창고명 완전 일치 필수)
"""
```

### 효과
- 개발자 및 운영자 실시간 인지 가능
- 유지보수 시 혼란 방지
- 운영 위험 최소화

## 2. CI Pre-commit 훅 설치

### 설치 방법

1. **pre-commit 설치** (최초 1회)
```bash
pip install pre-commit
```

2. **훅 설치**
```bash
pre-commit install
```

3. **수동 실행** (선택사항)
```bash
pre-commit run --all-files
```

### 포함된 검증 항목

- **YAML Lint**: YAML 문법 오류 검사
- **온톨로지 정합성**: 창고 ID 일치성 검증
- **코드 스타일**: trailing whitespace, end-of-file 등
- **Python 코드**: Black, Flake8 검사

### 효과
- YAML 오타, 온톨로지 불일치, tolerance 구조 오류를 commit 단계에서 즉시 차단
- 코드 품질 자동 관리

## 3. RDF 변환 자동화 명령

### 사용 방법

```bash
# 기본 RDF 변환
python tools/ontology_mapper.py

# SPARQL 쿼리 포함
python tools/ontology_mapper.py --sparql

# 온톨로지 검증 포함
python tools/ontology_mapper.py --validate

# 출력 파일 지정
python tools/ontology_mapper.py --output custom_output.ttl
```

### 생성되는 파일

- **RDF TTL**: `rdf_output/warehouse_ontology_YYYYMMDD_HHMMSS.ttl`
- **SPARQL 쿼리**: `rdf_output/sparql_queries.txt`

### 효과
- YAML 및 재고 데이터의 RDF/OWL 자동 변환
- 온톨로지 기반 표준화 및 질의 가능
- WMS/ERP/RDF 일관성 검증

## ✅ 최종 점검 체크리스트

| 항목                | 조치 방식       | 적용여부  | 비고                    |
| ----------------- | ----------- | ----- | --------------------- |
| tolerance 우선순위 주석 | 주석(코드수정X)   | ✅     | core/config_manager.py에 추가 |
| Pre-commit 훅      | 설정파일/스크립트   | ✅     | .pre-commit-config.yaml 생성 |
| RDF 자동화 명령        | 필요시 명령/스크립트 | ✅     | tools/ontology_mapper.py 생성 |

## 추가 설정 및 커스터마이징

### Pre-commit 훅 커스터마이징

`.pre-commit-config.yaml` 파일을 수정하여 추가 검증 규칙을 설정할 수 있습니다:

```yaml
# 추가 검증 규칙 예시
- repo: https://github.com/pycqa/isort
  rev: 5.12.0
  hooks:
    - id: isort
      args: [--profile=black]
```

### RDF 변환 커스터마이징

`tools/ontology_mapper.py`를 수정하여 추가 온톨로지 클래스나 속성을 정의할 수 있습니다.

## 문제 해결

### Pre-commit 훅 오류 시

1. **개별 훅 실행**
```bash
pre-commit run yamllint
pre-commit run yaml-ontology-validate
```

2. **훅 건너뛰기** (긴급 시)
```bash
git commit --no-verify
```

### RDF 변환 오류 시

1. **필수 파일 확인**
   - `mapping_rules_v2.4.json`
   - `expected_stock.yml`

2. **출력 디렉토리 권한 확인**
   - `rdf_output/` 디렉토리 생성 권한

## 연락처 및 지원

추가 설정, 커스터마이징, 문제 해결이 필요한 경우:

- **문서**: 이 가이드 및 README.md 참조
- **스크립트**: `tools/` 디렉토리의 각 스크립트 참조
- **설정**: `config/` 디렉토리의 설정 파일 참조

---

**이 3가지 운영 안전장치만 추가하면 온톨로지·정합성·자동화·유지보수 모두 "최상" 수준으로 확보됩니다.** 