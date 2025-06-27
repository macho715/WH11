# HVDC 창고 관리 온톨로지 문서

## 개요
- **네임스페이스**: `http://samsung.com/project-logistics#`
- **버전**: v2.4
- **생성일**: 2025-06-24 15:16:57

## 클래스 계층구조

```
Thing
├── Event
│   ├── TransportEvent (물류 이동 이벤트)
│   └── StockSnapshot (재고 스냅샷)
├── Location
│   ├── Warehouse (창고)
│   │   ├── IndoorWarehouse (실내 창고)
│   │   ├── OutdoorWarehouse (실외 창고)
│   │   └── DangerousCargoWarehouse (위험물 창고)
│   └── Site (현장)
└── Object
    ├── Case (케이스)
    └── Item (품목)
```

## 창고 분류

### Indoor 그룹

### Indoor 그룹
- DSV Indoor
- DSV Al Markaz
- Hauler Indoor

### Outdoor 그룹
- DSV Outdoor
- DSV MZP
- MOSB

### Site 그룹
- AGI
- DAS
- MIR
- SHU

### Dangerous_cargo 그룹
- AAA Storage
- Dangerous Storage

## 속성 (Properties)

### Object Properties
- `hasLocation`: 위치 관계
- `fromLocation`: 출발 위치  
- `toLocation`: 도착 위치

### Datatype Properties
- `hasCase`: 케이스 번호 (xsd:string)
- `hasDate`: 날짜 (xsd:dateTime)
- `hasQuantity`: 수량 (xsd:integer)
- `hasTransactionType`: 트랜잭션 타입 (xsd:string)
- `hasCurrentStatus`: 현재 상태 (xsd:string)
- `hasStorageType`: 저장 유형 (xsd:string)

## 사용 예시

### 1. 트랜잭션 이벤트
```turtle
ex:TransportEvent_001 rdf:type ex:TransportEvent ;
    ex:hasCase "CASE_12345" ;
    ex:hasDate "2025-06-24T10:30:00Z"^^xsd:dateTime ;
    ex:hasQuantity 5 ;
    ex:hasLocation ex:DSVIndoor ;
    ex:hasTransactionType "IN" .
```

### 2. 재고 스냅샷
```turtle
ex:StockSnapshot_DSVIndoor_20250624 rdf:type ex:StockSnapshot ;
    ex:hasLocation ex:DSVIndoor ;
    ex:hasDate "2025-06-24"^^xsd:date ;
    ex:hasOpeningStock 1450 ;
    ex:hasClosingStock 1498 .
```

## SPARQL 쿼리 예시

### 최신 재고 조회
```sparql
PREFIX ex: <{mapper.namespace}>
SELECT ?warehouse ?stock
WHERE {{
    ?snapshot rdf:type ex:StockSnapshot ;
              ex:hasLocation ?warehouse ;
              ex:hasClosingStock ?stock .
}}
ORDER BY DESC(?stock)
```

### 현장 배송 조회
```sparql
PREFIX ex: <{mapper.namespace}>
SELECT ?case ?site ?date
WHERE {{
    ?event rdf:type ex:TransportEvent ;
           ex:hasCase ?case ;
           ex:hasLocation ?site ;
           ex:hasDate ?date ;
           ex:hasTransactionType "FINAL_OUT" .
    ?site rdf:type ex:Site .
}}
ORDER BY DESC(?date)
```
