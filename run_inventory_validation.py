# run_inventory_validation.py
"""
GitHub Action용 재고 검증 실행 스크립트
회귀 방지 및 지속적 검증을 위한 자동화 스크립트
"""

import sys
import traceback
from test_inventory_assertions import test_inventory_calculations

def main():
    """메인 실행 함수"""
    print("🚀 GitHub Action - 재고 검증 파이프라인 실행")
    print("=" * 60)
    
    try:
        # Unit Test 실행
        stock_results = test_inventory_calculations()
        
        # 검증 결과 확인
        required_warehouses = ["DSV Al Markaz", "DSV Indoor"]
        missing_warehouses = [wh for wh in required_warehouses if wh not in stock_results]
        
        if missing_warehouses:
            print(f"❌ 누락된 창고: {missing_warehouses}")
            sys.exit(1)
        
        # 최소 재고 검증 (음수 재고 방지)
        negative_stocks = {wh: stock for wh, stock in stock_results.items() if stock < 0}
        if negative_stocks:
            print(f"❌ 음수 재고 발견: {negative_stocks}")
            # Shifting 창고는 예외 허용 (임시 음수 가능)
            if any(wh != 'Shifting' for wh in negative_stocks.keys()):
                sys.exit(1)
        
        print("\n✅ 모든 검증 통과!")
        print("✅ GitHub Action 성공!")
        return 0
        
    except Exception as e:
        print(f"❌ 검증 실패: {str(e)}")
        print("❌ 스택 트레이스:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 