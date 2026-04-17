import json
import shutil
import uuid
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app_graph import graph
from database import SessionLocal, engine, Base
from models import AuditTask, AuditProject,AuditWorkpaper
from schemas import ChatRequest, RerunRequest, CreateProjectRequest
from fastapi.responses import FileResponse
from services.workpaper_generator import generate_workpapers_for_task

Base.metadata.create_all(bind=engine)
BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates" / "audit_workpaper_template.docx"
WORKPAPER_DIR = BASE_DIR / "generated_workpapers"
WORKPAPER_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Audit Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
WORKPAPER_DIR = BASE_DIR / "generated_workpapers"
WORKPAPER_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/")
def root():
    return {"message": "audit agent is running"}


@app.get("/health")
def health():
    return {"ok": True}
def save_uploaded_file(upload_file: UploadFile) -> str:
    original_name = Path(upload_file.filename or "uploaded_file").name
    unique_name = f"{uuid.uuid4().hex}_{original_name}"
    save_path = UPLOAD_DIR / unique_name

    with save_path.open("wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)

    return str(save_path)
def parse_file_paths(raw_value: str | None) -> List[str]:
    if not raw_value:
        return []

    try:
        value = json.loads(raw_value)
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [value]
        return []
    except Exception:
        return [raw_value]


def parse_json_list(raw_value: str | None) -> List[str]:
    if not raw_value:
        return []

    try:
        value = json.loads(raw_value)
        return value if isinstance(value, list) else []
    except Exception:
        return []


@app.post("/upload")
def upload_files(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="no files uploaded")

    saved_paths = []
    for file in files:
        saved_paths.append(save_uploaded_file(file))

    return {
        "file_paths": saved_paths
    }
@app.post("/projects")
def create_project(req: CreateProjectRequest):
    db: Session = SessionLocal()
    try:
        project = AuditProject(
            audited_entity_name=req.audited_entity_name,
            project_name=req.project_name,
            audit_items=json.dumps(req.audit_items, ensure_ascii=False),
            description=req.description or "",
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        return {
            "project_id": project.id,
            "audited_entity_name": project.audited_entity_name,
            "project_name": project.project_name,
            "audit_items": req.audit_items,
            "description": project.description or "",
            "created_at": project.created_at.isoformat(),
        }
    finally:
        db.close()


@app.get("/projects")
def list_projects():
    db: Session = SessionLocal()
    try:
        projects = db.query(AuditProject).order_by(AuditProject.created_at.desc()).all()
        return [
            {
                "project_id": p.id,
                "audited_entity_name": p.audited_entity_name,
                "project_name": p.project_name,
                "audit_items": parse_json_list(p.audit_items),
                "description": p.description or "",
                "created_at": p.created_at.isoformat(),
            }
            for p in projects
        ]
    finally:
        db.close()


@app.get("/projects/{project_id}")
def get_project(project_id: int):
    db: Session = SessionLocal()
    try:
        project = db.query(AuditProject).filter(AuditProject.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="project not found")

        tasks = (
            db.query(AuditTask)
            .filter(AuditTask.project_id == project_id)
            .order_by(AuditTask.created_at.desc())
            .all()
        )

        return {
            "project_id": project.id,
            "audited_entity_name": project.audited_entity_name,
            "project_name": project.project_name,
            "audit_items": parse_json_list(project.audit_items),
            "description": project.description or "",
            "created_at": project.created_at.isoformat(),
            "tasks": [
                {
                    "task_id": t.id,
                    "parent_task_id": t.parent_task_id,
                    "created_at": t.created_at.isoformat(),
                }
                for t in tasks
            ],
        }
    finally:
        db.close()

@app.post("/projects/{project_id}/chat")
def project_chat(project_id: int, req: ChatRequest):
    db: Session = SessionLocal()
    try:
        project = db.query(AuditProject).filter(AuditProject.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="project not found")

        result = graph.invoke({
            "user_input": req.text,
            "file_paths": req.file_paths,
            "messages": [],
            "material_types": [],
            "observations": [],
            "inspection_framework": [],
            "issue_framework": [],
            "inspection_results": [],
            "risk_findings": [],
            "additional_findings": [],
            "draft_answer": "",
            "reflection": "",
            "next_action": "",
            "final_answer": {},
        })

        task = AuditTask(
            project_id=project.id,
            parent_task_id=None,
            user_input=result["user_input"],
            file_path=json.dumps(req.file_paths, ensure_ascii=False),
            observations=json.dumps(result["observations"], ensure_ascii=False),
            inspection_results=json.dumps(result["inspection_results"], ensure_ascii=False),
            risk_findings=json.dumps(result["risk_findings"], ensure_ascii=False),
            additional_findings=json.dumps(result["additional_findings"], ensure_ascii=False),
            final_result=json.dumps(result["final_answer"], ensure_ascii=False),
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        project = db.query(AuditProject).filter(AuditProject.id == project_id).first()

        final_answer = result["final_answer"]

        print("project_chat final_answer type before normalize:", type(final_answer))

        if isinstance(final_answer, str):
            final_answer = json.loads(final_answer)

        print("project_chat final_answer type after normalize:", type(final_answer))

        workpapers = generate_workpapers_for_task(
            db=db,
            project=project,
            task=task,
            final_result=final_answer,
            template_path=TEMPLATE_PATH,
            output_root=WORKPAPER_DIR,
        )

        db.commit()

        return {
            "project_id": project.id,
            "task_id": task.id,
            "parent_task_id": task.parent_task_id,
            "user_input": result["user_input"],
            "file_paths": req.file_paths,
            "messages": result["messages"],
            "observations": result["observations"],
            "inspection_results": result["inspection_results"],
            "risk_findings": result["risk_findings"],
            "additional_findings": result["additional_findings"],
            "final_result": result["final_answer"],
            "workpapers": workpapers,
        }
    finally:
        db.close()

@app.post("/chat")
def chat(req: ChatRequest):
    result = graph.invoke({
        "user_input": req.text,
        "file_paths": req.file_paths,
        "messages": [],
        "material_types": [],
        "observations": [],
        "inspection_framework": [],
        "issue_framework": [],
        "inspection_results": [],
        "risk_findings": [],
        "additional_findings": [],
        "draft_answer": "",
        "reflection": "",
        "next_action": "",
        "final_answer": {},
    })

    db: Session = SessionLocal()
    try:
        task = AuditTask(
            parent_task_id=None,
            user_input=result["user_input"],
            file_path=json.dumps(req.file_paths, ensure_ascii=False),
            observations=json.dumps(result["observations"], ensure_ascii=False),
            inspection_results=json.dumps(result["inspection_results"], ensure_ascii=False),
            risk_findings=json.dumps(result["risk_findings"], ensure_ascii=False),
            additional_findings=json.dumps(result["additional_findings"], ensure_ascii=False),
            final_result=json.dumps(result["final_answer"], ensure_ascii=False),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
    finally:
        db.close()

    return {
        "task_id": task.id,
        "parent_task_id": task.parent_task_id,
        "user_input": result["user_input"],
        "file_paths": req.file_paths,
        "messages": result["messages"],
        "observations": result["observations"],
        "inspection_results": result["inspection_results"],
        "risk_findings": result["risk_findings"],
        "additional_findings": result["additional_findings"],
        "final_result": result["final_answer"],
    }


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    db: Session = SessionLocal()
    try:
        task = db.query(AuditTask).filter(AuditTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="task not found")

        workpapers = (
            db.query(AuditWorkpaper)
            .filter(AuditWorkpaper.task_id == task.id)
            .order_by(AuditWorkpaper.created_at.asc())
            .all()
        )

        return {
            "task_id": task.id,
            "project_id": task.project_id,
            "parent_task_id": task.parent_task_id,
            "user_input": task.user_input,
            "file_paths": json.loads(task.file_path) if task.file_path else [],
            "observations": json.loads(task.observations),
            "inspection_results": json.loads(task.inspection_results),
            "risk_findings": json.loads(task.risk_findings),
            "additional_findings": json.loads(task.additional_findings),
            "final_result": json.loads(task.final_result),
            "workpapers": [
                {
                    "workpaper_id": wp.id,
                    "risk_title": wp.risk_title,
                    "filename": Path(wp.pdf_path).name,
                    "download_url": f"/workpapers/{wp.id}/download",
                }
                for wp in workpapers
            ],
            "created_at": task.created_at.isoformat(),
        }
    finally:
        db.close()


@app.post("/tasks/{task_id}/rerun")
def rerun_task(task_id: int, req: RerunRequest):
    db: Session = SessionLocal()
    try:
        old_task = db.query(AuditTask).filter(AuditTask.id == task_id).first()
        if not old_task:
            raise HTTPException(status_code=404, detail="task not found")

        old_file_paths = json.loads(old_task.file_path) if old_task.file_path else []

        new_text = req.text.strip() if req.text else old_task.user_input

        weak_rerun_keywords = ["复查", "继续", "重新", "再看", "补充资料", "补充材料"]

        if req.text:
            req_text = req.text.strip()
            if any(k in req_text for k in weak_rerun_keywords):
                new_text = f"{old_task.user_input}。补充材料复查：{req_text}"
        new_file_paths = req.file_paths if req.file_paths else old_file_paths

        result = graph.invoke({
            "user_input": new_text,
            "file_paths": new_file_paths,
            "messages": [],
            "material_types": [],
            "observations": [],
            "inspection_framework": [],
            "issue_framework": [],
            "inspection_results": [],
            "risk_findings": [],
            "additional_findings": [],
            "draft_answer": "",
            "reflection": "",
            "next_action": "",
            "final_answer": {},
        })

        new_task = AuditTask(
            project_id=old_task.project_id,
            parent_task_id=old_task.id,
            user_input=result["user_input"],
            file_path=json.dumps(new_file_paths, ensure_ascii=False),
            observations=json.dumps(result["observations"], ensure_ascii=False),
            inspection_results=json.dumps(result["inspection_results"], ensure_ascii=False),
            risk_findings=json.dumps(result["risk_findings"], ensure_ascii=False),
            additional_findings=json.dumps(result["additional_findings"], ensure_ascii=False),
            final_result=json.dumps(result["final_answer"], ensure_ascii=False),
        )

        db.add(new_task)
        db.commit()
        db.refresh(new_task)

        project = db.query(AuditProject).filter(AuditProject.id == old_task.project_id).first()

        final_answer = result["final_answer"]

        print("rerun final_answer type before normalize:", type(final_answer))

        if isinstance(final_answer, str):
            final_answer = json.loads(final_answer)

        print("rerun final_answer type after normalize:", type(final_answer))

        workpapers = generate_workpapers_for_task(
            db=db,
            project=project,
            task=new_task,
            final_result=final_answer,
            template_path=TEMPLATE_PATH,
            output_root=WORKPAPER_DIR,
        )
        db.commit()

        return {
            "task_id": new_task.id,
            "project_id": new_task.project_id,
            "parent_task_id": new_task.parent_task_id,
            "user_input": result["user_input"],
            "file_paths": new_file_paths,
            "messages": result["messages"],
            "observations": result["observations"],
            "inspection_results": result["inspection_results"],
            "risk_findings": result["risk_findings"],
            "additional_findings": result["additional_findings"],
            "final_result": result["final_answer"],
            "workpapers": workpapers,
        }
    finally:
        db.close()

@app.get("/workpapers/{workpaper_id}/download")
def download_workpaper(workpaper_id: int):
    db: Session = SessionLocal()
    try:
        wp = db.query(AuditWorkpaper).filter(AuditWorkpaper.id == workpaper_id).first()
        if not wp:
            raise HTTPException(status_code=404, detail="workpaper not found")

        return FileResponse(
            path=wp.pdf_path,
            filename=Path(wp.pdf_path).name,
            media_type="application/pdf",
        )
    finally:
        db.close()


@app.get("/workpapers/{workpaper_id}/download-docx")
def download_workpaper_docx(workpaper_id: int):
    db: Session = SessionLocal()
    try:
        wp = db.query(AuditWorkpaper).filter(AuditWorkpaper.id == workpaper_id).first()
        if not wp:
            raise HTTPException(status_code=404, detail="workpaper not found")

        return FileResponse(
            path=wp.docx_path,
            filename=Path(wp.docx_path).name,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    finally:
        db.close()