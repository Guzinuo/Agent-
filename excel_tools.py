import pandas as pd


def read_excel_preview(file_path: str, sample_rows: int = 8):
    df = pd.read_excel(file_path)

    preview = {
        "columns": df.columns.tolist(),
        "row_count": len(df),
        "sample_rows": df.head(sample_rows).fillna("").to_dict(orient="records"),
    }

    return preview


def summarize_table_basic(file_path: str):
    df = pd.read_excel(file_path)

    summary = {
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": df.columns.tolist(),
        "null_count_by_column": df.isnull().sum().to_dict(),
        "dtype_by_column": {col: str(dtype) for col, dtype in df.dtypes.items()},
    }

    return summary