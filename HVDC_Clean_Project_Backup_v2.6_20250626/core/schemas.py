#!/usr/bin/env python3
"""
HVDC Warehouse Management System - 데이터 검증 스키마
Pydantic 모델을 사용한 입력 데이터 검증
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import pandas as pd

class StorageType(str, Enum):
    """Storage Type 열거형"""
    INDOOR = "Indoor"
    OUTDOOR = "Outdoor"
    SITE = "Site"
    DANGEROUS_CARGO = "dangerous_cargo"
    UNKNOWN = "Unknown"

class TransactionType(str, Enum):
    """트랜잭션 타입 열거형"""
    IN = "IN"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    FINAL_OUT = "FINAL_OUT"

class TransactionData(BaseModel):
    """트랜잭션 데이터 모델"""
    case: str = Field(..., description="케이스 ID")
    date: datetime = Field(..., description="트랜잭션 날짜")
    warehouse: str = Field(..., description="창고/현장명")
    incoming: int = Field(default=0, ge=0, description="입고 수량")
    outgoing: int = Field(default=0, ge=0, description="출고 수량")
    inventory: Optional[int] = Field(default=None, ge=0, description="재고 수량")
    storage_type: Optional[StorageType] = Field(default=None, description="Storage Type")
    
    @validator('incoming', 'outgoing')
    def validate_quantities(cls, v):
        """수량 검증"""
        if v < 0:
            raise ValueError("수량은 0 이상이어야 합니다")
        if v > 10000:
            raise ValueError("수량은 10,000을 초과할 수 없습니다")
        return v
    
    @validator('date')
    def validate_date(cls, v):
        """날짜 검증"""
        if v > datetime.now():
            raise ValueError("미래 날짜는 허용되지 않습니다")
        return v

class TransactionRecord(BaseModel):
    """트랜잭션 레코드 모델"""
    source_file: str = Field(..., description="소스 파일명")
    timestamp: datetime = Field(default_factory=datetime.now, description="처리 타임스탬프")
    data: TransactionData = Field(..., description="트랜잭션 데이터")

class WarehouseLocation(BaseModel):
    """창고 위치 모델"""
    name: str = Field(..., description="창고명")
    storage_type: StorageType = Field(..., description="Storage Type")
    is_active: bool = Field(default=True, description="활성 상태")
    
    @validator('name')
    def validate_name(cls, v):
        """창고명 검증"""
        if not v or v.strip() == "":
            raise ValueError("창고명은 비어있을 수 없습니다")
        return v.strip()

class ExpectedStock(BaseModel):
    """기대 재고 모델"""
    date: str = Field(..., description="날짜 (YYYY-MM-DD)")
    warehouse: str = Field(..., description="창고명")
    expected_quantity: int = Field(..., ge=0, description="기대 수량")
    tolerance: float = Field(default=2.0, ge=0, le=100, description="허용 오차 (%)")
    
    @validator('date')
    def validate_date_format(cls, v):
        """날짜 형식 검증"""
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError("날짜는 YYYY-MM-DD 형식이어야 합니다")

class InventorySnapshot(BaseModel):
    """재고 스냅샷 모델"""
    date: datetime = Field(..., description="스냅샷 날짜")
    location: str = Field(..., description="위치")
    inventory: int = Field(..., ge=0, description="재고 수량")
    transaction_type: Optional[TransactionType] = Field(default=None, description="트랜잭션 타입")
    qty: Optional[int] = Field(default=None, ge=0, description="수량")
    
    @validator('inventory')
    def validate_inventory(cls, v):
        """재고 검증"""
        if v < 0:
            raise ValueError("재고는 0 이상이어야 합니다")
        return v

class MappingRule(BaseModel):
    """매핑 규칙 모델"""
    storage_type: StorageType = Field(..., description="Storage Type")
    locations: List[str] = Field(..., description="위치 목록")
    
    @validator('locations')
    def validate_locations(cls, v):
        """위치 목록 검증"""
        if not v:
            raise ValueError("위치 목록은 비어있을 수 없습니다")
        return [loc.strip() for loc in v if loc.strip()]

class ValidationResult(BaseModel):
    """검증 결과 모델"""
    is_valid: bool = Field(..., description="검증 통과 여부")
    errors: List[str] = Field(default_factory=list, description="오류 목록")
    warnings: List[str] = Field(default_factory=list, description="경고 목록")
    summary: Dict[str, Any] = Field(default_factory=dict, description="검증 요약")

class ProcessingConfig(BaseModel):
    """처리 설정 모델"""
    enable_deduplication: bool = Field(default=True, description="중복 제거 활성화")
    enable_transfer_reconciliation: bool = Field(default=True, description="TRANSFER 짝 보정 활성화")
    enable_validation: bool = Field(default=True, description="검증 활성화")
    tolerance_percentage: float = Field(default=2.0, ge=0, le=100, description="허용 오차 (%)")
    max_processing_time: int = Field(default=300, ge=1, description="최대 처리 시간 (초)")

def validate_transaction_dataframe(df: pd.DataFrame) -> ValidationResult:
    """
    트랜잭션 DataFrame 검증
    
    Args:
        df: 검증할 DataFrame
        
    Returns:
        ValidationResult: 검증 결과
    """
    errors = []
    warnings = []
    
    # 필수 컬럼 확인
    required_columns = ['Case_No', 'Date', 'Qty', 'TxType_Refined', 'Location']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        errors.append(f"필수 컬럼 누락: {missing_columns}")
    
    # 데이터 타입 검증
    if 'Date' in df.columns:
        try:
            pd.to_datetime(df['Date'])
        except Exception as e:
            errors.append(f"날짜 컬럼 형식 오류: {e}")
    
    if 'Qty' in df.columns:
        try:
            pd.to_numeric(df['Qty'], errors='coerce')
            if df['Qty'].isna().any():
                warnings.append("수량 컬럼에 NaN 값이 있습니다")
        except Exception as e:
            errors.append(f"수량 컬럼 형식 오류: {e}")
    
    # 트랜잭션 타입 검증
    if 'TxType_Refined' in df.columns:
        valid_types = [t.value for t in TransactionType]
        invalid_types = df[~df['TxType_Refined'].isin(valid_types)]['TxType_Refined'].unique()
        if len(invalid_types) > 0:
            warnings.append(f"알 수 없는 트랜잭션 타입: {invalid_types}")
    
    # 중복 검사
    if len(df) != len(df.drop_duplicates()):
        duplicate_count = len(df) - len(df.drop_duplicates())
        warnings.append(f"중복 레코드 {duplicate_count}건 발견")
    
    is_valid = len(errors) == 0
    
    return ValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        summary={
            "total_records": len(df),
            "unique_cases": df['Case_No'].nunique() if 'Case_No' in df.columns else 0,
            "unique_locations": df['Location'].nunique() if 'Location' in df.columns else 0,
            "date_range": {
                "start": df['Date'].min() if 'Date' in df.columns else None,
                "end": df['Date'].max() if 'Date' in df.columns else None
            }
        }
    )

def validate_expected_stock_data(data: Dict[str, Any]) -> ValidationResult:
    """
    기대 재고 데이터 검증
    
    Args:
        data: 검증할 데이터
        
    Returns:
        ValidationResult: 검증 결과
    """
    errors = []
    warnings = []
    
    try:
        # expected 섹션 확인
        if 'expected' not in data:
            errors.append("'expected' 섹션이 없습니다")
            return ValidationResult(is_valid=False, errors=errors)
        
        expected_data = data['expected']
        
        for date_str, warehouses in expected_data.items():
            # 날짜 형식 검증
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                errors.append(f"잘못된 날짜 형식: {date_str}")
            
            # 창고별 수량 검증
            if isinstance(warehouses, dict):
                for warehouse, quantity in warehouses.items():
                    if not isinstance(quantity, (int, float)) or quantity < 0:
                        errors.append(f"잘못된 수량: {warehouse} = {quantity}")
            else:
                errors.append(f"잘못된 창고 데이터 형식: {date_str}")
        
        # tolerance 섹션 확인
        if 'tolerance' in data:
            tolerance = data['tolerance']
            if not isinstance(tolerance, dict):
                errors.append("tolerance는 딕셔너리여야 합니다")
        
    except Exception as e:
        errors.append(f"데이터 검증 중 오류: {e}")
    
    is_valid = len(errors) == 0
    
    return ValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        summary={
            "total_dates": len(expected_data) if 'expected' in data else 0,
            "total_warehouses": sum(len(w) for w in expected_data.values()) if 'expected' in data else 0
        }
    )

# 편의 함수들
def create_transaction_from_dict(data: Dict[str, Any]) -> TransactionRecord:
    """딕셔너리에서 트랜잭션 레코드 생성"""
    return TransactionRecord(**data)

def create_warehouse_from_dict(data: Dict[str, Any]) -> WarehouseLocation:
    """딕셔너리에서 창고 위치 생성"""
    return WarehouseLocation(**data)

def create_expected_stock_from_dict(data: Dict[str, Any]) -> ExpectedStock:
    """딕셔너리에서 기대 재고 생성"""
    return ExpectedStock(**data) 