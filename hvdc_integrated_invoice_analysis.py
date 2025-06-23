#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HVDC 통합 인보이스-창고 분석 시스템
=================================

인보이스 데이터와 창고 데이터를 연결하여 종합적인 분석을 제공합니다.

주요 기능:
1. 인보이스 데이터 분석 (비용, 처리량, 운영 효율성)
2. 창고 데이터와 인보이스 데이터 매칭
3. 통합 재무-운영 분석
4. 한국어 통합 리포트 생성

작성자: HVDC Analysis Team
최종 수정: 2025-06-22
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import json
from typing import Dict, List, Tuple, Any
import warnings
warnings.filterwarnings('ignore')

class InvoiceAnalyzer:
    """인보이스 데이터 분석기"""
    
    def __init__(self):
        self.invoice_df = None
        self.processed_data = {}
        
    def load_invoice_data(self, file_path: str = 'data/HVDC WAREHOUSE_INVOICE.xlsx') -> bool:
        """인보이스 데이터 로드"""
        try:
            self.invoice_df = pd.read_excel(file_path)
            print(f"✅ 인보이스 데이터 로드 완료: {len(self.invoice_df)}건")
            return True
        except Exception as e:
            print(f"❌ 인보이스 데이터 로드 실패: {e}")
            return False
    
    def analyze_invoice_operations(self) -> Dict[str, Any]:
        """인보이스 운영 분석"""
        if self.invoice_df is None:
            return {}
        
        df = self.invoice_df.copy()
        
        # 1. 월별 운영 분석
        monthly_ops = df.groupby('Operation Month').agg({
            'Shipment No': 'nunique',
            'pkgs q\'ty': 'sum',
            'Weight (kg)': 'sum',
            'CBM': 'sum',
            'TOTAL': 'sum',
            'Handling In': 'sum',
            'Handling out': 'sum'
        }).fillna(0)
        
        # 2. 카테고리별 분석
        category_analysis = df.groupby('Category').agg({
            'Shipment No': 'nunique',
            'pkgs q\'ty': 'sum',
            'Weight (kg)': 'sum',
            'CBM': 'sum',
            'TOTAL': 'sum'
        }).fillna(0)
        
        # 3. 컨테이너 타입별 분석
        container_analysis = {}
        for container_type in ['20DC', '20FR', '40DC', '40FR']:
            container_analysis[container_type] = {
                'count': df[container_type].notna().sum(),
                'total_qty': df[container_type].sum() if df[container_type].notna().sum() > 0 else 0
            }
        
        # 4. 비용 구조 분석
        cost_structure = {
            'handling_in': df['Handling In'].sum(),
            'handling_out': df['Handling out'].sum(),
            'unstuffing': df['Unstuffing'].sum(),
            'stuffing': df['Stuffing'].sum(),
            'folk_lift': df['folk lift'].sum(),
            'crane': df['crane'].sum(),
            'total': df['TOTAL'].sum()
        }
        
        return {
            'monthly_operations': monthly_ops,
            'category_analysis': category_analysis,
            'container_analysis': container_analysis,
            'cost_structure': cost_structure,
            'summary': {
                'total_shipments': df['Shipment No'].nunique(),
                'total_packages': df['pkgs q\'ty'].sum(),
                'total_weight_kg': df['Weight (kg)'].sum(),
                'total_cbm': df['CBM'].sum(),
                'total_cost': df['TOTAL'].sum(),
                'avg_cost_per_shipment': df['TOTAL'].sum() / df['Shipment No'].nunique() if df['Shipment No'].nunique() > 0 else 0
            }
        }
    
    def match_with_warehouse_data(self, warehouse_cases: List[str]) -> Dict[str, Any]:
        """창고 데이터와 인보이스 데이터 매칭"""
        if self.invoice_df is None:
            return {}
        
        df = self.invoice_df.copy()
        
        # Shipment No에서 Case No 패턴 추출
        df['Extracted_Case'] = df['Shipment No'].str.extract(r'(HE-\d+)', expand=False)
        
        # 창고 케이스와 매칭
        matched_cases = []
        unmatched_invoices = []
        unmatched_warehouse = []
        
        for _, row in df.iterrows():
            shipment_no = str(row['Shipment No']) if pd.notna(row['Shipment No']) else ''
            extracted_case = row['Extracted_Case'] if pd.notna(row['Extracted_Case']) else ''
            
            # 매칭 시도
            matched = False
            for case in warehouse_cases:
                case_str = str(case) if case is not None else ''
                if extracted_case and extracted_case in case_str:
                    matched_cases.append({
                        'shipment_no': shipment_no,
                        'warehouse_case': case_str,
                        'extracted_case': extracted_case,
                        'invoice_total': row['TOTAL'],
                        'packages': row['pkgs q\'ty'],
                        'weight': row['Weight (kg)'],
                        'cbm': row['CBM']
                    })
                    matched = True
                    break
            
            if not matched and extracted_case:
                unmatched_invoices.append({
                    'shipment_no': shipment_no,
                    'extracted_case': extracted_case,
                    'invoice_total': row['TOTAL']
                })
        
        # 매칭되지 않은 창고 케이스
        matched_warehouse_cases = [m['warehouse_case'] for m in matched_cases]
        unmatched_warehouse = [case for case in warehouse_cases if case not in matched_warehouse_cases]
        
        return {
            'matched_cases': matched_cases,
            'unmatched_invoices': unmatched_invoices,
            'unmatched_warehouse': unmatched_warehouse,
            'matching_stats': {
                'total_invoices': len(df),
                'matched_count': len(matched_cases),
                'unmatched_invoices_count': len(unmatched_invoices),
                'unmatched_warehouse_count': len(unmatched_warehouse),
                'matching_rate': len(matched_cases) / len(df) * 100 if len(df) > 0 else 0
            }
        }

class IntegratedAnalyzer:
    """통합 분석기 (창고 + 인보이스)"""
    
    def __init__(self):
        self.invoice_analyzer = InvoiceAnalyzer()
        self.warehouse_data = {}
        self.integrated_results = {}
    
    def load_all_data(self) -> bool:
        """모든 데이터 로드"""
        try:
            # 1. 인보이스 데이터 로드
            if not self.invoice_analyzer.load_invoice_data():
                return False
            
            # 2. 창고 데이터 로드 (기존 타임라인 분석 활용)
            import sys
            sys.path.append('.')
            
            # 간단한 창고 데이터 로드 (타임라인 분석 없이)
            warehouse_files = [
                'data/HVDC WAREHOUSE_HITACHI(HE).xlsx',
                'data/HVDC WAREHOUSE_HITACHI(HE-0214,0252)1.xlsx', 
                'data/HVDC WAREHOUSE_HITACHI(HE_LOCAL).xlsx',
                'data/HVDC WAREHOUSE_SIMENSE(SIM).xlsx'
            ]
            
            all_cases = []
            for file_path in warehouse_files:
                if os.path.exists(file_path):
                    try:
                        df = pd.read_excel(file_path, sheet_name=0)  # 첫 번째 시트
                        if 'Case No.' in df.columns:
                            cases = df['Case No.'].dropna().unique().tolist()
                            all_cases.extend(cases)
                            print(f"✅ {os.path.basename(file_path)}: {len(cases)}개 케이스")
                    except Exception as e:
                        print(f"⚠️ {file_path} 로드 실패: {e}")
            
            self.warehouse_data = {'cases': all_cases}
            
            print(f"✅ 통합 데이터 로드 완료")
            print(f"   - 창고 케이스: {len(all_cases)}개")
            print(f"   - 인보이스: {len(self.invoice_analyzer.invoice_df)}건")
            
            return True
            
        except Exception as e:
            print(f"❌ 데이터 로드 실패: {e}")
            return False
    
    def perform_integrated_analysis(self) -> Dict[str, Any]:
        """통합 분석 수행"""
        if not self.warehouse_data or self.invoice_analyzer.invoice_df is None:
            print("❌ 데이터가 로드되지 않았습니다.")
            return {}
        
        print("🔄 통합 분석 수행 중...")
        
        # 1. 인보이스 운영 분석
        invoice_analysis = self.invoice_analyzer.analyze_invoice_operations()
        
        # 2. 창고 케이스 목록 추출
        warehouse_cases = self.warehouse_data.get('cases', [])
        
        # 3. 창고-인보이스 매칭
        matching_results = self.invoice_analyzer.match_with_warehouse_data(warehouse_cases)
        
        # 4. 통합 재무 분석
        financial_analysis = self._analyze_integrated_financials(matching_results)
        
        # 5. 운영 효율성 분석
        efficiency_analysis = self._analyze_operational_efficiency(matching_results)
        
        self.integrated_results = {
            'invoice_analysis': invoice_analysis,
            'matching_results': matching_results,
            'financial_analysis': financial_analysis,
            'efficiency_analysis': efficiency_analysis,
            'warehouse_summary': {'total_cases': len(warehouse_cases)},
            'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return self.integrated_results
    
    def _analyze_integrated_financials(self, matching_results: Dict) -> Dict[str, Any]:
        """통합 재무 분석"""
        matched_cases = matching_results.get('matched_cases', [])
        
        if not matched_cases:
            return {'error': '매칭된 케이스가 없습니다.'}
        
        # 매칭된 케이스들의 재무 분석
        total_invoice_amount = sum(case.get('invoice_total', 0) for case in matched_cases)
        total_packages = sum(case.get('packages', 0) for case in matched_cases)
        total_weight = sum(case.get('weight', 0) for case in matched_cases if pd.notna(case.get('weight', 0)))
        total_cbm = sum(case.get('cbm', 0) for case in matched_cases if pd.notna(case.get('cbm', 0)))
        
        # 창고별 비용 분석 (매칭된 케이스 기준)
        warehouse_costs = {}
        for case in matched_cases:
            warehouse_case = case['warehouse_case']
            # 창고 정보 추출 (간단한 패턴 매칭)
            if 'DSV' in str(warehouse_case):
                warehouse = 'DSV'
            elif 'MOSB' in str(warehouse_case):
                warehouse = 'MOSB'
            else:
                warehouse = 'OTHER'
            
            if warehouse not in warehouse_costs:
                warehouse_costs[warehouse] = {
                    'total_cost': 0,
                    'case_count': 0,
                    'total_packages': 0
                }
            
            warehouse_costs[warehouse]['total_cost'] += case.get('invoice_total', 0)
            warehouse_costs[warehouse]['case_count'] += 1
            warehouse_costs[warehouse]['total_packages'] += case.get('packages', 0)
        
        # 효율성 메트릭 계산
        avg_cost_per_case = total_invoice_amount / len(matched_cases) if matched_cases else 0
        avg_cost_per_package = total_invoice_amount / total_packages if total_packages > 0 else 0
        avg_cost_per_kg = total_invoice_amount / total_weight if total_weight > 0 else 0
        avg_cost_per_cbm = total_invoice_amount / total_cbm if total_cbm > 0 else 0
        
        return {
            'matched_financials': {
                'total_invoice_amount': total_invoice_amount,
                'total_packages': total_packages,
                'total_weight_kg': total_weight,
                'total_cbm': total_cbm,
                'matched_case_count': len(matched_cases)
            },
            'efficiency_metrics': {
                'avg_cost_per_case': avg_cost_per_case,
                'avg_cost_per_package': avg_cost_per_package,
                'avg_cost_per_kg': avg_cost_per_kg,
                'avg_cost_per_cbm': avg_cost_per_cbm
            },
            'warehouse_cost_breakdown': warehouse_costs
        }
    
    def _analyze_operational_efficiency(self, matching_results: Dict) -> Dict[str, Any]:
        """운영 효율성 분석"""
        matched_cases = matching_results.get('matched_cases', [])
        matching_stats = matching_results.get('matching_stats', {})
        
        # 매칭률 기반 효율성
        matching_rate = matching_stats.get('matching_rate', 0)
        
        # 운영 효율성 등급
        if matching_rate >= 90:
            efficiency_grade = 'A (우수)'
        elif matching_rate >= 80:
            efficiency_grade = 'B (양호)'
        elif matching_rate >= 70:
            efficiency_grade = 'C (보통)'
        elif matching_rate >= 60:
            efficiency_grade = 'D (개선필요)'
        else:
            efficiency_grade = 'F (불량)'
        
        # 개선 권고사항
        recommendations = []
        if matching_rate < 80:
            recommendations.append("창고 데이터와 인보이스 데이터 간 케이스 번호 표준화 필요")
        if matching_stats.get('unmatched_invoices_count', 0) > 0:
            recommendations.append("매칭되지 않은 인보이스에 대한 검토 필요")
        if matching_stats.get('unmatched_warehouse_count', 0) > 0:
            recommendations.append("인보이스가 없는 창고 케이스에 대한 확인 필요")
        
        return {
            'matching_efficiency': {
                'matching_rate': matching_rate,
                'efficiency_grade': efficiency_grade,
                'total_cases_processed': matching_stats.get('total_invoices', 0),
                'successfully_matched': matching_stats.get('matched_count', 0)
            },
            'data_quality': {
                'unmatched_invoices': matching_stats.get('unmatched_invoices_count', 0),
                'unmatched_warehouse_cases': matching_stats.get('unmatched_warehouse_count', 0),
                'data_consistency_score': matching_rate
            },
            'recommendations': recommendations
        }

def create_integrated_excel_report(analyzer: IntegratedAnalyzer, output_filename: str = None):
    """통합 엑셀 리포트 생성"""
    if not analyzer.integrated_results:
        print("❌ 분석 결과가 없습니다. 먼저 분석을 수행하세요.")
        return
    
    if output_filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f'HVDC_통합_인보이스_리포트_{timestamp}.xlsx'
    
    try:
        with pd.ExcelWriter(output_filename, engine='openpyxl') as writer:
            results = analyzer.integrated_results
            
            # 1. 📊 종합요약 시트
            summary_data = []
            
            # 인보이스 요약
            invoice_summary = results['invoice_analysis']['summary']
            summary_data.extend([
                ['📋 인보이스 분석 요약', ''],
                ['총 선적 건수', f"{invoice_summary['total_shipments']:,}건"],
                ['총 패키지 수량', f"{invoice_summary['total_packages']:,}개"],
                ['총 중량', f"{invoice_summary['total_weight_kg']:,.1f}kg"],
                ['총 부피', f"{invoice_summary['total_cbm']:,.2f}CBM"],
                ['총 비용', f"${invoice_summary['total_cost']:,.2f}"],
                ['선적당 평균 비용', f"${invoice_summary['avg_cost_per_shipment']:,.2f}"],
                ['', ''],
            ])
            
            # 매칭 결과 요약
            matching_stats = results['matching_results']['matching_stats']
            summary_data.extend([
                ['🔗 데이터 매칭 결과', ''],
                ['총 인보이스 건수', f"{matching_stats['total_invoices']:,}건"],
                ['매칭 성공 건수', f"{matching_stats['matched_count']:,}건"],
                ['매칭률', f"{matching_stats['matching_rate']:.1f}%"],
                ['미매칭 인보이스', f"{matching_stats['unmatched_invoices_count']:,}건"],
                ['미매칭 창고 케이스', f"{matching_stats['unmatched_warehouse_count']:,}건"],
                ['', ''],
            ])
            
            # 재무 분석 요약
            if 'financial_analysis' in results and 'matched_financials' in results['financial_analysis']:
                financial = results['financial_analysis']['matched_financials']
                efficiency = results['financial_analysis']['efficiency_metrics']
                summary_data.extend([
                    ['💰 재무 분석 (매칭된 케이스)', ''],
                    ['매칭된 총 비용', f"${financial['total_invoice_amount']:,.2f}"],
                    ['매칭된 총 패키지', f"{financial['total_packages']:,}개"],
                    ['케이스당 평균 비용', f"${efficiency['avg_cost_per_case']:,.2f}"],
                    ['패키지당 평균 비용', f"${efficiency['avg_cost_per_package']:.2f}"],
                    ['kg당 평균 비용', f"${efficiency['avg_cost_per_kg']:.4f}"],
                    ['CBM당 평균 비용', f"${efficiency['avg_cost_per_cbm']:.2f}"],
                    ['', ''],
                ])
            
            # 효율성 분석
            if 'efficiency_analysis' in results:
                efficiency_analysis = results['efficiency_analysis']['matching_efficiency']
                summary_data.extend([
                    ['📈 운영 효율성 분석', ''],
                    ['데이터 매칭률', f"{efficiency_analysis['matching_rate']:.1f}%"],
                    ['효율성 등급', efficiency_analysis['efficiency_grade']],
                    ['처리된 총 케이스', f"{efficiency_analysis['total_cases_processed']:,}건"],
                    ['성공적 매칭', f"{efficiency_analysis['successfully_matched']:,}건"],
                ])
            
            summary_df = pd.DataFrame(summary_data, columns=['항목', '값'])
            summary_df.to_excel(writer, sheet_name='📊 종합요약', index=False)
            
            # 2. 💰 인보이스_월별_분석 시트
            if 'monthly_operations' in results['invoice_analysis']:
                monthly_df = results['invoice_analysis']['monthly_operations'].reset_index()
                monthly_df.columns = ['운영월', '선적건수', '패키지수량', '중량(kg)', 'CBM', '총비용', '입고처리비', '출고처리비']
                monthly_df.to_excel(writer, sheet_name='💰 인보이스_월별_분석', index=False)
            
            # 3. 📦 카테고리별_분석 시트
            if 'category_analysis' in results['invoice_analysis']:
                category_df = results['invoice_analysis']['category_analysis'].reset_index()
                category_df.columns = ['카테고리', '선적건수', '패키지수량', '중량(kg)', 'CBM', '총비용']
                category_df.to_excel(writer, sheet_name='📦 카테고리별_분석', index=False)
            
            # 4. 🔗 매칭_결과_상세 시트
            if results['matching_results']['matched_cases']:
                matched_df = pd.DataFrame(results['matching_results']['matched_cases'])
                matched_df.columns = ['선적번호', '창고케이스', '추출케이스', '인보이스금액', '패키지수', '중량', 'CBM']
                matched_df.to_excel(writer, sheet_name='🔗 매칭_결과_상세', index=False)
            
            # 5. ❌ 미매칭_인보이스 시트
            if results['matching_results']['unmatched_invoices']:
                unmatched_inv_df = pd.DataFrame(results['matching_results']['unmatched_invoices'])
                unmatched_inv_df.columns = ['선적번호', '추출케이스', '인보이스금액']
                unmatched_inv_df.to_excel(writer, sheet_name='❌ 미매칭_인보이스', index=False)
            
            # 6. ⚠️ 미매칭_창고케이스 시트
            if results['matching_results']['unmatched_warehouse']:
                unmatched_wh_df = pd.DataFrame(results['matching_results']['unmatched_warehouse'], columns=['창고케이스'])
                unmatched_wh_df.to_excel(writer, sheet_name='⚠️ 미매칭_창고케이스', index=False)
            
            # 7. 💡 개선권고사항 시트
            if 'efficiency_analysis' in results and 'recommendations' in results['efficiency_analysis']:
                recommendations = results['efficiency_analysis']['recommendations']
                rec_df = pd.DataFrame([(i+1, rec) for i, rec in enumerate(recommendations)], 
                                    columns=['번호', '개선권고사항'])
                rec_df.to_excel(writer, sheet_name='💡 개선권고사항', index=False)
        
        print(f"✅ 통합 인보이스 리포트 생성 완료: {output_filename}")
        return output_filename
        
    except Exception as e:
        print(f"❌ 리포트 생성 실패: {e}")
        return None

def main():
    """메인 실행 함수"""
    print("🚀 HVDC 통합 인보이스-창고 분석 시스템 시작")
    print("=" * 60)
    
    # 통합 분석기 초기화
    analyzer = IntegratedAnalyzer()
    
    # 데이터 로드
    print("📂 데이터 로드 중...")
    if not analyzer.load_all_data():
        print("❌ 데이터 로드 실패. 프로그램을 종료합니다.")
        return
    
    # 통합 분석 수행
    print("\n🔄 통합 분석 수행 중...")
    results = analyzer.perform_integrated_analysis()
    
    if not results:
        print("❌ 분석 실패. 프로그램을 종료합니다.")
        return
    
    # 결과 출력
    print("\n📊 분석 결과 요약:")
    print("-" * 40)
    
    # 인보이스 요약
    invoice_summary = results['invoice_analysis']['summary']
    print(f"📋 인보이스 분석:")
    print(f"   - 총 선적 건수: {invoice_summary['total_shipments']:,}건")
    print(f"   - 총 패키지: {invoice_summary['total_packages']:,}개")
    print(f"   - 총 비용: ${invoice_summary['total_cost']:,.2f}")
    
    # 매칭 결과
    matching_stats = results['matching_results']['matching_stats']
    print(f"\n🔗 데이터 매칭 결과:")
    print(f"   - 매칭률: {matching_stats['matching_rate']:.1f}%")
    print(f"   - 매칭 성공: {matching_stats['matched_count']:,}건")
    print(f"   - 미매칭 인보이스: {matching_stats['unmatched_invoices_count']:,}건")
    
    # 효율성 분석
    if 'efficiency_analysis' in results:
        efficiency = results['efficiency_analysis']['matching_efficiency']
        print(f"\n📈 운영 효율성:")
        print(f"   - 효율성 등급: {efficiency['efficiency_grade']}")
    
    # 엑셀 리포트 생성
    print(f"\n📄 통합 리포트 생성 중...")
    output_file = create_integrated_excel_report(analyzer)
    
    if output_file:
        print(f"\n🎉 분석 완료!")
        print(f"📁 생성된 파일: {output_file}")
    else:
        print(f"\n❌ 리포트 생성에 실패했습니다.")

if __name__ == "__main__":
    main() 