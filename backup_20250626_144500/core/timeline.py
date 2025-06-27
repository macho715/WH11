"""
HVDC 케이스별 이동 타임라인 추적 모듈
각 케이스의 이동 경로와 시간을 완전 추적
"""

import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
from collections import defaultdict, deque

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TimelineTracker:
    """HVDC 케이스별 이동 타임라인 추적기"""
    
    def __init__(self):
        self.case_timelines = {}  # case_id -> timeline
        self.location_history = defaultdict(list)  # case_id -> location history
        self.movement_chains = defaultdict(list)  # case_id -> movement chain
        self.timeline_rules = {
            'max_timeline_days': 365,  # 최대 추적 기간
            'movement_gap_hours': 24,  # 이동 간격 임계값
            'location_validation': True,  # 위치 유효성 검증
        }
        
    def create_case_timeline(self, transactions: List[Dict]) -> Dict[str, List[Dict]]:
        """케이스별 타임라인 생성"""
        logger.info(f"📅 케이스별 타임라인 생성 시작: {len(transactions)}건")
        
        # 케이스별 트랜잭션 그룹화
        case_groups = self._group_by_case_id(transactions)
        
        timelines = {}
        
        for case_id, case_transactions in case_groups.items():
            # 시간순 정렬
            sorted_transactions = sorted(
                case_transactions, 
                key=lambda x: self._extract_datetime(x)
            )
            
            # 타임라인 생성
            timeline = self._build_case_timeline(case_id, sorted_transactions)
            timelines[case_id] = timeline
            
        logger.info(f"✅ 타임라인 생성 완료: {len(timelines)}개 케이스")
        return timelines
    
    def _group_by_case_id(self, transactions: List[Dict]) -> Dict[str, List[Dict]]:
        """케이스 ID별로 트랜잭션 그룹화"""
        groups = defaultdict(list)
        
        for transaction in transactions:
            case_id = self._extract_case_id(transaction)
            if case_id:
                groups[case_id].append(transaction)
                
        return dict(groups)
    
    def _extract_case_id(self, transaction: Dict) -> Optional[str]:
        """트랜잭션에서 케이스 ID 추출"""
        data = transaction.get('data', {})
        
        # 여러 필드에서 케이스 ID 찾기
        case_fields = ['Case', 'case_id', 'CaseID', 'ID', 'SerialNumber', 'Part']
        
        for field in case_fields:
            if field in data and data[field]:
                return str(data[field])
                
        # 파일명에서 케이스 정보 추출 시도
        source_file = transaction.get('source_file', '')
        if 'case' in source_file.lower():
            # 파일명 기반 케이스 ID 생성
            return f"FILE_{source_file.split('.')[0]}"
            
        return None
    
    def _extract_datetime(self, transaction: Dict) -> datetime:
        """트랜잭션에서 날짜/시간 추출"""
        data = transaction.get('data', {})
        
        # 날짜 필드들 확인
        date_fields = ['date', 'timestamp', 'Date', 'Timestamp']
        
        for field in date_fields:
            if field in data and data[field]:
                try:
                    if isinstance(data[field], datetime):
                        return data[field]
                    elif isinstance(data[field], str):
                        return pd.to_datetime(data[field])
                except:
                    continue
                    
        # 기본값: 현재 시간
        return datetime.now()
    
    def _build_case_timeline(self, case_id: str, transactions: List[Dict]) -> List[Dict]:
        """단일 케이스의 타임라인 구축"""
        timeline = []
        
        for i, transaction in enumerate(transactions):
            timeline_entry = {
                'sequence': i + 1,
                'case_id': case_id,
                'timestamp': self._extract_datetime(transaction),
                'location': self._extract_location(transaction),
                'action': self._determine_action(transaction),
                'quantity': self._extract_quantities(transaction),
                'source': transaction.get('source_file', ''),
                'raw_data': transaction['data']
            }
            
            # 이전 위치와 비교하여 이동 감지
            if i > 0:
                prev_location = timeline[i-1]['location']
                curr_location = timeline_entry['location']
                
                if prev_location != curr_location:
                    timeline_entry['movement'] = {
                        'from': prev_location,
                        'to': curr_location,
                        'duration': self._calculate_duration(timeline[i-1], timeline_entry)
                    }
                    
            timeline.append(timeline_entry)
            
        return timeline
    
    def _extract_location(self, transaction: Dict) -> str:
        """트랜잭션에서 위치 정보 추출"""
        data = transaction.get('data', {})
        
        # 위치 필드들 우선순위별 확인
        location_fields = ['warehouse', 'site', 'location', 'from', 'to']
        
        for field in location_fields:
            if field in data and data[field]:
                return str(data[field])
                
        return 'UNKNOWN'
    
    def _determine_action(self, transaction: Dict) -> str:
        """트랜잭션 액션 유형 결정"""
        data = transaction.get('data', {})
        
        incoming = data.get('incoming', 0)
        outgoing = data.get('outgoing', 0)
        
        if incoming > 0 and outgoing == 0:
            return 'INBOUND'
        elif outgoing > 0 and incoming == 0:
            return 'OUTBOUND'
        elif incoming > 0 and outgoing > 0:
            return 'TRANSFER'
        else:
            return 'STATUS_CHECK'
    
    def _extract_quantities(self, transaction: Dict) -> Dict[str, float]:
        """수량 정보 추출"""
        data = transaction.get('data', {})
        
        return {
            'incoming': data.get('incoming', 0),
            'outgoing': data.get('outgoing', 0),
            'inventory': data.get('inventory', 0)
        }
    
    def _calculate_duration(self, prev_entry: Dict, curr_entry: Dict) -> Dict[str, Any]:
        """이동 소요 시간 계산"""
        prev_time = prev_entry['timestamp']
        curr_time = curr_entry['timestamp']
        
        duration = curr_time - prev_time
        
        return {
            'total_seconds': duration.total_seconds(),
            'hours': duration.total_seconds() / 3600,
            'days': duration.days,
            'human_readable': str(duration)
        }
    
    def analyze_movement_patterns(self, timelines: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """이동 패턴 분석"""
        logger.info("📊 이동 패턴 분석 시작")
        
        movement_stats = {
            'total_cases': len(timelines),
            'total_movements': 0,
            'location_frequency': defaultdict(int),
            'movement_routes': defaultdict(int),
            'average_stay_duration': {},
            'movement_velocity': []
        }
        
        for case_id, timeline in timelines.items():
            for entry in timeline:
                # 위치 빈도 계산
                location = entry['location']
                movement_stats['location_frequency'][location] += 1
                
                # 이동 경로 계산
                if 'movement' in entry:
                    movement_stats['total_movements'] += 1
                    route = f"{entry['movement']['from']} → {entry['movement']['to']}"
                    movement_stats['movement_routes'][route] += 1
                    
                    # 이동 속도 계산
                    duration_hours = entry['movement']['duration']['hours']
                    if duration_hours > 0:
                        movement_stats['movement_velocity'].append(duration_hours)
                        
        # 통계 계산
        if movement_stats['movement_velocity']:
            movement_stats['avg_movement_time'] = sum(movement_stats['movement_velocity']) / len(movement_stats['movement_velocity'])
            movement_stats['fastest_movement'] = min(movement_stats['movement_velocity'])
            movement_stats['slowest_movement'] = max(movement_stats['movement_velocity'])
            
        logger.info(f"✅ 이동 패턴 분석 완료: {movement_stats['total_movements']}건 이동")
        return movement_stats
    
    def detect_anomalous_movements(self, timelines: Dict[str, List[Dict]]) -> List[Dict]:
        """비정상적인 이동 패턴 감지"""
        logger.info("🚨 비정상 이동 패턴 감지")
        
        anomalies = []
        
        for case_id, timeline in timelines.items():
            case_anomalies = self._detect_case_anomalies(case_id, timeline)
            anomalies.extend(case_anomalies)
            
        logger.info(f"⚠️ 비정상 패턴 감지: {len(anomalies)}건")
        return anomalies
    
    def _detect_case_anomalies(self, case_id: str, timeline: List[Dict]) -> List[Dict]:
        """단일 케이스의 비정상 패턴 감지"""
        anomalies = []
        
        for i, entry in enumerate(timeline):
            # 1. 순간이동 감지 (너무 짧은 시간 내 이동)
            if 'movement' in entry:
                duration_hours = entry['movement']['duration']['hours']
                if duration_hours < 0.1:  # 6분 미만
                    anomalies.append({
                        'case_id': case_id,
                        'type': 'INSTANT_MOVEMENT',
                        'entry': entry,
                        'reason': f'Movement in {duration_hours:.2f} hours'
                    })
                    
            # 2. 장기 체류 감지
            if i < len(timeline) - 1:
                next_entry = timeline[i + 1]
                if 'movement' in next_entry:
                    stay_duration = next_entry['movement']['duration']['hours']
                    if stay_duration > 24 * 30:  # 30일 이상
                        anomalies.append({
                            'case_id': case_id,
                            'type': 'LONG_STAY',
                            'entry': entry,
                            'reason': f'Stayed {stay_duration:.1f} hours at {entry["location"]}'
                        })
                        
            # 3. 동일 위치 반복 방문
            if i > 1:
                prev_locations = [timeline[j]['location'] for j in range(max(0, i-3), i)]
                if entry['location'] in prev_locations:
                    anomalies.append({
                        'case_id': case_id,
                        'type': 'LOCATION_REVISIT',
                        'entry': entry,
                        'reason': f'Revisited {entry["location"]}'
                    })
                    
        return anomalies
    
    def generate_movement_report(self, timelines: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """이동 리포트 생성"""
        logger.info("📋 이동 리포트 생성")
        
        # 패턴 분석
        patterns = self.analyze_movement_patterns(timelines)
        
        # 비정상 패턴 감지
        anomalies = self.detect_anomalous_movements(timelines)
        
        # 케이스별 요약
        case_summaries = {}
        for case_id, timeline in timelines.items():
            case_summaries[case_id] = self._summarize_case(timeline)
            
        report = {
            'summary': {
                'total_cases': len(timelines),
                'total_timeline_entries': sum(len(timeline) for timeline in timelines.values()),
                'analysis_timestamp': datetime.now()
            },
            'movement_patterns': patterns,
            'anomalies': {
                'count': len(anomalies),
                'types': self._categorize_anomalies(anomalies),
                'details': anomalies[:10]  # 상위 10개만
            },
            'case_summaries': case_summaries,
            'top_locations': dict(sorted(patterns['location_frequency'].items(), 
                                       key=lambda x: x[1], reverse=True)[:10]),
            'top_routes': dict(sorted(patterns['movement_routes'].items(), 
                                    key=lambda x: x[1], reverse=True)[:10])
        }
        
        logger.info("✅ 이동 리포트 생성 완료")
        return report
    
    def _summarize_case(self, timeline: List[Dict]) -> Dict[str, Any]:
        """케이스별 요약 생성"""
        if not timeline:
            return {}
            
        movements = [entry for entry in timeline if 'movement' in entry]
        locations = list(set(entry['location'] for entry in timeline))
        
        return {
            'total_entries': len(timeline),
            'total_movements': len(movements),
            'unique_locations': len(locations),
            'start_location': timeline[0]['location'],
            'end_location': timeline[-1]['location'],
            'timeline_duration': {
                'start': timeline[0]['timestamp'],
                'end': timeline[-1]['timestamp'],
                'total_days': (timeline[-1]['timestamp'] - timeline[0]['timestamp']).days
            },
            'location_path': [entry['location'] for entry in timeline]
        }
    
    def _categorize_anomalies(self, anomalies: List[Dict]) -> Dict[str, int]:
        """비정상 패턴 유형별 분류"""
        categories = defaultdict(int)
        
        for anomaly in anomalies:
            categories[anomaly['type']] += 1
            
        return dict(categories)
    
    def export_timeline_to_dataframe(self, timelines: Dict[str, List[Dict]]) -> pd.DataFrame:
        """타임라인을 DataFrame으로 변환"""
        logger.info("📊 타임라인 DataFrame 변환")
        
        all_entries = []
        
        for case_id, timeline in timelines.items():
            for entry in timeline:
                flat_entry = {
                    'case_id': case_id,
                    'sequence': entry['sequence'],
                    'timestamp': entry['timestamp'],
                    'location': entry['location'],
                    'action': entry['action'],
                    'incoming': entry['quantity']['incoming'],
                    'outgoing': entry['quantity']['outgoing'],
                    'inventory': entry['quantity']['inventory'],
                    'source_file': entry['source']
                }
                
                # 이동 정보 추가
                if 'movement' in entry:
                    flat_entry.update({
                        'movement_from': entry['movement']['from'],
                        'movement_to': entry['movement']['to'],
                        'movement_duration_hours': entry['movement']['duration']['hours']
                    })
                else:
                    flat_entry.update({
                        'movement_from': None,
                        'movement_to': None,
                        'movement_duration_hours': None
                    })
                    
                all_entries.append(flat_entry)
                
        df = pd.DataFrame(all_entries)
        logger.info(f"✅ DataFrame 변환 완료: {len(df)}행")
        
        return df
    
    def validate_timeline_integrity(self, timelines: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """타임라인 무결성 검증"""
        logger.info("🔍 타임라인 무결성 검증")
        
        validation_results = {
            'total_cases': len(timelines),
            'valid_cases': 0,
            'invalid_cases': 0,
            'validation_errors': []
        }
        
        for case_id, timeline in timelines.items():
            is_valid, errors = self._validate_single_timeline(case_id, timeline)
            
            if is_valid:
                validation_results['valid_cases'] += 1
            else:
                validation_results['invalid_cases'] += 1
                validation_results['validation_errors'].extend(errors)
                
        validation_results['integrity_rate'] = (
            validation_results['valid_cases'] / validation_results['total_cases'] * 100
            if validation_results['total_cases'] > 0 else 0
        )
        
        logger.info(f"✅ 무결성 검증 완료: {validation_results['integrity_rate']:.1f}% 통과")
        return validation_results
    
    def _validate_single_timeline(self, case_id: str, timeline: List[Dict]) -> Tuple[bool, List[str]]:
        """단일 타임라인 검증"""
        errors = []
        
        if not timeline:
            errors.append(f"Case {case_id}: Empty timeline")
            return False, errors
            
        # 시간순 정렬 확인
        for i in range(1, len(timeline)):
            if timeline[i]['timestamp'] < timeline[i-1]['timestamp']:
                errors.append(f"Case {case_id}: Timeline not chronological at entry {i}")
                
        # 위치 유효성 확인
        for i, entry in enumerate(timeline):
            if entry['location'] == 'UNKNOWN':
                errors.append(f"Case {case_id}: Unknown location at entry {i}")
                
        # 수량 일관성 확인
        for i, entry in enumerate(timeline):
            quantities = entry['quantity']
            if quantities['incoming'] < 0 or quantities['outgoing'] < 0:
                errors.append(f"Case {case_id}: Negative quantity at entry {i}")
                
        return len(errors) == 0, errors 