#!/usr/bin/env python3
"""
HVDC 통합 자동화 파이프라인 v2.6
최신 실무 기준: 확장형 매핑 + 온톨로지 연계 + 자동화 리포트
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import logging

# 핵심 모듈 임포트
try:
    from excel_reporter import generate_excel_comprehensive_report
    from ontology_mapper import dataframe_to_rdf
except ImportError as e:
    print(f"⚠️ 모듈 임포트 실패: {e}")
    print("필요 모듈: excel_reporter, ontology_mapper")

class HVDCAutomationPipeline:
    """HVDC 통합 자동화 파이프라인 v2.6"""
    
    def __init__(self, mapping_file: str = "mapping_rules_v2.6.json"):
        self.mapping_file = mapping_file
        self.logger = self._setup_logger()
        self.mapping_rules = self._load_mapping_rules()
        
    def _load_mapping_rules(self) -> dict:
        """확장형 매핑 규칙 로드"""
        try:
            with open(self.mapping_file, 'r', encoding='utf-8') as f:
                rules = json.load(f)
            self.logger.info(f"✅ 매핑 규칙 로드 완료: {self.mapping_file}")
            return rules
        except Exception as e:
            self.logger.error(f"❌ 매핑 규칙 로드 실패: {e}")
            return {}
    
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(__name__)
    
    def normalize_vendor(self, df: pd.DataFrame, vendor_col: str = "Vendor") -> pd.DataFrame:
        """벤더명 표준화 (mapping_rules 기반)"""
        if vendor_col not in df.columns:
            return df
            
        vendor_mappings = self.mapping_rules.get("vendor_mappings", {})
        
        def normalize(val):
            if pd.isna(val): return 'Unknown'
            for k, std in vendor_mappings.items():
                if k in str(val).upper():
                    return std
            return str(val).upper()
        
        df[vendor_col] = df[vendor_col].apply(normalize)
        self.logger.info(f"✅ 벤더 표준화 완료: {df[vendor_col].nunique()}개 고유 벤더")
        return df
    
    def standardize_container_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """컨테이너 컬럼 그룹핑 (20FT/40FT/20FR/40FR)"""
        container_groups = self.mapping_rules.get("container_column_groups", {})
        
        for std_col, variants in container_groups.items():
            df[std_col] = 0  # initialize
            for var in variants:
                for col in df.columns:
                    if col.replace(" ", "").replace("-", "").upper() == var.replace(" ", "").replace("-", "").upper():
                        df[std_col] = df[std_col] + pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        self.logger.info(f"✅ 컨테이너 그룹핑 완료: {list(container_groups.keys())}")
        return df
    
    def add_storage_type(self, df: pd.DataFrame, location_col: str = "Location") -> pd.DataFrame:
        """Storage_Type 자동분류"""
        if location_col not in df.columns:
            return df
            
        warehouse_classification = self.mapping_rules.get("warehouse_classification", {})
        
        def classify_storage_type(location):
            if pd.isna(location): return 'Unknown'
            location_str = str(location).strip()
            for storage_type, keywords in warehouse_classification.items():
                if any(keyword.lower() in location_str.lower() for keyword in keywords):
                    return storage_type
            return 'Unknown'
        
        df['Storage_Type'] = df[location_col].apply(classify_storage_type)
        self.logger.info(f"✅ Storage_Type 분류 완료: {df['Storage_Type'].value_counts().to_dict()}")
        return df
    
    def process_logistics_data(self, input_file: str) -> pd.DataFrame:
        """전체 로직스 데이터 처리 파이프라인"""
        self.logger.info(f"🚀 데이터 처리 시작: {input_file}")
        
        # 1. 데이터 로딩
        df = pd.read_excel(input_file)
        self.logger.info(f"📊 원본 데이터: {len(df)}행, {len(df.columns)}컬럼")
        
        # 2. 벤더 표준화
        df = self.normalize_vendor(df)
        
        # 3. 컨테이너 그룹핑
        df = self.standardize_container_columns(df)
        
        # 4. Storage_Type 분류
        df = self.add_storage_type(df)
        
        # 5. 날짜 처리
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['월'] = df['Date'].dt.strftime('%Y-%m')
        
        # 6. 숫자형 필드 정리
        numeric_columns = ['Amount', 'TOTAL', 'Handling In', 'Handling out', 'Unstuffing', 'Stuffing', 'folk lift', 'crane']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace(',', '')
                    .replace('N/A', '0')
                    .fillna(0)
                    .astype(float)
                )
        
        self.logger.info(f"✅ 데이터 처리 완료: {len(df)}행")
        return df
    
    def generate_comprehensive_report(self, df: pd.DataFrame, output_file: str = "HVDC_최종통합리포트_v2.6.xlsx") -> bool:
        """통합 리포트 생성"""
        try:
            self.logger.info(f"📊 통합 리포트 생성 시작: {output_file}")
            
            # Excel 리포트 생성
            generate_excel_comprehensive_report(
                transaction_df=df,
                daily_stock=pd.DataFrame(),  # 필요시 일별재고 추가
                output_file=output_file,
                debug=True
            )
            
            self.logger.info(f"✅ Excel 리포트 생성 완료: {output_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 리포트 생성 실패: {e}")
            return False
    
    def convert_to_ontology(self, df: pd.DataFrame, output_path: str = "rdf_output/hvdc_v2.6.ttl") -> str:
        """온톨로지 RDF 변환"""
        try:
            # 출력 디렉토리 생성
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # RDF 변환
            rdf_path = dataframe_to_rdf(df, output_path)
            
            if rdf_path:
                self.logger.info(f"✅ RDF 변환 완료: {rdf_path}")
                return rdf_path
            else:
                self.logger.warning("⚠️ RDF 변환 실패 (rdflib 미설치)")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ 온톨로지 변환 실패: {e}")
            return None
    
    def run_full_pipeline(self, input_file: str, output_file: str = "HVDC_최종통합리포트_v2.6.xlsx") -> dict:
        """전체 파이프라인 실행"""
        start_time = datetime.now()
        
        try:
            # 1. 데이터 처리
            df = self.process_logistics_data(input_file)
            
            # 2. 통합 리포트 생성
            report_success = self.generate_comprehensive_report(df, output_file)
            
            # 3. 온톨로지 변환
            rdf_path = self.convert_to_ontology(df)
            
            # 4. 결과 요약
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result = {
                'success': report_success,
                'input_file': input_file,
                'output_file': output_file,
                'rdf_path': rdf_path,
                'data_rows': len(df),
                'data_columns': len(df.columns),
                'duration_seconds': duration,
                'timestamp': end_time.isoformat()
            }
            
            self.logger.info(f"🎉 전체 파이프라인 완료: {duration:.2f}초")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 파이프라인 실패: {e}")
            return {'success': False, 'error': str(e)}

def main():
    """메인 실행 함수"""
    print("🚀 HVDC 통합 자동화 파이프라인 v2.6 시작")
    print("=" * 60)
    
    # 파이프라인 초기화
    pipeline = HVDCAutomationPipeline()
    
    # 입력 파일 확인
    input_files = [
        "HVDC WAREHOUSE_INVOICE1.xlsx",
        "invoice_full.xlsx",
        "data/HVDC WAREHOUSE_HITACHI(HE).xlsx"
    ]
    
    for input_file in input_files:
        if Path(input_file).exists():
            print(f"📄 입력 파일 발견: {input_file}")
            
            # 전체 파이프라인 실행
            result = pipeline.run_full_pipeline(input_file)
            
            if result['success']:
                print(f"✅ 성공: {result['output_file']}")
                print(f"📊 데이터: {result['data_rows']}행, {result['data_columns']}컬럼")
                print(f"⏱️ 소요시간: {result['duration_seconds']:.2f}초")
                if result['rdf_path']:
                    print(f"🔗 RDF: {result['rdf_path']}")
            else:
                print(f"❌ 실패: {result.get('error', 'Unknown error')}")
            
            break
    else:
        print("❌ 입력 파일을 찾을 수 없습니다.")
        print("사용 가능한 파일:")
        for file in input_files:
            print(f"  - {file}")

if __name__ == "__main__":
    main() 