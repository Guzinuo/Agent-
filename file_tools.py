from pathlib import Path
from typing import List, Dict, Any

from excel_tools import read_excel_preview, summarize_table_basic


def observe_single_file(file_path: str) -> Dict[str, Any]:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in [".xlsx", ".xls"]:
        preview = read_excel_preview(file_path)
        basic_summary = summarize_table_basic(file_path)
        return {
            "type": "excel_observation",
            "file_path": file_path,
            "preview": preview,
            "basic_summary": basic_summary,
        }

    if suffix in [".txt", ".md"]:
        content = path.read_text(encoding="utf-8")
        return {
            "type": "text_observation",
            "file_path": file_path,
            "content_preview": content[:2000],
        }

    return {
        "type": "unknown_file_observation",
        "file_path": file_path,
        "content_preview": "暂不支持该文件类型的自动观察"
    }


def observe_files(file_paths: List[str]) -> List[Dict[str, Any]]:
    results = []
    for file_path in file_paths:
        results.append(observe_single_file(file_path))
    return results