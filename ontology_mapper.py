#!/usr/bin/env python3
"""
HVDC Ontology Mapper v2.6 - DataFrame → RDF 변환

mapping_rules_v2.6.json 기반으로 DataFrame을 RDF로 변환하는 최신 실전 예제
"""

import pandas as pd
from rdflib import Graph, Namespace, Literal, RDF, RDFS, XSD
import json
from pathlib import Path
import logging
from datetime import datetime

# 🆕 NEW: mapping_utils에서 새로운 함수들 import
from mapping_utils import normalize_code_num, codes_match, is_valid_hvdc_vendor, is_warehouse_code

logger = logging.getLogger(__name__)

# 최신 mapping_rules 불러오기
try:
    with open('mapping_rules_v2.6.json', encoding='utf-8') as f:
        RULES = json.load(f)
    NS = {k: Namespace(v) for k, v in RULES["namespaces"].items()}
    FIELD_MAP = RULES["field_map"]
    PROPERTY_MAPPINGS = RULES["property_mappings"]
    CLASS_MAPPINGS = RULES["class_mappings"]
    # 🆕 NEW: 새로운 설정들 로드
    HVDC_CODE3_VALID = RULES.get('hvdc_code3_valid', ['HE', 'SIM'])
    WAREHOUSE_CODES = RULES.get('warehouse_codes', ['DSV Outdoor', 'DSV Indoor', 'DSV Al Markaz', 'DSV MZP'])
    MONTH_MATCHING = RULES.get('month_matching', 'operation_month_eq_eta_month')
except Exception as e:
    logger.warning(f"mapping_rules_v2.6.json 로드 실패, 기본값 사용: {e}")
    NS = {
        "ex": Namespace("http://samsung.com/project-logistics#"),
        "rdf": Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
        "rdfs": Namespace("http://www.w3.org/2000/01/rdf-schema#"),
        "xsd": Namespace("http://www.w3.org/2001/XMLSchema#")
    }
    FIELD_MAP = {}
    PROPERTY_MAPPINGS = {}
    CLASS_MAPPINGS = {}
    HVDC_CODE3_VALID = ['HE', 'SIM']
    WAREHOUSE_CODES = ['DSV Outdoor', 'DSV Indoor', 'DSV Al Markaz', 'DSV MZP']
    MONTH_MATCHING = 'operation_month_eq_eta_month'

def apply_hvdc_filters_to_rdf(df: pd.DataFrame) -> pd.DataFrame:
    """
    🆕 NEW: RDF 변환 전 HVDC 필터 적용
    
    Args:
        df: 원본 DataFrame
        
    Returns:
        pd.DataFrame: 필터링된 DataFrame
    """
    print("🔧 RDF 변환 전 HVDC 필터 적용 중...")
    
    # A. HVDC CODE 정규화 적용
    if 'HVDC CODE' in df.columns and 'HVDC CODE 4' in df.columns:
        df['HVDC_CODE_NORMALIZED'] = df['HVDC CODE'].apply(normalize_code_num)
        df['HVDC_CODE4_NORMALIZED'] = df['HVDC CODE 4'].apply(normalize_code_num)
        
        # 코드 매칭 검증
        df['CODE_MATCH'] = df.apply(
            lambda row: codes_match(row['HVDC CODE'], row['HVDC CODE 4']), axis=1
        )
        
        # 매칭되지 않는 행 필터링
        original_count = len(df)
        df = df[df['CODE_MATCH'] == True]
        filtered_count = len(df)
        print(f"  ✅ HVDC CODE 매칭: {original_count} → {filtered_count} (필터링: {original_count - filtered_count}건)")
    
    # B. CODE 3 필터 (HE, SIM만 처리)
    if 'HVDC CODE 3' in df.columns:
        original_count = len(df)
        df = df[df['HVDC CODE 3'].apply(lambda x: is_valid_hvdc_vendor(x, HVDC_CODE3_VALID))]
        filtered_count = len(df)
        print(f"  ✅ 벤더 필터 (HE/SIM): {original_count} → {filtered_count} (필터링: {original_count - filtered_count}건)")
    
    # C. 창고명(임대료) 필터 & SQM 적용
    if 'HVDC CODE' in df.columns:
        warehouse_mask = df['HVDC CODE'].apply(lambda x: is_warehouse_code(x, WAREHOUSE_CODES))
        warehouse_df = df[warehouse_mask].copy()
        
        if 'SQM' in warehouse_df.columns:
            warehouse_df['SQM'] = warehouse_df['SQM'].apply(lambda x: float(x) if pd.notna(x) else 0)
            print(f"  ✅ 창고 임대료 집계: {len(warehouse_df)}건 (SQM 포함)")
    
    # D. Operation Month(월) 매칭
    if 'Operation Month' in df.columns and 'ETA' in df.columns:
        # INVOICE 데이터: invoice_month
        # WAREHOUSE 데이터: warehouse_month (ETA)
        df['INVOICE_MONTH'] = pd.to_datetime(df['Operation Month'], errors='coerce').dt.strftime('%Y-%m')
        df['WAREHOUSE_MONTH'] = pd.to_datetime(df['ETA'], errors='coerce').dt.strftime('%Y-%m')
        
        original_count = len(df)
        df = df[df['INVOICE_MONTH'] == df['WAREHOUSE_MONTH']]
        filtered_count = len(df)
        print(f"  ✅ 월 매칭: {original_count} → {filtered_count} (필터링: {original_count - filtered_count}건)")
    
    # E. Handling IN/OUT 필드 집계
    handling_fields = ['Handling In freight ton', 'Handling out Freight Ton']
    for field in handling_fields:
        if field in df.columns:
            df[field] = df[field].apply(lambda x: float(x) if pd.notna(x) else 0)
            print(f"  ✅ {field} 처리 완료")
    
    return df

def dataframe_to_rdf(df: pd.DataFrame, output_path="rdf_output/output.ttl"):
    """
    DataFrame을 RDF로 변환 (mapping_rules 기반 + 🆕 NEW: HVDC 필터 적용)
    
    Args:
        df: 변환할 DataFrame
        output_path: 출력 파일 경로
        
    Returns:
        str: 생성된 RDF 파일 경로
    """
    print(f"🔗 DataFrame을 RDF로 변환 중: {output_path}")
    
    # 🆕 NEW: HVDC 필터 적용
    df = apply_hvdc_filters_to_rdf(df)
    
    # 출력 디렉토리 생성
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # RDF 그래프 생성
    g = Graph()
    
    # 네임스페이스 바인딩
    for prefix, ns in NS.items():
        g.bind(prefix, ns)
    
    # 각 행을 RDF 트리플로 변환
    for idx, row in df.iterrows():
        # TransportEvent URI 생성
        event_uri = NS["ex"][f"TransportEvent_{idx+1:05d}"]
        g.add((event_uri, RDF.type, NS["ex"].TransportEvent))
        
        # 각 컬럼을 RDF 프로퍼티로 변환
        for col, val in row.items():
            if pd.isna(val) or col not in FIELD_MAP:
                continue
                
            prop = NS["ex"][FIELD_MAP[col]]
            
            # 🆕 NEW: property_mappings에서 데이터 타입 확인
            datatype = PROPERTY_MAPPINGS.get(col, {}).get('datatype', XSD.decimal)
            
            # 데이터 타입에 따른 Literal 생성
            if isinstance(val, (int, float)):
                lit = Literal(val, datatype=datatype)
            elif isinstance(val, str):
                # 날짜 문자열인지 확인
                try:
                    date_val = pd.to_datetime(val)
                    lit = Literal(date_val.date(), datatype=XSD.date)
                except Exception:
                    lit = Literal(str(val))
            else:
                lit = Literal(str(val))
                
            g.add((event_uri, prop, lit))
    
    # RDF 파일 저장
    g.serialize(destination=output_path, format="turtle")
    print(f"✅ RDF 변환 완료: {output_path}")
    
    return output_path

def create_enhanced_rdf(df: pd.DataFrame, output_path="rdf_output/enhanced_output.ttl"):
    """
    향상된 RDF 변환 (추가 메타데이터 포함 + 🆕 NEW: HVDC 필터 적용)
    
    Args:
        df: 변환할 DataFrame
        output_path: 출력 파일 경로
        
    Returns:
        str: 생성된 RDF 파일 경로
    """
    print(f"🔗 향상된 RDF 변환 중: {output_path}")
    
    # 🆕 NEW: HVDC 필터 적용
    df = apply_hvdc_filters_to_rdf(df)
    
    # 출력 디렉토리 생성
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # RDF 그래프 생성
    g = Graph()
    
    # 네임스페이스 바인딩
    for prefix, ns in NS.items():
        g.bind(prefix, ns)
    
    # 데이터셋 메타데이터 추가
    dataset_uri = NS["ex"]["Dataset_001"]
    g.add((dataset_uri, RDF.type, NS["ex"].Dataset))
    g.add((dataset_uri, NS["ex"].hasCreationDate, Literal(datetime.now().date(), datatype=XSD.date)))
    g.add((dataset_uri, NS["ex"].hasRecordCount, Literal(len(df), datatype=XSD.integer)))
    
    # 각 행을 RDF 트리플로 변환
    for idx, row in df.iterrows():
        # TransportEvent URI 생성
        event_uri = NS["ex"][f"TransportEvent_{idx+1:05d}"]
        g.add((event_uri, RDF.type, NS["ex"].TransportEvent))
        g.add((event_uri, NS["ex"].belongsToDataset, dataset_uri))
        
        # 각 컬럼을 RDF 프로퍼티로 변환
        for col, val in row.items():
            if pd.isna(val) or col not in FIELD_MAP:
                continue
                
            prop = NS["ex"][FIELD_MAP[col]]
            
            # 🆕 NEW: property_mappings에서 데이터 타입 확인
            datatype = PROPERTY_MAPPINGS.get(col, {}).get('datatype', XSD.decimal)
            
            # 데이터 타입에 따른 Literal 생성
            if isinstance(val, (int, float)):
                lit = Literal(val, datatype=datatype)
            elif isinstance(val, str):
                # 날짜 문자열인지 확인
                try:
                    date_val = pd.to_datetime(val)
                    lit = Literal(date_val.date(), datatype=XSD.date)
                except Exception:
                    lit = Literal(str(val))
            else:
                lit = Literal(str(val))
                
            g.add((event_uri, prop, lit))
    
    # RDF 파일 저장
    g.serialize(destination=output_path, format="turtle")
    print(f"✅ 향상된 RDF 변환 완료: {output_path}")
    
    return output_path

def generate_sparql_queries(output_dir="sparql_queries"):
    """
    mapping_rules 기반 SPARQL 쿼리 생성
    
    Args:
        output_dir: 출력 디렉토리
        
    Returns:
        str: 생성된 SPARQL 파일 경로
    """
    print(f"🔍 SPARQL 쿼리 생성 중: {output_dir}")
    
    # 출력 디렉토리 생성
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 기본 쿼리 템플릿들
    queries = [
        {
            'name': 'monthly_warehouse_summary',
            'description': '월별 창고별 집계',
            'query': f"""
PREFIX ex: <{NS["ex"]}>
SELECT ?month ?warehouse (SUM(?amount) AS ?totalAmount) (SUM(?qty) AS ?totalQty)
WHERE {{
    ?event rdf:type ex:TransportEvent ;
           ex:hasLocation ?warehouse ;
           ex:hasDate ?date ;
           ex:hasAmount ?amount ;
           ex:hasQuantity ?qty .
    BIND(SUBSTR(STR(?date), 1, 7) AS ?month)
}}
GROUP BY ?month ?warehouse
ORDER BY ?month ?warehouse
"""
        },
        {
            'name': 'vendor_analysis',
            'description': '벤더별 분석',
            'query': f"""
PREFIX ex: <{NS["ex"]}>
SELECT ?vendor (SUM(?amount) AS ?totalAmount) (COUNT(?event) AS ?eventCount)
WHERE {{
    ?event rdf:type ex:TransportEvent ;
           ex:hasVendor ?vendor ;
           ex:hasAmount ?amount .
}}
GROUP BY ?vendor
ORDER BY DESC(?totalAmount)
"""
        },
        {
            'name': 'container_summary',
            'description': '컨테이너 요약',
            'query': f"""
PREFIX ex: <{NS["ex"]}>
SELECT ?warehouse (SUM(?container20) AS ?total20FT) (SUM(?container40) AS ?total40FT)
WHERE {{
    ?event rdf:type ex:TransportEvent ;
           ex:hasLocation ?warehouse ;
           ex:has20FTContainer ?container20 ;
           ex:has40FTContainer ?container40 .
}}
GROUP BY ?warehouse
ORDER BY ?warehouse
"""
        }
    ]
    
    # mapping_rules 기반 동적 쿼리 생성
    numeric_fields = [field for field, props in PROPERTY_MAPPINGS.items() 
                     if props.get('datatype') in ['xsd:decimal', 'xsd:integer']]
    
    # Handling Fee 특별 쿼리
    if 'Handling Fee' in numeric_fields:
        handling_fee_query = {
            'name': 'handling_fee_monthly_warehouse',
            'description': '월별 창고별 Handling Fee 집계',
            'query': f"""
PREFIX ex: <{NS["ex"]}>
SELECT ?month ?warehouse (SUM(?handlingFee) AS ?totalHandlingFee)
WHERE {{
    ?event rdf:type ex:TransportEvent ;
           ex:hasLocation ?warehouse ;
           ex:hasDate ?date ;
           ex:hasHandlingFee ?handlingFee .
    BIND(SUBSTR(STR(?date), 1, 7) AS ?month)
}}
GROUP BY ?month ?warehouse
ORDER BY ?month ?warehouse
"""
        }
        queries.append(handling_fee_query)
    
    # 쿼리 파일 저장
    sparql_file = f"{output_dir}/generated_queries_{timestamp}.sparql"
    with open(sparql_file, 'w', encoding='utf-8') as f:
        for query_info in queries:
            f.write(f"# {query_info['description']}\n")
            f.write(f"# Query: {query_info['name']}\n")
            f.write(query_info['query'])
            f.write("\n\n")
    
    print(f"✅ SPARQL 쿼리 생성 완료: {sparql_file}")
    return sparql_file

def validate_rdf_conversion(df: pd.DataFrame) -> dict:
    """
    RDF 변환 검증
    
    Args:
        df: 검증할 DataFrame
        
    Returns:
        dict: 검증 결과
    """
    validation_result = {
        'total_records': len(df),
        'mappable_fields': 0,
        'unmappable_fields': [],
        'missing_mappings': []
    }
    
    # 매핑 가능한 필드 확인
    for col in df.columns:
        if col in FIELD_MAP:
            validation_result['mappable_fields'] += 1
        else:
            validation_result['unmappable_fields'].append(col)
    
    # mapping_rules에 정의된 필드가 DataFrame에 없는지 확인
    for field in FIELD_MAP.keys():
        if field not in df.columns:
            validation_result['missing_mappings'].append(field)
    
    return validation_result

def create_rdf_schema(output_path="rdf_output/schema.ttl"):
    """
    RDF 스키마 생성 (mapping_rules 기반)
    
    Args:
        output_path: 출력 파일 경로
        
    Returns:
        str: 생성된 스키마 파일 경로
    """
    print(f"📋 RDF 스키마 생성 중: {output_path}")
    
    # 출력 디렉토리 생성
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # RDF 그래프 생성
    g = Graph()
    
    # 네임스페이스 바인딩
    for prefix, ns in NS.items():
        g.bind(prefix, ns)
    
    # 클래스 정의
    for class_name, class_uri in CLASS_MAPPINGS.items():
        class_ns = NS["ex"][class_uri]
        g.add((class_ns, RDF.type, RDFS.Class))
        g.add((class_ns, RDFS.label, Literal(class_name)))
    
    # 프로퍼티 정의
    for field_name, predicate in FIELD_MAP.items():
        prop_ns = NS["ex"][predicate]
        g.add((prop_ns, RDF.type, RDF.Property))
        g.add((prop_ns, RDFS.label, Literal(field_name)))
        
        # 데이터 타입 정보 추가
        if field_name in PROPERTY_MAPPINGS:
            datatype = PROPERTY_MAPPINGS[field_name].get('datatype', 'xsd:string')
            g.add((prop_ns, RDFS.range, NS["xsd"][datatype.split(':')[-1]]))
    
    # 스키마 파일 저장
    g.serialize(destination=output_path, format="turtle")
    print(f"✅ RDF 스키마 생성 완료: {output_path}")
    
    return output_path

# 편의 함수들
def quick_rdf_convert(df: pd.DataFrame, output_dir="rdf_output"):
    """
    빠른 RDF 변환 (기본 설정)
    
    Args:
        df: 변환할 DataFrame
        output_dir: 출력 디렉토리
        
    Returns:
        tuple: (rdf_path, sparql_path, schema_path)
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # RDF 변환
    rdf_path = f"{output_dir}/hvdc_data_{timestamp}.ttl"
    dataframe_to_rdf(df, rdf_path)
    
    # SPARQL 쿼리 생성
    sparql_path = generate_sparql_queries(output_dir)
    
    # 스키마 생성
    schema_path = f"{output_dir}/schema_{timestamp}.ttl"
    create_rdf_schema(schema_path)
    
    return rdf_path, sparql_path, schema_path

if __name__ == "__main__":
    # 테스트용 샘플 데이터
    test_data = {
        'Case_No': ['CASE001', 'CASE002'],
        'Date': ['2024-01-01', '2024-01-02'],
        'Location': ['DSV Indoor', 'DSV Outdoor'],
        'Qty': [100, 200],
        'Amount': [1000.0, 2000.0],
        'Handling Fee': [50.0, 100.0]
    }
    
    df = pd.DataFrame(test_data)
    
    # RDF 변환 테스트
    rdf_path, sparql_path, schema_path = quick_rdf_convert(df)
    
    print(f"✅ 테스트 완료:")
    print(f"  RDF: {rdf_path}")
    print(f"  SPARQL: {sparql_path}")
    print(f"  Schema: {schema_path}") 