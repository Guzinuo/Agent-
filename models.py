from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime

from database import Base


class AuditTask(Base):
    __tablename__ = "audit_tasks"

    id = Column(Integer, primary_key=True, index=True)
    parent_task_id = Column(Integer, nullable=True)

    user_input = Column(Text, nullable=False)
    file_path = Column(String, nullable=True)

    observations = Column(Text, nullable=False, default="[]")
    inspection_results = Column(Text, nullable=False, default="[]")
    risk_findings = Column(Text, nullable=False, default="[]")
    additional_findings = Column(Text, nullable=False, default="[]")
    final_result = Column(Text, nullable=False, default="{}")

    created_at = Column(DateTime, default=datetime.utcnow)
    project_id = Column(Integer, ForeignKey("audit_projects.id"), nullable=False, index=True)

class AuditProject(Base):
    __tablename__ = "audit_projects"

    id = Column(Integer, primary_key=True, index=True)
    audited_entity_name = Column(String(255), nullable=False)
    project_name = Column(String(255), nullable=False)
    audit_items = Column(Text, nullable=False)   # 先存 JSON 字符串
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditWorkpaper(Base):
    __tablename__ = "audit_workpapers"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("audit_projects.id"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("audit_tasks.id"), nullable=False, index=True)

    risk_issue_id = Column(String(100), nullable=True)
    risk_title = Column(String(255), nullable=False)

    docx_path = Column(Text, nullable=False)
    pdf_path = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)