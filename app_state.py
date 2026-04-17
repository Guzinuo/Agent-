from typing import TypedDict, List, Dict, Any


class AuditState(TypedDict):
    user_input: str
    file_paths: List[str]
    messages: List[str]

    material_types: List[str]
    observations: List[Dict[str, Any]]

    inspection_framework: List[Dict[str, Any]]
    issue_framework: List[Dict[str, Any]]

    inspection_results: List[Dict[str, Any]]
    risk_findings: List[Dict[str, Any]]
    additional_findings: List[Dict[str, Any]]

    draft_answer: str
    reflection: str
    next_action: str
    final_answer: Dict[str, Any]