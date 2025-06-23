"""
HVDC 이중계산 방지 모듈
트랜잭션 중복 제거 및 무결성 보장
"""

import pandas as pd
from typing import List, Dict, Any, Set, Tuple, Optional
import hashlib
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DeduplicationEngine:
    """HVDC 이중계산 방지 엔진"""
    
    def __init__(self):
        self.seen_transactions = set()
        self.duplicate_log = []
        self.deduplication_rules = {
            'time_window_minutes': 5,  # 5분 이내 동일 트랜잭션 중복으로 간주
            'quantity_tolerance': 0.01,  # 수량 차이 허용 범위
            'location_strict': True,  # 위치 정확히 일치해야 함
        }
        
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
            return time_diff <= self.deduplication_rules['time_window_minutes']
            
        except Exception as e:
            logger.warning(f"날짜 비교 실패: {e}")
            return True
    
    def _quantities_similar(self, data1: Dict, data2: Dict) -> bool:
        """수량 유사성 확인"""
        quantity_fields = ['incoming', 'outgoing', 'inventory']
        tolerance = self.deduplication_rules['quantity_tolerance']
        
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
    
    def remove_duplicates(self, transactions: List[Dict]) -> List[Dict]:
        """중복 트랜잭션 제거"""
        logger.info(f"🔍 중복 제거 시작: {len(transactions)}건")
        
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