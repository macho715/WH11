#!/usr/bin/env python3
"""
HITACHI 파일 단독 집계 검증 스크립트 (간단 버전)
목표: 총 수량 5,347개 기준으로 파이프라인 검증
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

# 프로젝트 루트 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def validate_hitachi_simple():
    """
    HITACHI 파일 단독 집계 및 5,347개 기준 검증 (간단 버전)
    """
    print("🔍 HITACHI 파일 단독 집계 검증 시작")
    print("목표: 총 수량 5,347개 기준 검증")
    print("=" * 60)
    
    # 1. 원본 엑셀 파일 직접 검증
    print("📊 1단계: 원본 엑셀 파일 직접 검증")
    try:
        df_hitachi = pd.read_excel('data/HVDC WAREHOUSE_HITACHI(HE).xlsx')
        print(f"   📋 원본 파일 로드: {len(df_hitachi)}행")
        
        # Pkg 컬럼 존재 확인
        if 'Pkg' in df_hitachi.columns:
            total_pkg = df_hitachi['Pkg'].sum()
            print(f"   📦 원본 Pkg 총합: {total_pkg:,}개")
            
            # 5,347개 기준 검증
            target_qty = 5347
            if total_pkg == target_qty:
                print(f"   ✅ 원본 검증 성공: {total_pkg:,}개 = 목표 {target_qty:,}개")
            else:
                print(f"   ❌ 원본 검증 실패: {total_pkg:,}개 ≠ 목표 {target_qty:,}개")
                print(f"   📊 차이: {abs(total_pkg - target_qty):,}개")
        else:
            print("   ⚠️ Pkg 컬럼 없음")
            
        # HVDC CODE 컬럼 확인
        if 'HVDC CODE' in df_hitachi.columns:
            unique_cases = df_hitachi['HVDC CODE'].nunique()
            print(f"   📦 고유 케이스 수: {unique_cases:,}개")
        else:
            print("   ⚠️ HVDC CODE 컬럼 없음")
            
        # 창고별 날짜 컬럼 확인
        warehouse_cols = [col for col in df_hitachi.columns if any(warehouse in str(col) for warehouse in 
                        ['DSV Indoor', 'DSV Al Markaz', 'DSV Outdoor', 'Hauler Indoor', 'MOSB', 'MIR', 'SHU', 'DAS', 'AGI'])]
        print(f"   🏢 창고별 날짜 컬럼: {len(warehouse_cols)}개")
        for col in warehouse_cols:
            non_null_count = df_hitachi[col].notna().sum()
            print(f"      {col}: {non_null_count}건")
            
    except Exception as e:
        print(f"   ❌ 원본 파일 로드 실패: {e}")
        return False
    
    # 2. 기존 파이프라인으로 검증
    print("\n🔄 2단계: 기존 파이프라인 검증")
    try:
        # 기존 test_excel_reporter.py 방식으로 HITACHI만 실행
        from core.loader import DataLoader
        from core.transaction_converter import TransactionConverter
        from core.deduplication import DeduplicationEngine
        
        # DataLoader 초기화
        loader = DataLoader()
        
        # HITACHI 파일만 로드
        hitachi_files = ['data/HVDC WAREHOUSE_HITACHI(HE).xlsx']
        transactions = loader.load_data(hitachi_files)
        
        print(f"   📊 파이프라인 트랜잭션 추출: {len(transactions):,}건")
        
        # 트랜잭션 변환
        converter = TransactionConverter()
        converted_txs = converter.convert_transactions(transactions)
        
        print(f"   🔄 변환된 트랜잭션: {len(converted_txs):,}건")
        
        # 중복 제거
        dedup_engine = DeduplicationEngine()
        dedup_txs = dedup_engine.remove_duplicates(converted_txs)
        
        print(f"   🧹 중복 제거 후: {len(dedup_txs):,}건")
        
        # 총 수량 계산
        total_qty = sum(tx['incoming'] - tx['outgoing'] for tx in dedup_txs)
        print(f"   📦 파이프라인 총 수량: {total_qty:,}개")
        
        # 5,347개 기준 검증
        target_qty = 5347
        if total_qty == target_qty:
            print(f"   ✅ 파이프라인 검증 성공: {total_qty:,}개 = 목표 {target_qty:,}개")
        else:
            print(f"   ❌ 파이프라인 검증 실패: {total_qty:,}개 ≠ 목표 {target_qty:,}개")
            print(f"   📊 차이: {abs(total_qty - target_qty):,}개")
            
        return total_qty == target_qty
        
    except Exception as e:
        print(f"   ❌ 파이프라인 검증 실패: {e}")
        return False
    
    # 3. 상세 분석
    print("\n📋 3단계: 상세 분석")
    try:
        # 창고별 분포
        warehouse_dist = {}
        for tx in converted_txs:
            warehouse = tx['warehouse']
            qty = tx['incoming'] - tx['outgoing']
            warehouse_dist[warehouse] = warehouse_dist.get(warehouse, 0) + qty
        
        print("   🏢 창고별 분포:")
        for warehouse, qty in sorted(warehouse_dist.items(), key=lambda x: x[1], reverse=True):
            print(f"      {warehouse}: {qty:,}개")
            
        # 트랜잭션 타입별 분포
        tx_types = {}
        for tx in converted_txs:
            tx_type = "IN" if tx['incoming'] > 0 else "OUT" if tx['outgoing'] > 0 else "TRANSFER"
            tx_types[tx_type] = tx_types.get(tx_type, 0) + 1
            
        print("   🔄 트랜잭션 타입별 분포:")
        for tx_type, count in tx_types.items():
            print(f"      {tx_type}: {count:,}건")
            
    except Exception as e:
        print(f"   ❌ 상세 분석 실패: {e}")

def print_final_summary():
    """
    최종 요약 출력
    """
    print("\n📊 최종 재고 요약")
    print("=" * 60)
    
    try:
        # 원본 파일에서 직접 계산
        df_hitachi = pd.read_excel('data/HVDC WAREHOUSE_HITACHI(HE).xlsx')
        total_pkg = df_hitachi['Pkg'].sum()
        
        print(f"📦 총 재고: {total_pkg:,} EA")
        print(f"📅 계산 기준일: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 데이터 소스: HVDC WAREHOUSE_HITACHI(HE).xlsx")
        
        if total_pkg == 5347:
            print("✅ 목표 수량(5,347개) 달성")
        else:
            print(f"⚠️ 목표 수량과 차이: {abs(total_pkg - 5347):,}개")
            
    except Exception as e:
        print(f"❌ 최종 요약 생성 실패: {e}")

if __name__ == "__main__":
    # 검증 실행
    success = validate_hitachi_simple()
    
    # 최종 요약 출력
    print_final_summary()
    
    if success:
        print("\n✅ HITACHI 재고 검증 완료 - 목표 달성")
    else:
        print("\n❌ HITACHI 재고 검증 실패 - 추가 분석 필요")
    
    print("=" * 60) 