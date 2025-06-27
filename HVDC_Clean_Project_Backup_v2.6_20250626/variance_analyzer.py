#!/usr/bin/env python3
"""
HVDC 월별 오차 심층 분석 운영 프로토콜 - 실전 자동화 시스템

Invoice(원본 청구) vs Report(실적) 데이터 비교 분석
오차율, 누락/중복 검증, BI 대시보드, RPA 연계 자동화
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from pathlib import Path
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

class VarianceAnalyzer:
    """월별 오차 심층 분석 자동화 시스템"""
    
    def __init__(self, mapping_rules_file: str = "mapping_rules_v2.6.json"):
        self.mapping_rules_file = mapping_rules_file
        self.load_mapping_rules()
        
    def load_mapping_rules(self):
        """매핑 규칙 로드"""
        try:
            with open(self.mapping_rules_file, 'r', encoding='utf-8') as f:
                self.rules = json.load(f)
            logger.info(f"✅ 매핑 규칙 로드 완료: {self.mapping_rules_file}")
        except Exception as e:
            logger.warning(f"매핑 규칙 로드 실패, 기본값 사용: {e}")
            self.rules = {}
    
    def create_monthly_variance_report(self, 
                                     df_invoice: pd.DataFrame, 
                                     df_report: pd.DataFrame,
                                     output_file: str = None) -> Dict:
        """
        1️⃣ 청구액-실적액 월별 대조 리포트 생성
        
        Args:
            df_invoice: Invoice(원본 청구) 데이터
            df_report: Report(실적) 데이터
            output_file: 출력 파일 경로
            
        Returns:
            Dict: 분석 결과 및 리포트 파일 경로
        """
        print("📊 월별 오차 심층 분석 시작...")
        
        # 1. 년월 Key 생성
        df_invoice = self._prepare_invoice_data(df_invoice)
        df_report = self._prepare_report_data(df_report)
        
        # 2. 년월 Key로 Join
        df_merge = self._merge_invoice_report(df_invoice, df_report)
        
        # 3. 오차/오차율 계산
        df_merge = self._calculate_variance(df_merge)
        
        # 4. 누락/중복 검증
        validation_results = self._validate_data_integrity(df_invoice, df_report, df_merge)
        
        # 5. 오차 원인 자동 태깅
        df_merge = self._auto_tag_error_reasons(df_merge)
        
        # 6. BI 대시보드 데이터 생성
        dashboard_data = self._generate_dashboard_data(df_merge)
        
        # 7. 리포트 저장
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"월별오차분석리포트_{timestamp}.xlsx"
        
        self._save_variance_report(df_merge, validation_results, dashboard_data, output_file)
        
        return {
            'merged_data': df_merge,
            'validation_results': validation_results,
            'dashboard_data': dashboard_data,
            'output_file': output_file
        }
    
    def _prepare_invoice_data(self, df_invoice: pd.DataFrame) -> pd.DataFrame:
        """Invoice 데이터 전처리"""
        df = df_invoice.copy()
        
        # 년월 Key 생성
        if 'Billing Year' in df.columns and 'Billing month' in df.columns:
            df['년월'] = df['Billing Year'].astype(str) + '-' + df['Billing month'].astype(str).str.zfill(2)
        elif 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['년월'] = df['Date'].dt.strftime('%Y-%m')
        else:
            df['년월'] = 'Unknown'
        
        # 금액 컬럼 정규화
        amount_columns = ['Original Amount', 'Amount', 'Total Amount', 'Invoice Amount']
        for col in amount_columns:
            if col in df.columns:
                df['Invoice_Amount'] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                break
        else:
            df['Invoice_Amount'] = 0
        
        return df
    
    def _prepare_report_data(self, df_report: pd.DataFrame) -> pd.DataFrame:
        """Report 데이터 전처리"""
        df = df_report.copy()
        
        # 년월 Key 생성
        if 'Billing Year' in df.columns and 'Billing month' in df.columns:
            df['년월'] = df['Billing Year'].astype(str) + '-' + df['Billing month'].astype(str).str.zfill(2)
        elif 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['년월'] = df['Date'].dt.strftime('%Y-%m')
        else:
            df['년월'] = 'Unknown'
        
        # 금액 컬럼 정규화
        amount_columns = ['Report Amount', 'Amount', 'Total Amount', 'Actual Amount']
        for col in amount_columns:
            if col in df.columns:
                df['Report_Amount'] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                break
        else:
            df['Report_Amount'] = 0
        
        return df
    
    def _merge_invoice_report(self, df_invoice: pd.DataFrame, df_report: pd.DataFrame) -> pd.DataFrame:
        """Invoice와 Report 데이터 병합"""
        print("  🔗 Invoice-Report 데이터 병합 중...")
        
        # 년월별 집계
        invoice_monthly = df_invoice.groupby('년월').agg({
            'Invoice_Amount': 'sum',
            'Vendor': 'first' if 'Vendor' in df_invoice.columns else lambda x: 'Unknown',
            'Category': 'first' if 'Category' in df_invoice.columns else lambda x: 'Unknown',
            'HVDC CODE 1': 'first' if 'HVDC CODE 1' in df_invoice.columns else lambda x: 'Unknown'
        }).reset_index()
        
        report_monthly = df_report.groupby('년월').agg({
            'Report_Amount': 'sum',
            'Vendor': 'first' if 'Vendor' in df_report.columns else lambda x: 'Unknown',
            'Category': 'first' if 'Category' in df_report.columns else lambda x: 'Unknown',
            'HVDC CODE 1': 'first' if 'HVDC CODE 1' in df_report.columns else lambda x: 'Unknown'
        }).reset_index()
        
        # Outer Join으로 모든 년월 포함
        df_merge = pd.merge(invoice_monthly, report_monthly, on='년월', how='outer', suffixes=('_inv', '_rep'))
        
        # 결측값 처리
        df_merge['Invoice_Amount'] = df_merge['Invoice_Amount'].fillna(0)
        df_merge['Report_Amount'] = df_merge['Report_Amount'].fillna(0)
        
        print(f"  ✅ 병합 완료: {len(df_merge)}개월")
        return df_merge
    
    def _calculate_variance(self, df_merge: pd.DataFrame) -> pd.DataFrame:
        """오차 및 오차율 계산"""
        print("  📊 오차/오차율 계산 중...")
        
        # 오차 계산
        df_merge['오차'] = df_merge['Invoice_Amount'] - df_merge['Report_Amount']
        
        # 오차율 계산 (0으로 나누기 방지)
        df_merge['오차율(%)'] = np.where(
            df_merge['Invoice_Amount'] != 0,
            (df_merge['오차'] / df_merge['Invoice_Amount'] * 100).round(1),
            0
        )
        
        # 절대 오차율 (음수 제거)
        df_merge['절대오차율(%)'] = df_merge['오차율(%)'].abs()
        
        print(f"  ✅ 오차 계산 완료: 평균 오차율 {df_merge['절대오차율(%)'].mean():.1f}%")
        return df_merge
    
    def _validate_data_integrity(self, df_invoice: pd.DataFrame, df_report: pd.DataFrame, df_merge: pd.DataFrame) -> Dict:
        """
        2️⃣ 집계 누락/중복 검증
        """
        print("  🔍 데이터 무결성 검증 중...")
        
        validation_results = {
            'missing_months': [],
            'duplicate_records': {},
            'mismatch_analysis': {},
            'processing_issues': {}
        }
        
        # 1. 누락 월 검증
        invoice_months = set(df_invoice['년월'].unique())
        report_months = set(df_report['년월'].unique())
        validation_results['missing_months'] = {
            'invoice_only': list(invoice_months - report_months),
            'report_only': list(report_months - invoice_months)
        }
        
        # 2. 중복 검증
        for df_name, df in [('Invoice', df_invoice), ('Report', df_report)]:
            duplicates = df.groupby('년월').size()
            duplicates = duplicates[duplicates > 1]
            if not duplicates.empty:
                validation_results['duplicate_records'][df_name] = duplicates.to_dict()
        
        # 3. 기간 불일치 체크
        if 'Date' in df_invoice.columns and 'Date' in df_report.columns:
            invoice_dates = pd.to_datetime(df_invoice['Date'], errors='coerce')
            report_dates = pd.to_datetime(df_report['Date'], errors='coerce')
            
            validation_results['mismatch_analysis'] = {
                'invoice_date_range': [invoice_dates.min(), invoice_dates.max()],
                'report_date_range': [report_dates.min(), report_dates.max()]
            }
        
        # 4. 처리불가/환불/할인건 분석
        for df_name, df in [('Invoice', df_invoice), ('Report', df_report)]:
            if 'Status' in df.columns:
                status_counts = df['Status'].value_counts()
                validation_results['processing_issues'][df_name] = status_counts.to_dict()
        
        print(f"  ✅ 검증 완료: 누락 {len(validation_results['missing_months']['invoice_only'] + validation_results['missing_months']['report_only'])}개월")
        return validation_results
    
    def _auto_tag_error_reasons(self, df_merge: pd.DataFrame) -> pd.DataFrame:
        """
        4️⃣ 오차 원인 사유 태그 자동화
        """
        print("  🏷️ 오차 원인 자동 태깅 중...")
        
        def determine_error_reason(row):
            if row['Report_Amount'] == 0 and row['Invoice_Amount'] > 0:
                return '미승인'
            elif row['절대오차율(%)'] > 30:
                return '대폭조정'
            elif row['절대오차율(%)'] > 10:
                return '조정'
            elif row['절대오차율(%)'] > 5:
                return '소폭조정'
            else:
                return '정상'
        
        df_merge['오차사유'] = df_merge.apply(determine_error_reason, axis=1)
        
        # 오차 사유별 통계
        error_reason_stats = df_merge['오차사유'].value_counts()
        print(f"  ✅ 태깅 완료: {dict(error_reason_stats)}")
        
        return df_merge
    
    def _generate_dashboard_data(self, df_merge: pd.DataFrame) -> Dict:
        """
        3️⃣ BI 대시보드·알람 데이터 생성
        """
        print("  📈 BI 대시보드 데이터 생성 중...")
        
        dashboard_data = {
            'summary_stats': {},
            'alerts': {},
            'top_variance': {},
            'trend_analysis': {}
        }
        
        # 1. 요약 통계
        dashboard_data['summary_stats'] = {
            'total_months': len(df_merge),
            'total_invoice_amount': df_merge['Invoice_Amount'].sum(),
            'total_report_amount': df_merge['Report_Amount'].sum(),
            'total_variance': df_merge['오차'].sum(),
            'avg_variance_rate': df_merge['절대오차율(%)'].mean(),
            'max_variance_rate': df_merge['절대오차율(%)'].max()
        }
        
        # 2. 알람 데이터 (오차율 30% 이상)
        high_variance = df_merge[df_merge['절대오차율(%)'] > 30].copy()
        dashboard_data['alerts'] = {
            'high_variance_count': len(high_variance),
            'high_variance_months': high_variance['년월'].tolist(),
            'high_variance_details': high_variance[['년월', '절대오차율(%)', '오차사유']].to_dict('records')
        }
        
        # 3. Top 오차 월/공급사
        top_variance = df_merge.nlargest(5, '절대오차율(%)')
        dashboard_data['top_variance'] = {
            'top_months': top_variance[['년월', '절대오차율(%)', '오차사유']].to_dict('records')
        }
        
        # 4. 트렌드 분석
        if len(df_merge) > 1:
            df_merge_sorted = df_merge.sort_values('년월')
            dashboard_data['trend_analysis'] = {
                'variance_trend': df_merge_sorted['절대오차율(%)'].tolist(),
                'months': df_merge_sorted['년월'].tolist()
            }
        
        print(f"  ✅ 대시보드 데이터 생성 완료: {len(high_variance)}개 알람")
        return dashboard_data
    
    def _save_variance_report(self, df_merge: pd.DataFrame, validation_results: Dict, 
                            dashboard_data: Dict, output_file: str):
        """월별 오차 분석 리포트 저장"""
        print(f"  💾 리포트 저장 중: {output_file}")
        
        with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
            # 1. 월별 오차 분석 시트
            df_merge.to_excel(writer, sheet_name='01_월별오차분석', index=False)
            
            # 2. 검증 결과 시트
            validation_df = pd.DataFrame({
                '검증항목': ['누락월(Invoice만)', '누락월(Report만)', '중복기록(Invoice)', '중복기록(Report)'],
                '결과': [
                    len(validation_results['missing_months']['invoice_only']),
                    len(validation_results['missing_months']['report_only']),
                    len(validation_results['duplicate_records'].get('Invoice', {})),
                    len(validation_results['duplicate_records'].get('Report', {}))
                ]
            })
            validation_df.to_excel(writer, sheet_name='02_데이터검증', index=False)
            
            # 3. 알람 시트
            if dashboard_data['alerts']['high_variance_details']:
                alert_df = pd.DataFrame(dashboard_data['alerts']['high_variance_details'])
                alert_df.to_excel(writer, sheet_name='03_오차알람', index=False)
            
            # 4. 요약 통계 시트
            summary_df = pd.DataFrame(list(dashboard_data['summary_stats'].items()), 
                                    columns=['지표', '값'])
            summary_df.to_excel(writer, sheet_name='04_요약통계', index=False)
        
        print(f"  ✅ 리포트 저장 완료: {output_file}")
    
    def generate_automated_alerts(self, df_merge: pd.DataFrame, threshold: float = 30.0) -> Dict:
        """
        자동화 알람 생성 (RPA/슬랙/메일 연계용)
        """
        print(f"🚨 자동화 알람 생성 (임계값: {threshold}%)...")
        
        # 임계값 이상 오차 추출
        alerts = df_merge[df_merge['절대오차율(%)'] > threshold].copy()
        
        alert_data = {
            'alert_count': len(alerts),
            'alert_threshold': threshold,
            'alert_details': [],
            'summary_message': ''
        }
        
        if not alerts.empty:
            for _, row in alerts.iterrows():
                alert_data['alert_details'].append({
                    '년월': row['년월'],
                    '청구액': row['Invoice_Amount'],
                    '실적액': row['Report_Amount'],
                    '오차': row['오차'],
                    '오차율': row['오차율(%)'],
                    '오차사유': row['오차사유']
                })
            
            # 요약 메시지 생성
            alert_data['summary_message'] = (
                f"🚨 월별 오차 알람 ({threshold}% 이상)\n"
                f"• 총 {len(alerts)}개월 오차 발생\n"
                f"• 최대 오차율: {alerts['절대오차율(%)'].max():.1f}%\n"
                f"• 평균 오차율: {alerts['절대오차율(%)'].mean():.1f}%"
            )
        
        print(f"  ✅ 알람 생성 완료: {len(alerts)}개 알람")
        return alert_data

# 편의 함수들
def create_sample_data():
    """테스트용 샘플 데이터 생성"""
    # Invoice 데이터
    invoice_data = {
        'Billing Year': [2024, 2024, 2024, 2024, 2024],
        'Billing month': [1, 2, 3, 4, 5],
        'Original Amount': [1000000, 1200000, 1100000, 1300000, 1400000],
        'Vendor': ['SIM', 'HITACHI', 'SAMSUNG', 'SIM', 'HITACHI'],
        'Category': ['Equipment', 'Material', 'Service', 'Equipment', 'Material']
    }
    
    # Report 데이터 (일부 오차 포함)
    report_data = {
        'Billing Year': [2024, 2024, 2024, 2024, 2024],
        'Billing month': [1, 2, 3, 4, 5],
        'Report Amount': [950000, 1200000, 1050000, 0, 1350000],  # 4월 미승인, 1월/3월 조정
        'Vendor': ['SIM', 'HITACHI', 'SAMSUNG', 'SIM', 'HITACHI'],
        'Category': ['Equipment', 'Material', 'Service', 'Equipment', 'Material']
    }
    
    return pd.DataFrame(invoice_data), pd.DataFrame(report_data)

if __name__ == "__main__":
    # 테스트 실행
    print("🧪 월별 오차 분석 테스트 시작")
    
    # 샘플 데이터 생성
    df_invoice, df_report = create_sample_data()
    
    # 분석 실행
    analyzer = VarianceAnalyzer()
    results = analyzer.create_monthly_variance_report(df_invoice, df_report)
    
    # 알람 생성
    alerts = analyzer.generate_automated_alerts(results['merged_data'], threshold=10.0)
    
    print(f"\n✅ 테스트 완료!")
    print(f"📊 분석 결과: {results['output_file']}")
    print(f"🚨 알람: {alerts['alert_count']}개")
    print(f"📝 요약: {alerts['summary_message']}") 