from typing import Optional, List
from pydantic import BaseModel,Field


class ChatRequest(BaseModel):
    text: str
    file_paths: List[str]


class RerunRequest(BaseModel):
    text: Optional[str] = None
    file_paths: Optional[List[str]] = None

class CreateProjectRequest(BaseModel):
    audited_entity_name: str
    project_name: str
    audit_items: List[str]
    description: Optional[str] = ""


class ProjectResponse(BaseModel):
    project_id: int
    audited_entity_name: str
    project_name: str
    audit_items: List[str]
    description: Optional[str] = ""
    created_at: str