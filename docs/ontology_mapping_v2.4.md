# HVDC 온톨로지 매핑 시스템 v2.4

## 🎯 개요

HVDC 프로젝트의 온톨로지 매핑 시스템은 Excel 데이터를 표준화된 RDF/OWL 온톨로지로 변환하는 체계입니다.

## 📊 핵심 클래스 (Core Classes)

### 1. **TransportEvent** 
- **설명**: 물류 이동 이벤트
- **속성**: 
  - `hasCase`: 케이스 번호
  - `hasDate`: 이벤트 날짜
  - `hasQuantity`: 수량
  - `hasLocation`: 위치
  - `hasTransactionType`: 트랜잭션 타입 (IN/OUT/TRANSFER)

### 2. **StockSnapshot**
- **설명**: 특정 시점의 재고 상태
- **속성**:
  - `hasLocation`: 창고/현장 위치
  - `hasDate`: 스냅샷 날짜
  - `hasOpeningStock`: 기초재고
  - `hasInbound`: 입고량
  - `hasOutbound`: 출고량
  - `hasClosingStock`: 기말재고

### 3. **Warehouse**
- **설명**: 창고 위치
- **하위클래스**:
  - `IndoorWarehouse`: DSV Indoor, DSV Al Markaz, Hauler Indoor
  - `OutdoorWarehouse`: DSV Outdoor, DSV MZP, MOSB
  - `DangerousCargoWarehouse`: AAA Storage, Dangerous Storage

### 4. **Site**
- **설명**: 현장 위치
- **인스턴스**: AGI Site, DAS Site, MIR Site, SHU Site

### 5. **Case**
- **설명**: 물품 케이스
- **속성**:
  - `hasQuantity`: 수량
  - `hasCurrentLocation`: 현재 위치
  - `hasStatus`: 상태 정보

## 🔄 매핑 규칙 (Mapping Rules)

### Excel → 온톨로지 변환

```yaml
# mapping_rules_v2.4.json 구조

namespace: "http://samsung.com/project-logistics#"

class_mappings:
  TransportEvent: "TransportEvent"
  StockSnapshot: "StockSnapshot"
  Warehouse: "Warehouse"
  Site: "Site"
  Case: "Case"

property_mappings:
  Case_No: "hasCase"
  Date: "hasDate"
  Qty: "hasQuantity"
  Location: "hasLocation"
  TxType_Refined: "hasTransactionType"
  Status_Current: "hasCurrentStatus"
  Status_Location: "hasStatusLocation"
  Status_Storage: "hasStorageType"
```

### Status 매핑 로직

```python
# Excel Status → 온톨로지 클래스 매핑

Status_WAREHOUSE = 1 AND Status_Current = "창고":
  → rdf:type ex:Warehouse
  
Status_SITE = 1 AND Status_Current = "현장":
  → rdf:type ex:Site

Status_Storage = "Indoor":
  → rdf:type ex:IndoorWarehouse
  
Status_Storage = "Outdoor": 
  → rdf:type ex:OutdoorWarehouse
  
Status_Storage = "Site":
  → rdf:type ex:Site
  
Status_Storage = "dangerous cargo":
  → rdf:type ex:DangerousCargoWarehouse
```

## 📋 창고 분류 체계

### Indoor 그룹
```turtle
ex:DSVIndoor rdf:type ex:IndoorWarehouse ;
    ex:hasStorageType "Indoor" ;
    ex:hasCode "M44" .

ex:DSVAlMarkaz rdf:type ex:IndoorWarehouse ;
    ex:hasStorageType "Indoor" ;
    ex:hasCode "M1" .

ex:HaulerIndoor rdf:type ex:IndoorWarehouse ;
    ex:hasStorageType "Indoor" .
```

### Outdoor 그룹
```turtle
ex:DSVOutdoor rdf:type ex:OutdoorWarehouse ;
    ex:hasStorageType "Outdoor" .

ex:DSVMZP rdf:type ex:OutdoorWarehouse ;
    ex:hasStorageType "Outdoor" .

ex:MOSB rdf:type ex:OutdoorWarehouse ;
    ex:hasStorageType "Outdoor" .
```

### Site 그룹
```turtle
ex:AGISite rdf:type ex:Site ;
    ex:hasStorageType "Site" .

ex:DASSite rdf:type ex:Site ;
    ex:hasStorageType "Site" .

ex:MIRSite rdf:type ex:Site ;
    ex:hasStorageType "Site" .

ex:SHUSite rdf:type ex:Site ;
    ex:hasStorageType "Site" .
```

### dangerous cargo 그룹
```turtle
ex:AAAStorage rdf:type ex:DangerousCargoWarehouse ;
    ex:hasStorageType "dangerous cargo" ;
    ex:isDangerous true .

ex:DangerousStorage rdf:type ex:DangerousCargoWarehouse ;
    ex:hasStorageType "dangerous cargo" ;
    ex:isDangerous true .
```

## 🔄 트랜잭션 타입 매핑

```python
# Excel Status → 트랜잭션 타입 매핑

IF Status_Current = "현장":
    TxType_Refined = "FINAL_OUT"
    → ex:hasTransactionType ex:FinalDelivery

ELIF Status_Current = "창고":
    TxType_Refined = "TRANSFER_OUT" 
    → ex:hasTransactionType ex:Transfer

ELSE:
    TxType_Refined = "IN"
    → ex:hasTransactionType ex:Inbound
```

## 📊 예시 RDF 출력

### TransportEvent 예시
```turtle
ex:TransportEvent_001 rdf:type ex:TransportEvent ;
    ex:hasCase "CASE_12345" ;
    ex:hasDate "2025-06-24T10:30:00Z"^^xsd:dateTime ;
    ex:hasQuantity 5 ;
    ex:hasLocation ex:DSVIndoor ;
    ex:hasTransactionType ex:Inbound ;
    ex:hasStatusCurrent "창고" ;
    ex:hasStatusStorage "Indoor" .
```

### StockSnapshot 예시
```turtle
ex:StockSnapshot_DSVIndoor_20250624 rdf:type ex:StockSnapshot ;
    ex:hasLocation ex:DSVIndoor ;
    ex:hasDate "2025-06-24"^^xsd:date ;
    ex:hasOpeningStock 1450 ;
    ex:hasInbound 76 ;
    ex:hasOutbound 28 ;
    ex:hasClosingStock 1498 .
```

## 🔍 SPARQL 쿼리 예시

### 1. 창고별 최신 재고 조회
```sparql
PREFIX ex: <http://samsung.com/project-logistics#>

SELECT ?warehouse ?closingStock ?date
WHERE {
    ?snapshot rdf:type ex:StockSnapshot ;
              ex:hasLocation ?warehouse ;
              ex:hasClosingStock ?closingStock ;
              ex:hasDate ?date .
    
    # 각 창고별 최신 날짜 조회
    {
        SELECT ?warehouse (MAX(?date) AS ?maxDate)
        WHERE {
            ?s ex:hasLocation ?warehouse ;
               ex:hasDate ?date .
        }
        GROUP BY ?warehouse
    }
    
    FILTER(?date = ?maxDate)
}
ORDER BY DESC(?closingStock)
```

### 2. 현장 배송 이벤트 조회
```sparql
PREFIX ex: <http://samsung.com/project-logistics#>

SELECT ?case ?site ?date ?quantity
WHERE {
    ?event rdf:type ex:TransportEvent ;
           ex:hasCase ?case ;
           ex:hasLocation ?site ;
           ex:hasDate ?date ;
           ex:hasQuantity ?quantity ;
           ex:hasTransactionType ex:FinalDelivery .
    
    ?site rdf:type ex:Site .
}
ORDER BY DESC(?date)
```

### 3. 위험물 창고 재고 현황
```sparql
PREFIX ex: <http://samsung.com/project-logistics#>

SELECT ?warehouse ?closingStock
WHERE {
    ?snapshot rdf:type ex:StockSnapshot ;
              ex:hasLocation ?warehouse ;
              ex:hasClosingStock ?closingStock .
    
    ?warehouse rdf:type ex:DangerousCargoWarehouse .
}
```

## ⚙️ 매핑 설정 파일

### mapping_rules_v2.4.json
```json
{
  "namespace": "http://samsung.com/project-logistics#",
  "version": "2.4",
  "description": "HVDC Warehouse Ontology Mapping Rules",
  
  "class_mappings": {
    "TransportEvent": "TransportEvent",
    "StockSnapshot": "StockSnapshot", 
    "Warehouse": "Warehouse",
    "IndoorWarehouse": "IndoorWarehouse",
    "OutdoorWarehouse": "OutdoorWarehouse",
    "DangerousCargoWarehouse": "DangerousCargoWarehouse",
    "Site": "Site",
    "Case": "Case"
  },
  
  "property_mappings": {
    "Case_No": {
      "predicate": "hasCase",
      "datatype": "xsd:string"
    },
    "Date": {
      "predicate": "hasDate", 
      "datatype": "xsd:dateTime"
    },
    "Qty": {
      "predicate": "hasQuantity",
      "datatype": "xsd:integer"
    },
    "Location": {
      "predicate": "hasLocation",
      "datatype": "xsd:string"
    },
    "TxType_Refined": {
      "predicate": "hasTransactionType",
      "datatype": "xsd:string"
    }
  },
  
  "warehouse_classification": {
    "Indoor": ["DSV Indoor", "DSV Al Markaz", "Hauler Indoor"],
    "Outdoor": ["DSV Outdoor", "DSV MZP", "MOSB"],
    "Site": ["AGI", "DAS", "MIR", "SHU"],
    "dangerous_cargo": ["AAA Storage", "Dangerous Storage"]
  }
}
```

## 🚀 활용 방법

### 1. 온톨로지 매핑 적용
```python
from hvdc_ontology_pipeline import OntologyMapper

mapper = OntologyMapper("mapping_rules_v2.4.json")
mapped_data = mapper.map_dataframe_columns(df, "TransportEvent")
```

### 2. RDF/TTL 출력
```python
mapper.export_to_ttl(data_dict, "hvdc_warehouse_data.ttl")
```

### 3. 시맨틱 검색
```python
# SPARQL 엔드포인트를 통한 검색
results = sparql_query("""
    SELECT ?warehouse ?stock 
    WHERE { 
        ?s ex:hasLocation ?warehouse ; 
           ex:hasClosingStock ?stock 
    }
""")
```

## 📈 확장 계획

### v2.5 계획
- **Time Series 온톨로지**: 시계열 재고 데이터 추적
- **Logistics Chain 온톨로지**: 공급망 전체 추적
- **Cost Analysis 온톨로지**: 비용 분석 온톨로지
- **Predictive Analytics**: 예측 분석을 위한 온톨로지

---

**HVDC 온톨로지 매핑 시스템 v2.4** - 표준화된 시맨틱 데이터 관리 