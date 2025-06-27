#!/usr/bin/env python3
"""
HVDC BI 대시보드·알람 자동화 시스템

월별 오차 분석 결과를 기반으로 BI 대시보드 생성 및 RPA 연계
Plotly, PowerBI 연동 및 자동 알람 시스템
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from pathlib import Path
import logging
from typing import Dict, List, Tuple, Optional
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)

class BIDashboard:
    """BI 대시보드 자동화 시스템"""
    
    def __init__(self, output_dir: str = "dashboard_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
    def create_variance_dashboard(self, variance_data: Dict, output_file: str = None) -> str:
        """
        월별 오차 분석 대시보드 생성
        
        Args:
            variance_data: VarianceAnalyzer에서 생성된 데이터
            output_file: 출력 파일 경로
            
        Returns:
            str: 생성된 대시보드 파일 경로
        """
        print("📊 BI 대시보드 생성 중...")
        
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"월별오차분석_대시보드_{timestamp}.html"
        
        output_path = self.output_dir / output_file
        
        # 대시보드 생성
        fig = self._create_dashboard_figure(variance_data)
        
        # HTML 파일로 저장
        fig.write_html(str(output_path))
        
        print(f"✅ 대시보드 생성 완료: {output_path}")
        return str(output_path)
    
    def _create_dashboard_figure(self, variance_data: Dict) -> go.Figure:
        """대시보드 차트 생성"""
        df_merge = variance_data['merged_data']
        dashboard_data = variance_data['dashboard_data']
        
        # 서브플롯 생성 (2x2 레이아웃)
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                '월별 오차율 트렌드',
                '오차 사유별 분포',
                '청구액 vs 실적액 비교',
                'Top 5 오차 월'
            ),
            specs=[
                [{"type": "scatter"}, {"type": "pie"}],
                [{"type": "bar"}, {"type": "bar"}]
            ]
        )
        
        # 1. 월별 오차율 트렌드
        if 'trend_analysis' in dashboard_data:
            months = dashboard_data['trend_analysis']['months']
            variance_trend = dashboard_data['trend_analysis']['variance_trend']
            
            fig.add_trace(
                go.Scatter(
                    x=months,
                    y=variance_trend,
                    mode='lines+markers',
                    name='오차율(%)',
                    line=dict(color='red', width=2),
                    marker=dict(size=8)
                ),
                row=1, col=1
            )
        
        # 2. 오차 사유별 분포 (파이 차트)
        error_reason_counts = df_merge['오차사유'].value_counts()
        fig.add_trace(
            go.Pie(
                labels=error_reason_counts.index,
                values=error_reason_counts.values,
                name='오차사유',
                hole=0.3
            ),
            row=1, col=2
        )
        
        # 3. 청구액 vs 실적액 비교 (바 차트)
        months = df_merge['년월'].tolist()
        invoice_amounts = df_merge['Invoice_Amount'].tolist()
        report_amounts = df_merge['Report_Amount'].tolist()
        
        fig.add_trace(
            go.Bar(
                x=months,
                y=invoice_amounts,
                name='청구액',
                marker_color='blue'
            ),
            row=2, col=1
        )
        
        fig.add_trace(
            go.Bar(
                x=months,
                y=report_amounts,
                name='실적액',
                marker_color='green'
            ),
            row=2, col=1
        )
        
        # 4. Top 5 오차 월
        top_variance = df_merge.nlargest(5, '절대오차율(%)')
        fig.add_trace(
            go.Bar(
                x=top_variance['년월'],
                y=top_variance['절대오차율(%)'],
                name='Top 5 오차율',
                marker_color='orange'
            ),
            row=2, col=2
        )
        
        # 레이아웃 업데이트
        fig.update_layout(
            title={
                'text': 'HVDC 월별 오차 분석 대시보드',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 20}
            },
            height=800,
            showlegend=True
        )
        
        return fig
    
    def generate_alert_report(self, alerts: Dict, output_file: str = None) -> str:
        """
        알람 리포트 생성 (RPA/슬랙/메일 연계용)
        
        Args:
            alerts: VarianceAnalyzer에서 생성된 알람 데이터
            output_file: 출력 파일 경로
            
        Returns:
            str: 생성된 알람 리포트 파일 경로
        """
        print("🚨 알람 리포트 생성 중...")
        
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"오차알람리포트_{timestamp}.html"
        
        output_path = self.output_dir / output_file
        
        # 알람 리포트 HTML 생성
        html_content = self._create_alert_html(alerts)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ 알람 리포트 생성 완료: {output_path}")
        return str(output_path)
    
    def _create_alert_html(self, alerts: Dict) -> str:
        """알람 HTML 생성"""
        html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>HVDC 월별 오차 알람 리포트</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #ff4444; color: white; padding: 20px; border-radius: 5px; }}
        .alert-summary {{ background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; margin: 10px 0; border-radius: 5px; }}
        .alert-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        .alert-table th, .alert-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        .alert-table th {{ background-color: #f2f2f2; }}
        .high-variance {{ background-color: #ffebee; }}
        .medium-variance {{ background-color: #fff3e0; }}
        .low-variance {{ background-color: #f1f8e9; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚨 HVDC 월별 오차 알람 리포트</h1>
        <p>생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="alert-summary">
        <h2>📊 알람 요약</h2>
        <p><strong>임계값:</strong> {alerts['alert_threshold']}%</p>
        <p><strong>알람 건수:</strong> {alerts['alert_count']}개월</p>
        <p><strong>요약:</strong> {alerts['summary_message']}</p>
    </div>
    
    <h2>📋 상세 알람 내역</h2>
    <table class="alert-table">
        <thead>
            <tr>
                <th>년월</th>
                <th>청구액</th>
                <th>실적액</th>
                <th>오차</th>
                <th>오차율(%)</th>
                <th>오차사유</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for alert in alerts['alert_details']:
            variance_class = 'high-variance' if abs(alert['오차율']) > 30 else 'medium-variance' if abs(alert['오차율']) > 10 else 'low-variance'
            
            html_template += f"""
            <tr class="{variance_class}">
                <td>{alert['년월']}</td>
                <td>{alert['청구액']:,.0f}</td>
                <td>{alert['실적액']:,.0f}</td>
                <td>{alert['오차']:,.0f}</td>
                <td>{alert['오차율']:.1f}%</td>
                <td>{alert['오차사유']}</td>
            </tr>
"""
        
        html_template += """
        </tbody>
    </table>
    
    <div style="margin-top: 30px; padding: 15px; background-color: #e3f2fd; border-radius: 5px;">
        <h3>📝 권장 조치사항</h3>
        <ul>
            <li><strong>미승인:</strong> 해당 월 실적 데이터 확인 및 승인 처리</li>
            <li><strong>대폭조정 (30% 이상):</strong> 청구 내용과 실적 내용 상세 검토</li>
            <li><strong>조정 (10-30%):</strong> 일반적인 조정 범위, 정상 처리</li>
            <li><strong>소폭조정 (5-10%):</strong> 미미한 차이, 모니터링</li>
        </ul>
    </div>
</body>
</html>
"""
        
        return html_template
    
    def create_powerbi_data(self, variance_data: Dict, output_file: str = None) -> str:
        """
        PowerBI 연동용 데이터 생성
        
        Args:
            variance_data: VarianceAnalyzer에서 생성된 데이터
            output_file: 출력 파일 경로
            
        Returns:
            str: 생성된 PowerBI 데이터 파일 경로
        """
        print("📊 PowerBI 데이터 생성 중...")
        
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"PowerBI_데이터_{timestamp}.xlsx"
        
        output_path = self.output_dir / output_file
        
        # PowerBI용 데이터 시트 생성
        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            # 1. 월별 오차 분석 데이터
            variance_data['merged_data'].to_excel(writer, sheet_name='월별오차분석', index=False)
            
            # 2. 알람 데이터
            alerts = variance_data['merged_data'][variance_data['merged_data']['절대오차율(%)'] > 30]
            if not alerts.empty:
                alerts.to_excel(writer, sheet_name='오차알람', index=False)
            
            # 3. 요약 통계
            summary_stats = variance_data['dashboard_data']['summary_stats']
            summary_df = pd.DataFrame(list(summary_stats.items()), columns=['지표', '값'])
            summary_df.to_excel(writer, sheet_name='요약통계', index=False)
            
            # 4. 트렌드 데이터
            if 'trend_analysis' in variance_data['dashboard_data']:
                trend_data = variance_data['dashboard_data']['trend_analysis']
                trend_df = pd.DataFrame({
                    '년월': trend_data['months'],
                    '오차율(%)': trend_data['variance_trend']
                })
                trend_df.to_excel(writer, sheet_name='트렌드', index=False)
        
        print(f"✅ PowerBI 데이터 생성 완료: {output_path}")
        return str(output_path)
    
    def generate_rpa_commands(self, alerts: Dict) -> Dict:
        """
        RPA 연계 명령어 생성
        
        Args:
            alerts: 알람 데이터
            
        Returns:
            Dict: RPA 실행 명령어들
        """
        print("🤖 RPA 명령어 생성 중...")
        
        rpa_commands = {
            'email_notification': self._create_email_command(alerts),
            'slack_notification': self._create_slack_command(alerts),
            'approval_request': self._create_approval_command(alerts),
            'data_export': self._create_export_command(alerts)
        }
        
        print(f"✅ RPA 명령어 생성 완료: {len(rpa_commands)}개 명령어")
        return rpa_commands
    
    def _create_email_command(self, alerts: Dict) -> Dict:
        """이메일 알림 명령어 생성"""
        return {
            'type': 'email_notification',
            'subject': f'HVDC 월별 오차 알람 - {alerts["alert_count"]}개월 오차 발생',
            'recipients': ['finance@company.com', 'operations@company.com'],
            'body': alerts['summary_message'],
            'attachments': ['월별오차분석리포트.xlsx', '오차알람리포트.html']
        }
    
    def _create_slack_command(self, alerts: Dict) -> Dict:
        """슬랙 알림 명령어 생성"""
        return {
            'type': 'slack_notification',
            'channel': '#hvdc-alerts',
            'message': f"🚨 HVDC 월별 오차 알람\n{alerts['summary_message']}",
            'attachments': ['월별오차분석리포트.xlsx']
        }
    
    def _create_approval_command(self, alerts: Dict) -> Dict:
        """승인 요청 명령어 생성"""
        return {
            'type': 'approval_request',
            'system': 'ERP',
            'action': 'variance_approval',
            'data': alerts['alert_details'],
            'priority': 'high' if alerts['alert_count'] > 3 else 'medium'
        }
    
    def _create_export_command(self, alerts: Dict) -> Dict:
        """데이터 내보내기 명령어 생성"""
        return {
            'type': 'data_export',
            'format': 'excel',
            'sheets': ['월별오차분석', '오차알람', '요약통계'],
            'destination': 'shared_drive/hvdc_reports/'
        }

# 편의 함수들
def create_comprehensive_dashboard(variance_data: Dict, alerts: Dict, output_dir: str = "dashboard_output") -> Dict:
    """
    종합 대시보드 생성 (모든 기능 통합)
    
    Args:
        variance_data: VarianceAnalyzer 결과
        alerts: 알람 데이터
        output_dir: 출력 디렉토리
        
    Returns:
        Dict: 생성된 모든 파일 경로
    """
    print("🎯 종합 대시보드 생성 시작...")
    
    dashboard = BIDashboard(output_dir)
    
    # 1. 대시보드 생성
    dashboard_file = dashboard.create_variance_dashboard(variance_data)
    
    # 2. 알람 리포트 생성
    alert_file = dashboard.generate_alert_report(alerts)
    
    # 3. PowerBI 데이터 생성
    powerbi_file = dashboard.create_powerbi_data(variance_data)
    
    # 4. RPA 명령어 생성
    rpa_commands = dashboard.generate_rpa_commands(alerts)
    
    results = {
        'dashboard_file': dashboard_file,
        'alert_file': alert_file,
        'powerbi_file': powerbi_file,
        'rpa_commands': rpa_commands
    }
    
    print("✅ 종합 대시보드 생성 완료!")
    return results

if __name__ == "__main__":
    # 테스트 실행
    print("🧪 BI 대시보드 테스트 시작")
    
    # 샘플 데이터 생성 (VarianceAnalyzer와 연동)
    from variance_analyzer import create_sample_data, VarianceAnalyzer
    
    df_invoice, df_report = create_sample_data()
    analyzer = VarianceAnalyzer()
    variance_results = analyzer.create_monthly_variance_report(df_invoice, df_report)
    alerts = analyzer.generate_automated_alerts(variance_results['merged_data'], threshold=10.0)
    
    # 종합 대시보드 생성
    dashboard_results = create_comprehensive_dashboard(variance_results, alerts)
    
    print(f"\n✅ 테스트 완료!")
    print(f"📊 대시보드: {dashboard_results['dashboard_file']}")
    print(f"🚨 알람 리포트: {dashboard_results['alert_file']}")
    print(f"📈 PowerBI 데이터: {dashboard_results['powerbi_file']}")
    print(f"🤖 RPA 명령어: {len(dashboard_results['rpa_commands'])}개") 