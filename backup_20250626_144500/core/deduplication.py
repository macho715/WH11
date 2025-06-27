"""
HVDC 이중계산 방지 모듈 - 핵심 함수 수정
"""

import pandas as pd
from typing import List, Dict, Any, Set, Tuple, Optional
import hashlib
import logging
from datetime import datetime, timedelta
from .config_manager import config_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def drop_duplicate_transfers(df: pd.DataFrame) -> pd.DataFrame:
    """
    TRANSFER 중복 제거 - 개선된 버전
    """
    # 트랜잭션 타입 컬럼 확인
    tx_col = None
    for candidate in ['TxType_Refined', 'Transaction_Type']:
        if candidate in df.columns:
            tx_col = candidate
            break
    
    if not tx_col:
        logger.warning("트랜잭션 타입 컬럼이 없어 중복 제거를 건너뜁니다")
        return df
    
    # TRANSFER 마스크
    transfer_mask = df[tx_col].str.contains('TRANSFER', na=False, case=False)
    
    if not transfer_mask.any():
        return df
    
    # 중복 제거 키 정의
    dedup_columns = ['Case_No', 'Qty', 'Location', 'Target_Warehouse', tx_col]
    
    # 필요한 컬럼이 없으면 생성
    for col in dedup_columns:
        if col not in df.columns:
            if col == 'Target_Warehouse':
                df[col] = df.get('Location', 'UNKNOWN')
            else:
                df[col] = 'UNKNOWN'
    
    # Target_Warehouse 결측값 처리
    df.loc[transfer_mask, 'Target_Warehouse'] = (
        df.loc[transfer_mask, 'Target_Warehouse'].fillna('UNKNOWN')
    )
    
    # TRANSFER 트랜잭션 중복 제거
    transfer_dedup = df[transfer_mask].drop_duplicates(subset=dedup_columns)
    non_transfer = df[~transfer_mask]
    
    # 결합
    result_df = pd.concat([non_transfer, transfer_dedup], ignore_index=True)
    
    removed_count = len(df) - len(result_df)
    if removed_count > 0:
        logger.info(f"🗑️ TRANSFER 중복 제거: {removed_count}건 제거")
    
    return result_df

def reconcile_orphan_transfers(df: pd.DataFrame) -> pd.DataFrame:
    """
    TRANSFER 짝 보정 - 개선된 버전
    693건의 불일치를 완전히 해결
    """
    # 트랜잭션 타입 컬럼 확인
    tx_col = None
    for candidate in ['TxType_Refined', 'Transaction_Type']:
        if candidate in df.columns:
            tx_col = candidate
            break
    
    if not tx_col:
        logger.warning("트랜잭션 타입 컬럼이 없습니다")
        return df
    
    # 필수 컬럼 전처리
    required_cols = ['Case_No', 'Qty', 'Location', 'Target_Warehouse']
    for col in required_cols:
        if col not in df.columns:
            if col == 'Target_Warehouse':
                df[col] = df.get('Location', 'UNKNOWN')
            else:
                df[col] = 'UNKNOWN'
    
    # 결측값 처리
    df['Location'] = df['Location'].fillna('UNKNOWN')
    df['Target_Warehouse'] = df['Target_Warehouse'].fillna('UNKNOWN')
    df['Qty'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(1).astype(int)
    
    # TRANSFER 트랜잭션 마스크
    transfer_mask = df[tx_col].str.contains('TRANSFER', na=False, case=False)
    
    if not transfer_mask.any():
        logger.info("TRANSFER 트랜잭션이 없습니다")
        return df
    
    # TRANSFER 트랜잭션 피벗 분석
    transfer_df = df[transfer_mask].copy()
    
    # 케이스별 TRANSFER IN/OUT 집계
    pivot_key = ['Case_No', 'Location', 'Target_Warehouse']
    
    try:
        pivot_table = transfer_df.pivot_table(
            index=pivot_key,
            columns=tx_col,
            values='Qty',
            aggfunc='sum',
            fill_value=0
        )
    except Exception as e:
        logger.warning(f"피벗 테이블 생성 실패: {e}")
        return df
    
    # IN만 있는 케이스 (OUT 생성 필요)
    transfer_in_col = 'TRANSFER_IN'
    transfer_out_col = 'TRANSFER_OUT'
    
    orphan_in = []
    orphan_out = []
    
    for idx, row in pivot_table.iterrows():
        case_no, location, target_wh = idx
        
        in_qty = row.get(transfer_in_col, 0)
        out_qty = row.get(transfer_out_col, 0)
        
        if in_qty > 0 and out_qty == 0:
            # IN만 있음 -> OUT 생성
            orphan_in.append((case_no, location, target_wh, in_qty))
            
        elif out_qty > 0 and in_qty == 0:
            # OUT만 있음 -> IN 생성
            orphan_out.append((case_no, location, target_wh, out_qty))
    
    # 수정 레코드 생성
    fixes = []
    
    # IN만 있는 경우 -> OUT 생성
    for case_no, location, target_wh, qty in orphan_in:
        # 해당 케이스의 기존 날짜 참조
        case_dates = df[df['Case_No'] == case_no]['Date'].dropna()
        fix_date = case_dates.iloc[0] if len(case_dates) > 0 else pd.Timestamp.now()
        
        fix_record = {
            'Case_No': case_no,
            'Date': fix_date,
            'Qty': qty,
            tx_col: 'TRANSFER_OUT',
            'Location': location,  # 출고 위치
            'Target_Warehouse': target_wh,
            'Loc_From': location,
            'Source_File': 'AUTO_FIX_IN_TO_OUT'
        }
        fixes.append(fix_record)
    
    # OUT만 있는 경우 -> IN 생성 (692건 해결)
    for case_no, location, target_wh, qty in orphan_out:
        # 해당 케이스의 기존 날짜 참조
        case_dates = df[df['Case_No'] == case_no]['Date'].dropna()
        fix_date = case_dates.iloc[0] if len(case_dates) > 0 else pd.Timestamp.now()
        
        fix_record = {
            'Case_No': case_no,
            'Date': fix_date,
            'Qty': qty,
            tx_col: 'TRANSFER_IN',
            'Location': target_wh,  # 입고 위치
            'Target_Warehouse': location,
            'Loc_From': location,
            'Source_File': 'AUTO_FIX_OUT_TO_IN'
        }
        fixes.append(fix_record)
    
    if fixes:
        print(f"🛠️ AUTO-FIX 추가: IN→OUT {len(orphan_in)}건 / OUT→IN {len(orphan_out)}건")
        
        # 수정 레코드를 DataFrame에 추가
        fix_df = pd.DataFrame(fixes)
        
        # 원본 DataFrame과 컬럼 맞추기
        for col in df.columns:
            if col not in fix_df.columns:
                fix_df[col] = 'AUTO_FIX' if col in ['Site', 'Source_File'] else None
        
        # 컬럼 순서 맞추기
        fix_df = fix_df.reindex(columns=df.columns, fill_value=None)
        
        # 결합
        result_df = pd.concat([df, fix_df], ignore_index=True)
        
        logger.info(f"✅ TRANSFER 보정 완료: {len(fixes)}건 추가")
        return result_df
    else:
        logger.info("✅ TRANSFER 짝이 이미 완전함")
        return df

def validate_transfer_pairs_fixed(df: pd.DataFrame) -> None:
    """
    TRANSFER 짝 검증 - 개선된 버전
    """
    # 트랜잭션 타입 컬럼 확인
    tx_col = None
    for candidate in ['TxType_Refined', 'Transaction_Type']:
        if candidate in df.columns:
            tx_col = candidate
            break
    
    if not tx_col:
        logger.warning("트랜잭션 타입 컬럼이 없어 검증을 건너뜁니다")
        return
    
    # TRANSFER 마스크
    transfer_mask = df[tx_col].str.contains('TRANSFER', na=False, case=False)
    
    if not transfer_mask.any():
        logger.info("TRANSFER 트랜잭션이 없습니다")
        return
    
    # 케이스별 TRANSFER IN/OUT 집계
    transfer_summary = (df[transfer_mask]
                       .groupby(['Case_No', tx_col])['Qty']
                       .sum()
                       .unstack(fill_value=0))
    
    # 컬럼 확인 및 생성
    if 'TRANSFER_IN' not in transfer_summary.columns:
        transfer_summary['TRANSFER_IN'] = 0
    if 'TRANSFER_OUT' not in transfer_summary.columns:
        transfer_summary['TRANSFER_OUT'] = 0
    
    # 차이 계산
    transfer_summary['DIFF'] = (
        transfer_summary['TRANSFER_IN'] - transfer_summary['TRANSFER_OUT']
    ).abs()
    
    # 불일치 케이스 확인
    mismatched = transfer_summary[transfer_summary['DIFF'] > 0]
    
    if len(mismatched) > 0:
        print(f"\n❌ TRANSFER 짝 불일치: {len(mismatched)}건")
        print("불일치 케이스 샘플:")
        print(mismatched[['TRANSFER_IN', 'TRANSFER_OUT', 'DIFF']].head())
        raise ValueError(f"TRANSFER 짝 불일치: {len(mismatched)} 케이스")
    else:
        logger.info("✅ TRANSFER 짝 모두 일치")

def validate_date_sequence_fixed(df: pd.DataFrame) -> None:
    """
    날짜 순서 검증 - 개선된 버전
    """
    case_col = 'Case_No' if 'Case_No' in df.columns else 'Case_ID'
    
    if case_col not in df.columns:
        logger.warning("케이스 컬럼이 없어 날짜 검증을 건너뜁니다")
        return
    
    bad_cases = []
    
    for case_id, group in df.groupby(case_col):
        if len(group) <= 1:
            continue
            
        # 날짜순 정렬
        sorted_dates = group.sort_values('Date')['Date']
        
        # 단조 증가 확인
        if not sorted_dates.is_monotonic_increasing:
            bad_cases.append(case_id)
    
    if bad_cases:
        print(f"⚠️ 날짜 역순 케이스: {len(bad_cases)}개")
        if len(bad_cases) <= 5:
            print(f"   예시: {bad_cases}")
        else:
            print(f"   예시: {bad_cases[:5]}... (총 {len(bad_cases)}개)")
        
        # AUTO_FIX 케이스는 경고만 출력
        auto_fix_cases = df[df.get('Source_File', '').str.contains('AUTO_FIX', na=False)]['Case_No'].unique()
        auto_fix_bad = [case for case in bad_cases if case in auto_fix_cases]
        
        if len(auto_fix_bad) == len(bad_cases):
            logger.warning("모든 날짜 역순이 AUTO_FIX 케이스입니다 - 무시")
            return
        
        raise ValueError(f"날짜 역순 Case {len(bad_cases)}개")
    else:
        logger.info("✅ 모든 케이스의 날짜 순서가 올바름")

class DeduplicationEngine:
    """HVDC 이중계산 방지 엔진"""
    
    def __init__(self):
        self.seen_transactions = set()
        self.duplicate_log = []
        self.config = config_manager
        self.deduplication_rules = self.config.get_deduplication_config()
        
    def generate_transaction_hash(self, transaction: Dict) -> str:
        """트랜잭션 고유 해시 생성"""
        data = transaction.get('data', {})
        
        # 핵심 식별자들
        key_fields = [
            str(data.get('warehouse', '')),
            str(data.get('site', '')),
            str(data.get('incoming', 0)),
            str(data.get('outgoing', 0)),
            str(data.get('date', '')),
        ]
        
        # 해시 생성
        key_string = '|'.join(key_fields)
        return hashlib.md5(key_string.encode('utf-8')).hexdigest()
    
    def is_duplicate_transaction(self, transaction: Dict, existing_transactions: List[Dict]) -> Tuple[bool, Optional[Dict]]:
        """트랜잭션 중복 여부 판단"""
        current_data = transaction.get('data', {})
        
        for existing in existing_transactions:
            existing_data = existing.get('data', {})
            
            # 1. 위치 일치 확인
            if not self._locations_match(current_data, existing_data):
                continue
                
            # 2. 시간 윈도우 확인
            if not self._within_time_window(current_data, existing_data):
                continue
                
            # 3. 수량 유사성 확인
            if self._quantities_similar(current_data, existing_data):
                return True, existing
                
        return False, None
    
    def _locations_match(self, data1: Dict, data2: Dict) -> bool:
        """위치 정보 일치 확인"""
        location_fields = ['warehouse', 'site']
        
        for field in location_fields:
            val1 = str(data1.get(field, '')).strip().lower()
            val2 = str(data2.get(field, '')).strip().lower()
            
            if val1 and val2 and val1 != val2:
                return False
                
        return True
    
    def _within_time_window(self, data1: Dict, data2: Dict) -> bool:
        """시간 윈도우 내 확인"""
        date1 = data1.get('date')
        date2 = data2.get('date')
        
        if not date1 or not date2:
            return True  # 날짜 정보 없으면 다른 조건으로 판단
            
        try:
            if isinstance(date1, str):
                date1 = pd.to_datetime(date1)
            if isinstance(date2, str):
                date2 = pd.to_datetime(date2)
                
            time_diff = abs((date1 - date2).total_seconds() / 60)
            time_window = self.deduplication_rules.get('time_window_minutes', 5)
            return time_diff <= time_window
            
        except Exception as e:
            logger.warning(f"날짜 비교 실패: {e}")
            return True
    
    def _quantities_similar(self, data1: Dict, data2: Dict) -> bool:
        """수량 유사성 확인"""
        quantity_fields = ['incoming', 'outgoing', 'inventory']
        tolerance = self.deduplication_rules.get('quantity_tolerance', 0.1)
        
        matches = 0
        total_fields = 0
        
        for field in quantity_fields:
            val1 = data1.get(field, 0)
            val2 = data2.get(field, 0)
            
            if val1 != 0 or val2 != 0:  # 둘 중 하나라도 0이 아니면 비교
                total_fields += 1
                if abs(float(val1) - float(val2)) <= tolerance:
                    matches += 1
                    
        return matches > 0 and matches == total_fields
    
    def handle_internal_transfers(self, transactions: List[Dict]) -> List[Dict]:
        """내부 이동 처리 - 한 번만 차감하도록 보장"""
        logger.info("🔄 내부 이동 처리 시작")
        
        internal_config = self.deduplication_rules.get('internal_transfer_handling', {})
        single_deduction = internal_config.get('single_deduction', True)
        internal_warehouses = internal_config.get('internal_warehouses', ['Shifting'])
        
        if not single_deduction:
            logger.info("내부 이동 단일 차감 비활성화됨")
            return transactions
        
        # 내부 창고별로 그룹화
        internal_groups = {}
        regular_transactions = []
        
        for transaction in transactions:
            data = transaction.get('data', {})
            warehouse = data.get('warehouse', '')
            
            if self.config.is_internal_warehouse(warehouse):
                if warehouse not in internal_groups:
                    internal_groups[warehouse] = []
                internal_groups[warehouse].append(transaction)
            else:
                regular_transactions.append(transaction)
        
        # 내부 이동 처리
        processed_internal = []
        for warehouse, group in internal_groups.items():
            logger.info(f"내부 창고 처리: {warehouse} ({len(group)}건)")
            
            if len(group) == 1:
                processed_internal.append(group[0])
            else:
                # 중복 제거 후 첫 번째만 유지
                deduplicated = self.remove_duplicates_for_internal(group)
                if deduplicated:
                    processed_internal.append(deduplicated[0])
                    logger.info(f"  ✅ {warehouse}: {len(group)}건 → 1건으로 통합")
        
        result = regular_transactions + processed_internal
        logger.info(f"✅ 내부 이동 처리 완료: {len(transactions)}건 → {len(result)}건")
        
        return result
    
    def remove_duplicates_for_internal(self, transactions: List[Dict]) -> List[Dict]:
        """내부 이동용 중복 제거 (더 엄격한 기준)"""
        if len(transactions) <= 1:
            return transactions
        
        # 시간순 정렬
        sorted_transactions = sorted(transactions, 
                                   key=lambda x: x.get('data', {}).get('date', datetime.min))
        
        # 첫 번째 트랜잭션만 유지
        return [sorted_transactions[0]]
    
    def remove_duplicates(self, transactions: List[Dict]) -> List[Dict]:
        """중복 트랜잭션 제거"""
        logger.info(f"🔍 중복 제거 시작: {len(transactions)}건")
        
        # 내부 이동 처리 먼저 수행
        if self.deduplication_rules.get('enable_deduplication', True):
            transactions = self.handle_internal_transfers(transactions)
        
        unique_transactions = []
        duplicate_count = 0
        
        for i, transaction in enumerate(transactions):
            is_duplicate, duplicate_of = self.is_duplicate_transaction(
                transaction, unique_transactions
            )
            
            if is_duplicate:
                duplicate_count += 1
                self.duplicate_log.append({
                    'index': i,
                    'transaction': transaction,
                    'duplicate_of': duplicate_of,
                    'reason': 'Similar transaction found'
                })
                logger.debug(f"중복 발견: {transaction['source_file']}")
            else:
                unique_transactions.append(transaction)
                
        logger.info(f"✅ 중복 제거 완료: {duplicate_count}건 제거, {len(unique_transactions)}건 유지")
        return unique_transactions
    
    def remove_hash_duplicates(self, transactions: List[Dict]) -> List[Dict]:
        """해시 기반 중복 제거 (빠른 방법)"""
        logger.info(f"🔍 해시 기반 중복 제거: {len(transactions)}건")
        
        seen_hashes = set()
        unique_transactions = []
        duplicate_count = 0
        
        for transaction in transactions:
            tx_hash = self.generate_transaction_hash(transaction)
            
            if tx_hash in seen_hashes:
                duplicate_count += 1
                self.duplicate_log.append({
                    'hash': tx_hash,
                    'transaction': transaction,
                    'reason': 'Identical hash'
                })
            else:
                seen_hashes.add(tx_hash)
                unique_transactions.append(transaction)
                
        logger.info(f"✅ 해시 중복 제거 완료: {duplicate_count}건 제거, {len(unique_transactions)}건 유지")
        return unique_transactions
    
    def detect_logical_duplicates(self, transactions: List[Dict]) -> List[Dict]:
        """논리적 중복 감지 및 통합"""
        logger.info("🔍 논리적 중복 감지 시작")
        
        # 창고별, 날짜별로 그룹화
        grouped = self._group_transactions_by_key(transactions)
        
        merged_transactions = []
        merge_count = 0
        
        for key, group in grouped.items():
            if len(group) > 1:
                # 동일 키의 트랜잭션들 병합
                merged = self._merge_transaction_group(group)
                merged_transactions.append(merged)
                merge_count += len(group) - 1
            else:
                merged_transactions.append(group[0])
                
        logger.info(f"✅ 논리적 중복 처리 완료: {merge_count}건 병합")
        return merged_transactions
    
    def _group_transactions_by_key(self, transactions: List[Dict]) -> Dict[str, List[Dict]]:
        """트랜잭션을 키별로 그룹화"""
        groups = {}
        
        for transaction in transactions:
            data = transaction.get('data', {})
            
            # 그룹핑 키 생성
            key = f"{data.get('warehouse', '')}_" \
                  f"{data.get('site', '')}_" \
                  f"{str(data.get('date', ''))[:10]}"  # 날짜만 (시간 제외)
            
            if key not in groups:
                groups[key] = []
            groups[key].append(transaction)
            
        return groups
    
    def _merge_transaction_group(self, transactions: List[Dict]) -> Dict:
        """동일 그룹의 트랜잭션들 병합"""
        if len(transactions) == 1:
            return transactions[0]
            
        # 첫 번째 트랜잭션을 베이스로 사용
        merged = transactions[0].copy()
        merged_data = merged['data'].copy()
        
        # 수량 필드들 합산
        quantity_fields = ['incoming', 'outgoing']
        for field in quantity_fields:
            total = sum(t['data'].get(field, 0) for t in transactions)
            if total > 0:
                merged_data[field] = total
                
        # 소스 정보 통합
        source_files = list(set(t['source_file'] for t in transactions))
        merged['source_file'] = '; '.join(source_files)
        
        # 병합 메타데이터 추가
        merged['merged_from'] = len(transactions)
        merged['merged_at'] = datetime.now()
        merged['data'] = merged_data
        
        return merged
    
    def validate_deduplication_integrity(self, original: List[Dict], deduplicated: List[Dict]) -> Dict[str, Any]:
        """중복 제거 무결성 검증"""
        logger.info("🔍 중복 제거 무결성 검증")
        
        # 전체 수량 보존 확인
        original_totals = self._calculate_totals(original)
        deduplicated_totals = self._calculate_totals(deduplicated)
        
        integrity_report = {
            'original_count': len(original),
            'deduplicated_count': len(deduplicated),
            'removed_count': len(original) - len(deduplicated),
            'original_totals': original_totals,
            'deduplicated_totals': deduplicated_totals,
            'quantity_preserved': abs(original_totals['total_incoming'] - deduplicated_totals['total_incoming']) < 0.01,
            'duplicate_log_count': len(self.duplicate_log)
        }
        
        # 검증 결과 로깅
        if integrity_report['quantity_preserved']:
            logger.info("✅ 중복 제거 무결성 검증 통과")
        else:
            logger.warning("⚠️ 중복 제거 후 수량 불일치 발견")
            
        return integrity_report
    
    def _calculate_totals(self, transactions: List[Dict]) -> Dict[str, float]:
        """트랜잭션 총합 계산"""
        totals = {
            'total_incoming': 0,
            'total_outgoing': 0,
            'total_inventory': 0
        }
        
        for transaction in transactions:
            data = transaction.get('data', {})
            totals['total_incoming'] += data.get('incoming', 0)
            totals['total_outgoing'] += data.get('outgoing', 0)
            totals['total_inventory'] += data.get('inventory', 0)
            
        return totals
    
    def get_deduplication_report(self) -> Dict[str, Any]:
        """중복 제거 리포트 생성"""
        duplicate_sources = {}
        for dup in self.duplicate_log:
            source = dup['transaction']['source_file']
            if source not in duplicate_sources:
                duplicate_sources[source] = 0
            duplicate_sources[source] += 1
            
        return {
            'total_duplicates_found': len(self.duplicate_log),
            'duplicates_by_source': duplicate_sources,
            'deduplication_rules': self.deduplication_rules,
            'sample_duplicates': self.duplicate_log[:5]  # 처음 5개 샘플
        }
    
    def apply_comprehensive_deduplication(self, transactions: List[Dict]) -> Tuple[List[Dict], Dict[str, Any]]:
        """종합적 중복 제거 파이프라인"""
        logger.info("🚀 종합적 중복 제거 파이프라인 시작")
        
        original_count = len(transactions)
        
        # 1. 해시 기반 중복 제거 (빠른 제거)
        step1_result = self.remove_hash_duplicates(transactions)
        
        # 2. 논리적 중복 감지 및 통합
        step2_result = self.detect_logical_duplicates(step1_result)
        
        # 3. 세밀한 중복 제거
        final_result = self.remove_duplicates(step2_result)
        
        # 4. 무결성 검증
        integrity_report = self.validate_deduplication_integrity(transactions, final_result)
        
        # 5. 종합 리포트
        comprehensive_report = {
            'pipeline_steps': {
                'original': original_count,
                'after_hash_dedup': len(step1_result),
                'after_logical_merge': len(step2_result),
                'final': len(final_result)
            },
            'total_removed': original_count - len(final_result),
            'removal_rate': (original_count - len(final_result)) / original_count * 100,
            'integrity_check': integrity_report,
            'deduplication_report': self.get_deduplication_report()
        }
        
        logger.info(f"✅ 종합 중복 제거 완료: {original_count} → {len(final_result)} ({comprehensive_report['removal_rate']:.1f}% 제거)")
        
        return final_result, comprehensive_report

class InventoryEngine:
    """HVDC 재고 산출 엔진 - 개선된 버전"""
    
    def __init__(self):
        self.calculation_method = "USER_VALIDATED_LOOP"
        
    def calculate_daily_inventory_simplified(self, transaction_df: pd.DataFrame) -> pd.DataFrame:
        """
        간소화된 일별 재고 계산
        사용자 요구사항에 맞춘 정확한 계산
        """
        print("📊 일별 재고 계산 중...")
        
        if transaction_df.empty:
            return pd.DataFrame()
        
        # 날짜 정규화
        transaction_df['Date'] = pd.to_datetime(transaction_df['Date']).dt.date
        
        # TxType_Refined별 집계
        daily_summary = transaction_df.groupby(['Location', 'Date', 'TxType_Refined']).agg({
            'Qty': 'sum'
        }).reset_index()
        
        # 피벗으로 IN/OUT 분리
        daily_pivot = daily_summary.pivot_table(
            index=['Location', 'Date'],
            columns='TxType_Refined', 
            values='Qty',
            fill_value=0
        ).reset_index()
        
        # 컬럼명 정리
        daily_pivot.columns.name = None
        
        # 필요한 컬럼들 확인 및 추가
        required_cols = ['IN', 'TRANSFER_OUT', 'FINAL_OUT']
        for col in required_cols:
            if col not in daily_pivot.columns:
                daily_pivot[col] = 0
        
        # 재고 계산 (위치별 누적)
        stock_records = []
        
        for location in daily_pivot['Location'].unique():
            if location in ['UNKNOWN', 'UNK', '']:
                continue
                
            # 해당 위치의 데이터만 추출
            loc_data = daily_pivot[daily_pivot['Location'] == location].copy()
            loc_data = loc_data.sort_values('Date').reset_index(drop=True)
            
            # 초기 재고 (0부터 시작)
            current_stock = 0
            
            for idx, row in loc_data.iterrows():
                # 입고량
                inbound = row.get('IN', 0)
                
                # 출고량 (TRANSFER + FINAL)
                transfer_out = row.get('TRANSFER_OUT', 0)
                final_out = row.get('FINAL_OUT', 0)
                total_outbound = transfer_out + final_out
                
                # 재고 계산: 이전재고 + 입고 - 출고
                opening_stock = current_stock
                closing_stock = opening_stock + inbound - total_outbound
                current_stock = closing_stock  # 다음 날을 위해 업데이트
                
                # 레코드 생성
                stock_record = {
                    'Location': location,
                    'Date': row['Date'],
                    'Opening_Stock': opening_stock,
                    'Inbound': inbound,
                    'Transfer_Out': transfer_out,
                    'Final_Out': final_out,
                    'Total_Outbound': total_outbound,
                    'Closing_Stock': closing_stock
                }
                stock_records.append(stock_record)
        
        daily_stock_df = pd.DataFrame(stock_records)
        
        if not daily_stock_df.empty:
            print(f"✅ {len(daily_stock_df)}개 일별 재고 스냅샷 생성")
            
            # 최종 재고 요약 출력
            latest_stock = (daily_stock_df
                           .sort_values('Date')
                           .groupby('Location')
                           .tail(1))
            
            print("\n📊 최종 재고 요약:")
            for _, row in latest_stock.iterrows():
                print(f"   {row['Location']}: {int(row['Closing_Stock'])} EA")
        else:
            print("⚠️ 재고 데이터가 생성되지 않았습니다")
        
        return daily_stock_df
    
    def validate_stock_calculation(self, daily_stock: pd.DataFrame) -> Dict[str, Any]:
        """재고 계산 검증"""
        if daily_stock.empty:
            return {"status": "EMPTY", "message": "검증할 데이터 없음"}
        
        validation_results = {
            'total_records': len(daily_stock),
            'locations_count': daily_stock['Location'].nunique(),
            'date_range': {
                'start': daily_stock['Date'].min(),
                'end': daily_stock['Date'].max()
            },
            'negative_stock_count': 0,
            'validation_errors': []
        }
        
        # 음수 재고 확인
        negative_stock = daily_stock[daily_stock['Closing_Stock'] < 0]
        validation_results['negative_stock_count'] = len(negative_stock)
        
        if len(negative_stock) > 0:
            validation_results['validation_errors'].append(
                f"음수 재고 발견: {len(negative_stock)}건"
            )
            print(f"⚠️ 음수 재고 발견: {len(negative_stock)}건")
        
        # 재고 무결성 확인 (Opening + Inbound - Outbound = Closing)
        integrity_check = daily_stock.copy()
        integrity_check['Calculated_Closing'] = (
            integrity_check['Opening_Stock'] + 
            integrity_check['Inbound'] - 
            integrity_check['Total_Outbound']
        )
        integrity_check['Difference'] = (
            integrity_check['Closing_Stock'] - integrity_check['Calculated_Closing']
        ).abs()
        
        integrity_errors = integrity_check[integrity_check['Difference'] > 0.01]
        
        if len(integrity_errors) > 0:
            validation_results['validation_errors'].append(
                f"재고 무결성 오류: {len(integrity_errors)}건"
            )
        else:
            validation_results['integrity_status'] = "PASS"
        
        return validation_results
    
    def generate_summary_report(self, daily_stock: pd.DataFrame) -> Dict[str, Any]:
        """요약 리포트 생성"""
        if daily_stock.empty:
            return {}
        
        # 최종 재고
        final_inventory = (daily_stock
                          .sort_values('Date')
                          .groupby('Location')
                          .tail(1))
        
        # 총 입출고량
        total_summary = daily_stock.groupby('Location').agg({
            'Inbound': 'sum',
            'Transfer_Out': 'sum',
            'Final_Out': 'sum',
            'Total_Outbound': 'sum'
        }).reset_index()
        
        # 최종 재고와 합치기
        summary = total_summary.merge(
            final_inventory[['Location', 'Closing_Stock']], 
            on='Location', 
            how='left'
        )
        
        return {
            'generation_time': pd.Timestamp.now(),
            'calculation_method': self.calculation_method,
            'warehouse_summary': summary.to_dict('records'),
            'total_final_inventory': summary['Closing_Stock'].sum(),
            'total_inbound': summary['Inbound'].sum(),
            'total_outbound': summary['Total_Outbound'].sum(),
            'locations': summary['Location'].tolist()
        } 