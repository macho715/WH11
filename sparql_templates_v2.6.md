# HVDC SPARQL 쿼리 템플릿 v2.6

## 🎯 개요
HVDC 프로젝트의 온톨로지 기반 SPARQL 쿼리 템플릿입니다.
`mapping_rules_v2.6.json`의 property_mappings와 연동됩니다.

## 📊 기본 쿼리 템플릿

### 1. 월별/창고별 총 청구액 조회
```sparql
PREFIX ex: <http://samsung.com/project-logistics#>
SELECT ?month ?warehouse (SUM(?amount) AS ?totalAmount) (SUM(?qty) AS ?totalQty)
WHERE {
    ?event rdf:type ex:TransportEvent ;
           ex:hasLocation ?warehouse ;
           ex:hasDate ?date ;
           ex:hasAmount ?amount ;
           ex:hasQuantity ?qty .
    BIND(SUBSTR(STR(?date), 1, 7) AS ?month)
}
GROUP BY ?month ?warehouse
ORDER BY ?month ?warehouse
```

### 2. 벤더별 분석
```sparql
PREFIX ex: <http://samsung.com/project-logistics#>
SELECT ?vendor (SUM(?amount) AS ?totalAmount) (COUNT(?event) AS ?eventCount)
WHERE {
    ?event rdf:type ex:TransportEvent ;
           ex:hasVendor ?vendor ;
           ex:hasAmount ?amount .
}
GROUP BY ?vendor
ORDER BY DESC(?totalAmount)
```

### 3. 컨테이너 요약
```sparql
PREFIX ex: <http://samsung.com/project-logistics#>
SELECT ?warehouse (SUM(?container20) AS ?total20FT) (SUM(?container40) AS ?total40FT)
WHERE {
    ?event rdf:type ex:TransportEvent ;
           ex:hasLocation ?warehouse ;
           ex:has20FTContainer ?container20 ;
           ex:has40FTContainer ?container40 .
}
GROUP BY ?warehouse
ORDER BY ?warehouse
```

### 4. Storage Type별 분석
```sparql
PREFIX ex: <http://samsung.com/project-logistics#>
SELECT ?storageType (SUM(?amount) AS ?totalAmount) (COUNT(?event) AS ?eventCount)
WHERE {
    ?event rdf:type ex:TransportEvent ;
           ex:hasLocation ?warehouse ;
           ex:hasAmount ?amount .
    ?warehouse rdf:type ?warehouseType .
    BIND(
        IF(?warehouseType = ex:IndoorWarehouse, "Indoor",
        IF(?warehouseType = ex:OutdoorWarehouse, "Outdoor",
        IF(?warehouseType = ex:Site, "Site", "Unknown"))) AS ?storageType
    )
}
GROUP BY ?storageType
ORDER BY DESC(?totalAmount)
```

### 5. 기간별 트렌드 분석
```sparql
PREFIX ex: <http://samsung.com/project-logistics#>
SELECT ?month (SUM(?amount) AS ?totalAmount) (SUM(?qty) AS ?totalQty)
WHERE {
    ?event rdf:type ex:TransportEvent ;
           ex:hasDate ?date ;
           ex:hasAmount ?amount ;
           ex:hasQuantity ?qty .
    FILTER(?date >= "2025-01-01"^^xsd:date && ?date <= "2025-12-31"^^xsd:date)
    BIND(SUBSTR(STR(?date), 1, 7) AS ?month)
}
GROUP BY ?month
ORDER BY ?month
```

### 6. 하역비 분석
```sparql
PREFIX ex: <http://samsung.com/project-logistics#>
SELECT ?warehouse 
       (SUM(?handlingIn) AS ?totalHandlingIn)
       (SUM(?handlingOut) AS ?totalHandlingOut)
       (SUM(?unstuffing) AS ?totalUnstuffing)
       (SUM(?stuffing) AS ?totalStuffing)
WHERE {
    ?event rdf:type ex:TransportEvent ;
           ex:hasLocation ?warehouse ;
           ex:hasHandlingIn ?handlingIn ;
           ex:hasHandlingOut ?handlingOut ;
           ex:hasUnstuffing ?unstuffing ;
           ex:hasStuffing ?stuffing .
}
GROUP BY ?warehouse
ORDER BY ?warehouse
```

### 7. 장비 사용량 분석
```sparql
PREFIX ex: <http://samsung.com/project-logistics#>
SELECT ?warehouse (SUM(?forklift) AS ?totalForklift) (SUM(?crane) AS ?totalCrane)
WHERE {
    ?event rdf:type ex:TransportEvent ;
           ex:hasLocation ?warehouse ;
           ex:hasForklift ?forklift ;
           ex:hasCrane ?crane .
}
GROUP BY ?warehouse
ORDER BY DESC(?totalForklift)
```

### 8. 케이스별 추적
```sparql
PREFIX ex: <http://samsung.com/project-logistics#>
SELECT ?case ?warehouse ?date ?qty ?amount
WHERE {
    ?event rdf:type ex:TransportEvent ;
           ex:hasCase ?case ;
           ex:hasLocation ?warehouse ;
           ex:hasDate ?date ;
           ex:hasQuantity ?qty ;
           ex:hasAmount ?amount .
    FILTER(?case = "CASE_001")
}
ORDER BY ?date
```

### 9. 재고 스냅샷 조회
```sparql
PREFIX ex: <http://samsung.com/project-logistics#>
SELECT ?warehouse ?date ?openingStock ?inbound ?outbound ?closingStock
WHERE {
    ?snapshot rdf:type ex:StockSnapshot ;
              ex:hasLocation ?warehouse ;
              ex:hasDate ?date ;
              ex:hasOpeningStock ?openingStock ;
              ex:hasInbound ?inbound ;
              ex:hasOutbound ?outbound ;
              ex:hasClosingStock ?closingStock .
    FILTER(?date = "2025-06-24"^^xsd:date)
}
ORDER BY ?warehouse
```

### 10. 복합 조건 검색
```sparql
PREFIX ex: <http://samsung.com/project-logistics#>
SELECT ?case ?warehouse ?vendor ?amount ?qty
WHERE {
    ?event rdf:type ex:TransportEvent ;
           ex:hasCase ?case ;
           ex:hasLocation ?warehouse ;
           ex:hasVendor ?vendor ;
           ex:hasAmount ?amount ;
           ex:hasQuantity ?qty .
    FILTER(?amount > 1000)
    FILTER(?qty > 10)
    FILTER(?vendor = "SIM")
}
ORDER BY DESC(?amount)
LIMIT 20
```

## 🔧 고급 쿼리 패턴

### 동적 필터링
```sparql
PREFIX ex: <http://samsung.com/project-logistics#>
SELECT ?warehouse ?amount
WHERE {
    ?event rdf:type ex:TransportEvent ;
           ex:hasLocation ?warehouse ;
           ex:hasAmount ?amount .
    FILTER(?amount > ?threshold)
    BIND(1000 AS ?threshold)
}
```

### 조건부 집계
```sparql
PREFIX ex: <http://samsung.com/project-logistics#>
SELECT ?warehouse 
       (SUM(IF(?amount > 1000, ?amount, 0)) AS ?highValueAmount)
       (SUM(IF(?amount <= 1000, ?amount, 0)) AS ?lowValueAmount)
WHERE {
    ?event rdf:type ex:TransportEvent ;
           ex:hasLocation ?warehouse ;
           ex:hasAmount ?amount .
}
GROUP BY ?warehouse
```

## 📈 사용법

1. **RDF 파일 로드**: `hvdc_v2.6.ttl` 파일을 SPARQL 엔드포인트에 로드
2. **네임스페이스 설정**: `PREFIX ex: <http://samsung.com/project-logistics#>`
3. **쿼리 실행**: 위 템플릿을 기반으로 필요한 쿼리 작성
4. **결과 활용**: Excel, BI 도구, 대시보드 등에 연동

## 🎯 확장 가능성

- **새로운 컬럼 추가**: `mapping_rules_v2.6.json`의 property_mappings에 추가
- **새로운 쿼리 패턴**: 위 템플릿을 기반으로 비즈니스 요구사항에 맞게 확장
- **실시간 연동**: SPARQL 엔드포인트를 통한 실시간 데이터 조회

---

**모든 쿼리는 `mapping_rules_v2.6.json`의 property_mappings와 완전 호환됩니다!** 