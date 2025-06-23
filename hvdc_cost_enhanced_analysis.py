#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HVDC 비용 강화 분석 시스템 (Cost-Enhanced Analysis)
==================================================

hvdc_ontology_pipeline.py를 기반으로 운영 비용 계산을 추가하여
월별, 창고별, 사이트별 운영 비용을 상세 분석합니다.

주요 기능:
1. 🎯 온톨로지 매핑 룰 활용 (mapping_rules_v2.4.json)
2. 💰 인보이스 기반 비용 데이터 통합
3. 📊 월별/창고별/사이트별 운영 비용 계산
4. 🔍 비용 효율성 분석
5. 📈 종합 비용-운영 리포트 생성

작성자: HVDC Analysis Team
최종 수정: 2025-06-22
기반: hvdc_ontology_pipeline.py + 비용 분석 확장
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

# hvdc_ontology_pipeline.py에서 기본 클래스들 가져오기
from hvdc_ontology_pipeline import (
    OntologyMapper, 
    EnhancedDataLoader, 
    EnhancedTransactionEngine, 
    EnhancedAnalysisEngine,
    EnhancedReportWriter
)

# =============================================================================
# 1. COST ANALYSIS ENGINE (비용 분석 엔진)
# =============================================================================

class CostAnalysisEngine:
    """비용 분석 엔진 - 인보이스 데이터 기반 운영 비용 계산"""
    
    def __init__(self, ontology_mapper: OntologyMapper):
        self.mapper = ontology_mapper
        self.invoice_data = None
        self.cost_rates = {}
        self.cost_allocations = {}
    
    def load_invoice_cost_data(self, invoice_file: str = 'data/HVDC WAREHOUSE_INVOICE.xlsx') -> bool:
        """인보이스 비용 데이터 로드"""
        try:
            self.invoice_data = pd.read_excel(invoice_file)
            print(f"✅ 인보이스 비용 데이터 로드: {len(self.invoice_data)}건")
            
            # 비용 데이터 전처리
            self._preprocess_cost_data()
            
            # 비용 비율 계산
            self._calculate_cost_rates()
            
            return True
            
        except Exception as e:
            print(f"❌ 인보이스 비용 데이터 로드 실패: {e}")
            return False
    
    def _preprocess_cost_data(self):
        """비용 데이터 전처리"""
        if self.invoice_data is None:
            return
        
        df = self.invoice_data.copy()
        
        # 컬럼명 정리 (실제 인보이스 구조에 맞게 수정)
        column_mapping = {
            'Operation Month': 'operation_month',
            'Shipment No': 'shipment_no',
            'Category': 'category',
            'pkgs q\'ty': 'packages_qty',
            'TOTAL': 'total_cost',
            'Handling In': 'handling_in_cost',
            'Handling out': 'handling_out_cost',
            'Unstuffing': 'unstuffing_cost',
            'Stuffing': 'stuffing_cost',
            'folk lift': 'forklift_cost',
            'crane': 'crane_cost',
            'Amount': 'amount_cost'
        }
        
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns:
                df[new_col] = df[old_col]
        
        # 날짜 형식 통일
        df['operation_month'] = pd.to_datetime(df['operation_month'], errors='coerce')
        df['year_month'] = df['operation_month'].dt.strftime('%Y-%m')
        
        # 카테고리별 창고 매핑
        category_warehouse_map = {
            'Indoor(M44)': 'DSV Indoor',
            'Outdoor': 'DSV Outdoor',
            'Al Markaz': 'DSV Al Markaz'
        }
        
        df['warehouse'] = df['category'].map(category_warehouse_map).fillna('기타')
        
        # 비용 컬럼들 숫자형으로 변환 (실제 컬럼에 맞게 수정)
        cost_columns = ['total_cost', 'handling_in_cost', 'handling_out_cost', 'unstuffing_cost', 'stuffing_cost', 'forklift_cost', 'crane_cost', 'amount_cost']
        for col in cost_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        self.invoice_data = df
        print(f"🔄 비용 데이터 전처리 완료: {len(df)}건")
    
    def _calculate_cost_rates(self):
        """비용 비율 계산 (패키지당, 창고별)"""
        if self.invoice_data is None:
            return
        
        df = self.invoice_data.copy()
        
        # 1. 전체 평균 비용 비율
        total_packages = df['packages_qty'].sum()
        total_cost = df['total_cost'].sum()
        
        self.cost_rates['avg_cost_per_package'] = total_cost / total_packages if total_packages > 0 else 0
        
        # 2. 창고별 비용 비율
        warehouse_costs = df.groupby('warehouse').agg({
            'packages_qty': 'sum',
            'total_cost': 'sum',
            'handling_in_cost': 'sum',
            'handling_out_cost': 'sum',
            'unstuffing_cost': 'sum',
            'stuffing_cost': 'sum',
            'forklift_cost': 'sum',
            'crane_cost': 'sum'
        }).reset_index()
        
        warehouse_costs['cost_per_package'] = warehouse_costs['total_cost'] / warehouse_costs['packages_qty']
        warehouse_costs['handling_in_rate'] = warehouse_costs['handling_in_cost'] / warehouse_costs['packages_qty']
        warehouse_costs['handling_out_rate'] = warehouse_costs['handling_out_cost'] / warehouse_costs['packages_qty']
        warehouse_costs['unstuffing_rate'] = warehouse_costs['unstuffing_cost'] / warehouse_costs['packages_qty']
        warehouse_costs['stuffing_rate'] = warehouse_costs['stuffing_cost'] / warehouse_costs['packages_qty']
        
        self.cost_rates['warehouse_rates'] = warehouse_costs.set_index('warehouse').to_dict('index')
        
        # 3. 월별 비용 추세
        monthly_costs = df.groupby('year_month').agg({
            'packages_qty': 'sum',
            'total_cost': 'sum'
        }).reset_index()
        
        monthly_costs['cost_per_package'] = monthly_costs['total_cost'] / monthly_costs['packages_qty']
        self.cost_rates['monthly_trends'] = monthly_costs.set_index('year_month').to_dict('index')
        
        print(f"💰 비용 비율 계산 완료:")
        print(f"   - 평균 패키지당 비용: ${self.cost_rates['avg_cost_per_package']:.2f}")
        print(f"   - 창고별 비율: {len(self.cost_rates['warehouse_rates'])}개")
        print(f"   - 월별 추세: {len(self.cost_rates['monthly_trends'])}개월")
    
    def calculate_warehouse_monthly_costs(self, warehouse_data: pd.DataFrame) -> pd.DataFrame:
        """창고별 월별 운영 비용 계산"""
        if warehouse_data.empty or not self.cost_rates:
            return pd.DataFrame()
        
        print("🏢 창고별 월별 운영 비용 계산 중...")
        
        # 창고 데이터에서 월별 집계
        warehouse_data['year_month'] = pd.to_datetime(warehouse_data['Date']).dt.strftime('%Y-%m')
        
        monthly_operations = warehouse_data.groupby(['Location', 'year_month', 'TxType_Refined']).agg({
            'Qty': 'sum',
            'Case_No': 'nunique'
        }).reset_index()
        
        # 비용 계산 결과
        cost_results = []
        
        for _, row in monthly_operations.iterrows():
            warehouse = row['Location']
            year_month = row['year_month']
            tx_type = row['TxType_Refined']
            qty = row['Qty']
            cases = row['Case_No']
            
            # 창고별 비용 비율 적용
            warehouse_rates = self.cost_rates['warehouse_rates'].get(warehouse, {})
            
            if not warehouse_rates:
                # 기본 비율 사용
                cost_per_package = self.cost_rates['avg_cost_per_package']
                handling_in_rate = cost_per_package * 0.3
                handling_out_rate = cost_per_package * 0.2
                unstuffing_rate = cost_per_package * 0.15
                stuffing_rate = cost_per_package * 0.15
            else:
                cost_per_package = warehouse_rates.get('cost_per_package', 0)
                handling_in_rate = warehouse_rates.get('handling_in_rate', 0)
                handling_out_rate = warehouse_rates.get('handling_out_rate', 0)
                unstuffing_rate = warehouse_rates.get('unstuffing_rate', 0)
                stuffing_rate = warehouse_rates.get('stuffing_rate', 0)
            
            # 트랜잭션 타입별 비용 계산
            if tx_type == 'IN':
                operation_cost = qty * handling_in_rate
                cost_type = '입고처리비'
            elif tx_type in ['TRANSFER_OUT', 'FINAL_OUT']:
                operation_cost = qty * handling_out_rate
                cost_type = '출고처리비'
            else:
                operation_cost = qty * cost_per_package * 0.1  # 기타 비용
                cost_type = '기타운영비'
            
            cost_results.append({
                'Warehouse': warehouse,
                'YearMonth': year_month,
                'TxType': tx_type,
                'CostType': cost_type,
                'Qty': qty,
                'Cases': cases,
                'CostPerUnit': handling_in_rate if tx_type == 'IN' else handling_out_rate,
                'TotalCost': operation_cost
            })
        
        cost_df = pd.DataFrame(cost_results)
        
        if not cost_df.empty:
            print(f"   ✅ 창고별 월별 비용 계산 완료: {len(cost_df)}건")
        
        return cost_df
    
    def calculate_site_monthly_costs(self, site_data: pd.DataFrame) -> pd.DataFrame:
        """사이트별 월별 운영 비용 계산"""
        if site_data.empty or not self.cost_rates:
            return pd.DataFrame()
        
        print("🏗️ 사이트별 월별 운영 비용 계산 중...")
        
        # 사이트 배송 데이터 필터링
        site_deliveries = site_data[
            (site_data['TxType_Refined'] == 'FINAL_OUT') & 
            (site_data['Site'] != 'UNK')
        ].copy()
        
        if site_deliveries.empty:
            return pd.DataFrame()
        
        site_deliveries['year_month'] = pd.to_datetime(site_deliveries['Date']).dt.strftime('%Y-%m')
        
        # 월별 사이트별 배송량 집계
        monthly_deliveries = site_deliveries.groupby(['Site', 'year_month']).agg({
            'Qty': 'sum',
            'Case_No': 'nunique'
        }).reset_index()
        
        # 배송 비용 계산
        delivery_costs = []
        
        for _, row in monthly_deliveries.iterrows():
            site = row['Site']
            year_month = row['year_month']
            qty = row['Qty']
            cases = row['Case_No']
            
            # 배송 비용 = 운송비 + 현장 하역비
            transportation_rate = self.cost_rates['avg_cost_per_package'] * 0.3  # 운송비 30%
            site_handling_rate = self.cost_rates['avg_cost_per_package'] * 0.15  # 현장 하역비 15%
            
            total_delivery_cost = qty * (transportation_rate + site_handling_rate)
            
            delivery_costs.append({
                'Site': site,
                'YearMonth': year_month,
                'DeliveredQty': qty,
                'DeliveredCases': cases,
                'TransportationRate': transportation_rate,
                'SiteHandlingRate': site_handling_rate,
                'TotalDeliveryCost': total_delivery_cost
            })
        
        delivery_cost_df = pd.DataFrame(delivery_costs)
        
        if not delivery_cost_df.empty:
            print(f"   ✅ 사이트별 월별 비용 계산 완료: {len(delivery_cost_df)}건")
        
        return delivery_cost_df
    
    def create_cost_efficiency_analysis(self, warehouse_costs: pd.DataFrame, site_costs: pd.DataFrame) -> Dict[str, Any]:
        """비용 효율성 분석"""
        print("📊 비용 효율성 분석 중...")
        
        efficiency_results = {}
        
        # 1. 창고별 효율성 분석
        if not warehouse_costs.empty:
            warehouse_efficiency = warehouse_costs.groupby('Warehouse').agg({
                'Qty': 'sum',
                'Cases': 'sum',
                'TotalCost': 'sum'
            }).reset_index()
            
            warehouse_efficiency['CostPerQty'] = warehouse_efficiency['TotalCost'] / warehouse_efficiency['Qty']
            warehouse_efficiency['CostPerCase'] = warehouse_efficiency['TotalCost'] / warehouse_efficiency['Cases']
            
            # 효율성 순위
            warehouse_efficiency = warehouse_efficiency.sort_values('CostPerQty')
            warehouse_efficiency['EfficiencyRank'] = range(1, len(warehouse_efficiency) + 1)
            
            efficiency_results['warehouse_efficiency'] = warehouse_efficiency
        
        # 2. 사이트별 효율성 분석
        if not site_costs.empty:
            site_efficiency = site_costs.groupby('Site').agg({
                'DeliveredQty': 'sum',
                'DeliveredCases': 'sum',
                'TotalDeliveryCost': 'sum'
            }).reset_index()
            
            site_efficiency['CostPerQty'] = site_efficiency['TotalDeliveryCost'] / site_efficiency['DeliveredQty']
            site_efficiency['CostPerCase'] = site_efficiency['TotalDeliveryCost'] / site_efficiency['DeliveredCases']
            
            # 효율성 순위
            site_efficiency = site_efficiency.sort_values('CostPerQty')
            site_efficiency['EfficiencyRank'] = range(1, len(site_efficiency) + 1)
            
            efficiency_results['site_efficiency'] = site_efficiency
        
        # 3. 전체 비용 구조 분석
        total_warehouse_cost = warehouse_costs['TotalCost'].sum() if not warehouse_costs.empty else 0
        total_site_cost = site_costs['TotalDeliveryCost'].sum() if not site_costs.empty else 0
        total_cost = total_warehouse_cost + total_site_cost
        
        cost_structure = {
            'total_warehouse_cost': total_warehouse_cost,
            'total_site_cost': total_site_cost,
            'total_cost': total_cost,
            'warehouse_cost_ratio': total_warehouse_cost / total_cost * 100 if total_cost > 0 else 0,
            'site_cost_ratio': total_site_cost / total_cost * 100 if total_cost > 0 else 0
        }
        
        efficiency_results['cost_structure'] = cost_structure
        
        print(f"   ✅ 비용 효율성 분석 완료")
        print(f"      - 총 운영비용: ${total_cost:,.2f}")
        print(f"      - 창고 운영비: ${total_warehouse_cost:,.2f} ({cost_structure['warehouse_cost_ratio']:.1f}%)")
        print(f"      - 사이트 배송비: ${total_site_cost:,.2f} ({cost_structure['site_cost_ratio']:.1f}%)")
        
        return efficiency_results

# =============================================================================
# 2. ENHANCED REPORT WRITER (비용 리포트 추가)
# =============================================================================

class CostEnhancedReportWriter(EnhancedReportWriter):
    """비용 분석이 강화된 리포트 작성기"""
    
    def __init__(self, ontology_mapper: OntologyMapper, cost_engine: CostAnalysisEngine):
        super().__init__(ontology_mapper)
        self.cost_engine = cost_engine
    
    def save_cost_enhanced_report(self, analysis_results: Dict[str, Any], cost_results: Dict[str, Any], output_path: str):
        """비용 분석이 포함된 종합 리포트 저장"""
        print(f"📄 비용 강화 종합 리포트 생성: {output_path}")
        
        try:
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
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
                currency_format = workbook.add_format({'num_format': '$#,##0.00'})
                percentage_format = workbook.add_format({'num_format': '0.0%'})
                
                # 1. 📊 종합요약 (기존 + 비용 정보)
                summary_data = self._create_cost_summary(analysis_results, cost_results)
                summary_df = pd.DataFrame(summary_data, columns=['항목', '값'])
                summary_df.to_excel(writer, sheet_name='📊 종합요약', index=False)
                self._apply_sheet_format(writer, '📊 종합요약', summary_df, header_format)
                
                # 2. 💰 창고별_월별_운영비용
                if 'warehouse_costs' in cost_results:
                    warehouse_cost_df = cost_results['warehouse_costs']
                    if not warehouse_cost_df.empty:
                        # 피벗 테이블로 변환
                        warehouse_cost_pivot = warehouse_cost_df.pivot_table(
                            index='Warehouse',
                            columns='YearMonth',
                            values='TotalCost',
                            aggfunc='sum',
                            fill_value=0
                        ).reset_index()
                        
                        warehouse_cost_pivot.to_excel(writer, sheet_name='💰창고별_운영비용', index=False)
                        self._apply_sheet_format(writer, '💰창고별_운영비용', warehouse_cost_pivot, header_format, currency_format)
                
                # 3. 🏗️ 사이트별_월별_배송비용
                if 'site_costs' in cost_results:
                    site_cost_df = cost_results['site_costs']
                    if not site_cost_df.empty:
                        # 피벗 테이블로 변환
                        site_cost_pivot = site_cost_df.pivot_table(
                            index='Site',
                            columns='YearMonth',
                            values='TotalDeliveryCost',
                            aggfunc='sum',
                            fill_value=0
                        ).reset_index()
                        
                        site_cost_pivot.to_excel(writer, sheet_name='🏗️사이트별_배송비용', index=False)
                        self._apply_sheet_format(writer, '🏗️사이트별_배송비용', site_cost_pivot, header_format, currency_format)
                
                # 4. 📈 창고_효율성_분석
                if 'efficiency_analysis' in cost_results and 'warehouse_efficiency' in cost_results['efficiency_analysis']:
                    warehouse_eff_df = cost_results['efficiency_analysis']['warehouse_efficiency']
                    warehouse_eff_df.to_excel(writer, sheet_name='📈 창고_효율성_분석', index=False)
                    self._apply_sheet_format(writer, '📈 창고_효율성_분석', warehouse_eff_df, header_format, currency_format)
                
                # 5. 🎯 사이트_효율성_분석
                if 'efficiency_analysis' in cost_results and 'site_efficiency' in cost_results['efficiency_analysis']:
                    site_eff_df = cost_results['efficiency_analysis']['site_efficiency']
                    site_eff_df.to_excel(writer, sheet_name='🎯 사이트_효율성_분석', index=False)
                    self._apply_sheet_format(writer, '🎯 사이트_효율성_분석', site_eff_df, header_format, currency_format)
                
                # 6. 기존 분석 시트들 추가
                self._add_existing_analysis_sheets(writer, analysis_results, header_format, number_format)
            
            print(f"✅ 비용 강화 리포트 저장 완료: {output_path}")
            
        except Exception as e:
            print(f"❌ 비용 강화 리포트 저장 실패: {e}")
    
    def _create_cost_summary(self, analysis_results: Dict, cost_results: Dict) -> List[List]:
        """비용 정보가 포함된 종합 요약 생성"""
        summary_data = []
        
        # 기본 운영 정보
        if 'transaction_log' in analysis_results:
            tx_log = analysis_results['transaction_log']
            summary_data.extend([
                ['📦 운영 현황', ''],
                ['총 트랜잭션', f"{len(tx_log):,}건"],
                ['총 케이스', f"{tx_log['Case_No'].nunique():,}개"],
                ['총 수량', f"{tx_log['Qty'].sum():,}박스"],
                ['', ''],
            ])
        
        # 비용 정보
        if 'efficiency_analysis' in cost_results:
            cost_structure = cost_results['efficiency_analysis'].get('cost_structure', {})
            summary_data.extend([
                ['💰 비용 현황', ''],
                ['총 운영비용', f"${cost_structure.get('total_cost', 0):,.2f}"],
                ['창고 운영비', f"${cost_structure.get('total_warehouse_cost', 0):,.2f}"],
                ['사이트 배송비', f"${cost_structure.get('total_site_cost', 0):,.2f}"],
                ['창고 비용 비율', f"{cost_structure.get('warehouse_cost_ratio', 0):.1f}%"],
                ['배송 비용 비율', f"{cost_structure.get('site_cost_ratio', 0):.1f}%"],
                ['', ''],
            ])
        
        # 효율성 정보
        if 'efficiency_analysis' in cost_results:
            efficiency = cost_results['efficiency_analysis']
            
            if 'warehouse_efficiency' in efficiency:
                best_warehouse = efficiency['warehouse_efficiency'].iloc[0] if not efficiency['warehouse_efficiency'].empty else None
                if best_warehouse is not None:
                    summary_data.extend([
                        ['🏆 최고 효율 창고', ''],
                        ['창고명', best_warehouse['Warehouse']],
                        ['단위당 비용', f"${best_warehouse['CostPerQty']:.2f}"],
                        ['', ''],
                    ])
            
            if 'site_efficiency' in efficiency:
                best_site = efficiency['site_efficiency'].iloc[0] if not efficiency['site_efficiency'].empty else None
                if best_site is not None:
                    summary_data.extend([
                        ['🎯 최고 효율 사이트', ''],
                        ['사이트명', best_site['Site']],
                        ['단위당 비용', f"${best_site['CostPerQty']:.2f}"],
                    ])
        
        return summary_data
    
    def _apply_sheet_format(self, writer, sheet_name: str, df: pd.DataFrame, header_format, data_format=None):
        """시트 서식 적용"""
        try:
            worksheet = writer.sheets[sheet_name]
            
            # 헤더 서식
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # 데이터 서식 (숫자/통화 컬럼)
            if data_format:
                for i, col in enumerate(df.columns):
                    if any(keyword in col.lower() for keyword in ['cost', '비용', 'total', '합계']):
                        worksheet.set_column(i, i, 15, data_format)
                    else:
                        worksheet.set_column(i, i, 12)
        
        except Exception as e:
            print(f"⚠️ 시트 서식 적용 실패 ({sheet_name}): {e}")
    
    def _add_existing_analysis_sheets(self, writer, analysis_results: Dict, header_format, number_format):
        """기존 분석 시트들 추가"""
        existing_sheets = {
            'transaction_log': '📋 트랜잭션_로그',
            'daily_stock': '📊 일별_재고',
            'monthly_summary': '📅 월별_요약'
        }
        
        for key, sheet_name in existing_sheets.items():
            if key in analysis_results and not analysis_results[key].empty:
                try:
                    df = analysis_results[key]
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    self._apply_sheet_format(writer, sheet_name, df, header_format, number_format)
                except Exception as e:
                    print(f"⚠️ 기존 시트 추가 실패 ({sheet_name}): {e}")

# =============================================================================
# 3. MAIN PIPELINE (메인 파이프라인)
# =============================================================================

def run_cost_enhanced_analysis():
    """비용 강화 분석 메인 실행 함수"""
    print("🚀 HVDC 비용 강화 분석 시스템 시작")
    print("=" * 60)
    
    try:
        # 1. 온톨로지 매퍼 초기화
        mapper = OntologyMapper("mapping_rules_v2.4.json")
        print(f"✅ 온톨로지 매핑 룰 로드 완료")
        
        # 2. 비용 분석 엔진 초기화
        cost_engine = CostAnalysisEngine(mapper)
        
        # 3. 인보이스 비용 데이터 로드
        if not cost_engine.load_invoice_cost_data():
            print("❌ 인보이스 비용 데이터 로드 실패")
            return False
        
        # 4. 창고 데이터 로드 및 분석 (기존 온톨로지 파이프라인 활용)
        print("\n📂 창고 데이터 로드 및 분석 중...")
        
        data_loader = EnhancedDataLoader(mapper)
        raw_events = data_loader.load_and_process_files("data")
        
        if raw_events.empty:
            print("❌ 창고 데이터가 없습니다.")
            return False
        
        # 5. 트랜잭션 분석
        print("\n🔄 트랜잭션 분석 중...")
        tx_engine = EnhancedTransactionEngine(mapper)
        transaction_log = tx_engine.create_transaction_log(raw_events)
        
        # 6. 재고 분석
        print("\n📊 재고 분석 중...")
        analysis_engine = EnhancedAnalysisEngine(mapper)
        daily_stock = analysis_engine.calculate_daily_stock(transaction_log)
        monthly_summary = analysis_engine.create_monthly_summary(transaction_log, daily_stock)
        validation = analysis_engine.validate_stock_integrity(daily_stock)
        
        # 7. 비용 분석 수행
        print("\n💰 비용 분석 수행 중...")
        
        # 창고별 월별 운영 비용
        warehouse_costs = cost_engine.calculate_warehouse_monthly_costs(transaction_log)
        
        # 사이트별 월별 배송 비용
        site_costs = cost_engine.calculate_site_monthly_costs(transaction_log)
        
        # 비용 효율성 분석
        efficiency_analysis = cost_engine.create_cost_efficiency_analysis(warehouse_costs, site_costs)
        
        # 8. 결과 통합
        analysis_results = {
            'transaction_log': transaction_log,
            'daily_stock': daily_stock,
            'monthly_summary': monthly_summary,
            'validation': validation
        }
        
        cost_results = {
            'warehouse_costs': warehouse_costs,
            'site_costs': site_costs,
            'efficiency_analysis': efficiency_analysis
        }
        
        # 9. 비용 강화 리포트 생성
        print("\n📄 비용 강화 리포트 생성 중...")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'HVDC_비용강화_분석리포트_{timestamp}.xlsx'
        
        report_writer = CostEnhancedReportWriter(mapper, cost_engine)
        report_writer.save_cost_enhanced_report(analysis_results, cost_results, output_file)
        
        # 10. 결과 요약 출력
        print(f"\n📋 분석 결과 요약:")
        print(f"   📦 총 트랜잭션: {len(transaction_log):,}건")
        print(f"   📊 일별 재고 포인트: {len(daily_stock):,}개")
        print(f"   ✅ 재고 검증: {validation.get('status', 'UNKNOWN')}")
        
        if efficiency_analysis and 'cost_structure' in efficiency_analysis:
            cost_structure = efficiency_analysis['cost_structure']
            print(f"\n💰 비용 분석 결과:")
            print(f"   - 총 운영비용: ${cost_structure['total_cost']:,.2f}")
            print(f"   - 창고 운영비: ${cost_structure['total_warehouse_cost']:,.2f}")
            print(f"   - 사이트 배송비: ${cost_structure['total_site_cost']:,.2f}")
        
        print(f"\n🎉 비용 강화 분석 완료!")
        print(f"📁 생성된 파일: {output_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ 비용 강화 분석 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_cost_enhanced_analysis()
    if success:
        print(f"\n✅ HVDC 비용 강화 분석 시스템 실행 완료!")
    else:
        print(f"\n❌ HVDC 비용 강화 분석 시스템 실행 실패!") 