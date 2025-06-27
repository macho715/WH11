#!/usr/bin/env python3
"""
HVDC 통합 자동화 파이프라인 - mapping_rules_v2.6.json 기반

새로운 업무필드가 추가되면 mapping_rules에만 한 줄 추가하면
집계, 피벗, 엑셀 리포트, RDF, SPARQL 쿼리까지 모두 자동 확장됨
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json
import sys
from pathlib import Path

# 핵심 모듈 임포트
try:
    from config import load_expected_stock
except Exception as e:
    print(f"⚠️ 설정 로드 실패: {e}")
    def load_expected_stock(as_of=None):
        return {}
        
from core.deduplication import drop_duplicate_transfers, reconcile_orphan_transfers
from core.loader import DataLoader
from excel_reporter import (
    generate_monthly_in_out_stock_report,
    normalize_location_column,
    generate_excel_comprehensive_report
)
from mapping_utils import (
    mapping_manager, 
    add_storage_type_to_dataframe,
    normalize_vendor, 
    standardize_container_columns
)

# ontology_mapper 임포트 (RDF 변환용)
try:
    from ontology_mapper import dataframe_to_rdf
except ImportError:
    print("⚠️ ontology_mapper 모듈이 없습니다. RDF 변환은 건너뜁니다.")
    def dataframe_to_rdf(df, output_path):
        print(f"RDF 변환 건너뜀: {output_path}")
        return output_path

def load_mapping_rules():
    """mapping_rules_v2.6.json 로드"""
    try:
        with open('mapping_rules_v2.6.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ mapping_rules_v2.6.json 로드 실패: {e}")
        return {}

def apply_mapping_rules_to_dataframe(df, mapping_rules):
    """mapping_rules 기반으로 DataFrame 전처리 및 확장"""
    print("🔄 mapping_rules 기반 DataFrame 전처리 중...")
    
    # 1. 필수 컬럼 생성 (날짜/월)
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['월'] = df['Date'].dt.strftime('%Y-%m')
    
    # 2. mapping_rules의 field_map에 있는 모든 필드가 DataFrame에 있는지 확인
    field_map = mapping_rules.get('field_map', {})
    for field_name, predicate in field_map.items():
        if field_name not in df.columns:
            print(f"  📝 필드 추가: {field_name} (기본값: 0)")
            df[field_name] = 0
    
    # 3. 벤더 표준화 (vendor_mappings 적용)
    if 'Vendor' in df.columns:
        df['Vendor'] = df['Vendor'].apply(normalize_vendor)
    
    # 4. 컨테이너 컬럼 표준화 (container_column_groups 적용)
    df = standardize_container_columns(df)
    
    # 5. 카테고리 정규화
    if 'Category' in df.columns:
        df['Category'] = df['Category'].str.strip().str.title()
    
    # 6. Storage Type 추가
    df = add_storage_type_to_dataframe(df, "Location")
    
    print(f"✅ DataFrame 전처리 완료: {len(df.columns)}개 컬럼")
    return df

def generate_comprehensive_reports(df, mapping_rules, output_dir="reports"):
    """통합 리포트 생성 (mapping_rules 기반 자동 확장)"""
    print("📊 통합 리포트 생성 중...")
    
    # 출력 디렉토리 생성
    Path(output_dir).mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 1. 기본 월별 IN/OUT/재고 리포트
    in_df, out_df, stock_df = generate_monthly_in_out_stock_report(df)
    
    # 2. mapping_rules 기반 자동 집계 리포트 생성
    field_map = mapping_rules.get('field_map', {})
    property_mappings = mapping_rules.get('property_mappings', {})
    
    # 숫자형 필드들 자동 집계
    numeric_fields = []
    for field, props in property_mappings.items():
        if props.get('datatype') in ['xsd:decimal', 'xsd:integer'] and field in df.columns:
            numeric_fields.append(field)
    
    print(f"  📈 자동 집계 필드: {numeric_fields}")
    
    # 3. 통합 엑셀 리포트 생성
    excel_report_path = f"{output_dir}/HVDC_통합자동화리포트_{timestamp}.xlsx"
    
    with pd.ExcelWriter(excel_report_path, engine='xlsxwriter') as writer:
        # 기본 시트들
        in_df.to_excel(writer, sheet_name='01_월별IN_창고현장', index=False)
        out_df.to_excel(writer, sheet_name='02_월별OUT_창고현장', index=False)
        stock_df.to_excel(writer, sheet_name='03_월별재고_창고현장', index=False)
        
        # mapping_rules 기반 자동 집계 시트들
        sheet_counter = 4
        
        # 월별 집계 (각 숫자 필드별)
        for field in numeric_fields:
            if field in df.columns and df[field].sum() > 0:
                monthly_agg = df.groupby('월')[field].sum().reset_index()
                monthly_agg.columns = ['월', f'월별{field}합계']
                sheet_name = f'{sheet_counter:02d}_월별{field}'
                monthly_agg.to_excel(writer, sheet_name=sheet_name, index=False)
                sheet_counter += 1
                print(f"    ✅ {field} 월별 집계 완료")
        
        # 창고별 집계 (각 숫자 필드별)
        for field in numeric_fields:
            if field in df.columns and df[field].sum() > 0:
                location_agg = df.groupby('Location')[field].sum().reset_index()
                location_agg.columns = ['창고/현장', f'총{field}합계']
                location_agg = location_agg.sort_values(f'총{field}합계', ascending=False)
                sheet_name = f'{sheet_counter:02d}_창고별{field}'
                location_agg.to_excel(writer, sheet_name=sheet_name, index=False)
                sheet_counter += 1
                print(f"    ✅ {field} 창고별 집계 완료")
        
        # 통계 요약 시트
        stats_data = []
        for field in numeric_fields:
            if field in df.columns:
                stats_data.append({
                    '필드명': field,
                    '총합': df[field].sum(),
                    '평균': df[field].mean(),
                    '최대값': df[field].max(),
                    '최소값': df[field].min(),
                    '표준편차': df[field].std()
                })
        
        if stats_data:
            stats_df = pd.DataFrame(stats_data)
            stats_df.to_excel(writer, sheet_name=f'{sheet_counter:02d}_통계요약', index=False)
            print(f"    ✅ 통계 요약 완료")
    
    print(f"✅ 통합 엑셀 리포트 생성 완료: {excel_report_path}")
    return excel_report_path

def generate_rdf_from_dataframe(df, mapping_rules, output_dir="rdf_output"):
    """DataFrame을 RDF로 변환 (mapping_rules 기반)"""
    print("🔗 RDF 변환 중...")
    
    # 출력 디렉토리 생성
    Path(output_dir).mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    rdf_path = f"{output_dir}/hvdc_automation_{timestamp}.ttl"
    
    try:
        # ontology_mapper의 dataframe_to_rdf 함수 사용
        result_path = dataframe_to_rdf(df, rdf_path)
        print(f"✅ RDF 변환 완료: {result_path}")
        return result_path
    except Exception as e:
        print(f"⚠️ RDF 변환 실패: {e}")
        return None

def generate_sparql_queries(mapping_rules, output_dir="sparql_queries"):
    """mapping_rules 기반 SPARQL 쿼리 생성"""
    print("🔍 SPARQL 쿼리 생성 중...")
    
    # 출력 디렉토리 생성
    Path(output_dir).mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    sparql_templates = mapping_rules.get('sparql_templates', {})
    namespace = mapping_rules.get('namespace', 'http://samsung.com/project-logistics#')
    
    queries = []
    
    # 기본 템플릿 쿼리들
    for query_name, template in sparql_templates.items():
        query = template.format(namespace=namespace)
        queries.append({
            'name': query_name,
            'query': query,
            'description': f'자동 생성된 {query_name} 쿼리'
        })
    
    # mapping_rules 기반 동적 쿼리 생성
    property_mappings = mapping_rules.get('property_mappings', {})
    numeric_fields = [field for field, props in property_mappings.items() 
                     if props.get('datatype') in ['xsd:decimal', 'xsd:integer']]
    
    # Handling Fee 특별 쿼리
    if 'Handling Fee' in numeric_fields:
        handling_fee_query = f"""
PREFIX ex: <{namespace}>
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
        queries.append({
            'name': 'handling_fee_monthly_warehouse',
            'query': handling_fee_query,
            'description': '월별 창고별 Handling Fee 집계'
        })
    
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

def main():
    """통합 자동화 파이프라인 메인 함수"""
    print("🚀 HVDC 통합 자동화 파이프라인 시작")
    print("=" * 60)
    
    try:
        # 1. mapping_rules 로드
        print("📋 mapping_rules_v2.6.json 로드 중...")
        mapping_rules = load_mapping_rules()
        if not mapping_rules:
            print("❌ mapping_rules 로드 실패!")
            return False
        
        print(f"✅ mapping_rules 로드 완료: v{mapping_rules.get('version', 'unknown')}")
        
        # 2. 데이터 로딩
        print("\n📄 데이터 로딩 중...")
        loader = DataLoader()
        excel_files = loader.load_excel_files("data")
        
        if not excel_files:
            print("❌ Excel 파일이 없습니다!")
            return False
            
        raw_transactions = loader.extract_transactions(excel_files)
        print(f"📊 총 {len(raw_transactions):,}건의 원시 트랜잭션 수집")

        # 3. DataFrame 변환
        print("\n🔄 DataFrame 변환 중...")
        transaction_df = transactions_to_dataframe(raw_transactions)
        print(f"✅ {len(transaction_df)}건 트랜잭션 생성")
        
        # 4. mapping_rules 기반 전처리 및 확장
        transaction_df = apply_mapping_rules_to_dataframe(transaction_df, mapping_rules)
        
        # 5. 데이터 전처리
        print("\n🛠️ 데이터 전처리 중...")
        transaction_df = reconcile_orphan_transfers(transaction_df)
        transaction_df = drop_duplicate_transfers(transaction_df)
        print("✅ 데이터 검증 완료")
        
        # 6. 통합 리포트 생성
        excel_report_path = generate_comprehensive_reports(transaction_df, mapping_rules)
        
        # 7. RDF 변환
        rdf_path = generate_rdf_from_dataframe(transaction_df, mapping_rules)
        
        # 8. SPARQL 쿼리 생성
        sparql_path = generate_sparql_queries(mapping_rules)
        
        # 9. 결과 요약
        print("\n" + "=" * 60)
        print("🎉 통합 자동화 파이프라인 완료!")
        print("=" * 60)
        print(f"📊 DataFrame 컬럼 수: {len(transaction_df.columns)}개")
        print(f"📄 엑셀 리포트: {excel_report_path}")
        if rdf_path:
            print(f"🔗 RDF 파일: {rdf_path}")
        print(f"🔍 SPARQL 쿼리: {sparql_path}")
        
        # 10. mapping_rules 확장 가능성 안내
        print("\n📋 mapping_rules 확장 가이드:")
        print("  - 새로운 필드 추가: field_map과 property_mappings에 한 줄 추가")
        print("  - 벤더 매핑: vendor_mappings에 추가")
        print("  - 컨테이너 그룹: container_column_groups에 추가")
        print("  - SPARQL 템플릿: sparql_templates에 추가")
        print("  → 코드 수정 없이 자동으로 모든 리포트/RDF/쿼리에 반영됨!")
        
        return True
        
    except Exception as e:
        print(f"❌ 파이프라인 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def transactions_to_dataframe(transactions):
    """트랜잭션 리스트를 DataFrame으로 변환"""
    data = []
    
    for tx in transactions:
        tx_data = tx.get('data', {})
        
        # 기본 정보 추출
        case_id = extract_case_id(tx_data)
        warehouse = extract_warehouse(tx_data)
        date_val = extract_datetime(tx_data)
        
        # 수량 처리
        incoming = tx_data.get('incoming', 0) or 0
        outgoing = tx_data.get('outgoing', 0) or 0
        
        # 기본 레코드 템플릿
        base_record = {
            'Case_No': case_id,
            'Date': date_val,
            'Location': warehouse,
            'Source_File': tx.get('source_file', ''),
            'Loc_From': 'SOURCE',
            'Target_Warehouse': warehouse,
            'Amount': tx_data.get('amount', 0),
            'Handling Fee': tx_data.get('handling_fee', 0),  # mapping_rules에 추가된 필드
            'Storage_Type': tx_data.get('storage_type', 'Unknown'),
            'storage_type': tx_data.get('storage_type', 'Unknown')
        }
        
        # IN 트랜잭션 생성
        if incoming > 0:
            record = base_record.copy()
            record.update({
                'TxType_Refined': 'IN',
                'Qty': int(incoming),
                'Incoming': int(incoming),
                'Outgoing': 0
            })
            data.append(record)
            
        # OUT 트랜잭션 생성
        if outgoing > 0:
            record = base_record.copy()
            site = extract_site(warehouse)
            tx_type = 'FINAL_OUT' if site in ['AGI', 'DAS', 'MIR', 'SHU'] else 'TRANSFER_OUT'
                
            record.update({
                'TxType_Refined': tx_type,
                'Qty': int(outgoing),
                'Loc_From': warehouse,
                'Target_Warehouse': 'DESTINATION',
                'Incoming': 0,
                'Outgoing': int(outgoing)
            })
            data.append(record)
    
    df = pd.DataFrame(data)
    if not df.empty:
        df = normalize_location_column(df)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['Date'] = df['Date'].fillna(pd.Timestamp.now())
        df['Billing month'] = df['Date'].dt.strftime('%Y-%m')
        df['Category'] = 'General'
        
    return df

def extract_case_id(data):
    """케이스 ID 추출"""
    case_fields = ['case', 'Case', 'case_id', 'CaseID', 'ID', 'carton', 'box', 'mr#']
    
    for field in case_fields:
        if field in data and data[field]:
            case_value = str(data[field]).strip()
            if case_value and case_value.lower() not in ['nan', 'none', '']:
                return case_value
    
    return f"CASE_{abs(hash(str(data))) % 100000}"

def extract_warehouse(data):
    """창고명 추출 및 정규화"""
    warehouse_fields = ['warehouse', 'Warehouse', 'site', 'Site', 'location', 'Location']
    
    for field in warehouse_fields:
        if field in data and data[field]:
            raw_warehouse = str(data[field]).strip()
            if raw_warehouse and raw_warehouse.lower() not in ['nan', 'none', '']:
                return normalize_warehouse_name(raw_warehouse)
    
    return 'UNKNOWN'

def extract_datetime(data):
    """날짜/시간 추출"""
    date_fields = ['date', 'Date', 'timestamp', 'Timestamp', 'datetime']
    
    for field in date_fields:
        if field in data and data[field]:
            try:
                date_value = data[field]
                if isinstance(date_value, str) and date_value.lower() in ['nan', 'none', '']:
                    continue
                return pd.to_datetime(date_value)
            except:
                continue
    
    return pd.Timestamp.now()

def normalize_warehouse_name(raw_name):
    """창고명 정규화"""
    if pd.isna(raw_name) or not raw_name:
        return 'UNKNOWN'
    
    all_locations = []
    for locations in mapping_manager.warehouse_classification.values():
        all_locations.extend(locations)
    
    name_lower = str(raw_name).lower().strip()
    
    for location in all_locations:
        if location.lower() in name_lower or name_lower in location.lower():
            return location
    
    return str(raw_name).strip()

def extract_site(warehouse_name):
    """사이트명 추출"""
    if pd.isna(warehouse_name):
        return 'UNK'
    
    if mapping_manager.classify_storage_type(warehouse_name) == 'Site':
        return warehouse_name
    
    return 'UNK'

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 통합 자동화 파이프라인 성공!")
        sys.exit(0)
    else:
        print("\n❌ 파이프라인 실패!")
        sys.exit(1) 