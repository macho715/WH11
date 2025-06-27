import mapping_utils

def apply_all_preprocessing(df):
    # 표준화
    df = mapping_utils.normalize_all_keys(df)
    # Storage_Type 추가
    if 'Location' in df.columns:
        df = mapping_utils.add_storage_type_to_dataframe(df, "Location")
    return df

# dataframe_to_rdf 함수 내 DataFrame 변환 직후 아래 줄 추가
# df = apply_all_preprocessing(df) 