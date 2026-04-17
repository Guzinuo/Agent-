from docxtpl import DocxTemplate
from docx2pdf import convert
from models import AuditWorkpaper
from pathlib import Path

def sanitize_filename(name: str) -> str:
    bad = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
    for ch in bad:
        name = name.replace(ch, "_")
    return name.strip()
def build_workpaper_context(project, task, risk):
    evidence = risk.get("evidence", []) or []
    actions = risk.get("suggested_actions", []) or []

    fact_lines = []
    if risk.get("description"):
        fact_lines.append(f"风险描述：{risk['description']}")
    if evidence:
        fact_lines.append("核查证据：")
        fact_lines.extend([f"- {item}" for item in evidence])

    resolution_status = risk.get("resolution_status", "open")
    if resolution_status == "open":
        conclusion = "已识别异常迹象，尚待进一步获取资料核查。"
    elif resolution_status == "partially_explained":
        conclusion = "事项已获得初步业务解释，但仍需补充关键资料完成闭环核查。"
    elif resolution_status == "pending_closure":
        conclusion = "主要事项已解释，待补充关键凭证后完成闭环。"
    else:
        conclusion = "当前证据不足，建议继续核查。"

    attachment_names = []
    for item in evidence:
        left = item.split("：")[0] if "：" in item else item
        attachment_names.append(left)

    attachment_names = list(dict.fromkeys(attachment_names))

    return {
        "audited_entity_name": project.audited_entity_name,
        "project_name": project.project_name,
        "audit_item": risk.get("title", ""),
        "fact_desc": "\n".join(fact_lines) if fact_lines else "暂无可填充事实。",
        "audit_conclusion": conclusion,
        "issue_characterization": risk.get("title", ""),
        "audit_basis": "依据已获取的交易流水、合同资料、审批资料及补充说明材料进行初步审计核查。",
        "suggestions": "\n".join([f"- {a}" for a in actions]) if actions else "建议继续补充相关资料并实施进一步核查。",
        "entity_opinion": "待被审计单位书面反馈。",
        "attachments": "、".join(attachment_names) if attachment_names else "相关制度复印件",
        "compiler": "审计智能体（初稿）",
        "reviewer": "",
    }



def render_docx(template_path: str, output_path: str, context: dict):
    tpl = DocxTemplate(template_path)
    tpl.render(context)
    tpl.save(output_path)

def convert_to_pdf(docx_path: str, pdf_path: str):
    docx_file = Path(docx_path)
    pdf_file = Path(pdf_path)

    output_dir = pdf_file.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # docx2pdf 在 Windows 上更稳的是传“输出目录”
    convert(str(docx_file), str(output_dir))

    generated_pdf = output_dir / f"{docx_file.stem}.pdf"
    if not generated_pdf.exists():
        raise RuntimeError(f"PDF conversion failed, file not found: {generated_pdf}")

    # 如果目标文件名和默认生成名不同，就重命名
    if generated_pdf.resolve() != pdf_file.resolve():
        if pdf_file.exists():
            pdf_file.unlink()
        generated_pdf.rename(pdf_file)

def generate_workpapers_for_task(db, project, task, final_result, template_path, output_root):
    risk_findings = final_result.get("risk_findings", []) or []
    additional_findings = final_result.get("additional_findings", []) or []

    all_risks = risk_findings + additional_findings
    generated = []

    task_dir = output_root / f"project_{project.id}" / f"task_{task.id}"
    task_dir.mkdir(parents=True, exist_ok=True)

    for idx, risk in enumerate(all_risks, start=1):
        risk_title = risk.get("title", f"风险事项{idx}")
        safe_title = sanitize_filename(risk_title)
        safe_project = sanitize_filename(project.project_name)

        base_name = f"{safe_project}_task{task.id}_{safe_title}"
        docx_path = task_dir / f"{base_name}.docx"
        pdf_path = task_dir / f"{base_name}.pdf"

        context = build_workpaper_context(project, task, risk)
        render_docx(str(template_path), str(docx_path), context)

        pdf_generated = True
        pdf_error = None

        try:
            convert_to_pdf(str(docx_path), str(pdf_path))
        except Exception as e:
            pdf_generated = False
            pdf_error = str(e)

        wp = AuditWorkpaper(
            project_id=project.id,
            task_id=task.id,
            risk_issue_id=risk.get("issue_id"),
            risk_title=risk_title,
            docx_path=str(docx_path),
            pdf_path=str(pdf_path),
        )
        db.add(wp)
        db.flush()

        generated.append({
            "workpaper_id": wp.id,
            "risk_title": risk_title,
            "docx_path": str(docx_path),
            "pdf_path": str(pdf_path) if pdf_generated else "",
            "filename": pdf_path.name if pdf_generated else docx_path.name,
            "download_url": f"/workpapers/{wp.id}/download-docx" if not pdf_generated else f"/workpapers/{wp.id}/download",
            "file_type": "pdf" if pdf_generated else "docx",
            "pdf_error": pdf_error,
        })
    return generated