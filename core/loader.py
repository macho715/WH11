"""
HVDC 데이터 로딩 및 전처리 모듈
온톨로지 기반 정규화 및 데이터 통합 처리
"""

import pandas as pd
import os
from typing import List, Dict, Any, Optional
import json
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataLoader:
    """HVDC 데이터 로딩 및 전처리 클래스"""
    
    def __init__(self, mapping_rules_path: str = "mapping_rules_v2.4.json"):
        """
        Args:
            mapping_rules_path: 온톨로지 매핑 규칙 파일 경로
        """
        self.mapping_rules_path = mapping_rules_path
        self.mapping_rules = self._load_mapping_rules()
        self.raw_data = {}
        self.processed_data = {}
        
    def _load_mapping_rules(self) -> Dict[str, Any]:
        """매핑 규칙 로드"""
        try:
            with open(self.mapping_rules_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"매핑 규칙 로드 실패: {e}")
            return {}
    
    def load_excel_files(self, data_dir: str = "data") -> Dict[str, pd.DataFrame]:
        """Excel 파일들을 로드"""
        excel_files = {}
        
        if not os.path.exists(data_dir):
            logger.error(f"데이터 디렉토리 없음: {data_dir}")
            return excel_files
            
        for filename in os.listdir(data_dir):
            if filename.endswith('.xlsx'):
                file_path = os.path.join(data_dir, filename)
                try:
                    # Excel 파일의 모든 시트 로드
                    excel_file = pd.read_excel(file_path, sheet_name=None, engine='openpyxl')
                    excel_files[filename] = excel_file
                    logger.info(f"로드 완료: {filename} ({len(excel_file)} 시트)")
                except Exception as e:
                    logger.error(f"Excel 파일 로드 실패 {filename}: {e}")
                    
        return excel_files
    
    def normalize_location_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """위치명 정규화 (온톨로지 기반)"""
        if 'location_mappings' not in self.mapping_rules:
            return df
            
        location_mappings = self.mapping_rules['location_mappings']
        
        # 위치 관련 컬럼들 정규화
        location_columns = ['Warehouse', 'Site', 'Location', 'From', 'To']
        
        for col in location_columns:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: self._normalize_single_location(x, location_mappings))
                
        return df
    
    def _normalize_single_location(self, location: str, mappings: Dict) -> str:
        """단일 위치명 정규화"""
        if pd.isna(location):
            return location
            
        location_str = str(location).strip()
        
        # 직접 매핑 확인
        for standard_name, variants in mappings.items():
            if location_str in variants or location_str == standard_name:
                return standard_name
                
        # 부분 매칭 시도
        for standard_name, variants in mappings.items():
            for variant in variants:
                if variant.lower() in location_str.lower() or location_str.lower() in variant.lower():
                    return standard_name
                    
        return location_str
    
    def extract_transactions(self, excel_files: Dict) -> List[Dict]:
        """Excel 파일들에서 트랜잭션 데이터 추출"""
        all_transactions = []
        
        for filename, sheets in excel_files.items():
            for sheet_name, df in sheets.items():
                try:
                    # 시트별 트랜잭션 추출
                    transactions = self._extract_sheet_transactions(df, filename, sheet_name)
                    all_transactions.extend(transactions)
                    logger.info(f"트랜잭션 추출: {filename}/{sheet_name} - {len(transactions)}건")
                except Exception as e:
                    logger.error(f"트랜잭션 추출 실패 {filename}/{sheet_name}: {e}")
                    
        return all_transactions
    
    def _extract_sheet_transactions(self, df: pd.DataFrame, filename: str, sheet_name: str) -> List[Dict]:
        """단일 시트에서 트랜잭션 추출"""
        transactions = []
        
        if df.empty:
            return transactions
            
        # 컬럼명 정규화
        df = self._normalize_column_names(df)
        
        # 위치명 정규화
        df = self.normalize_location_names(df)
        
        # 날짜 컬럼 식별 및 처리
        date_columns = self._identify_date_columns(df)
        
        for idx, row in df.iterrows():
            try:
                transaction = self._create_transaction_record(row, filename, sheet_name, date_columns)
                if transaction:
                    transactions.append(transaction)
            except Exception as e:
                logger.warning(f"트랜잭션 생성 실패 {filename}/{sheet_name} row {idx}: {e}")
                
        return transactions
    
    def _normalize_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """컬럼명 정규화"""
        column_mappings = {
            'incoming': ['Incoming', 'In', 'Inbound', '입고', '입고량'],
            'outgoing': ['Outgoing', 'Out', 'Outbound', '출고', '출고량'],
            'inventory': ['Inventory', 'Stock', '재고', '재고량'],
            'date': ['Date', 'Timestamp', '날짜', '일자'],
            'warehouse': ['Warehouse', 'WH', '창고'],
            'site': ['Site', 'Location', '사이트', '위치']
        }
        
        new_columns = {}
        for standard_name, variants in column_mappings.items():
            for col in df.columns:
                if any(variant.lower() in str(col).lower() for variant in variants):
                    new_columns[col] = standard_name
                    break
                    
        if new_columns:
            df = df.rename(columns=new_columns)
            
        return df
    
    def _identify_date_columns(self, df: pd.DataFrame) -> List[str]:
        """날짜 컬럼 식별"""
        date_columns = []
        
        for col in df.columns:
            if 'date' in str(col).lower() or 'time' in str(col).lower():
                date_columns.append(col)
            elif df[col].dtype == 'datetime64[ns]':
                date_columns.append(col)
                
        return date_columns
    
    def _create_transaction_record(self, row: pd.Series, filename: str, sheet_name: str, date_columns: List[str]) -> Optional[Dict]:
        """트랜잭션 레코드 생성"""
        transaction = {
            'source_file': filename,
            'source_sheet': sheet_name,
            'timestamp': datetime.now(),
            'data': {}
        }
        
        # 기본 필드 추출
        essential_fields = ['incoming', 'outgoing', 'inventory', 'warehouse', 'site']
        has_essential_data = False
        
        for field in essential_fields:
            if field in row.index and pd.notna(row[field]):
                transaction['data'][field] = row[field]
                if field in ['incoming', 'outgoing', 'inventory'] and row[field] != 0:
                    has_essential_data = True
                    
        # 날짜 정보 추출
        for date_col in date_columns:
            if date_col in row.index and pd.notna(row[date_col]):
                transaction['data']['date'] = row[date_col]
                break
                
        # 추가 메타데이터
        for col in row.index:
            if col not in transaction['data'] and pd.notna(row[col]):
                transaction['data'][col] = row[col]
                
        return transaction if has_essential_data else None
    
    def load_and_process_files(self, data_dir: str = "data") -> List[Dict]:
        """전체 데이터 로딩 및 처리 파이프라인"""
        logger.info("🚀 HVDC 데이터 로딩 및 전처리 시작")
        
        # 1. Excel 파일들 로드
        excel_files = self.load_excel_files(data_dir)
        logger.info(f"Excel 파일 로드 완료: {len(excel_files)}개")
        
        # 2. 트랜잭션 추출
        transactions = self.extract_transactions(excel_files)
        logger.info(f"트랜잭션 추출 완료: {len(transactions)}건")
        
        # 3. 데이터 품질 검증
        validated_transactions = self._validate_transactions(transactions)
        logger.info(f"데이터 검증 완료: {len(validated_transactions)}건")
        
        self.raw_data = excel_files
        self.processed_data = validated_transactions
        
        return validated_transactions
    
    def _validate_transactions(self, transactions: List[Dict]) -> List[Dict]:
        """트랜잭션 데이터 검증"""
        validated = []
        
        for transaction in transactions:
            if self._is_valid_transaction(transaction):
                validated.append(transaction)
            else:
                logger.warning(f"유효하지 않은 트랜잭션: {transaction}")
                
        return validated
    
    def _is_valid_transaction(self, transaction: Dict) -> bool:
        """트랜잭션 유효성 검사"""
        data = transaction.get('data', {})
        
        # 필수 필드 확인
        required_fields = ['warehouse']
        for field in required_fields:
            if field not in data or pd.isna(data[field]):
                return False
                
        # 수량 데이터 확인
        quantity_fields = ['incoming', 'outgoing', 'inventory']
        has_quantity = any(field in data and pd.notna(data[field]) and data[field] != 0 
                          for field in quantity_fields)
        
        return has_quantity
    
    def get_summary_statistics(self) -> Dict[str, Any]:
        """데이터 로딩 요약 통계"""
        return {
            'total_files': len(self.raw_data),
            'total_transactions': len(self.processed_data),
            'warehouses': list(set(t['data'].get('warehouse') for t in self.processed_data if 'warehouse' in t['data'])),
            'date_range': self._get_date_range(),
            'file_summary': {filename: len(sheets) for filename, sheets in self.raw_data.items()}
        }
    
    def _get_date_range(self) -> Dict[str, Any]:
        """날짜 범위 계산"""
        dates = []
        for transaction in self.processed_data:
            if 'date' in transaction['data']:
                dates.append(transaction['data']['date'])
                
        if dates:
            return {
                'start_date': min(dates),
                'end_date': max(dates),
                'total_days': (max(dates) - min(dates)).days
            }
        return {} 