#!/usr/bin/env python3
"""
Location 정규화 테스트 스크립트
가이드에 따른 Location 컬럼 정규화 및 OUT 집계 검증
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# excel_reporter 모듈 import
from excel_reporter import (
    normalize_location_column,
    validate_location_consistency,
    create_test_out_transaction,
    generate_monthly_in_out_stock_report,
    test_location_normalization
)

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_test_data():
    """테스트용 트랜잭션 데이터 생성"""
    logger.info("📊 테스트 데이터 생성 중...")
    
    # 다양한 Location 형태로 테스트 데이터 생성
    test_data = {
        'Case_No': [
            'CASE001', 'CASE002', 'CASE003', 'CASE004', 'CASE005',
            'CASE006', 'CASE007', 'CASE008', 'CASE009', 'CASE010'
        ],
        'Date': [
            '2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05',
            '2024-01-06', '2024-01-07', '2024-01-08', '2024-01-09', '2024-01-10'
        ],
        'Location': [
            'DSV Indoor',      # 정상
            'DSV Indoor ',     # 뒤에 공백
            ' DSV Indoor',     # 앞에 공백
            'dsv indoor',      # 소문자
            'DSV OUTDOOR',     # 대문자
            'DSV Outdoor',     # 정상
            'DSV Al Markaz',   # 정상
            'DSV Al Markaz ',  # 뒤에 공백
            ' DSV Al Markaz',  # 앞에 공백
            'dsv al markaz'    # 소문자
        ],
        'TxType_Refined': [
            'IN', 'IN', 'IN', 'IN', 'IN',
            'IN', 'IN', 'IN', 'IN', 'IN'
        ],
        'Qty': [100, 150, 200, 120, 180, 90, 110, 130, 160, 140],
        'Source_File': ['HITACHI'] * 10,
        'Loc_From': ['SOURCE'] * 10,
        'Target_Warehouse': ['DSV Indoor', 'DSV Indoor', 'DSV Indoor', 'DSV Indoor', 'DSV Indoor',
                           'DSV Outdoor', 'DSV Outdoor', 'DSV Al Markaz', 'DSV Al Markaz', 'DSV Al Markaz']
    }
    
    df = pd.DataFrame(test_data)
    logger.info(f"✅ 테스트 데이터 생성 완료: {len(df)}건")
    logger.info(f"📊 원본 Location 목록: {sorted(df['Location'].unique())}")
    
    return df

def test_location_normalization_basic():
    """기본 Location 정규화 테스트"""
    logger.info("🧪 기본 Location 정규화 테스트 시작...")
    
    # 테스트 데이터 생성
    test_df = create_test_data()
    
    # 1. 원본 데이터 검증
    original_validation = validate_location_consistency(test_df)
    logger.info(f"📊 원본 검증 결과: {original_validation}")
    
    # 2. 정규화 적용
    normalized_df = normalize_location_column(test_df.copy())
    normalized_validation = validate_location_consistency(normalized_df)
    logger.info(f"📊 정규화 후 검증 결과: {normalized_validation}")
    
    # 3. 정규화 결과 확인
    original_locations = sorted(test_df['Location'].unique())
    normalized_locations = sorted(normalized_df['Location'].unique())
    
    logger.info(f"📊 원본 Location ({len(original_locations)}개): {original_locations}")
    logger.info(f"📊 정규화 Location ({len(normalized_locations)}개): {normalized_locations}")
    
    # 4. 중복 제거 확인
    if len(original_locations) > len(normalized_locations):
        logger.info("✅ 정규화로 중복 Location이 제거되었습니다.")
    else:
        logger.info("ℹ️ 중복 Location이 없었습니다.")
    
    return normalized_df

def test_out_transaction_creation():
    """OUT 트랜잭션 생성 테스트"""
    logger.info("🧪 OUT 트랜잭션 생성 테스트 시작...")
    
    # 정규화된 테스트 데이터
    test_df = test_location_normalization_basic()
    
    # 다양한 Location으로 OUT 트랜잭션 생성 테스트
    test_cases = [
        ('DSV Indoor', 40),
        ('dsv indoor', 50),  # 소문자
        (' DSV Indoor', 60),  # 앞에 공백
        ('DSV Indoor ', 70),  # 뒤에 공백
        ('DSV Outdoor', 80),
        ('DSV Al Markaz', 90)
    ]
    
    for warehouse, qty in test_cases:
        logger.info(f"🔄 OUT 트랜잭션 생성 테스트: '{warehouse}'에서 {qty}개")
        
        try:
            # OUT 트랜잭션 추가
            test_df_with_out = create_test_out_transaction(test_df, warehouse=warehouse, qty=qty)
            
            # OUT 트랜잭션 확인
            out_transactions = test_df_with_out[test_df_with_out['TxType_Refined'].isin(['TRANSFER_OUT', 'FINAL_OUT'])]
            
            if not out_transactions.empty:
                logger.info(f"✅ OUT 트랜잭션 생성 성공: {len(out_transactions)}건")
                for _, row in out_transactions.iterrows():
                    logger.info(f"   📍 {row['Location']}: {row['Qty']}개")
            else:
                logger.warning("⚠️ OUT 트랜잭션이 생성되지 않았습니다.")
                
        except Exception as e:
            logger.error(f"❌ OUT 트랜잭션 생성 실패: {e}")
    
    return test_df

def test_monthly_aggregation():
    """월별 집계 테스트"""
    logger.info("🧪 월별 집계 테스트 시작...")
    
    # 정규화된 테스트 데이터 생성
    test_df = test_location_normalization_basic()
    
    # OUT 트랜잭션 추가
    logger.info("🔄 OUT 트랜잭션 추가 중...")
    test_df_with_out = create_test_out_transaction(test_df, warehouse='DSV Indoor', qty=40)
    
    # 추가 OUT 트랜잭션 확인
    out_transactions = test_df_with_out[test_df_with_out['TxType_Refined'].isin(['TRANSFER_OUT', 'FINAL_OUT'])]
    logger.info(f"📊 추가된 OUT 트랜잭션: {len(out_transactions)}건")
    for _, row in out_transactions.iterrows():
        logger.info(f"   📍 {row['Location']}: {row['Qty']}개")
    
    try:
        # OUT 트랜잭션이 포함된 데이터로 월별 IN/OUT/재고 집계
        in_df, out_df, stock_df = generate_monthly_in_out_stock_report(test_df_with_out)
        
        logger.info("📊 집계 결과:")
        logger.info(f"   IN DataFrame: {in_df.shape}")
        logger.info(f"   OUT DataFrame: {out_df.shape}")
        logger.info(f"   Stock DataFrame: {stock_df.shape}")
        
        # OUT 데이터 상세 확인
        if not out_df.empty and '알림' not in out_df.columns:
            logger.info("📊 OUT 집계 상세:")
            logger.info(f"   컬럼: {list(out_df.columns)}")
            
            # 각 Location별 OUT 합계
            for col in out_df.columns:
                if col != '월':
                    col_sum = out_df[col].sum()
                    if col_sum > 0:
                        logger.info(f"   📍 {col}: {col_sum}개")
                    else:
                        logger.info(f"   📍 {col}: 0개")
            
            # 전체 OUT 합계
            total_out = out_df.iloc[:, 1:].sum().sum()
            logger.info(f"   📊 총 OUT: {total_out}개")
            
        else:
            logger.warning("⚠️ OUT 데이터가 없거나 오류가 있습니다.")
            
        # 엑셀 파일 저장
        output_file = f"test_location_normalization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        in_df, out_df, stock_df = generate_monthly_in_out_stock_report(test_df_with_out, output_file)
        logger.info(f"✅ 테스트 결과 저장: {output_file}")
        
    except Exception as e:
        logger.error(f"❌ 월별 집계 테스트 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())

def main():
    """메인 테스트 실행"""
    logger.info("🚀 Location 정규화 종합 테스트 시작")
    logger.info("=" * 80)
    
    try:
        # 1. 기본 정규화 테스트
        test_location_normalization_basic()
        logger.info("-" * 40)
        
        # 2. OUT 트랜잭션 생성 테스트
        test_out_transaction_creation()
        logger.info("-" * 40)
        
        # 3. 월별 집계 테스트
        test_monthly_aggregation()
        logger.info("-" * 40)
        
        logger.info("✅ 모든 테스트 완료")
        
    except Exception as e:
        logger.error(f"❌ 테스트 실행 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main() 