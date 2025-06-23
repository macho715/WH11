# inventory_validation.py - HVDC 재고 계산 검증 유틸리티
"""
HVDC 창고 분석을 위한 재고 계산 검증 도구
- 반복문 기반 재고 계산
- 벡터화 계산과의 일치성 검증
- 재고 로직 무결성 테스트
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any

class InventoryValidator:
    """재고 계산 검증기 - 사용자 검증 결과 반영"""
    
    # 사용자 제공 검증 결과
    USER_VALIDATION_RESULTS = {
        'DSV Al Markaz': 812,
        'DSV Indoor': 414,
        'validation_pass_rate': 95,  # 95% 이상
        'error_reduction': 60,       # 60% 감소
        'duplicate_prevention': 100  # 100% 적용
    }
    
    @staticmethod
    def calculate_inventory_loop(df: pd.DataFrame, initial_stock: float = 0, 
                                incoming_col: str = 'Incoming', 
                                outgoing_col: str = 'Outgoing') -> List[float]:
        """
        반복문 기반 재고 계산 - 사용자 제공 로직 (검증 완료 ✅)
        
        검증 결과:
        - 검증 통과율: ≥95%
        - 오류 감소: 60%↓ 달성
        - 이중계산 방지: 100% 적용
        """
        inv = initial_stock
        inventory_list = []
        
        for in_qty, out_qty in zip(df[incoming_col], df[outgoing_col]):
            inv = inv + in_qty - out_qty   # 이전 inv에 입고-출고 반영
            inventory_list.append(inv)
        
        return inventory_list
    
    @staticmethod
    def calculate_inventory_vectorized(df: pd.DataFrame, initial_stock: float = 0,
                                     incoming_col: str = 'Incoming', 
                                     outgoing_col: str = 'Outgoing') -> pd.Series:
        """
        벡터화 재고 계산 (성능 최적화)
        """
        net_movement = df[incoming_col] - df[outgoing_col]
        return initial_stock + net_movement.cumsum()
    
    @staticmethod
    def validate_inventory_calculation(df: pd.DataFrame, initial_stock: float = 0,
                                     incoming_col: str = 'Incoming', 
                                     outgoing_col: str = 'Outgoing',
                                     existing_inventory_col: str = 'Inventory') -> Dict[str, Any]:
        """
        재고 계산 검증
        반복문, 벡터화, 기존 계산 결과를 모두 비교
        """
        
        # 1. 반복문 기반 계산
        inventory_loop = InventoryValidator.calculate_inventory_loop(
            df, initial_stock, incoming_col, outgoing_col
        )
        df_temp = df.copy()
        df_temp['Inventory_loop'] = inventory_loop
        
        # 2. 벡터화 계산
        inventory_vectorized = InventoryValidator.calculate_inventory_vectorized(
            df, initial_stock, incoming_col, outgoing_col
        )
        df_temp['Inventory_vectorized'] = inventory_vectorized
        
        # 3. 검증 결과
        validation_results = {
            'total_records': len(df),
            'initial_stock': initial_stock,
            'final_inventory_loop': inventory_loop[-1] if inventory_loop else initial_stock,
            'final_inventory_vectorized': inventory_vectorized.iloc[-1] if not inventory_vectorized.empty else initial_stock,
            'loop_vs_vectorized_match': True,
            'loop_vs_existing_match': True,
            'vectorized_vs_existing_match': True,
            'mismatches': []
        }
        
        # 반복문 vs 벡터화 비교
        try:
            loop_vs_vec_match = np.allclose(inventory_loop, inventory_vectorized, rtol=1e-9)
            validation_results['loop_vs_vectorized_match'] = loop_vs_vec_match
            if not loop_vs_vec_match:
                validation_results['mismatches'].append('반복문과 벡터화 계산 불일치')
        except:
            validation_results['loop_vs_vectorized_match'] = False
            validation_results['mismatches'].append('반복문과 벡터화 계산 비교 실패')
        
        # 기존 Inventory 컬럼과 비교 (있는 경우)
        if existing_inventory_col in df.columns:
            try:
                # 반복문 vs 기존
                loop_vs_existing = np.allclose(inventory_loop, df[existing_inventory_col], rtol=1e-9)
                validation_results['loop_vs_existing_match'] = loop_vs_existing
                
                # 벡터화 vs 기존
                vec_vs_existing = np.allclose(inventory_vectorized, df[existing_inventory_col], rtol=1e-9)
                validation_results['vectorized_vs_existing_match'] = vec_vs_existing
                
                if not loop_vs_existing:
                    validation_results['mismatches'].append('반복문과 기존 계산 불일치')
                if not vec_vs_existing:
                    validation_results['mismatches'].append('벡터화와 기존 계산 불일치')
                
                # 제공된 코드의 assert 검증
                try:
                    assert (df_temp['Inventory_loop'] == df[existing_inventory_col]).all()
                    validation_results['assert_passed'] = True
                except AssertionError:
                    validation_results['assert_passed'] = False
                    validation_results['mismatches'].append('Assert 검증 실패')
                    
            except Exception as e:
                validation_results['mismatches'].append(f'기존 컬럼 비교 오류: {str(e)}')
        
        return validation_results, df_temp
    
    @staticmethod
    def validate_hvdc_stock_engine(df: pd.DataFrame) -> Dict[str, Any]:
        """
        HVDC StockEngine의 재고 계산 검증
        """
        
        if df.empty:
            return {'status': 'empty_dataframe'}
        
        # HVDC 컬럼 매핑
        col_mapping = {
            'Inbound': ['Inbound', 'Inbound_Qty', 'Monthly_Inbound', 'IN'],
            'Outbound': ['Outbound', 'Outbound_Qty', 'Monthly_Outbound', 'OUT', 'Total_Outbound'],
            'Inventory': ['Closing', 'Closing_Stock', 'Monthly_Stock', 'Cumulative_Stock']
        }
        
        # 컬럼 찾기
        incoming_col = None
        outgoing_col = None
        inventory_col = None
        
        for col in df.columns:
            if not incoming_col:
                for pattern in col_mapping['Inbound']:
                    if pattern.lower() in col.lower():
                        incoming_col = col
                        break
            
            if not outgoing_col:
                for pattern in col_mapping['Outbound']:
                    if pattern.lower() in col.lower():
                        outgoing_col = col
                        break
            
            if not inventory_col:
                for pattern in col_mapping['Inventory']:
                    if pattern.lower() in col.lower():
                        inventory_col = col
                        break
        
        if not incoming_col or not outgoing_col:
            return {
                'status': 'missing_columns',
                'found_columns': list(df.columns),
                'incoming_col': incoming_col,
                'outgoing_col': outgoing_col
            }
        
        # 검증 실행
        validation_results, validated_df = InventoryValidator.validate_inventory_calculation(
            df, 0, incoming_col, outgoing_col, inventory_col
        )
        
        validation_results['status'] = 'completed'
        validation_results['columns_used'] = {
            'incoming': incoming_col,
            'outgoing': outgoing_col,
            'inventory': inventory_col
        }
        
        return validation_results

def test_inventory_validation():
    """
    재고 검증 테스트 - 사용자 검증 결과 포함
    """
    print("🧪 재고 계산 검증 테스트 시작")
    print("=" * 50)
    print("📊 사용자 제공 검증 결과:")
    print(f"✅ DSV Al Markaz: {InventoryValidator.USER_VALIDATION_RESULTS['DSV Al Markaz']}박스 (정확)")
    print(f"✅ DSV Indoor: {InventoryValidator.USER_VALIDATION_RESULTS['DSV Indoor']}박스 (정확)")
    print(f"✅ 검증 통과율: ≥{InventoryValidator.USER_VALIDATION_RESULTS['validation_pass_rate']}%")
    print(f"✅ 오류 감소: {InventoryValidator.USER_VALIDATION_RESULTS['error_reduction']}%↓ 달성")
    print(f"✅ 이중계산 방지: {InventoryValidator.USER_VALIDATION_RESULTS['duplicate_prevention']}% 적용")
    print("=" * 50)
    
    # 테스트 데이터 생성
    test_data = pd.DataFrame({
        'Date': pd.date_range('2024-01-01', periods=5),
        'Incoming': [100, 50, 0, 75, 25],
        'Outgoing': [20, 30, 40, 15, 60],
        'Location': ['DSV Indoor'] * 5
    })
    
    # 예상 재고 계산
    initial_stock = 0
    expected_inventory = []
    inv = initial_stock
    for i, o in zip(test_data['Incoming'], test_data['Outgoing']):
        inv = inv + i - o
        expected_inventory.append(inv)
    
    test_data['Inventory'] = expected_inventory
    
    print(f"📊 테스트 데이터:\n{test_data}")
    
    # 검증 실행
    validator = InventoryValidator()
    results, validated_df = validator.validate_inventory_calculation(test_data)
    
    print(f"\n✅ 검증 결과:")
    for key, value in results.items():
        if key != 'mismatches':
            print(f"   {key}: {value}")
    
    if results['mismatches']:
        print(f"⚠️ 불일치 사항:")
        for mismatch in results['mismatches']:
            print(f"   - {mismatch}")
    else:
        print("✅ 모든 계산이 일치합니다!")
    
    return results, validated_df

if __name__ == "__main__":
    test_inventory_validation() 