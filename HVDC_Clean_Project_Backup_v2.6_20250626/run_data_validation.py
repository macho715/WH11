#!/usr/bin/env python3
"""
HVDC 데이터 품질 검증 실행 스크립트

실제 HVDC 트랜잭션 데이터를 로드하여 종합적인 데이터 품질 검증 수행
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

# 핵심 모듈 임포트
from data_validation_engine import DataValidationEngine
from core.loader import DataLoader
from core.deduplication import drop_duplicate_transfers, reconcile_orphan_transfers
from mapping_utils import add_storage_type_to_dataframe, normalize_location_column

def load_actual_transaction_data():
    """실제 HVDC 트랜잭션 데이터 로드"""
    print("📄 실제 HVDC 트랜잭션 데이터 로딩 중...")
    
    try:
        # DataLoader를 사용하여 실제 데이터 로드
        loader = DataLoader()
        excel_files = loader.load_excel_files("data")
        
        if not excel_files:
            print("❌ Excel 파일이 없습니다!")
            return None
            
        raw_transactions = loader.extract_transactions(excel_files)
        print(f"📊 총 {len(raw_transactions):,}건의 원시 트랜잭션 수집")

        # 트랜잭션 DataFrame 변환
        print("🔄 트랜잭션 변환 중...")
        transaction_df = transactions_to_dataframe(raw_transactions)
        print(f"✅ {len(transaction_df)}건 트랜잭션 생성")
        
        # 통합 매핑 적용
        print("🔄 통합 매핑 적용 중...")
        transaction_df = add_storage_type_to_dataframe(transaction_df, "Location")
        
        # 데이터 전처리
        print("🛠️ 데이터 전처리 중...")
        transaction_df = reconcile_orphan_transfers(transaction_df)
        transaction_df = drop_duplicate_transfers(transaction_df)
        
        return transaction_df
        
    except Exception as e:
        print(f"❌ 데이터 로딩 실패: {e}")
        return None

def transactions_to_dataframe(transactions):
    """트랜잭션 리스트를 DataFrame으로 변환"""
    data = []
    
    for tx in transactions:
        tx_data = tx.get('data', {})
        
        # 기본 정보 추출
        case_id = extract_case_id(tx_data)
        warehouse = extract_warehouse(tx_data)
        date_val = extract_datetime(tx_data)
        
        # 수량 처리
        incoming = tx_data.get('incoming', 0) or 0
        outgoing = tx_data.get('outgoing', 0) or 0
        
        # 기본 레코드 템플릿
        base_record = {
            'Case_No': case_id,
            'Date': date_val,
            'Location': warehouse,
            'Source_File': tx.get('source_file', ''),
            'Loc_From': 'SOURCE',
            'Target_Warehouse': warehouse,
            'Amount': tx_data.get('amount', 0),
            'Handling Fee': tx_data.get('handling_fee', 0) or 0
        }
        
        # IN 트랜잭션 생성
        if incoming > 0:
            record = base_record.copy()
            record.update({
                'TxType_Refined': 'IN',
                'Qty': int(incoming),
                'Incoming': int(incoming),
                'Outgoing': 0
            })
            data.append(record)
            
        # OUT 트랜잭션 생성
        if outgoing > 0:
            record = base_record.copy()
            
            # 사이트 구분하여 FINAL_OUT vs TRANSFER_OUT 결정
            site = extract_site(warehouse)
            tx_type = 'FINAL_OUT' if site in ['AGI', 'DAS', 'MIR', 'SHU'] else 'TRANSFER_OUT'
                
            record.update({
                'TxType_Refined': tx_type,
                'Qty': int(outgoing),
                'Loc_From': warehouse,
                'Target_Warehouse': 'DESTINATION',
                'Incoming': 0,
                'Outgoing': int(outgoing)
            })
            data.append(record)
    
    df = pd.DataFrame(data)
    if not df.empty:
        # Location 정규화 적용
        df = normalize_location_column(df)
        
        # 날짜 처리
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['Date'] = df['Date'].fillna(pd.Timestamp.now())
        df['Billing month'] = df['Date'].dt.strftime('%Y-%m')
        df['Category'] = 'General'
        
    return df

def extract_case_id(data):
    """케이스 ID 추출"""
    case_fields = ['case', 'Case', 'case_id', 'CaseID', 'ID', 'carton', 'box', 'mr#']
    
    for field in case_fields:
        if field in data and data[field]:
            case_value = str(data[field]).strip()
            if case_value and case_value.lower() not in ['nan', 'none', '']:
                return case_value
    
    return f"CASE_{abs(hash(str(data))) % 100000}"

def extract_warehouse(data):
    """창고명 추출 및 정규화"""
    warehouse_fields = ['warehouse', 'Warehouse', 'site', 'Site', 'location', 'Location']
    
    for field in warehouse_fields:
        if field in data and data[field]:
            raw_warehouse = str(data[field]).strip()
            if raw_warehouse and raw_warehouse.lower() not in ['nan', 'none', '']:
                return normalize_warehouse_name(raw_warehouse)
    
    return 'UNKNOWN'

def extract_datetime(data):
    """날짜/시간 추출"""
    date_fields = ['date', 'Date', 'timestamp', 'Timestamp', 'datetime']
    
    for field in date_fields:
        if field in data and data[field]:
            try:
                date_value = data[field]
                if isinstance(date_value, str) and date_value.lower() in ['nan', 'none', '']:
                    continue
                return pd.to_datetime(date_value)
            except:
                continue
    
    return pd.Timestamp.now()

def normalize_warehouse_name(raw_name):
    """창고명 정규화"""
    if pd.isna(raw_name) or not raw_name:
        return 'UNKNOWN'
    
    # 매핑 규칙의 모든 Location으로 정규화
    from mapping_utils import mapping_manager
    
    all_locations = []
    for locations in mapping_manager.warehouse_classification.values():
        all_locations.extend(locations)
    
    name_lower = str(raw_name).lower().strip()
    
    for location in all_locations:
        if location.lower() in name_lower or name_lower in location.lower():
            return location
    
    return str(raw_name).strip()

def extract_site(warehouse_name):
    """사이트명 추출"""
    if pd.isna(warehouse_name):
        return 'UNK'
    
    # Site 타입인지 확인
    from mapping_utils import mapping_manager
    if mapping_manager.classify_storage_type(warehouse_name) == 'Site':
        return warehouse_name
    
    return 'UNK'

def run_comprehensive_validation():
    """종합 데이터 검증 실행"""
    print("🔍 HVDC 데이터 품질 종합 검증 시작")
    print("=" * 70)
    
    try:
        # 1. 실제 데이터 로드
        transaction_df = load_actual_transaction_data()
        
        if transaction_df is None:
            print("❌ 데이터 로딩 실패")
            return False
        
        print(f"\n📊 로드된 데이터 현황:")
        print(f"   총 레코드: {len(transaction_df):,}건")
        print(f"   기간: {transaction_df['Date'].min().strftime('%Y-%m-%d')} ~ {transaction_df['Date'].max().strftime('%Y-%m-%d')}")
        print(f"   창고/현장 수: {transaction_df['Location'].nunique()}개")
        print(f"   트랜잭션 타입: {transaction_df['TxType_Refined'].value_counts().to_dict()}")
        
        # 2. 데이터 검증 엔진 초기화 및 실행
        print("\n🔍 데이터 품질 검증 시작...")
        validator = DataValidationEngine()
        validation_results = validator.validate_complete_dataset(transaction_df)
        
        # 3. 검증 결과 출력
        print(f"\n📊 검증 결과 요약:")
        print(f"   데이터 품질 점수: {validation_results['data_quality_score']}/100")
        print(f"   크리티컬 이슈: {len(validation_results['critical_issues'])}개")
        print(f"   경고 사항: {len(validation_results['warnings'])}개")
        print(f"   권장사항: {len(validation_results['recommendations'])}개")
        
        # 4. 품질 점수에 따른 등급 출력
        score = validation_results['data_quality_score']
        if score >= 90:
            grade = "🟢 우수"
        elif score >= 70:
            grade = "🟡 양호"
        elif score >= 50:
            grade = "🟠 보통"
        else:
            grade = "🔴 불량"
        
        print(f"   등급: {grade}")
        
        # 5. 크리티컬 이슈 출력
        if validation_results['critical_issues']:
            print(f"\n🚨 크리티컬 이슈:")
            for i, issue in enumerate(validation_results['critical_issues'], 1):
                print(f"   {i}. {issue}")
        
        # 6. 경고 사항 출력
        if validation_results['warnings']:
            print(f"\n⚠️ 경고 사항:")
            for i, warning in enumerate(validation_results['warnings'], 1):
                print(f"   {i}. {warning}")
        
        # 7. 권장사항 출력
        if validation_results['recommendations']:
            print(f"\n💡 권장사항:")
            for i, rec in enumerate(validation_results['recommendations'], 1):
                print(f"   {i}. {rec}")
        
        # 8. 상세 검증 결과 출력
        print(f"\n📋 상세 검증 결과:")
        for test_name, test_results in validation_results['validation_tests'].items():
            status = "✅ 통과" if test_results.get('passed', True) else "❌ 실패"
            print(f"   {test_name.replace('_', ' ').title()}: {status}")
            
            if test_results.get('issues'):
                for issue in test_results['issues']:
                    print(f"     - {issue}")
        
        # 9. 검증 리포트 생성
        print(f"\n📋 검증 리포트 생성 중...")
        report_file = validator.generate_validation_report()
        
        print(f"\n✅ 데이터 품질 검증 완료!")
        print(f"📋 리포트: {report_file}")
        
        # 10. 추가 분석 리포트 생성
        generate_detailed_analysis_report(transaction_df, validation_results)
        
        return True
        
    except Exception as e:
        print(f"❌ 데이터 검증 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_detailed_analysis_report(transaction_df, validation_results):
    """상세 분석 리포트 생성"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = f"HVDC_데이터상세분석리포트_{timestamp}.md"
    
    report_content = f"""# HVDC 데이터 상세 분석 리포트

## 📋 분석 개요
- **분석 일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **총 레코드 수**: {len(transaction_df):,}건
- **데이터 품질 점수**: {validation_results['data_quality_score']}/100

## 📊 데이터 현황 분석

### 기본 통계
- **총 트랜잭션**: {len(transaction_df):,}건
- **기간**: {transaction_df['Date'].min().strftime('%Y-%m-%d')} ~ {transaction_df['Date'].max().strftime('%Y-%m-%d')}
- **총 일수**: {(transaction_df['Date'].max() - transaction_df['Date'].min()).days}일
- **창고/현장 수**: {transaction_df['Location'].nunique()}개

### 트랜잭션 타입별 분포
"""
    
    tx_type_counts = transaction_df['TxType_Refined'].value_counts()
    for tx_type, count in tx_type_counts.items():
        percentage = (count / len(transaction_df)) * 100
        report_content += f"- **{tx_type}**: {count:,}건 ({percentage:.1f}%)\n"
    
    report_content += f"""
### 창고/현장별 분포
"""
    
    location_counts = transaction_df['Location'].value_counts().head(10)
    for location, count in location_counts.items():
        percentage = (count / len(transaction_df)) * 100
        report_content += f"- **{location}**: {count:,}건 ({percentage:.1f}%)\n"
    
    report_content += f"""
### Storage Type별 분포
"""
    
    if 'Storage_Type' in transaction_df.columns:
        storage_counts = transaction_df['Storage_Type'].value_counts()
        for storage_type, count in storage_counts.items():
            percentage = (count / len(transaction_df)) * 100
            report_content += f"- **{storage_type}**: {count:,}건 ({percentage:.1f}%)\n"
    
    report_content += f"""
## 📈 시간적 분석

### 월별 트랜잭션 분포
"""
    
    # 월별 분포
    transaction_df['YearMonth'] = transaction_df['Date'].dt.to_period('M')
    monthly_counts = transaction_df['YearMonth'].value_counts().sort_index()
    
    for month, count in monthly_counts.items():
        report_content += f"- **{month}**: {count:,}건\n"
    
    report_content += f"""
### 요일별 트랜잭션 분포
"""
    
    # 요일별 분포
    transaction_df['DayOfWeek'] = transaction_df['Date'].dt.day_name()
    day_counts = transaction_df['DayOfWeek'].value_counts()
    
    for day, count in day_counts.items():
        percentage = (count / len(transaction_df)) * 100
        report_content += f"- **{day}**: {count:,}건 ({percentage:.1f}%)\n"
    
    report_content += f"""
## 🔍 데이터 품질 분석

### 검증 결과 요약
- **품질 점수**: {validation_results['data_quality_score']}/100
- **크리티컬 이슈**: {len(validation_results['critical_issues'])}개
- **경고 사항**: {len(validation_results['warnings'])}개

### 상세 검증 결과
"""
    
    for test_name, test_results in validation_results['validation_tests'].items():
        status = "✅ 통과" if test_results.get('passed', True) else "❌ 실패"
        report_content += f"#### {test_name.replace('_', ' ').title()}: {status}\n"
        
        if test_results.get('details'):
            for key, value in test_results['details'].items():
                report_content += f"- **{key}**: {value}\n"
        
        report_content += "\n"
    
    report_content += f"""
## 💡 개선 권장사항

### 즉시 조치 필요
"""
    
    if validation_results['critical_issues']:
        for issue in validation_results['critical_issues']:
            report_content += f"- {issue}\n"
    else:
        report_content += "- 크리티컬 이슈 없음\n"
    
    report_content += f"""
### 개선 권장사항
"""
    
    if validation_results['recommendations']:
        for rec in validation_results['recommendations']:
            report_content += f"- {rec}\n"
    else:
        report_content += "- 추가 권장사항 없음\n"
    
    report_content += f"""
## 📊 수량 및 금액 분석

### 수량 통계
"""
    
    if 'Qty' in transaction_df.columns:
        qty_stats = transaction_df['Qty'].describe()
        report_content += f"""
- **총 수량**: {transaction_df['Qty'].sum():,}
- **평균 수량**: {qty_stats['mean']:.2f}
- **최대 수량**: {qty_stats['max']}
- **최소 수량**: {qty_stats['min']}
- **표준편차**: {qty_stats['std']:.2f}
"""
    
    report_content += f"""
### Handling Fee 분석
"""
    
    if 'Handling Fee' in transaction_df.columns:
        handling_stats = transaction_df['Handling Fee'].describe()
        report_content += f"""
- **총 Handling Fee**: {transaction_df['Handling Fee'].sum():,.2f}
- **평균 Handling Fee**: {handling_stats['mean']:.2f}
- **최대 Handling Fee**: {handling_stats['max']:.2f}
- **최소 Handling Fee**: {handling_stats['min']:.2f}
- **표준편차**: {handling_stats['std']:.2f}
"""
    
    report_content += f"""
---
**리포트 생성**: HVDC 데이터 상세 분석 엔진 v1.0
**생성일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    print(f"📋 상세 분석 리포트: {report_file}")
    return report_file

def main():
    """메인 함수"""
    print("🚀 HVDC 데이터 품질 검증 실행")
    print("=" * 70)
    
    success = run_comprehensive_validation()
    
    if success:
        print("\n🎉 데이터 품질 검증 성공!")
        print("📋 생성된 리포트:")
        print("   - HVDC_데이터품질검증리포트_YYYYMMDD_HHMMSS.md")
        print("   - HVDC_데이터상세분석리포트_YYYYMMDD_HHMMSS.md")
    else:
        print("\n❌ 데이터 품질 검증 실패!")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 