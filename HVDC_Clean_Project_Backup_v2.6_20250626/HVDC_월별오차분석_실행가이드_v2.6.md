# HVDC 월별 오차 심층 분석 시스템 v2.6 - 실행 가이드

## 📋 시스템 개요

HVDC 프로젝트의 월별 청구액-실적액 오차 분석을 위한 완전 자동화 시스템입니다.
Invoice vs Report 비교, 오차율 분석, BI 대시보드, RPA 연계까지 모든 기능이 통합되어 있습니다.

### 🎯 주요 기능
- **월별 오차 분석**: 청구액 vs 실적액 대조 분석
- **자동화 알람**: 임계값 기반 자동 알림 시스템
- **BI 대시보드**: 실시간 대시보드 및 리포트 생성
- **RPA 연계**: 이메일/슬랙/승인 요청 자동화
- **PowerBI 연계**: PowerBI 데이터 자동 생성

## 🚀 빠른 시작

### 1. 시스템 설치 및 설정

```bash
# 1. 필요한 패키지 설치
pip install pandas numpy openpyxl plotly dash

# 2. 시스템 파일 확인
ls -la *.py
```

### 2. 기본 실행

```bash
# 통합 테스트 실행 (모든 기능 검증)
python test_variance_analysis.py

# 개별 모듈 테스트
python variance_analyzer.py
python bi_dashboard.py
```

## 📊 데이터 형식

### Invoice 데이터 (청구 데이터)
```csv
Billing Year,Billing month,Original Amount,Vendor,Category,HVDC CODE 1,Status
2024,1,1200000,SIM,Equipment,HVDC_001,Approved
2024,2,1350000,HITACHI,Material,HVDC_002,Approved
```

### Report 데이터 (실적 데이터)
```csv
Billing Year,Billing month,Report Amount,Vendor,Category,HVDC CODE 1,Status
2024,1,1140000,SIM,Equipment,HVDC_001,Approved
2024,2,1350000,HITACHI,Material,HVDC_002,Approved
```

## 🔧 상세 사용법

### 1. 월별 오차 분석 실행

```python
from variance_analyzer import VarianceAnalyzer

# 분석기 초기화
analyzer = VarianceAnalyzer()

# 데이터 로드 (실제 데이터로 교체)
df_invoice = pd.read_excel('invoice_data.xlsx')
df_report = pd.read_excel('report_data.xlsx')

# 월별 오차 분석 실행
results = analyzer.create_monthly_variance_report(df_invoice, df_report)

# 결과 확인
print(f"분석 완료: {results['output_file']}")
```

### 2. 자동화 알람 설정

```python
# 10% 이상 오차 알람 생성
alerts = analyzer.generate_automated_alerts(results['merged_data'], threshold=10.0)

# 알람 결과 확인
print(f"알람 개수: {alerts['alert_count']}")
for alert in alerts['alert_details']:
    print(f"{alert['년월']}: {alert['오차율']:.1f}% 오차")
```

### 3. BI 대시보드 생성

```python
from bi_dashboard import create_comprehensive_dashboard

# 종합 대시보드 생성
dashboard_results = create_comprehensive_dashboard(results, alerts)

# 생성된 파일들
print(f"대시보드: {dashboard_results['dashboard_file']}")
print(f"알람 리포트: {dashboard_results['alert_file']}")
print(f"PowerBI 데이터: {dashboard_results['powerbi_file']}")
```

## 📈 생성되는 파일들

### 1. 월별 오차 분석 리포트
- **파일명**: `월별오차분석리포트_YYYYMMDD_HHMMSS.xlsx`
- **내용**: 
  - 월별 청구액 vs 실적액 비교
  - 오차 및 오차율 계산
  - 오차 사유 분류 (정상/미승인/누락/중복)
  - 검증 결과 요약

### 2. BI 대시보드
- **파일명**: `dashboard_output/월별오차분석_대시보드_YYYYMMDD_HHMMSS.html`
- **기능**:
  - 실시간 차트 및 그래프
  - 오차율 트렌드 분석
  - 공급사별/카테고리별 분석
  - 인터랙티브 필터링

### 3. 알람 리포트
- **파일명**: `dashboard_output/오차알람리포트_YYYYMMDD_HHMMSS.html`
- **내용**:
  - 임계값 초과 월 목록
  - 상세 오차 분석
  - 권장 조치사항

### 4. PowerBI 데이터
- **파일명**: `dashboard_output/PowerBI_데이터_YYYYMMDD_HHMMSS.xlsx`
- **시트**:
  - 월별오차분석
  - 오차알람
  - 요약통계
  - 트렌드

## 🤖 RPA 연계

### 자동화 명령어 생성

```python
from bi_dashboard import BIDashboard

dashboard = BIDashboard()
rpa_commands = dashboard.generate_rpa_commands(alerts)

# 이메일 알림
email_cmd = rpa_commands['email_notification']
print(f"제목: {email_cmd['subject']}")
print(f"수신자: {email_cmd['recipients']}")

# 슬랙 알림
slack_cmd = rpa_commands['slack_notification']
print(f"채널: {slack_cmd['channel']}")

# 승인 요청
approval_cmd = rpa_commands['approval_request']
print(f"시스템: {approval_cmd['system']}")
```

### RPA 명령어 형식

```json
{
  "email_notification": {
    "subject": "HVDC 월별 오차 알람 - X개월 오차 발생",
    "recipients": ["finance@company.com", "operations@company.com"],
    "attachments": ["월별오차분석리포트.xlsx", "오차알람리포트.html"]
  },
  "slack_notification": {
    "channel": "#hvdc-alerts",
    "message": "🚨 HVDC 월별 오차 알람..."
  },
  "approval_request": {
    "system": "ERP",
    "action": "variance_approval",
    "priority": "medium"
  }
}
```

## ⚙️ 설정 및 커스터마이징

### 1. 알람 임계값 설정

```python
# 기본 임계값: 10%
alerts_10 = analyzer.generate_automated_alerts(data, threshold=10.0)

# 높은 임계값: 30%
alerts_30 = analyzer.generate_automated_alerts(data, threshold=30.0)

# 사용자 정의 임계값
custom_threshold = 15.0
alerts_custom = analyzer.generate_automated_alerts(data, threshold=custom_threshold)
```

### 2. 대시보드 커스터마이징

```python
# 대시보드 설정 수정
dashboard_config = {
    'title': 'HVDC 월별 오차 분석 대시보드',
    'theme': 'light',  # 'light' or 'dark'
    'charts': ['line', 'bar', 'pie'],  # 표시할 차트 타입
    'refresh_interval': 3600  # 자동 새로고침 간격 (초)
}
```

### 3. RPA 연계 설정

```python
# 이메일 설정
email_config = {
    'smtp_server': 'smtp.company.com',
    'smtp_port': 587,
    'username': 'alerts@company.com',
    'password': 'your_password'
}

# 슬랙 설정
slack_config = {
    'webhook_url': 'https://hooks.slack.com/services/...',
    'channel': '#hvdc-alerts',
    'username': 'HVDC Alert Bot'
}
```

## 🔍 문제 해결

### 1. 일반적인 오류

#### 데이터 형식 오류
```python
# 해결방법: 데이터 형식 확인
print(df_invoice.dtypes)
print(df_report.dtypes)

# 필요한 컬럼 확인
required_columns = ['Billing Year', 'Billing month', 'Original Amount', 'Vendor']
missing_columns = [col for col in required_columns if col not in df_invoice.columns]
```

#### 메모리 부족 오류
```python
# 해결방법: 청크 단위 처리
chunk_size = 1000
for chunk in pd.read_excel('large_file.xlsx', chunksize=chunk_size):
    # 청크별 처리
    process_chunk(chunk)
```

### 2. 성능 최적화

```python
# 대용량 데이터 처리 최적화
import pandas as pd

# 데이터 타입 최적화
df['Billing Year'] = df['Billing Year'].astype('int16')
df['Billing month'] = df['Billing month'].astype('int8')

# 인덱스 설정
df.set_index(['Billing Year', 'Billing month'], inplace=True)
```

## 📊 모니터링 및 유지보수

### 1. 로그 모니터링

```python
import logging

# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hvdc_analysis.log'),
        logging.StreamHandler()
    ]
)

# 로그 사용
logging.info("월별 오차 분석 시작")
logging.warning("오차율 10% 초과 감지")
logging.error("데이터 처리 오류 발생")
```

### 2. 정기 백업

```python
import shutil
from datetime import datetime

# 백업 생성
backup_dir = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
shutil.copytree('dashboard_output', f"{backup_dir}/dashboard_output")
shutil.copy('월별오차분석리포트.xlsx', f"{backup_dir}/")
```

## 🎯 운영 프로토콜

### 1. 일일 운영 체크리스트

- [ ] 데이터 파일 업로드 확인
- [ ] 월별 오차 분석 실행
- [ ] 알람 발생 여부 확인
- [ ] 대시보드 업데이트 확인
- [ ] RPA 명령어 실행 확인

### 2. 주간 운영 체크리스트

- [ ] 전체 시스템 성능 점검
- [ ] 백업 파일 정리
- [ ] 로그 파일 분석
- [ ] 사용자 피드백 수집
- [ ] 시스템 개선사항 검토

### 3. 월간 운영 체크리스트

- [ ] 전체 데이터 정합성 검증
- [ ] 시스템 업데이트 적용
- [ ] 성능 최적화 검토
- [ ] 보안 점검
- [ ] 사용자 교육 실시

## 📞 지원 및 문의

### 기술 지원
- **이메일**: tech-support@company.com
- **전화**: 02-1234-5678
- **슬랙**: #hvdc-support

### 문서 및 자료
- **시스템 문서**: `/docs/`
- **API 문서**: `/docs/api/`
- **사용자 가이드**: `/docs/user-guide/`

## 🔄 버전 히스토리

### v2.6 (2025-06-26)
- ✅ 월별 오차 심층 분석 시스템 완성
- ✅ 자동화 알람 시스템 구현
- ✅ BI 대시보드 자동 생성
- ✅ RPA 연계 기능 추가
- ✅ PowerBI 데이터 자동 생성
- ✅ 통합 테스트 완료

### v2.5 (2025-06-25)
- Handling Fee 집계 기능 추가
- 데이터 정규화 개선
- 오차 분석 알고리즘 최적화

### v2.4 (2025-06-24)
- 초기 시스템 구축
- 기본 오차 분석 기능
- 리포트 생성 기능

---

**시스템 버전**: v2.6  
**최종 업데이트**: 2025-06-26  
**담당자**: HVDC 프로젝트팀 