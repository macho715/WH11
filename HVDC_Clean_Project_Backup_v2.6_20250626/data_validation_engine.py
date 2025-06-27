#!/usr/bin/env python3
"""
HVDC 데이터 품질 검증 엔진

통합 매핑 시스템 기반 데이터 품질 심층 검증
데이터 무결성, 일관성, 완전성, 비즈니스 규칙 검증
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from pathlib import Path
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataValidationEngine:
    """HVDC 데이터 품질 검증 엔진"""
    
    def __init__(self):
        self.validation_results = {}
        self.issues_found = []
        self.recommendations = []
        
    def validate_complete_dataset(self, transaction_df):
        """전체 데이터셋 종합 검증"""
        logger.info("🔍 HVDC 데이터 품질 종합 검증 시작")
        
        validation_summary = {
            'timestamp': datetime.now().isoformat(),
            'total_records': len(transaction_df),
            'validation_tests': {},
            'critical_issues': [],
            'warnings': [],
            'recommendations': [],
            'data_quality_score': 0
        }
        
        # 1. 기본 데이터 무결성 검증
        logger.info("1️⃣ 기본 데이터 무결성 검증")
        integrity_results = self.validate_data_integrity(transaction_df)
        validation_summary['validation_tests']['integrity'] = integrity_results
        
        # 2. 비즈니스 규칙 검증
        logger.info("2️⃣ 비즈니스 규칙 검증")
        business_results = self.validate_business_rules(transaction_df)
        validation_summary['validation_tests']['business_rules'] = business_results
        
        # 3. 데이터 일관성 검증
        logger.info("3️⃣ 데이터 일관성 검증")
        consistency_results = self.validate_data_consistency(transaction_df)
        validation_summary['validation_tests']['consistency'] = consistency_results
        
        # 4. 완전성 검증
        logger.info("4️⃣ 데이터 완전성 검증")
        completeness_results = self.validate_data_completeness(transaction_df)
        validation_summary['validation_tests']['completeness'] = completeness_results
        
        # 5. 통합 매핑 검증
        logger.info("5️⃣ 통합 매핑 검증")
        mapping_results = self.validate_mapping_integrity(transaction_df)
        validation_summary['validation_tests']['mapping'] = mapping_results
        
        # 6. 시간적 일관성 검증
        logger.info("6️⃣ 시간적 일관성 검증")
        temporal_results = self.validate_temporal_consistency(transaction_df)
        validation_summary['validation_tests']['temporal'] = temporal_results
        
        # 7. 수량 및 금액 검증
        logger.info("7️⃣ 수량 및 금액 검증")
        quantity_results = self.validate_quantities_and_amounts(transaction_df)
        validation_summary['validation_tests']['quantities'] = quantity_results
        
        # 종합 점수 계산
        validation_summary['data_quality_score'] = self.calculate_quality_score(validation_summary)
        
        # 크리티컬 이슈 및 권장사항 수집
        validation_summary['critical_issues'] = self.collect_critical_issues(validation_summary)
        validation_summary['warnings'] = self.collect_warnings(validation_summary)
        validation_summary['recommendations'] = self.generate_recommendations(validation_summary)
        
        self.validation_results = validation_summary
        return validation_summary
    
    def validate_data_integrity(self, df):
        """데이터 무결성 검증"""
        results = {
            'passed': True,
            'issues': [],
            'details': {}
        }
        
        # 필수 컬럼 존재 확인
        required_columns = ['Case_No', 'Date', 'Location', 'TxType_Refined', 'Qty']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            results['passed'] = False
            results['issues'].append(f"필수 컬럼 누락: {missing_columns}")
        
        # NULL 값 검증
        null_counts = df[required_columns].isnull().sum()
        critical_null_columns = null_counts[null_counts > 0]
        
        if not critical_null_columns.empty:
            results['issues'].append(f"NULL 값 발견: {critical_null_columns.to_dict()}")
            if critical_null_columns.max() > len(df) * 0.1:  # 10% 이상 NULL
                results['passed'] = False
        
        # 중복 레코드 검증
        duplicate_count = df.duplicated().sum()
        if duplicate_count > 0:
            results['issues'].append(f"중복 레코드: {duplicate_count}건")
            if duplicate_count > len(df) * 0.05:  # 5% 이상 중복
                results['passed'] = False
        
        results['details'] = {
            'total_records': len(df),
            'null_counts': null_counts.to_dict(),
            'duplicate_count': duplicate_count
        }
        
        return results
    
    def validate_business_rules(self, df):
        """비즈니스 규칙 검증"""
        results = {
            'passed': True,
            'issues': [],
            'details': {}
        }
        
        # 1. 수량 검증
        if 'Qty' in df.columns:
            negative_qty = (df['Qty'] < 0).sum()
            zero_qty = (df['Qty'] == 0).sum()
            
            if negative_qty > 0:
                results['issues'].append(f"음수 수량: {negative_qty}건")
                results['passed'] = False
            
            if zero_qty > len(df) * 0.1:  # 10% 이상 0수량
                results['issues'].append(f"0수량 비율 높음: {zero_qty}건 ({zero_qty/len(df)*100:.1f}%)")
        
        # 2. 날짜 범위 검증
        if 'Date' in df.columns:
            date_range = df['Date'].agg(['min', 'max'])
            future_dates = (df['Date'] > datetime.now()).sum()
            very_old_dates = (df['Date'] < datetime(2020, 1, 1)).sum()
            
            if future_dates > 0:
                results['issues'].append(f"미래 날짜: {future_dates}건")
            
            if very_old_dates > 0:
                results['issues'].append(f"과거 날짜 (2020년 이전): {very_old_dates}건")
            
            results['details']['date_range'] = {
                'min': str(date_range['min']),
                'max': str(date_range['max']),
                'future_dates': future_dates,
                'very_old_dates': very_old_dates
            }
        
        # 3. 트랜잭션 타입 검증
        if 'TxType_Refined' in df.columns:
            valid_types = ['IN', 'TRANSFER_OUT', 'FINAL_OUT']
            invalid_types = df[~df['TxType_Refined'].isin(valid_types)]['TxType_Refined'].unique()
            
            if len(invalid_types) > 0:
                results['issues'].append(f"잘못된 트랜잭션 타입: {invalid_types}")
                results['passed'] = False
        
        # 4. 창고/현장 검증
        if 'Location' in df.columns:
            empty_locations = df['Location'].isnull().sum()
            unknown_locations = (df['Location'] == 'UNKNOWN').sum()
            
            if empty_locations > 0:
                results['issues'].append(f"빈 Location: {empty_locations}건")
            
            if unknown_locations > len(df) * 0.05:  # 5% 이상 UNKNOWN
                results['issues'].append(f"UNKNOWN Location 비율 높음: {unknown_locations}건")
        
        return results
    
    def validate_data_consistency(self, df):
        """데이터 일관성 검증"""
        results = {
            'passed': True,
            'issues': [],
            'details': {}
        }
        
        # 1. Storage Type 일관성
        if 'Storage_Type' in df.columns and 'storage_type' in df.columns:
            inconsistent_storage = (df['Storage_Type'] != df['storage_type']).sum()
            if inconsistent_storage > 0:
                results['issues'].append(f"Storage Type 불일치: {inconsistent_storage}건")
                results['passed'] = False
        
        # 2. Location과 Storage Type 일관성
        if 'Location' in df.columns and 'Storage_Type' in df.columns:
            location_storage_mapping = df.groupby('Location')['Storage_Type'].nunique()
            inconsistent_locations = location_storage_mapping[location_storage_mapping > 1]
            
            if len(inconsistent_locations) > 0:
                results['issues'].append(f"Location별 Storage Type 불일치: {inconsistent_locations.to_dict()}")
        
        # 3. Case_No 일관성
        if 'Case_No' in df.columns:
            case_duplicates = df.groupby('Case_No').size()
            multiple_cases = case_duplicates[case_duplicates > 1]
            
            if len(multiple_cases) > 0:
                results['details']['case_duplicates'] = {
                    'multiple_cases_count': len(multiple_cases),
                    'max_duplicates': multiple_cases.max()
                }
        
        return results
    
    def validate_data_completeness(self, df):
        """데이터 완전성 검증"""
        results = {
            'passed': True,
            'issues': [],
            'details': {}
        }
        
        # 1. 필수 필드 완전성
        required_fields = ['Case_No', 'Date', 'Location', 'Qty']
        completeness_rates = {}
        
        for field in required_fields:
            if field in df.columns:
                completeness_rate = (df[field].notnull().sum() / len(df)) * 100
                completeness_rates[field] = completeness_rate
                
                if completeness_rate < 95:  # 95% 미만 완전성
                    results['issues'].append(f"{field} 완전성 낮음: {completeness_rate:.1f}%")
                    if completeness_rate < 80:
                        results['passed'] = False
        
        # 2. 시간적 완전성 (월별 데이터 분포)
        if 'Date' in df.columns:
            df['YearMonth'] = df['Date'].dt.to_period('M')
            monthly_distribution = df['YearMonth'].value_counts().sort_index()
            
            # 월별 데이터 분포 분석
            avg_monthly_records = monthly_distribution.mean()
            std_monthly_records = monthly_distribution.std()
            
            # 데이터가 없는 월 확인
            date_range = pd.date_range(df['Date'].min(), df['Date'].max(), freq='M')
            missing_months = []
            for month in date_range:
                if month.to_period('M') not in monthly_distribution.index:
                    missing_months.append(str(month.to_period('M')))
            
            if missing_months:
                results['issues'].append(f"데이터 없는 월: {missing_months}")
            
            results['details']['temporal_completeness'] = {
                'monthly_distribution': monthly_distribution.to_dict(),
                'avg_monthly_records': avg_monthly_records,
                'std_monthly_records': std_monthly_records,
                'missing_months': missing_months
            }
        
        results['details']['completeness_rates'] = completeness_rates
        return results
    
    def validate_mapping_integrity(self, df):
        """통합 매핑 검증"""
        results = {
            'passed': True,
            'issues': [],
            'details': {}
        }
        
        # 1. Storage Type 분류 검증
        if 'Storage_Type' in df.columns:
            storage_type_counts = df['Storage_Type'].value_counts()
            unknown_storage = storage_type_counts.get('Unknown', 0)
            
            if unknown_storage > 0:
                results['issues'].append(f"Unknown Storage Type: {unknown_storage}건")
                if unknown_storage > len(df) * 0.1:  # 10% 이상 Unknown
                    results['passed'] = False
            
            results['details']['storage_type_distribution'] = storage_type_counts.to_dict()
        
        # 2. Location 매핑 검증
        if 'Location' in df.columns:
            # 매핑 규칙에 없는 Location 확인
            from mapping_utils import mapping_manager
            
            all_valid_locations = []
            for locations in mapping_manager.warehouse_classification.values():
                all_valid_locations.extend(locations)
            
            unmapped_locations = df[~df['Location'].isin(all_valid_locations)]['Location'].unique()
            
            if len(unmapped_locations) > 0:
                results['issues'].append(f"매핑되지 않은 Location: {unmapped_locations}")
                results['passed'] = False
        
        return results
    
    def validate_temporal_consistency(self, df):
        """시간적 일관성 검증"""
        results = {
            'passed': True,
            'issues': [],
            'details': {}
        }
        
        if 'Date' not in df.columns:
            return results
        
        # 1. 날짜 순서 검증
        df_sorted = df.sort_values('Date')
        date_sequence_issues = 0
        
        # 2. 월별 데이터 분포 검증
        df['YearMonth'] = df['Date'].dt.to_period('M')
        monthly_counts = df['YearMonth'].value_counts().sort_index()
        
        # 급격한 변화 감지
        if len(monthly_counts) > 1:
            monthly_changes = monthly_counts.pct_change().abs()
            sudden_changes = monthly_changes[monthly_changes > 2.0]  # 200% 이상 변화
            
            if len(sudden_changes) > 0:
                results['issues'].append(f"급격한 월별 변화: {sudden_changes.to_dict()}")
        
        # 3. 주말/공휴일 패턴 검증
        df['DayOfWeek'] = df['Date'].dt.dayofweek
        weekend_transactions = (df['DayOfWeek'] >= 5).sum()
        weekend_ratio = weekend_transactions / len(df)
        
        if weekend_ratio > 0.3:  # 30% 이상 주말 트랜잭션
            results['issues'].append(f"주말 트랜잭션 비율 높음: {weekend_ratio:.1%}")
        
        results['details']['temporal_analysis'] = {
            'total_months': len(monthly_counts),
            'weekend_ratio': weekend_ratio,
            'monthly_distribution': monthly_counts.to_dict()
        }
        
        return results
    
    def validate_quantities_and_amounts(self, df):
        """수량 및 금액 검증"""
        results = {
            'passed': True,
            'issues': [],
            'details': {}
        }
        
        # 1. 수량 검증
        if 'Qty' in df.columns:
            qty_stats = df['Qty'].describe()
            
            # 이상치 검증
            q1, q3 = qty_stats['25%'], qty_stats['75%']
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            outliers = df[(df['Qty'] < lower_bound) | (df['Qty'] > upper_bound)]
            outlier_count = len(outliers)
            
            if outlier_count > 0:
                results['issues'].append(f"수량 이상치: {outlier_count}건")
                if outlier_count > len(df) * 0.05:  # 5% 이상 이상치
                    results['passed'] = False
            
            results['details']['quantity_analysis'] = {
                'mean': qty_stats['mean'],
                'std': qty_stats['std'],
                'min': qty_stats['min'],
                'max': qty_stats['max'],
                'outlier_count': outlier_count
            }
        
        # 2. 금액 검증 (Handling Fee)
        if 'Handling Fee' in df.columns:
            handling_fee_stats = df['Handling Fee'].describe()
            
            # 음수 Handling Fee 검증
            negative_fees = (df['Handling Fee'] < 0).sum()
            if negative_fees > 0:
                results['issues'].append(f"음수 Handling Fee: {negative_fees}건")
            
            results['details']['handling_fee_analysis'] = {
                'mean': handling_fee_stats['mean'],
                'std': handling_fee_stats['std'],
                'total': df['Handling Fee'].sum(),
                'negative_count': negative_fees
            }
        
        return results
    
    def calculate_quality_score(self, validation_summary):
        """데이터 품질 점수 계산"""
        total_tests = len(validation_summary['validation_tests'])
        passed_tests = sum(1 for test in validation_summary['validation_tests'].values() 
                          if test.get('passed', False))
        
        base_score = (passed_tests / total_tests) * 100
        
        # 크리티컬 이슈에 따른 감점
        critical_penalty = len(validation_summary['critical_issues']) * 10
        warning_penalty = len(validation_summary['warnings']) * 2
        
        final_score = max(0, base_score - critical_penalty - warning_penalty)
        
        return round(final_score, 1)
    
    def collect_critical_issues(self, validation_summary):
        """크리티컬 이슈 수집"""
        critical_issues = []
        
        for test_name, test_results in validation_summary['validation_tests'].items():
            if not test_results.get('passed', True):
                critical_issues.extend(test_results.get('issues', []))
        
        return critical_issues
    
    def collect_warnings(self, validation_summary):
        """경고 사항 수집"""
        warnings = []
        
        for test_name, test_results in validation_summary['validation_tests'].items():
            if test_results.get('passed', True):  # 통과했지만 주의사항이 있는 경우
                warnings.extend(test_results.get('issues', []))
        
        return warnings
    
    def generate_recommendations(self, validation_summary):
        """권장사항 생성"""
        recommendations = []
        
        # 데이터 무결성 권장사항
        if 'integrity' in validation_summary['validation_tests']:
            integrity_test = validation_summary['validation_tests']['integrity']
            if not integrity_test.get('passed', True):
                recommendations.append("데이터 무결성 문제 해결 필요: NULL 값 및 중복 데이터 정리")
        
        # 비즈니스 규칙 권장사항
        if 'business_rules' in validation_summary['validation_tests']:
            business_test = validation_summary['validation_tests']['business_rules']
            if not business_test.get('passed', True):
                recommendations.append("비즈니스 규칙 위반 데이터 검토 및 수정 필요")
        
        # 매핑 권장사항
        if 'mapping' in validation_summary['validation_tests']:
            mapping_test = validation_summary['validation_tests']['mapping']
            if not mapping_test.get('passed', True):
                recommendations.append("통합 매핑 규칙 업데이트 필요: 미매핑 Location 추가")
        
        # 완전성 권장사항
        if 'completeness' in validation_summary['validation_tests']:
            completeness_test = validation_summary['validation_tests']['completeness']
            if not completeness_test.get('passed', True):
                recommendations.append("데이터 완전성 개선 필요: 누락 데이터 보완")
        
        # 품질 점수 기반 권장사항
        quality_score = validation_summary['data_quality_score']
        if quality_score < 70:
            recommendations.append("전반적인 데이터 품질 개선 필요")
        elif quality_score < 90:
            recommendations.append("데이터 품질 양호하나 일부 개선 필요")
        else:
            recommendations.append("데이터 품질 우수 - 정기적 모니터링 권장")
        
        return recommendations
    
    def generate_validation_report(self, output_file=None):
        """검증 결과 리포트 생성"""
        if not self.validation_results:
            logger.error("검증 결과가 없습니다. validate_complete_dataset()를 먼저 실행하세요.")
            return None
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if output_file is None:
            output_file = f"HVDC_데이터품질검증리포트_{timestamp}.md"
        
        report_content = f"""# HVDC 데이터 품질 검증 리포트

## 📋 검증 개요
- **검증 일시**: {self.validation_results['timestamp']}
- **총 레코드 수**: {self.validation_results['total_records']:,}건
- **데이터 품질 점수**: {self.validation_results['data_quality_score']}/100

## 🎯 검증 결과 요약

### 품질 점수: {self.validation_results['data_quality_score']}/100
"""
        
        # 품질 점수에 따른 등급
        score = self.validation_results['data_quality_score']
        if score >= 90:
            grade = "🟢 우수"
        elif score >= 70:
            grade = "🟡 양호"
        elif score >= 50:
            grade = "🟠 보통"
        else:
            grade = "🔴 불량"
        
        report_content += f"**등급**: {grade}\n\n"
        
        # 크리티컬 이슈
        if self.validation_results['critical_issues']:
            report_content += "## 🚨 크리티컬 이슈\n"
            for issue in self.validation_results['critical_issues']:
                report_content += f"- {issue}\n"
            report_content += "\n"
        
        # 경고 사항
        if self.validation_results['warnings']:
            report_content += "## ⚠️ 경고 사항\n"
            for warning in self.validation_results['warnings']:
                report_content += f"- {warning}\n"
            report_content += "\n"
        
        # 권장사항
        if self.validation_results['recommendations']:
            report_content += "## 💡 권장사항\n"
            for rec in self.validation_results['recommendations']:
                report_content += f"- {rec}\n"
            report_content += "\n"
        
        # 상세 검증 결과
        report_content += "## 📊 상세 검증 결과\n"
        for test_name, test_results in self.validation_results['validation_tests'].items():
            status = "✅ 통과" if test_results.get('passed', True) else "❌ 실패"
            report_content += f"### {test_name.replace('_', ' ').title()}: {status}\n"
            
            if test_results.get('issues'):
                report_content += "**발견된 이슈**:\n"
                for issue in test_results['issues']:
                    report_content += f"- {issue}\n"
            
            if test_results.get('details'):
                report_content += "**상세 정보**:\n"
                for key, value in test_results['details'].items():
                    report_content += f"- {key}: {value}\n"
            
            report_content += "\n"
        
        report_content += f"""
---
**리포트 생성**: HVDC 데이터 품질 검증 엔진 v1.0
**생성일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"✅ 검증 리포트 생성 완료: {output_file}")
        return output_file

def main():
    """데이터 검증 메인 함수"""
    print("🔍 HVDC 데이터 품질 검증 엔진 시작")
    print("=" * 60)
    
    try:
        # 데이터 로딩
        from test_excel_reporter import main as load_test_data
        
        print("📄 테스트 데이터 로딩 중...")
        # 테스트 데이터 로딩 함수 호출
        # 실제로는 transaction_df를 직접 로드해야 함
        
        # 임시로 샘플 데이터 생성
        sample_data = {
            'Case_No': ['CASE_001', 'CASE_002', 'CASE_003'],
            'Date': [datetime.now(), datetime.now(), datetime.now()],
            'Location': ['DSV Indoor', 'DSV Outdoor', 'SHU'],
            'TxType_Refined': ['IN', 'IN', 'IN'],
            'Qty': [1, 1, 1],
            'Storage_Type': ['Indoor', 'Outdoor', 'Site'],
            'storage_type': ['Indoor', 'Outdoor', 'Site']
        }
        
        transaction_df = pd.DataFrame(sample_data)
        
        # 검증 엔진 초기화 및 실행
        validator = DataValidationEngine()
        validation_results = validator.validate_complete_dataset(transaction_df)
        
        # 결과 출력
        print(f"\n📊 검증 결과 요약:")
        print(f"   총 레코드: {validation_results['total_records']:,}건")
        print(f"   품질 점수: {validation_results['data_quality_score']}/100")
        print(f"   크리티컬 이슈: {len(validation_results['critical_issues'])}개")
        print(f"   경고 사항: {len(validation_results['warnings'])}개")
        
        # 리포트 생성
        report_file = validator.generate_validation_report()
        
        print(f"\n✅ 데이터 검증 완료!")
        print(f"📋 리포트: {report_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ 데이터 검증 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 데이터 품질 검증 성공!")
    else:
        print("\n❌ 데이터 품질 검증 실패!") 