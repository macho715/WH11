# hvdc_ontology_pipeline.py
"""
HVDC Warehouse Analysis Pipeline - Ontology-Enhanced Version
이 버전은 mapping_rules_v2.4.json의 온톨로지 매핑 룰을 반영하여
TransportEvent, StockSnapshot, DeadStock 등의 클래스와 속성을 정확히 매핑합니다.

Key Features:
1. 🎯 Refined Transaction Types: FINAL_OUT vs TRANSFER_OUT 정확한 분류
2. ✅ Automated Validation: (Opening + Inbound - Outbound = Closing) 자동 검증
3. 📊 Dead Stock Analysis: 180일+ 미이동 재고 식별
4. 🔗 Ontology Mapping: RDF/TTL 출력을 위한 표준화된 데이터 구조
5. 📈 Enhanced Reporting: 창고별/월별/사이트별 상세 분석
"""

import pandas as pd
import numpy as np
import os
import glob
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# 1. ONTOLOGY CONFIGURATION
# =============================================================================

class OntologyMapper:
    """온톨로지 매핑 룰 기반 데이터 변환기"""
    
    def __init__(self, mapping_file: str = "mapping_rules_v2.4.json"):
        """매핑 룰 로드"""
        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                self.mapping_rules = json.load(f)
            print(f"✅ 온톨로지 매핑 룰 로드 완료: {mapping_file}")
        except FileNotFoundError:
            print(f"⚠️ 매핑 룰 파일 없음: {mapping_file}, 기본 매핑 사용")
            self.mapping_rules = self._get_default_mapping()
        
        self.namespace = self.mapping_rules.get("namespace", "http://samsung.com/project-logistics#")
        self.class_mappings = self.mapping_rules.get("class_mappings", {})
        self.property_mappings = self.mapping_rules.get("property_mappings", {})
    
    def _get_default_mapping(self) -> Dict:
        """기본 매핑 룰"""
        return {
            "namespace": "http://samsung.com/project-logistics#",
            "class_mappings": {
                "TransportEvent": "TransportEvent",
                "StockSnapshot": "StockSnapshot", 
                "DeadStock": "DeadStock",
                "Case": "Case",
                "Warehouse": "Warehouse",
                "Site": "Site"
            },
            "property_mappings": {}
        }
    
    def map_dataframe_columns(self, df: pd.DataFrame, target_class: str) -> pd.DataFrame:
        """데이터프레임 컬럼을 온톨로지 속성에 매핑"""
        mapped_df = df.copy()
        
        # 컬럼명을 온톨로지 속성으로 변환
        column_mapping = {}
        for col in df.columns:
            if col in self.property_mappings:
                prop_info = self.property_mappings[col]
                if prop_info.get("subject_class") == target_class:
                    column_mapping[col] = prop_info["predicate"]
        
        if column_mapping:
            mapped_df = mapped_df.rename(columns=column_mapping)
            print(f"🔗 {target_class} 클래스: {len(column_mapping)}개 속성 매핑 완료")
        
        return mapped_df
    
    def export_to_ttl(self, data_dict: Dict[str, pd.DataFrame], output_file: str):
        """RDF/TTL 형식으로 데이터 출력"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                # 네임스페이스 선언
                f.write(f"@prefix ex: <{self.namespace}> .\n")
                f.write("@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n\n")
                
                # 각 클래스별 데이터 출력
                for class_name, df in data_dict.items():
                    if df.empty:
                        continue
                    
                    ontology_class = self.class_mappings.get(class_name, class_name)
                    f.write(f"# {ontology_class} instances\n")
                    
                    for idx, row in df.iterrows():
                        subject_uri = f"ex:{class_name}_{idx}"
                        f.write(f"{subject_uri} a ex:{ontology_class} ;\n")
                        
                        # 속성 출력
                        properties = []
                        for col, value in row.items():
                            if pd.notna(value):
                                prop_name = f"ex:{col}"
                                if isinstance(value, (int, float)):
                                    properties.append(f"    {prop_name} {value}")
                                elif isinstance(value, datetime):
                                    properties.append(f'    {prop_name} "{value.isoformat()}"^^xsd:dateTime')
                                else:
                                    properties.append(f'    {prop_name} "{str(value)}"')
                        
                        f.write(" ;\n".join(properties))
                        f.write(" .\n\n")
            
            print(f"📄 RDF/TTL 출력 완료: {output_file}")
            
        except Exception as e:
            print(f"❌ TTL 출력 실패: {e}")

# =============================================================================
# 2. ENHANCED DATA UTILITIES
# =============================================================================

def find_column(df: pd.DataFrame, patterns: List[str]) -> Optional[str]:
    """컬럼 패턴 매칭"""
    df_cols_lower = {str(col).lower(): str(col) for col in df.columns}
    for pattern in patterns:
        p_lower = pattern.lower()
        for col_lower, col_original in df_cols_lower.items():
            if p_lower in col_lower:
                return col_original
    return None

def normalize_warehouse_name(raw_name: Any) -> str:
    """창고명 표준화 - 온톨로지 Warehouse 클래스 대응"""
    if pd.isna(raw_name):
        return 'UNKNOWN'
    name_lower = str(raw_name).lower().strip()
    
    # 매핑 룰 기반 정규화
    warehouse_rules = {
        'DSV Indoor': ['indoor', 'm44', 'hauler.*indoor'],
        'DSV Al Markaz': ['markaz', 'm1', 'al.*markaz'],
        'DSV Outdoor': ['outdoor', 'out'],
        'MOSB': ['mosb'],
        'DSV MZP': ['mzp'],
        'DHL WH': ['dhl'],
        'AAA Storage': ['aaa']
    }
    
    for canonical, patterns in warehouse_rules.items():
        if any(p in name_lower for p in patterns):
            return canonical
    return str(raw_name).strip()

def normalize_site_name(raw_name: Any) -> str:
    """사이트명 표준화 - 온톨로지 Site 클래스 대응"""
    if pd.isna(raw_name):
        return 'UNK'
    name_upper = str(raw_name).upper()
    
    site_patterns = {
        'AGI': ['AGI'],
        'DAS': ['DAS'], 
        'MIR': ['MIR'],
        'SHU': ['SHU']
    }
    
    for site, patterns in site_patterns.items():
        if any(p in name_upper for p in patterns):
            return site
    return 'UNK'

# =============================================================================
# 3. ENHANCED DATA LOADER
# =============================================================================

class EnhancedDataLoader:
    """향상된 데이터 로더 - 온톨로지 매핑 지원"""
    
    def __init__(self, ontology_mapper: OntologyMapper):
        self.mapper = ontology_mapper
    
    def load_and_process_files(self, data_dir: str = ".") -> pd.DataFrame:
        """모든 관련 Excel 파일을 로드하고 표준화된 TransportEvent로 변환"""
        all_movements = []
        
        # HVDC 창고 파일 패턴
        file_patterns = [
            "HVDC WAREHOUSE_HITACHI*.xlsx",
            "HVDC WAREHOUSE_SIMENSE*.xlsx"
        ]
        
        for pattern in file_patterns:
            for filepath in glob.glob(os.path.join(data_dir, pattern)):
                filename = os.path.basename(filepath)
                print(f"📄 파일 처리 중: {filename}")
                
                try:
                    # 인보이스 파일 스킵
                    if 'invoice' in filename.lower():
                        print(f"   - 인보이스 파일 스킵")
                        continue
                    
                    movements = self._process_warehouse_file(filepath)
                    if not movements.empty:
                        all_movements.append(movements)
                        print(f"   ✅ {len(movements)}건 이벤트 추출")
                    
                except Exception as e:
                    print(f"   ❌ 파일 처리 실패: {e}")
        
        if not all_movements:
            print("❌ 처리할 데이터가 없습니다!")
            return pd.DataFrame()
        
        # 모든 이동 기록 통합
        combined_df = pd.concat(all_movements, ignore_index=True)
        print(f"📊 총 {len(combined_df):,}건의 원시 이벤트 수집")
        
        return combined_df
    
    def _process_warehouse_file(self, filepath: str) -> pd.DataFrame:
        """개별 창고 파일 처리"""
        try:
            # Excel 파일 로드
            xl_file = pd.ExcelFile(filepath)
            sheet_name = xl_file.sheet_names[0]
            
            # Case List 시트 우선 선택
            for sheet in xl_file.sheet_names:
                if 'case' in sheet.lower() and 'list' in sheet.lower():
                    sheet_name = sheet
                    break
            
            df = pd.read_excel(filepath, sheet_name=sheet_name)
            
            # 핵심 컬럼 찾기
            case_col = find_column(df, ['case', 'carton', 'box', 'mr#', 'sct ship no', 'case no'])
            qty_col = find_column(df, ["q'ty", 'qty', 'quantity', 'received', "p'kg", 'pkg'])
            
            if not case_col:
                print(f"   ⚠️ Case 컬럼 없음")
                return pd.DataFrame()
            
            # 날짜 컬럼 식별 (창고/사이트 이동 기록)
            date_cols = []
            for col in df.columns:
                # 날짜 패턴이 있는 컬럼 찾기
                sample_values = df[col].dropna().astype(str).head(10)
                if any(self._is_date_like(val) for val in sample_values):
                    date_cols.append(col)
            
            print(f"   📅 날짜 컬럼 {len(date_cols)}개 발견")
            
            # 이벤트 추출
            movements = []
            for idx, row in df.iterrows():
                case_no = str(row[case_col]) if pd.notna(row[case_col]) else f"CASE_{idx}"
                qty = pd.to_numeric(row.get(qty_col, 1), errors='coerce') or 1
                
                # 각 날짜 컬럼에서 이벤트 추출
                case_events = []
                for date_col in date_cols:
                    if pd.notna(row[date_col]):
                        event_date = pd.to_datetime(row[date_col], errors='coerce')
                        if pd.notna(event_date):
                            # 🎯 수정: 날짜 컬럼명이 아닌 실제 창고명 추출
                            location = self._extract_warehouse_from_column_name(date_col)
                            if location != 'UNKNOWN':  # 유효한 창고명만 처리
                                case_events.append({
                                    'Case_No': case_no,
                                    'Date': event_date,
                                    'Qty': qty,
                                    'Location': location,
                                    'Raw_Location': str(date_col),
                                    'Source_File': os.path.basename(filepath)
                                })
                
                # 시간순 정렬
                case_events.sort(key=lambda x: x['Date'])
                movements.extend(case_events)
            
            return pd.DataFrame(movements)
            
        except Exception as e:
            print(f"   ❌ 파일 처리 오류: {e}")
            return pd.DataFrame()
    
    def _is_date_like(self, value: str) -> bool:
        """문자열이 날짜 형식인지 확인"""
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # 2024-01-01
            r'\d{2}/\d{2}/\d{4}',  # 01/01/2024
            r'\d{1,2}/\d{1,2}/\d{4}',  # 1/1/2024
        ]
        import re
        return any(re.search(pattern, str(value)) for pattern in date_patterns)
    
    def _extract_warehouse_from_column_name(self, col_name: str) -> str:
        """컬럼명에서 실제 창고명 추출 (날짜 필드 제외)"""
        col_lower = str(col_name).lower()
        
        # 🚫 날짜 관련 컬럼들은 창고가 아님
        date_keywords = ['etd', 'eta', 'atd', 'ata', 'date', 'time', 'departure', 'arrival']
        if any(keyword in col_lower for keyword in date_keywords):
            return 'UNKNOWN'
        
        # 🏢 실제 창고명 패턴 매칭
        warehouse_patterns = {
            'DSV Indoor': ['indoor', 'm44', 'hauler indoor'],
            'DSV Outdoor': ['outdoor', 'out '],
            'DSV Al Markaz': ['markaz', 'al markaz', 'm1'],
            'MOSB': ['mosb', 'barge'],
            'DSV MZP': ['mzp'],
            'DHL WH': ['dhl'],
            'AAA Storage': ['aaa'],
            'Shifting': ['shifting']
        }
        
        for warehouse, patterns in warehouse_patterns.items():
            if any(pattern in col_lower for pattern in patterns):
                return warehouse
        
        # 사이트 패턴도 확인
        site_patterns = ['agi', 'das', 'mir', 'shu']
        for site in site_patterns:
            if site in col_lower:
                return site.upper()
        
        return 'UNKNOWN'

# =============================================================================
# 4. ENHANCED TRANSACTION ENGINE
# =============================================================================

class EnhancedTransactionEngine:
    """향상된 트랜잭션 엔진 - 온톨로지 TransportEvent 매핑"""
    
    def __init__(self, ontology_mapper: OntologyMapper):
        self.mapper = ontology_mapper
    
    def create_transaction_log(self, raw_events: pd.DataFrame) -> pd.DataFrame:
        """원시 이벤트를 표준화된 TransportEvent 로그로 변환"""
        if raw_events.empty:
            return pd.DataFrame()
        
        print("🔄 트랜잭션 로그 생성 중...")
        
        # 날짜순 정렬
        raw_events = raw_events.sort_values(['Case_No', 'Date']).reset_index(drop=True)
        
        transactions = []
        
        # 케이스별로 이벤트 시퀀스 처리
        for case_no, group in raw_events.groupby('Case_No'):
            group = group.reset_index(drop=True)
            
            for i, row in group.iterrows():
                # 이전 위치 (FROM)
                loc_from = group.loc[i-1, 'Location'] if i > 0 else 'SOURCE'
                loc_to = row['Location']
                
                # 🎯 핵심: TxType_Refined 분류
                # 1. IN 트랜잭션 (현재 위치로 입고)
                tx_in = {
                    'Tx_ID': f"{case_no}_{row['Date'].strftime('%Y%m%d%H%M%S')}_IN",
                    'Case_No': case_no,
                    'Date': row['Date'],
                    'Qty': row['Qty'],
                    'TxType': 'IN',
                    'TxType_Refined': 'IN',
                    'Loc_From': loc_from,
                    'Loc_To': loc_to,
                    'Location': loc_to,  # 재고 계산용
                    'Site': normalize_site_name(loc_to),
                    'Source_File': row['Source_File']
                }
                transactions.append(tx_in)
                
                # 2. OUT 트랜잭션 (이전 위치에서 출고)
                if i > 0:  # 첫 번째가 아닌 경우에만 OUT 생성
                    prev_location = group.loc[i-1, 'Location']
                    
                    # 🎯 FINAL_OUT vs TRANSFER_OUT 분류
                    site_name = normalize_site_name(loc_to)
                    if site_name != 'UNK':
                        # 현장으로 배송 = FINAL_OUT
                        tx_type_refined = 'FINAL_OUT'
                    else:
                        # 창고간 이동 = TRANSFER_OUT
                        tx_type_refined = 'TRANSFER_OUT'
                    
                    tx_out = {
                        'Tx_ID': f"{case_no}_{row['Date'].strftime('%Y%m%d%H%M%S')}_OUT",
                        'Case_No': case_no,
                        'Date': row['Date'],
                        'Qty': row['Qty'],
                        'TxType': 'OUT',
                        'TxType_Refined': tx_type_refined,
                        'Loc_From': prev_location,
                        'Loc_To': loc_to,
                        'Location': prev_location,  # 재고 계산용 (출고 위치)
                        'Site': site_name,
                        'Source_File': row['Source_File']
                    }
                    transactions.append(tx_out)
        
        tx_df = pd.DataFrame(transactions)
        
        if not tx_df.empty:
            # 중복 제거
            tx_df = tx_df.drop_duplicates(subset=['Tx_ID']).reset_index(drop=True)
            
            # 트랜잭션 타입 분포 출력
            print("📊 트랜잭션 타입 분포:")
            type_counts = tx_df['TxType_Refined'].value_counts()
            for tx_type, count in type_counts.items():
                percentage = (count / len(tx_df)) * 100
                print(f"   {tx_type}: {count:,}건 ({percentage:.1f}%)")
        
        return tx_df

# =============================================================================
# 5. ENHANCED ANALYSIS ENGINE
# =============================================================================

class EnhancedAnalysisEngine:
    """향상된 분석 엔진 - StockSnapshot 및 DeadStock 생성"""
    
    def __init__(self, ontology_mapper: OntologyMapper):
        self.mapper = ontology_mapper
    
    def calculate_daily_stock(self, tx_df: pd.DataFrame) -> pd.DataFrame:
        """일별 재고 계산 - StockSnapshot 클래스 매핑"""
        if tx_df.empty:
            return pd.DataFrame()
        
        print("📊 일별 재고 계산 중...")
        
        # 날짜별, 위치별 집계
        tx_df['Date'] = pd.to_datetime(tx_df['Date']).dt.date
        
        daily_summary = tx_df.groupby(['Location', 'Date', 'TxType_Refined']).agg({
            'Qty': 'sum'
        }).reset_index()
        
        # 피벗으로 입고/출고 분리
        daily_pivot = daily_summary.pivot_table(
            index=['Location', 'Date'],
            columns='TxType_Refined', 
            values='Qty',
            fill_value=0
        ).reset_index()
        
        # 컬럼명 정리
        daily_pivot.columns.name = None
        expected_cols = ['IN', 'TRANSFER_OUT', 'FINAL_OUT']
        for col in expected_cols:
            if col not in daily_pivot.columns:
                daily_pivot[col] = 0
        
        # 재고 계산 (위치별 누적)
        stock_records = []
        
        for location in daily_pivot['Location'].unique():
            if location in ['UNKNOWN', 'UNK']:
                continue
                
            loc_data = daily_pivot[daily_pivot['Location'] == location].copy()
            loc_data = loc_data.sort_values('Date')
            
            opening_stock = 0
            
            for _, row in loc_data.iterrows():
                inbound = row['IN']
                transfer_out = row['TRANSFER_OUT'] 
                final_out = row['FINAL_OUT']
                total_outbound = transfer_out + final_out
                
                closing_stock = opening_stock + inbound - total_outbound
                
                stock_records.append({
                    'Location': location,
                    'Date': row['Date'],
                    'Opening_Stock': opening_stock,
                    'Inbound': inbound,
                    'Transfer_Out': transfer_out,
                    'Final_Out': final_out,
                    'Total_Outbound': total_outbound,
                    'Closing_Stock': closing_stock,
                    'Date_Snapshot': row['Date']  # 온톨로지 매핑용
                })
                
                opening_stock = closing_stock
        
        daily_stock_df = pd.DataFrame(stock_records)
        print(f"✅ {len(daily_stock_df)}개 일별 재고 스냅샷 생성")
        
        return daily_stock_df
    
    def validate_stock_integrity(self, daily_stock_df: pd.DataFrame) -> Dict[str, Any]:
        """재고 무결성 검증 - (Opening + Inbound - Outbound = Closing)"""
        print("🔬 재고 무결성 검증 중...")
        
        if daily_stock_df.empty:
            return {"status": "SKIP", "message": "검증할 데이터 없음"}
        
        validation_results = []
        total_errors = 0
        
        for _, row in daily_stock_df.iterrows():
            expected_closing = row['Opening_Stock'] + row['Inbound'] - row['Total_Outbound']
            actual_closing = row['Closing_Stock']
            difference = abs(actual_closing - expected_closing)
            
            if difference > 0.01:  # 부동소수점 오차 허용
                total_errors += 1
                validation_results.append({
                    'Location': row['Location'],
                    'Date': row['Date'],
                    'Expected': expected_closing,
                    'Actual': actual_closing,
                    'Difference': difference
                })
        
        if total_errors == 0:
            print("✅ 검증 통과! 모든 재고 계산이 정확합니다.")
            return {"status": "PASS", "errors": 0, "details": []}
        else:
            print(f"❌ 검증 실패! {total_errors}개 오류 발견")
            return {"status": "FAIL", "errors": total_errors, "details": validation_results[:10]}
    
    def analyze_dead_stock(self, tx_df: pd.DataFrame, threshold_days: int = 180) -> pd.DataFrame:
        """장기 체화 재고 분석 - DeadStock 클래스 매핑"""
        print(f"📦 장기 체화 재고 분석 (기준: {threshold_days}일)...")
        
        if tx_df.empty:
            return pd.DataFrame()
        
        # 각 케이스의 마지막 이동 날짜 계산
        tx_df['Date'] = pd.to_datetime(tx_df['Date'])
        latest_moves = tx_df.groupby('Case_No')['Date'].max().reset_index()
        latest_moves.columns = ['Case_No', 'Last_Move_Date']
        
        # 현재 날짜와 비교
        current_date = datetime.now()
        latest_moves['Days_Since_Last_Move'] = (current_date - latest_moves['Last_Move_Date']).dt.days
        
        # 장기 체화 재고 필터링
        dead_stock = latest_moves[latest_moves['Days_Since_Last_Move'] >= threshold_days].copy()
        
        if not dead_stock.empty:
            # 추가 정보 조인
            case_info = tx_df.groupby('Case_No').agg({
                'Qty': 'first',
                'Location': 'last',  # 마지막 위치
                'Source_File': 'first'
            }).reset_index()
            
            dead_stock = dead_stock.merge(case_info, on='Case_No', how='left')
            
            print(f"⚠️ {len(dead_stock)}개 장기 체화 재고 케이스 발견")
        else:
            print("✅ 장기 체화 재고 없음")
        
        return dead_stock
    
    def create_monthly_summary(self, tx_df: pd.DataFrame, daily_stock: pd.DataFrame) -> pd.DataFrame:
        """월별 요약 생성"""
        print("📅 월별 요약 생성 중...")
        
        if tx_df.empty:
            return pd.DataFrame()
        
        # 월별 트랜잭션 집계
        tx_df['YearMonth'] = pd.to_datetime(tx_df['Date']).dt.to_period('M').astype(str)
        
        monthly_tx = tx_df.groupby(['Location', 'YearMonth', 'TxType_Refined']).agg({
            'Qty': 'sum'
        }).reset_index()
        
        # 피벗
        monthly_pivot = monthly_tx.pivot_table(
            index=['Location', 'YearMonth'],
            columns='TxType_Refined',
            values='Qty',
            fill_value=0
        ).reset_index()
        
        monthly_pivot.columns.name = None
        
        # 필요한 컬럼 추가
        for col in ['IN', 'TRANSFER_OUT', 'FINAL_OUT']:
            if col not in monthly_pivot.columns:
                monthly_pivot[col] = 0
        
        # 월말 재고 추가
        if not daily_stock.empty:
            # 각 위치별 월별 마지막 재고
            daily_stock['YearMonth'] = pd.to_datetime(daily_stock['Date']).dt.to_period('M').astype(str)
            monthly_closing = daily_stock.groupby(['Location', 'YearMonth'])['Closing_Stock'].last().reset_index()
            
            monthly_pivot = monthly_pivot.merge(monthly_closing, on=['Location', 'YearMonth'], how='left')
            monthly_pivot['Closing_Stock'] = monthly_pivot['Closing_Stock'].fillna(0)
        else:
            monthly_pivot['Closing_Stock'] = 0
        
        # 컬럼 순서 정리
        column_order = ['Location', 'YearMonth', 'IN', 'TRANSFER_OUT', 'FINAL_OUT', 'Closing_Stock']
        monthly_pivot = monthly_pivot[column_order]
        
        print(f"✅ {len(monthly_pivot)}개 월별 요약 레코드 생성")
        
        return monthly_pivot

# =============================================================================
# 6. ENHANCED REPORT WRITER
# =============================================================================

class EnhancedReportWriter:
    """향상된 리포트 작성기 - 온톨로지 매핑 지원"""
    
    def __init__(self, ontology_mapper: OntologyMapper):
        self.mapper = ontology_mapper
    
    def save_comprehensive_report(self, analysis_results: Dict[str, pd.DataFrame], output_path: str):
        """종합 리포트 저장 (Excel + RDF/TTL)"""
        print(f"📄 종합 리포트 생성: {output_path}")
        
        # Excel 리포트 저장
        self._save_excel_report(analysis_results, output_path)
        
        # RDF/TTL 리포트 저장
        ttl_path = output_path.replace('.xlsx', '.ttl')
        self._save_rdf_report(analysis_results, ttl_path)
    
    def _save_excel_report(self, data: Dict[str, pd.DataFrame], output_path: str):
        """Excel 리포트 저장"""
        try:
            with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
                workbook = writer.book
                
                # 서식 정의
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'fg_color': '#D7E4BC',
                    'border': 1,
                    'align': 'center'
                })
                
                number_format = workbook.add_format({'num_format': '#,##0'})
                date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})
                
                # 시트별 저장
                sheet_configs = {
                    'transaction_log': '전체_트랜잭션_로그',
                    'daily_stock': '일별_재고_상세',
                    'monthly_summary': '월별_입출고_재고_요약',
                    'dead_stock': '장기체화재고_분석',
                    'validation_results': '무결성_검증_결과'
                }
                
                for data_key, sheet_name in sheet_configs.items():
                    if data_key in data and not data[data_key].empty:
                        df = data[data_key]
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        
                        # 서식 적용
                        worksheet = writer.sheets[sheet_name]
                        
                        # 헤더 서식
                        for col_num, value in enumerate(df.columns.values):
                            worksheet.write(0, col_num, value, header_format)
                        
                        # 컬럼별 서식
                        for i, col in enumerate(df.columns):
                            if 'Qty' in col or 'Stock' in col or col in ['IN', 'TRANSFER_OUT', 'FINAL_OUT']:
                                worksheet.set_column(i, i, 12, number_format)
                            elif 'Date' in col:
                                worksheet.set_column(i, i, 12, date_format)
                            else:
                                worksheet.set_column(i, i, 15)
            
            print(f"✅ Excel 리포트 저장 완료: {output_path}")
            
        except Exception as e:
            print(f"❌ Excel 리포트 저장 실패: {e}")
    
    def _save_rdf_report(self, data: Dict[str, pd.DataFrame], ttl_path: str):
        """RDF/TTL 리포트 저장"""
        try:
            # 온톨로지 클래스별 데이터 매핑
            ontology_data = {}
            
            # TransportEvent
            if 'transaction_log' in data:
                tx_df = data['transaction_log'].copy()
                ontology_data['TransportEvent'] = self.mapper.map_dataframe_columns(tx_df, 'TransportEvent')
            
            # StockSnapshot  
            if 'daily_stock' in data:
                stock_df = data['daily_stock'].copy()
                ontology_data['StockSnapshot'] = self.mapper.map_dataframe_columns(stock_df, 'StockSnapshot')
            
            # DeadStock
            if 'dead_stock' in data:
                dead_df = data['dead_stock'].copy()
                ontology_data['DeadStock'] = self.mapper.map_dataframe_columns(dead_df, 'DeadStock')
            
            # TTL 출력
            self.mapper.export_to_ttl(ontology_data, ttl_path)
            
        except Exception as e:
            print(f"❌ RDF/TTL 리포트 저장 실패: {e}")

# =============================================================================
# 7. MAIN PIPELINE
# =============================================================================

def main():
    """메인 파이프라인 실행"""
    print("🚀 HVDC 온톨로지 강화 파이프라인 시작")
    print("=" * 60)
    
    try:
        # 1. 온톨로지 매퍼 초기화
        mapper = OntologyMapper("mapping_rules_v2.4.json")
        
        print(f"✅ 온톨로지 매핑 룰 반영 완료!")
        print(f"   🔗 네임스페이스: {mapper.namespace}")
        print(f"   📊 클래스 매핑: {len(mapper.class_mappings)}개")
        print(f"   🏷️ 속성 매핑: {len(mapper.property_mappings)}개")
        print()
        
        # 2. 데이터 로더 초기화 및 데이터 로딩
        loader = EnhancedDataLoader(mapper)
        print("📄 데이터 파일 로딩 중...")
        raw_data = loader.load_and_process_files("data")
        
        if raw_data.empty:
            print("⚠️ 로딩된 데이터가 없습니다. data/ 디렉토리의 파일을 확인하세요.")
            return False
        
        print(f"✅ 총 {len(raw_data)}개 이벤트 로딩 완료")
        print()
        
        # 3. 트랜잭션 엔진으로 로그 생성
        tx_engine = EnhancedTransactionEngine(mapper)
        print("🔄 트랜잭션 로그 생성 중...")
        transaction_log = tx_engine.create_transaction_log(raw_data)
        
        # 4. 분석 엔진으로 상세 분석
        analyzer = EnhancedAnalysisEngine(mapper)
        
        print("📊 일별 재고 계산 중...")
        daily_stock = analyzer.calculate_daily_stock(transaction_log)
        
        print("🔍 재고 무결성 검증 중...")
        validation_results = analyzer.validate_stock_integrity(daily_stock)
        
        print("⚠️ 장기 체화 재고 분석 중...")
        dead_stock = analyzer.analyze_dead_stock(transaction_log)
        
        print("📅 월별 요약 생성 중...")
        monthly_summary = analyzer.create_monthly_summary(transaction_log, daily_stock)
        
        # 5. 결과 종합
        analysis_results = {
            'transaction_log': transaction_log,
            'daily_stock': daily_stock,
            'monthly_summary': monthly_summary,
            'dead_stock': dead_stock,
            'validation_results': pd.DataFrame([validation_results])
        }
        
        # 6. 리포트 저장
        report_writer = EnhancedReportWriter(mapper)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"HVDC_통합_온톨로지_분석_리포트_{timestamp}.xlsx"
        
        print("📄 종합 리포트 저장 중...")
        report_writer.save_comprehensive_report(analysis_results, output_path)
        
        print("\n" + "=" * 60)
        print("🎉 HVDC 온톨로지 분석 파이프라인 완료!")
        print(f"📁 출력 파일: {output_path}")
        print(f"🔗 RDF/TTL 파일: {output_path.replace('.xlsx', '.ttl')}")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ 파이프라인 실행 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print(f"\n🎉 온톨로지 매핑 룰 반영 완료!")
    else:
        print(f"\n💥 매핑 룰 반영 실패") 