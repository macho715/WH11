import pandas as pd
import json
from pathlib import Path
import logging
import os
import glob
from mapping_utils import mapping_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataLoader:
    def __init__(self):
        # ✅ 통합 매핑 매니저 사용
        self.mapping_manager = mapping_manager
        logger.info("✅ DataLoader 초기화 완료 - 통합 매핑 시스템 적용")

    def load_excel_files(self, data_dir: str = "data"):
        """Excel 파일들을 로드"""
        excel_files = {}
        
        if not os.path.exists(data_dir):
            logger.error(f"데이터 디렉토리 없음: {data_dir}")
            return excel_files
            
        # HVDC 창고 파일 패턴
        file_patterns = [
            "HVDC WAREHOUSE_HITACHI*.xlsx",
            "HVDC WAREHOUSE_SIMENSE*.xlsx"
        ]
        
        for pattern in file_patterns:
            for filepath in glob.glob(os.path.join(data_dir, pattern)):
                filename = os.path.basename(filepath)
                
                # 인보이스 파일 스킵
                if 'invoice' in filename.lower():
                    continue
                    
                try:
                    print(f"📄 파일 처리 중: {filename}")
                    
                    # Excel 파일 로드
                    xl_file = pd.ExcelFile(filepath)
                    
                    # Case List 시트 우선 선택
                    sheet_name = xl_file.sheet_names[0]
                    for sheet in xl_file.sheet_names:
                        if 'case' in sheet.lower() and 'list' in sheet.lower():
                            sheet_name = sheet
                            break
                    
                    df = pd.read_excel(filepath, sheet_name=sheet_name)
                    
                    if not df.empty:
                        excel_files[filename] = df
                        
                        # 간단한 통계 출력
                        print(f"   📊 {len(df)}행 데이터 로드")
                        
                        case_col = self._find_case_column(df)
                        if case_col:
                            case_count = df[case_col].nunique()
                            print(f"   📦 고유 케이스 {case_count}개")
                    
                except Exception as e:
                    logger.error(f"Excel 파일 로드 실패 {filename}: {e}")
                    
        return excel_files
    
    def _find_case_column(self, df):
        """케이스 컬럼 찾기"""
        case_patterns = ['case', 'carton', 'box', 'mr#', 'mr #', 'sct ship no', 'case no']
        
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if any(pattern in col_lower for pattern in case_patterns):
                return col
        return None

    def classify_storage_type(self, location):
        """
        창고/현장 Location명을 Storage Type으로 분류 (통합 매핑 사용)
        """
        return self.mapping_manager.classify_storage_type(location)

    def add_storage_type(self, df):
        """
        DataFrame의 Location 컬럼 기준으로 Storage_Type 컬럼을 추가 (통합 매핑 사용)
        """
        return self.mapping_manager.add_storage_type_to_dataframe(df, "Location")

    def extract_transactions(self, excel_files):
        """
        여러 Excel 파일에서 트랜잭션 데이터 추출 후 Storage_Type 추가
        """
        all_transactions = []
        for filename, df in excel_files.items():
            try:
                # ✅ Location 컬럼이 있으면 통합 매핑으로 Storage_Type 태깅
                if 'Location' in df.columns:
                    df = self.add_storage_type(df)
                    print(f"   🏷️ Storage_Type 컬럼 추가됨 (통합 매핑)")
                    
                    # 검증 로그
                    validation = self.mapping_manager.validate_mapping(df)
                    print(f"   매핑 검증: {validation}")
                    
                transactions = self._extract_file_transactions(df, filename)
                all_transactions.extend(transactions)
                print(f"   ✅ {len(transactions)}건 이벤트 추출")
            except Exception as e:
                logger.error(f"트랜잭션 추출 실패 {filename}: {e}")
        return all_transactions
    
    def _extract_file_transactions(self, df, filename):
        """
        개별 파일 내 각 행을 트랜잭션으로 변환, Storage_Type도 포함
        가이드 A안: 'Pkg' 컬럼을 수량으로, 'SERIAL NO.' 또는 'HVDC CODE'를 케이스로, 
        각 창고명 컬럼의 날짜값이 있으면 이벤트(입출고)로 분할 추출
        """
        transactions = []
        
        if df.empty:
            return transactions
            
        # 가이드 A안: 창고별 날짜 컬럼 찾기 (SIMENSE 파일 구조에 맞춤)
        date_columns = []
        warehouse_locations = self.mapping_manager.get_warehouse_locations() + self.mapping_manager.get_site_locations()
        
        print(f"🔍 {filename} 파일 분석 중...")
        print(f"   📋 전체 컬럼 수: {len(df.columns)}개")
        
        for col in df.columns:
            col_str = str(col).strip()
            # 창고명이 포함된 컬럼을 날짜 컬럼으로 인식
            if any(warehouse.lower() in col_str.lower() for warehouse in warehouse_locations):
                date_columns.append(col)
                print(f"   📅 날짜 컬럼 발견: {col}")
        
        print(f"   📊 발견된 날짜 컬럼: {len(date_columns)}개")
        
        # 가이드 A안: 케이스 컬럼 찾기 (SERIAL NO. 또는 HVDC CODE 우선)
        case_col = None
        case_patterns = ['serial no', 'hvdc code', 'case', 'carton', 'box', 'mr#', 'mr #', 'sct ship no', 'case no']
        
        for pattern in case_patterns:
            for col in df.columns:
                col_lower = str(col).lower().strip()
                if pattern in col_lower:
                    case_col = col
                    print(f"   📦 케이스 컬럼 발견: {col} (패턴: {pattern})")
                    break
            if case_col:
                break
                
        if not case_col:
            logger.warning(f"케이스 컬럼을 찾을 수 없음: {filename}")
            print(f"   ⚠️ 케이스 컬럼 없음 - 사용 가능한 컬럼: {[col for col in df.columns if any(word in str(col).lower() for word in ['serial', 'hvdc', 'case', 'pkg'])]}")
            return transactions
        
        # 가이드 A안: 수량 컬럼 찾기 (Pkg 우선)
        qty_col = None
        qty_patterns = ['pkg', 'qty', 'quantity', 'pieces', 'piece', 'q\'ty']
        
        for pattern in qty_patterns:
            for col in df.columns:
                col_lower = str(col).lower().strip()
                if pattern in col_lower:
                    qty_col = col
                    print(f"   📦 수량 컬럼 발견: {col} (패턴: {pattern})")
                    break
            if qty_col:
                break
                
        if not qty_col:
            qty_col = 'Pkg'  # 기본값
            print(f"   📦 수량 컬럼 기본값 사용: {qty_col}")
        
        print(f"   🔄 트랜잭션 추출 시작...")
        
        for idx, row in df.iterrows():
            # 가이드 A안: 케이스 ID 추출
            case_id = str(row[case_col]) if pd.notna(row[case_col]) else f"CASE_{idx}"
            
            # 가이드 A안: 수량 추출 (Pkg 컬럼 활용)
            try:
                quantity = int(row[qty_col]) if pd.notna(row[qty_col]) else 1
            except (ValueError, TypeError):
                quantity = 1
                print(f"   ⚠️ 행 {idx}: 수량 변환 실패, 기본값 1 사용")
            
            # 가이드 A안: 각 창고별 날짜 컬럼에서 이벤트 추출
            events_found = 0
            for date_col in date_columns:
                if pd.notna(row[date_col]):
                    try:
                        event_date = pd.to_datetime(row[date_col])
                        warehouse = self._extract_warehouse_from_column(date_col)
                        
                        # 통합 매핑으로 storage_type 분류
                        storage_type = self.classify_storage_type(warehouse)
                        
                        if warehouse != 'UNKNOWN':
                            # 트랜잭션 데이터 생성 (가이드 A안 방식)
                            tx = {
                                'source_file': filename,
                                'timestamp': pd.Timestamp.now(),
                                'data': {
                                    'case': case_id,
                                    'date': event_date,
                                    'warehouse': warehouse,
                                    'incoming': quantity,
                                    'outgoing': 0,
                                    'inventory': quantity,
                                    'storage_type': storage_type,
                                    'pkg': quantity,  # 가이드 A안: Pkg 정보 추가
                                    'serial_no': case_id if 'serial' in str(case_col).lower() else None,
                                    'hvdc_code': case_id if 'hvdc' in str(case_col).lower() else None
                                }
                            }
                            transactions.append(tx)
                            events_found += 1
                            
                    except Exception as e:
                        logger.debug(f"날짜 파싱 실패 {date_col}: {e}")
                        continue
            
            if events_found == 0:
                print(f"   ⚠️ 행 {idx}: 이벤트 없음 (케이스: {case_id}, 수량: {quantity})")
        
        print(f"   ✅ {filename}: {len(transactions)}건 트랜잭션 추출 완료")
        return transactions
    
    def _find_quantity_column(self, df):
        """수량 컬럼 찾기"""
        qty_patterns = ['pkg', 'qty', 'quantity', 'pieces', 'piece', 'q\'ty']
        
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if any(pattern in col_lower for pattern in qty_patterns):
                return col
        return None

    def _extract_warehouse_from_column(self, col_name):
        """컬럼명에서 창고명 추출"""
        col_lower = str(col_name).lower().strip()
        
        warehouse_mapping = {
            'dsv indoor': 'DSV Indoor',
            'dsv al markaz': 'DSV Al Markaz',
            'dsv outdoor': 'DSV Outdoor',
            'hauler indoor': 'Hauler Indoor',
            'dsv mzp': 'DSV MZP',
            'mosb': 'MOSB',
            'mir': 'MIR',
            'shu': 'SHU',
            'das': 'DAS',
            'agi': 'AGI'
        }
        
        for pattern, warehouse in warehouse_mapping.items():
            if pattern in col_lower:
                return warehouse
        
        return 'UNKNOWN' 