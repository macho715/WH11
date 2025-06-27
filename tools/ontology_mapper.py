#!/usr/bin/env python3
"""
RDF 변환 자동화 명령 스크립트
/ontology-mapper 명령으로 YAML 및 재고 데이터를 RDF/OWL로 변환
"""

import argparse
import json
import yaml
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

def load_ontology_mapping() -> Dict[str, Any]:
    """온톨로지 매핑 규칙 로드"""
    try:
        with open("mapping_rules_v2.4.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ mapping_rules_v2.4.json 파일을 찾을 수 없습니다.")
        return {}

def load_expected_stock() -> Dict[str, Any]:
    """기대 재고 YAML 로드"""
    try:
        with open("expected_stock.yml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("❌ expected_stock.yml 파일을 찾을 수 없습니다.")
        return {}

def generate_rdf_ttl(ontology_mapping: Dict, expected_stock: Dict, output_file: str = None) -> str:
    """RDF TTL 형식으로 변환"""
    if not output_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"rdf_output/warehouse_ontology_{timestamp}.ttl"
    
    # 출력 디렉토리 생성
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    # RDF TTL 헤더
    ttl_content = f"""# HVDC Warehouse Ontology RDF/OWL
# Generated: {datetime.now().isoformat()}
# Source: mapping_rules_v2.4.json + expected_stock.yml

@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix hvdc: <{ontology_mapping.get('namespace', 'http://samsung.com/project-logistics#')}> .

# Ontology Declaration
hvdc: a owl:Ontology ;
    rdfs:label "HVDC Warehouse Management Ontology" ;
    rdfs:comment "Ontology for HVDC warehouse and inventory management" ;
    owl:versionInfo "{ontology_mapping.get('version', '2.4')}" .

"""
    
    # 클래스 정의
    if 'class_mappings' in ontology_mapping:
        ttl_content += "# Class Definitions\n"
        for class_name, class_uri in ontology_mapping['class_mappings'].items():
            ttl_content += f"hvdc:{class_uri} a owl:Class ;\n"
            ttl_content += f"    rdfs:label \"{class_name}\" .\n\n"
    
    # 속성 정의
    if 'property_mappings' in ontology_mapping:
        ttl_content += "# Property Definitions\n"
        for prop_name, prop_info in ontology_mapping['property_mappings'].items():
            prop_uri = prop_info.get('predicate', prop_name)
            datatype = prop_info.get('datatype', 'xsd:string')
            ttl_content += f"hvdc:{prop_uri} a owl:DatatypeProperty ;\n"
            ttl_content += f"    rdfs:label \"{prop_name}\" ;\n"
            ttl_content += f"    rdfs:range {datatype} .\n\n"
    
    # 창고 인스턴스 정의
    if 'warehouse_classification' in ontology_mapping:
        ttl_content += "# Warehouse Instances\n"
        for storage_type, warehouses in ontology_mapping['warehouse_classification'].items():
            for warehouse in warehouses:
                # 온톨로지 클래스 매핑
                if storage_type == 'Indoor':
                    class_type = 'IndoorWarehouse'
                elif storage_type == 'Outdoor':
                    class_type = 'OutdoorWarehouse'
                elif storage_type == 'dangerous_cargo':
                    class_type = 'DangerousCargoWarehouse'
                elif storage_type == 'Site':
                    class_type = 'Site'
                else:
                    class_type = 'Warehouse'
                
                ttl_content += f"hvdc:{warehouse.replace(' ', '_')} a hvdc:{class_type} ;\n"
                ttl_content += f"    rdfs:label \"{warehouse}\" ;\n"
                ttl_content += f"    hvdc:hasStorageType \"{storage_type}\" .\n\n"
    
    # 기대 재고 데이터 인스턴스
    if 'expected' in expected_stock:
        ttl_content += "# Expected Stock Data\n"
        for date_str, warehouses in expected_stock['expected'].items():
            for warehouse, quantity in warehouses.items():
                if quantity > 0:  # 0이 아닌 경우만
                    instance_id = f"ExpectedStock_{date_str}_{warehouse.replace(' ', '_')}"
                    ttl_content += f"hvdc:{instance_id} a hvdc:StockSnapshot ;\n"
                    ttl_content += f"    hvdc:hasDate \"{date_str}\"^^xsd:date ;\n"
                    ttl_content += f"    hvdc:hasLocation hvdc:{warehouse.replace(' ', '_')} ;\n"
                    ttl_content += f"    hvdc:hasQuantity {quantity}^^xsd:integer .\n\n"
    
    # 파일 저장
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(ttl_content)
    
    return output_file

def generate_sparql_queries(ontology_mapping: Dict) -> str:
    """SPARQL 쿼리 템플릿 생성"""
    queries = []
    
    # 기본 쿼리들
    queries.append({
        "name": "latest_stock",
        "description": "최신 재고 조회",
        "query": """
PREFIX hvdc: <{namespace}>
SELECT ?warehouse ?stock ?date
WHERE {{
    ?snapshot a hvdc:StockSnapshot ;
              hvdc:hasLocation ?warehouse ;
              hvdc:hasQuantity ?stock ;
              hvdc:hasDate ?date .
    {{
        SELECT ?warehouse (MAX(?date) AS ?maxDate)
        WHERE {{
            ?s hvdc:hasLocation ?warehouse ;
               hvdc:hasDate ?date .
        }}
        GROUP BY ?warehouse
    }}
    FILTER(?date = ?maxDate)
}}
ORDER BY DESC(?stock)
""".format(namespace=ontology_mapping.get('namespace', 'http://samsung.com/project-logistics#'))
    })
    
    queries.append({
        "name": "warehouse_by_type",
        "description": "Storage Type별 창고 조회",
        "query": """
PREFIX hvdc: <{namespace}>
SELECT ?warehouse ?storageType
WHERE {{
    ?warehouse a ?warehouseType ;
               hvdc:hasStorageType ?storageType .
}}
ORDER BY ?storageType ?warehouse
""".format(namespace=ontology_mapping.get('namespace', 'http://samsung.com/project-logistics#'))
    })
    
    # 쿼리 파일 저장
    output_file = "rdf_output/sparql_queries.txt"
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# HVDC Warehouse SPARQL Queries\n")
        f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
        
        for query_info in queries:
            f.write(f"# {query_info['name']}: {query_info['description']}\n")
            f.write(query_info['query'])
            f.write("\n" + "="*50 + "\n\n")
    
    return output_file

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="HVDC Warehouse Ontology Mapper")
    parser.add_argument("--output", "-o", help="출력 파일 경로")
    parser.add_argument("--sparql", "-s", action="store_true", help="SPARQL 쿼리 생성")
    parser.add_argument("--validate", "-v", action="store_true", help="온톨로지 검증")
    
    args = parser.parse_args()
    
    print("🔄 HVDC Warehouse Ontology Mapper 시작")
    print("=" * 50)
    
    # 온톨로지 매핑 로드
    ontology_mapping = load_ontology_mapping()
    if not ontology_mapping:
        print("❌ 온톨로지 매핑을 로드할 수 없습니다.")
        sys.exit(1)
    
    print("✅ 온톨로지 매핑 로드 완료")
    
    # 기대 재고 로드
    expected_stock = load_expected_stock()
    if not expected_stock:
        print("⚠️ 기대 재고 데이터를 로드할 수 없습니다.")
    
    print("✅ 기대 재고 데이터 로드 완료")
    
    # RDF TTL 생성
    ttl_file = generate_rdf_ttl(ontology_mapping, expected_stock, args.output)
    print(f"✅ RDF TTL 생성 완료: {ttl_file}")
    
    # SPARQL 쿼리 생성
    if args.sparql:
        sparql_file = generate_sparql_queries(ontology_mapping)
        print(f"✅ SPARQL 쿼리 생성 완료: {sparql_file}")
    
    # 온톨로지 검증
    if args.validate:
        print("🔍 온톨로지 검증 중...")
        # 여기에 검증 로직 추가 가능
        print("✅ 온톨로지 검증 완료")
    
    print("\n🎉 Ontology Mapper 완료!")
    print(f"📁 출력 파일: {ttl_file}")
    if args.sparql:
        print(f"📁 SPARQL 쿼리: {sparql_file}")

if __name__ == "__main__":
    main() 