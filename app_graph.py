import json
import os

from dotenv import load_dotenv
from openai import OpenAI
from langgraph.graph import StateGraph, END
from pathlib import Path

from app_state import AuditState
from file_tools import observe_files
from framework_tools import load_inspection_framework, load_issue_framework

load_dotenv(encoding="utf-8")

client = OpenAI(
    api_key=os.getenv("SILICONFLOW_API_KEY"),
    base_url="https://api.siliconflow.cn/v1",
)
MODEL_NAME = os.getenv("SILICONFLOW_MODEL", "Qwen/Qwen2.5-72B-Instruct")

import re

def normalize_final_answer_schema(final_answer):
    if not isinstance(final_answer, dict):
        return final_answer

    valid_risk_levels = {"low", "medium", "high"}
    valid_resolution_status = {
        "open",
        "partially_explained",
        "pending_closure",
        "insufficient_evidence"
    }

    risk_findings = final_answer.get("risk_findings", [])
    for item in risk_findings:
        risk_level = item.get("risk_level")
        resolution_status = item.get("resolution_status")

        # 如果 risk_level 被错误写成 resolution_status 的值
        if risk_level in valid_resolution_status and resolution_status not in valid_resolution_status:
            item["resolution_status"] = risk_level
            item["risk_level"] = "low"

        # 风险等级兜底
        if item.get("risk_level") not in valid_risk_levels:
            item["risk_level"] = "low"

        # resolution_status 兜底
        if item.get("resolution_status") not in valid_resolution_status:
            item["resolution_status"] = "open"

    final_answer["risk_findings"] = risk_findings
    return final_answer

def clean_summary_next_steps(final_answer):
    if not isinstance(final_answer, dict):
        return final_answer

    overall_summary = final_answer.get("overall_summary", {})
    steps = overall_summary.get("recommended_next_steps", [])

    filtered = []
    for step in steps:
        if any(x in step for x in ["JSON 解析", "模型输出格式", "API 返回内容"]):
            continue
        filtered.append(step)

    overall_summary["recommended_next_steps"] = filtered
    final_answer["overall_summary"] = overall_summary
    return final_answer

def build_minimum_inspection_results(observations):
    observed_files = []
    for obs in observations:
        fp = obs.get("file_path")
        if fp:
            observed_files.append(fp.split("\\")[-1])

    observed_text = ", ".join(dict.fromkeys(observed_files)) if observed_files else "当前已提供材料"

    fallback_topics = [
        ("（一）资金管理情况", "1.资金管理制度建设与执行情况"),
        ("（一）资金管理情况", "2.银行账户资金管理情况"),
        ("（二）会计信息质量", "1.会计政策"),
    ]

    results = []
    for area, topic in fallback_topics:
        results.append({
            "area": area,
            "topic": topic,
            "status": "insufficient_evidence",
            "judgment": f"当前仅依据已提供材料，无法对“{topic}”形成充分判断。",
            "evidence": [f"当前已查看材料：{observed_text}；但仍不足以支持“{topic}”的判断。"],
            "missing_documents": build_missing_documents_for_topic(topic),
            "remark": ""
        })

    return results

def fill_inspection_evidence_if_empty(inspection_results, observations):
    observed_files = []
    for obs in observations:
        fp = obs.get("file_path")
        if fp:
            observed_files.append(fp.split("\\")[-1])

    observed_files = list(dict.fromkeys(observed_files))

    for item in inspection_results:
        if item.get("status") == "insufficient_evidence" and not item.get("evidence"):
            topic = item.get("topic", "")
            if observed_files:
                item["evidence"] = [
                    f"当前已查看材料：{', '.join(observed_files)}；但仍不足以支持“{topic}”的判断。"
                ]
    return inspection_results

def normalize_risk_titles(risk_findings):
    for item in risk_findings:
        title = item.get("title", "")
        evidence = item.get("evidence", [])
        resolution_status = item.get("resolution_status", "")

        joined_evidence = " ".join(evidence) if evidence else ""

        if "高频报销" in title:
            if "一笔差旅报销" in joined_evidence or "一笔报销" in joined_evidence:
                item["title"] = "差旅报销交易待核验"

        if title == "差旅报销异常" and resolution_status in ["partially_explained", "pending_closure"]:
            item["title"] = "差旅报销交易待核验"

        if title == "同日多笔近似金额交易" and resolution_status == "pending_closure":
            item["title"] = "同日多笔付款待闭环核查"

    return risk_findings

def normalize_inspection_judgment_text(inspection_results):
    for item in inspection_results:
        if item.get("status") == "insufficient_evidence":
            judgment = item.get("judgment", "")
            topic = item.get("topic", "")

            if not judgment:
                item["judgment"] = f"当前仅依据已提供材料，无法完成“{topic}”的充分判断。"
            else:
                judgment = judgment.replace("当前仅依据交易流水样本", "当前仅依据已提供材料")
                judgment = judgment.replace("当前仅依据交易流水", "当前仅依据已提供材料")
                judgment = judgment.replace("当前仅依据已提供材料和合同", "当前仅依据已提供材料")
                judgment = judgment.replace("当前仅依据已提供材料和合同资料", "当前仅依据已提供材料")
                item["judgment"] = judgment

    return inspection_results


def safe_parse_json(text: str):
    text = text.strip()

    # 去掉 markdown 代码块
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[len("```"):].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    # 截取最外层 JSON 对象
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    return json.loads(text)

def extract_dates_from_evidence(evidence):
    dates = []
    if not evidence:
        return dates

    date_pattern = r"\d{4}-\d{2}-\d{2}"

    for item in evidence:
        if isinstance(item, str):
            matches = re.findall(date_pattern, item)
            dates.extend(matches)
        elif isinstance(item, dict):
            for value in item.values():
                if isinstance(value, str):
                    matches = re.findall(date_pattern, value)
                    dates.extend(matches)
    return dates


def normalize_time_description(text: str, evidence):
    if not text:
        return text

    dates = extract_dates_from_evidence(evidence)

    if dates:
        unique_dates = sorted(set(dates))
        if len(unique_dates) == 1:
            text = text.replace("连续三天", "同日")
            text = text.replace("连续多天", "同日")
            text = text.replace("连续两天", "同日")
        elif len(unique_dates) > 1:
            # 有多天证据时，不做替换
            pass

    return text


def post_validate_findings(risk_findings, additional_findings):
    def fix_items(items):
        fixed = []
        for item in items:
            evidence = item.get("evidence", [])
            if "title" in item and isinstance(item["title"], str):
                item["title"] = normalize_time_description(item["title"], evidence)
            if "description" in item and isinstance(item["description"], str):
                item["description"] = normalize_time_description(item["description"], evidence)
            fixed.append(item)
        return fixed

    return fix_items(risk_findings), fix_items(additional_findings)

def normalize_inspection_judgment_text(inspection_results):
    for item in inspection_results:
        status = item.get("status", "")
        topic = item.get("topic", "")
        judgment = item.get("judgment", "")

        if status == "insufficient_evidence":
            if not judgment:
                item["judgment"] = f"当前仅依据已提供材料，无法对“{topic}”形成充分判断。"
            else:
                judgment = judgment.replace("当前仅依据交易流水样本", "当前仅依据已提供材料")
                judgment = judgment.replace("当前仅依据交易流水", "当前仅依据已提供材料")
                judgment = judgment.replace("当前仅依据已提供材料和合同", "当前仅依据已提供材料")
                judgment = judgment.replace("当前仅依据已提供材料和合同资料", "当前仅依据已提供材料")
                judgment = judgment.replace("当前资料不足，无法完成该主题判断。", f"当前仅依据已提供材料，无法对“{topic}”形成充分判断。")
                item["judgment"] = judgment

    return inspection_results

def build_missing_documents_for_topic(topic: str):
    topic_doc_map = {
        "1.资金管理制度建设与执行情况": ["资金管理制度", "审批授权文件", "岗位职责文件"],
        "2.银行账户资金管理情况": ["银行账户台账", "开户/变更审批资料", "银行对账单"],
        "3.现金管理情况": ["现金日记账", "库存现金盘点记录", "备用金台账"],
        "4.财务人员配备与管理情况": ["岗位分工表", "人员任职资料", "轮岗/交接记录"],
        "5.网银U盾、银行印鉴及重要票证管理情况": ["U盾管理台账", "印鉴管理台账", "票据登记簿"],
        "9.特殊资金管理": ["专户资料", "特殊资金审批资料", "特殊资金对账资料"],
        "1.会计政策": ["会计政策文件", "会计估计说明", "报表编制依据"],
        "2.收入": ["收入合同", "收入确认依据", "开票记录"],
        "3.成本费用": ["成本费用明细账", "报销及付款凭证", "费用审批资料"],
        "4.资产核算": ["固定资产台账", "存货盘点资料", "在建工程台账"],
        "5.资产减值": ["减值测试资料", "资产评估资料"],
        "1.小金库": ["银行流水", "备用金记录", "账外资金相关说明"],
    }
    return topic_doc_map.get(topic, ["相关制度资料", "审批资料", "支持性附件"])


def deduplicate_additional_findings(risk_findings, additional_findings):
    risk_titles = {item.get("title", "").strip() for item in risk_findings}
    deduped = []

    for item in additional_findings:
        title = item.get("title", "").strip()
        description = item.get("description", "").strip()

        duplicated = False
        if title in risk_titles:
            duplicated = True

        for rf in risk_findings:
            rf_desc = rf.get("description", "").strip()
            if description and rf_desc and description == rf_desc:
                duplicated = True
                break

        if not duplicated:
            deduped.append(item)

    return deduped


def planner_node(state: AuditState):
    text = state["user_input"].lower()
    file_paths = state.get("file_paths", [])
    observations = state.get("observations", [])

    material_types = []

    # 1. 先根据文件扩展名和文件名初筛
    for file_path in file_paths:
        p = str(file_path).lower()
        name = Path(p).name

        if p.endswith((".xlsx", ".xls")):
            material_types.append("spreadsheet")

            if any(keyword in name for keyword in ["data", "transaction", "流水", "明细", "台账", "账簿"]):
                material_types.append("transaction_table")

        elif p.endswith((".txt", ".md")):
            material_types.append("text_document")

            if any(keyword in name for keyword in ["contract", "合同"]):
                material_types.append("contract")
            if any(keyword in name for keyword in ["approval", "审批"]):
                material_types.append("approval_doc")
            if any(keyword in name for keyword in ["travel", "reimbursement", "报销", "差旅"]):
                material_types.append("reimbursement_doc")
            if any(keyword in name for keyword in ["policy", "制度", "办法", "规定"]):
                material_types.append("policy_doc")

        elif p.endswith((".pdf", ".doc", ".docx")):
            material_types.append("document_file")

            if any(keyword in name for keyword in ["contract", "合同"]):
                material_types.append("contract")
            if any(keyword in name for keyword in ["approval", "审批"]):
                material_types.append("approval_doc")
            if any(keyword in name for keyword in ["policy", "制度", "办法", "规定"]):
                material_types.append("policy_doc")

        elif p.endswith((".png", ".jpg", ".jpeg", ".webp")):
            material_types.append("image_material")

    # 2. 再根据 observations 内容补充识别
    for obs in observations:
        obs_type = obs.get("type", "")

        if obs_type == "excel_observation":
            preview = obs.get("preview", {})
            columns = preview.get("columns", [])

            normalized_columns = [str(c).strip() for c in columns]

            if any(col in normalized_columns for col in ["日期", "对手方", "金额", "摘要"]):
                material_types.append("transaction_table")

            if any(col in normalized_columns for col in ["科目", "余额", "借方", "贷方"]):
                material_types.append("accounting_table")

        elif obs_type == "text_observation":
            content = obs.get("content_preview", "").lower()

            if "合同编号" in content or "付款安排" in content or "合同总额" in content:
                material_types.append("contract")
            if "审批单编号" in content or "审批链" in content or "审批日期" in content:
                material_types.append("approval_doc")
            if "报销金额" in content or "出差时间" in content or "费用构成" in content:
                material_types.append("reimbursement_doc")
            if "制度" in content or "管理办法" in content or "管理规定" in content:
                material_types.append("policy_doc")

    # 去重，保持顺序
    deduped_material_types = []
    for item in material_types:
        if item not in deduped_material_types:
            deduped_material_types.append(item)
    material_types = deduped_material_types

    # 3. 根据材料类型 + 用户意图决定 next_action
    if "transaction_table" in material_types and any(
        x in material_types for x in ["contract", "approval_doc", "reimbursement_doc", "policy_doc"]
    ):
        task_type = "multi_material_transaction_analysis"
        message = "已识别为多材料联合审计分析任务"

    elif "transaction_table" in material_types:
        task_type = "transaction_analysis"
        message = "已识别为交易流水审计分析任务"

    elif any(x in material_types for x in ["policy_doc"]) and not any(
        x in material_types for x in ["transaction_table", "contract", "approval_doc"]
    ):
        task_type = "policy_compliance_analysis"
        message = "已识别为制度/政策合规分析任务"

    elif any(x in material_types for x in ["contract", "approval_doc", "reimbursement_doc", "document_file", "text_document"]):
        task_type = "document_analysis"
        message = "已识别为文本/文档材料分析任务"

    elif (
        "交易" in text
        or "流水" in text
        or "异常" in text
        or "审计" in text
        or "复查" in text
        or "报销" in text
        or "合同" in text
        or "审批" in text
    ):
        task_type = "general_audit_analysis"
        message = "已识别为通用审计分析任务"

    else:
        task_type = "general_analysis"
        message = "未识别出明确材料类型，先按通用分析处理"

    return {
        "user_input": state["user_input"],
        "file_paths": file_paths,
        "messages": state["messages"] + [message + f"；材料类型：{', '.join(material_types) if material_types else '未识别'}"],

        "material_types": material_types,
        "observations": state["observations"],

        "inspection_framework": state["inspection_framework"],
        "issue_framework": state["issue_framework"],

        "inspection_results": state["inspection_results"],
        "risk_findings": state["risk_findings"],
        "additional_findings": state["additional_findings"],

        "draft_answer": state["draft_answer"],
        "reflection": state["reflection"],
        "next_action": task_type,
        "final_answer": state["final_answer"],
    }


def load_framework_node(state: AuditState):
    inspection_framework = load_inspection_framework()
    issue_framework = load_issue_framework()

    return {
        "user_input": state["user_input"],
        "file_path": state.get("file_path"),
        "messages": state["messages"] + ["已加载内部检查框架"],
        "material_types": state["material_types"],

        "observations": state["observations"],

        "inspection_framework": inspection_framework,
        "issue_framework": issue_framework,

        "inspection_results": state["inspection_results"],
        "risk_findings": state["risk_findings"],
        "additional_findings": state["additional_findings"],

        "draft_answer": state["draft_answer"],
        "reflection": state["reflection"],
        "next_action": state["next_action"],
        "final_answer": state["final_answer"],
    }


def observe_node(state: AuditState):
    file_paths = state.get("file_paths", [])
    action = state["next_action"]

    if action not in [
        "transaction_analysis",
        "multi_material_transaction_analysis",
        "document_analysis",
        "policy_compliance_analysis",
        "general_audit_analysis",
    ]:
        return {
            "user_input": state["user_input"],
            "file_paths": file_paths,
            "messages": state["messages"] + ["当前任务暂不执行文件观察"],
            "material_types": state["material_types"],

            "observations": state["observations"],

            "inspection_framework": state["inspection_framework"],
            "issue_framework": state["issue_framework"],

            "inspection_results": state["inspection_results"],
            "risk_findings": state["risk_findings"],
            "additional_findings": state["additional_findings"],

            "draft_answer": state["draft_answer"],
            "reflection": state["reflection"],
            "next_action": "reason",
            "final_answer": state["final_answer"],
        }

    if not file_paths:
        return {
            "user_input": state["user_input"],
            "file_paths": file_paths,
            "messages": state["messages"] + ["未提供文件路径，无法读取资料"],

            "observations": state["observations"],

            "inspection_framework": state["inspection_framework"],
            "issue_framework": state["issue_framework"],

            "inspection_results": state["inspection_results"],
            "risk_findings": state["risk_findings"],
            "additional_findings": state["additional_findings"],

            "draft_answer": state["draft_answer"],
            "reflection": state["reflection"],
            "next_action": "reason",
            "final_answer": state["final_answer"],
        }

    try:
        observations = observe_files(file_paths)

        return {
            "user_input": state["user_input"],
            "file_paths": file_paths,
            "messages": state["messages"] + [f"已完成文件观察，共读取 {len(file_paths)} 份材料"],

            "observations": state["observations"] + observations,

            "inspection_framework": state["inspection_framework"],
            "issue_framework": state["issue_framework"],

            "inspection_results": state["inspection_results"],
            "risk_findings": state["risk_findings"],
            "additional_findings": state["additional_findings"],

            "draft_answer": state["draft_answer"],
            "reflection": state["reflection"],
            "next_action": "reason",
            "final_answer": state["final_answer"],
        }
    except Exception as e:
        return {
            "user_input": state["user_input"],
            "file_paths": file_paths,
            "messages": state["messages"] + [f"文件观察失败: {str(e)}"],

            "observations": state["observations"],

            "inspection_framework": state["inspection_framework"],
            "issue_framework": state["issue_framework"],

            "inspection_results": state["inspection_results"],
            "risk_findings": state["risk_findings"],
            "additional_findings": state["additional_findings"],

            "draft_answer": state["draft_answer"],
            "reflection": state["reflection"],
            "next_action": "reason",
            "final_answer": state["final_answer"],
        }

def reason_node(state: AuditState):
    observations = state["observations"]

    output_template = {
        "inspection_results": [
            {
                "area": "",
                "topic": "",
                "status": "insufficient_evidence",
                "judgment": "当前资料不足，无法完成该主题判断。",
                "evidence": [],
                "missing_documents": [],
                "remark": ""
            }
        ],
        "risk_findings": [
            {
                "issue_id": "",
                "title": "",
                "risk_level": "low",
                "resolution_status": "open",
                "description": "",
                "amount_involved": None,
                "evidence": [],
                "suggested_actions": []
            }
        ],
        "additional_findings": [
            {
                "title": "",
                "risk_level": "low",
                "description": "",
                "evidence": [],
                "suggested_actions": []
            }
        ],
        "overall_summary": {
            "overall_risk_level": "low",
            "summary": "",
            "recommended_next_steps": []
        }
    }

    prompt = f"""
    你是一个审计/合规检查智能体。

    你的任务是依据内部检查要求，对当前资料进行系统性分析。
    注意：内部检查要求仅作为你的分析约束，不要在输出中提及“清单”或“框架”字样。

    【用户目标】
    {state["user_input"]}

    【观察结果】
    {json.dumps(observations, ensure_ascii=False, indent=2)}

    【内部检查维度】
    {json.dumps(state["inspection_framework"], ensure_ascii=False, indent=2)}

    【内部风险维度】
    {json.dumps(state["issue_framework"], ensure_ascii=False, indent=2)}

    【输出模板】
    {json.dumps(output_template, ensure_ascii=False, indent=2)}

    请严格输出 JSON，且只能输出 JSON，不要输出解释文字，不要加 markdown 代码块。

    要求：
    1. inspection_results 表示基于内部检查维度形成的结果。
    2. 如果证据不足：
       - status 必须写 insufficient_evidence
       - judgment 必须明确写出“当前仅依据什么资料，无法判断什么内容”
       - missing_documents 必须列出至少 1-3 项缺失资料
    3. risk_findings 仅保留真正有证据支持的风险。
    4. additional_findings 仅保留框架外新增发现，不要与 risk_findings 重复。
    5. overall_summary 要简洁。
    6. status 只能是：compliant / non_compliant / not_applicable / insufficient_evidence
    7. risk_level 只能是：low / medium / high
    8. 只能依据观察结果做判断，不要编造不存在的证据。
    9. 所有风险描述必须严格基于 evidence 中已经出现的事实。
    10. 不得擅自改写日期、金额、次数、交易对象。
    11. 如果 evidence 显示是“同一天多笔交易”，不得写成“连续三天”或“连续多天”。
    12. 如果 evidence 只显示“一笔交易”，不得写成“多笔交易”。
    13. 如果 evidence 中没有“长期”“频繁”“持续”等时间信息，不得自行补充这些表述。
    14. 优先使用保守表述，例如“可能存在”“需进一步核查”，不要直接下最终结论。
    15. 如果 pattern 风险已经足以描述当前异常，就优先输出 pattern 风险，不要跳过 pattern 直接命中 advanced 风险。
    16. 如果 advanced 风险尚不能成立，可以在 description 中写“当前仅呈现为模式异常，需补充资料后进一步判断是否涉及更高阶合规问题”。
    【风险识别分层规则】
    1. 内部风险维度中，risk_type = pattern 表示可直接由当前样本或流水识别的模式型风险。
    2. 内部风险维度中，risk_type = advanced 表示需要更多背景资料、制度文件、合同、审批记录或访谈信息才能判断的高阶合规风险。
    3. 在当前仅有交易流水或样本数据时，优先识别 risk_type = pattern 的风险。
    4. 对于 risk_type = advanced 的风险，只有当 observation 和 evidence 已经足以支持时才允许命中。
    5. 如果当前证据不足以支持 advanced 风险，不要直接命中该风险，而应在 inspection_results 中体现证据不足，或在 suggested_actions / recommended_next_steps 中说明“补充资料后再判断是否上升为高阶合规风险”。
    6. 不要因为存在大额交易、同日多笔交易、差旅报销等表面模式，就直接上升判断为利益输送、隐匿收入、小金库、虚假差旅等高阶合规风险。
    【补充材料驱动风险收敛规则】
    1. 如果补充材料能够对模式异常提供合理解释，应降低风险判断强度。
    2. 如果合同、审批单、报销说明等材料能够解释交易背景、付款安排或审批流程，不要继续把该事项表述为强异常。
    3. 对于已获得初步业务解释的事项，可以保留为“待进一步闭环核查”，不要直接定性为违规。
    4. 如果补充材料支持“同一合同项下分期支付”，则应将“疑似拆分支付”收敛为“已获得初步业务解释，但仍需补充发票、验收单等资料进一步闭环”。
    5. 如果补充材料支持“差旅报销具有明确业务背景且已审批”，则应降低差旅风险等级，仅保留“待补票据核验”的提示。
    6. 如果补充材料与原交易记录明显矛盾，则应提升风险等级，并指出矛盾点。
    7. 对已经被补充材料部分解释的风险，risk_level 可降低一级，description 中应明确写出“已获得初步解释”。
    【证据表达规则】
    1. evidence 不要只写文件路径。
    2. evidence 应尽量写成“文件名：关键事实摘要”的形式。
    3. 每条 evidence 应包含：
    - 来自哪个文件
    - 支撑结论的关键事实
    4. 示例：
    - data.xlsx：2026-01-03发生三笔设备采购付款，金额分别为120000、118000、119500
    - contract_b_company.txt：合同HT-B-2026-001总额357500元，约定三期付款
    - approval_b_company.txt：三笔付款均已于2026-01-02完成审批
    5. 如果无法提炼证据摘要，才允许退化为文件路径。
    【风险状态规则】
    1. risk_findings 中新增字段 resolution_status。
    2. resolution_status 只能取以下值之一：
    - open：已发现异常，尚未解释
    - partially_explained：已获得初步解释，但仍需补充资料闭环
    - pending_closure：主要问题已解释，待补关键凭证完成闭环
    - insufficient_evidence：当前证据不足，仅提示继续核查
    3. 如果补充材料已经对模式异常提供初步解释，应优先使用 partially_explained。
    4. 如果只差发票、验收单、报销附件等最后一类关键资料，可使用 pending_closure。
    【状态判定规则补充】
    1. 只有当某主题在当前任务场景下客观不适用时，才允许使用 not_applicable。
    2. 如果只是当前资料不足以支持判断，应优先使用 insufficient_evidence，而不是 not_applicable。
    3. 对资金管理、会计信息质量、小金库等常规审计主题，除非明确不适用，否则优先判定为 insufficient_evidence。
    【inspection_results 证据规则】
    1. 对于 insufficient_evidence 的 inspection_results，evidence 应说明当前已查看到的材料范围。
    2. 如果当前只看到交易流水、合同、审批单等局部资料，应在 evidence 中明确写出“已查看哪些材料，但仍不足以支持该主题判断”。
    3. 不要让 insufficient_evidence 的 evidence 为空，除非当前确实没有任何相关材料。
    【overall_summary 规则】
    1. overall_summary.summary 应包括三层信息：
    - 本轮识别到的主要事项
    - 哪些事项已获得初步业务解释
    - 哪些事项仍需补充关键资料闭环
    2. recommended_next_steps 应尽量与 risk_findings 的 suggested_actions 对应。
    3. overall_summary.summary 除了说明已识别事项和已获得初步解释的事项外，还应概括说明：对资金管理制度、银行账户管理、会计政策等整体性主题，目前仍普遍处于证据不足状态。
    """

    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "你是专业的审计智能体，擅长依据内部检查要求对资料进行系统性分析，并输出严格结构化 JSON。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2
        )

        draft_answer = resp.choices[0].message.content

        try:
            parsed = safe_parse_json(draft_answer)
        except Exception:
            retry_prompt = f"""
    你刚才输出的内容不是合法 JSON。

    请基于下面相同任务，重新输出一次。
    要求：
    1. 只能输出合法 JSON
    2. 不要输出解释文字
    3. 不要输出 markdown 代码块
    4. 所有字符串必须正确闭合
    5. 输出字段必须完整

    原任务如下：

    {prompt}
    """
            retry_resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": "你是专业的审计智能体，必须输出严格合法的 JSON。"
                    },
                    {
                        "role": "user",
                        "content": retry_prompt
                    }
                ],
                temperature=0.1
            )

            draft_answer = retry_resp.choices[0].message.content
            parsed = safe_parse_json(draft_answer)

        inspection_results = parsed.get("inspection_results", [])
        risk_findings = parsed.get("risk_findings", [])
        additional_findings = parsed.get("additional_findings", [])

        for item in inspection_results:
            if item.get("status") == "insufficient_evidence":
                if not item.get("judgment"):
                    item["judgment"] = f"当前仅依据已提供材料，无法完成“{item.get('topic', '')}”的充分判断。"
                if not item.get("missing_documents"):
                    item["missing_documents"] = build_missing_documents_for_topic(item.get("topic", ""))

        inspection_results = fill_inspection_evidence_if_empty(inspection_results, state["observations"])
        inspection_results = normalize_inspection_judgment_text(inspection_results)
        additional_findings = deduplicate_additional_findings(risk_findings, additional_findings)
        risk_findings, additional_findings = post_validate_findings(risk_findings, additional_findings)
        risk_findings = normalize_risk_titles(risk_findings)

        return {
            "user_input": state["user_input"],
            "file_paths": state.get("file_paths", []),
            "messages": state["messages"] + ["已完成初步审计推理"],

            "observations": state["observations"],

            "inspection_framework": state["inspection_framework"],
            "issue_framework": state["issue_framework"],

            "inspection_results": inspection_results,
            "risk_findings": risk_findings,
            "additional_findings": additional_findings,

            "draft_answer": draft_answer,
            "reflection": state["reflection"],
            "next_action": "reflect",
            "final_answer": state["final_answer"],
            "material_types": state["material_types"],
        }

    except Exception as e:
        fallback = {
            "inspection_results": build_minimum_inspection_results(state["observations"]),
            "risk_findings": [],
            "additional_findings": [],
            "overall_summary": {
                "overall_risk_level": "low",
                "summary": f"初步审计推理失败：{str(e)}",
                "recommended_next_steps": [
                    "检查模型输出格式",
                    "检查 JSON 解析",
                    "检查 API 返回内容"
                ]
            }
        }

        return {
            "user_input": state["user_input"],
            "file_paths": state.get("file_paths", []),
            "messages": state["messages"] + [f"初步审计推理失败: {str(e)}"],

            "observations": state["observations"],

            "inspection_framework": state["inspection_framework"],
            "issue_framework": state["issue_framework"],

            "inspection_results": fallback["inspection_results"],
            "risk_findings": fallback["risk_findings"],
            "additional_findings": fallback["additional_findings"],

            "draft_answer": json.dumps(fallback, ensure_ascii=False, indent=2),
            "reflection": state["reflection"],
            "next_action": "reflect",
            "final_answer": state["final_answer"],
            "material_types": state["material_types"],
        }

def inspect_node(state: AuditState):
    observations = state["observations"]

    output_template = {
        "inspection_results": [
            {
                "area": "",
                "topic": "",
                "status": "insufficient_evidence",
                "judgment": "当前资料不足，无法完成该主题判断。",
                "evidence": [],
                "missing_documents": [],
                "remark": ""
            }
        ]
    }

    prompt = f"""
你是一个审计检查智能体。

你的任务是仅依据当前资料，输出 inspection_results。
只输出 JSON，不要输出解释文字，不要输出 markdown 代码块。

【用户目标】
{state["user_input"]}

【观察结果】
{json.dumps(observations, ensure_ascii=False, indent=2)}

【内部检查维度】
{json.dumps(state["inspection_framework"], ensure_ascii=False, indent=2)}

【输出模板】
{json.dumps(output_template, ensure_ascii=False, indent=2)}

要求：
1. 只能输出 inspection_results，不要输出 risk_findings、additional_findings、overall_summary。
2. inspection_results 不得为空；如果无法覆盖全部主题，也必须至少输出 3-5 个最关键主题。
3. 如果资料不足，应优先使用 insufficient_evidence，而不是 not_applicable。
4. 只有当某主题客观不适用于当前任务时，才允许使用 not_applicable。
5. judgment 应说明“当前仅依据什么资料，无法判断什么内容”。
6. evidence 应说明已查看到的材料范围。
7. missing_documents 必须列出 1-3 项最关键缺失资料。
"""

    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "你是专业的审计检查智能体，必须输出严格合法的 JSON。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )

        text = resp.choices[0].message.content

        try:
            parsed = safe_parse_json(text)
        except Exception:
            retry_prompt = f"""
你刚才输出的内容不是合法 JSON。

请重新输出一次。
要求：
1. 只能输出合法 JSON
2. 只能包含 inspection_results
3. 不要输出解释文字
4. 不要输出 markdown 代码块

原任务如下：

{prompt}
"""
            retry_resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "你是专业的审计检查智能体，必须输出严格合法的 JSON。"},
                    {"role": "user", "content": retry_prompt}
                ],
                temperature=0.1
            )
            text = retry_resp.choices[0].message.content
            parsed = safe_parse_json(text)

        inspection_results = parsed.get("inspection_results", [])

        for item in inspection_results:
            if item.get("status") == "insufficient_evidence":
                if not item.get("judgment"):
                    item["judgment"] = f"当前仅依据已提供材料，无法对“{item.get('topic', '')}”形成充分判断。"
                if not item.get("missing_documents"):
                    item["missing_documents"] = build_missing_documents_for_topic(item.get("topic", ""))

        inspection_results = normalize_inspection_judgment_text(inspection_results)
        inspection_results = fill_inspection_evidence_if_empty(inspection_results, state["observations"])

        return {
            "user_input": state["user_input"],
            "file_paths": state.get("file_paths", []),
            "messages": state["messages"] + ["已完成检查项分析"],

            "material_types": state.get("material_types", []),
            "observations": state["observations"],

            "inspection_framework": state["inspection_framework"],
            "issue_framework": state["issue_framework"],

            "inspection_results": inspection_results,
            "risk_findings": state["risk_findings"],
            "additional_findings": state["additional_findings"],

            "draft_answer": text,
            "reflection": state["reflection"],
            "next_action": "risk",
            "final_answer": state["final_answer"],
        }

    except Exception as e:
        fallback_inspection = build_minimum_inspection_results(state["observations"])

        return {
            "user_input": state["user_input"],
            "file_paths": state.get("file_paths", []),
            "messages": state["messages"] + [f"检查项分析失败: {str(e)}"],

            "material_types": state.get("material_types", []),
            "observations": state["observations"],

            "inspection_framework": state["inspection_framework"],
            "issue_framework": state["issue_framework"],

            "inspection_results": fallback_inspection,
            "risk_findings": state["risk_findings"],
            "additional_findings": state["additional_findings"],

            "draft_answer": json.dumps({"inspection_results": fallback_inspection}, ensure_ascii=False, indent=2),
            "reflection": state["reflection"],
            "next_action": "risk",
            "final_answer": state["final_answer"],
        }

def risk_node(state: AuditState):
    observations = state["observations"]

    output_template = {
        "risk_findings": [
            {
                "issue_id": "",
                "title": "",
                "risk_level": "low",
                "resolution_status": "open",
                "description": "",
                "amount_involved": None,
                "evidence": [],
                "suggested_actions": []
            }
        ],
        "additional_findings": [
            {
                "title": "",
                "risk_level": "low",
                "description": "",
                "evidence": [],
                "suggested_actions": []
            }
        ],
        "overall_summary": {
            "overall_risk_level": "low",
            "summary": "",
            "recommended_next_steps": []
        }
    }

    prompt = f"""
你是一个审计风险分析智能体。

你的任务是仅依据当前资料和 inspection_results，输出风险识别结果。
只输出 JSON，不要输出解释文字，不要输出 markdown 代码块。

【用户目标】
{state["user_input"]}

【观察结果】
{json.dumps(observations, ensure_ascii=False, indent=2)}

【inspection_results】
{json.dumps(state["inspection_results"], ensure_ascii=False, indent=2)}

【内部风险维度】
{json.dumps(state["issue_framework"], ensure_ascii=False, indent=2)}

【输出模板】
{json.dumps(output_template, ensure_ascii=False, indent=2)}

要求：
1. 只能输出 risk_findings、additional_findings、overall_summary。
2. 不要重复输出 inspection_results。
3. 优先识别 pattern 风险，不要轻易上升到 advanced 风险。
4. 如果补充材料能够解释风险，应降低风险等级或使用：
   - partially_explained
   - pending_closure
5. evidence 应尽量写成“文件名：关键事实摘要”的形式。
6. overall_summary 需要概括：
   - 本轮识别到的主要事项
   - 哪些已获得初步解释
   - 哪些仍需补充关键资料闭环
   - 哪些整体性主题仍证据不足
"""

    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "你是专业的审计风险分析智能体，必须输出严格合法的 JSON。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )

        text = resp.choices[0].message.content

        try:
            parsed = safe_parse_json(text)
        except Exception:
            retry_prompt = f"""
你刚才输出的内容不是合法 JSON。

请重新输出一次。
要求：
1. 只能输出合法 JSON
2. 只能包含 risk_findings、additional_findings、overall_summary
3. 不要输出解释文字
4. 不要输出 markdown 代码块

原任务如下：

{prompt}
"""
            retry_resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "你是专业的审计风险分析智能体，必须输出严格合法的 JSON。"},
                    {"role": "user", "content": retry_prompt}
                ],
                temperature=0.1
            )
            text = retry_resp.choices[0].message.content
            parsed = safe_parse_json(text)

        risk_findings = parsed.get("risk_findings", [])
        additional_findings = parsed.get("additional_findings", [])

        additional_findings = deduplicate_additional_findings(risk_findings, additional_findings)
        risk_findings, additional_findings = post_validate_findings(risk_findings, additional_findings)
        risk_findings = normalize_risk_titles(risk_findings)

        parsed["risk_findings"] = risk_findings
        parsed["additional_findings"] = additional_findings
        parsed = clean_summary_next_steps(parsed)

        return {
            "user_input": state["user_input"],
            "file_paths": state.get("file_paths", []),
            "messages": state["messages"] + ["已完成风险分析"],

            "material_types": state.get("material_types", []),
            "observations": state["observations"],

            "inspection_framework": state["inspection_framework"],
            "issue_framework": state["issue_framework"],

            "inspection_results": state["inspection_results"],
            "risk_findings": risk_findings,
            "additional_findings": additional_findings,

            "draft_answer": text,
            "reflection": json.dumps(parsed, ensure_ascii=False, indent=2),
            "next_action": "reflect",
            "final_answer": parsed,
        }

    except Exception as e:
        fallback = {
            "risk_findings": [],
            "additional_findings": [],
            "overall_summary": {
                "overall_risk_level": "low",
                "summary": f"风险分析失败：{str(e)}",
                "recommended_next_steps": []
            }
        }

        return {
            "user_input": state["user_input"],
            "file_paths": state.get("file_paths", []),
            "messages": state["messages"] + [f"风险分析失败: {str(e)}"],

            "material_types": state.get("material_types", []),
            "observations": state["observations"],

            "inspection_framework": state["inspection_framework"],
            "issue_framework": state["issue_framework"],

            "inspection_results": state["inspection_results"],
            "risk_findings": [],
            "additional_findings": [],

            "draft_answer": text if 'text' in locals() else json.dumps(fallback, ensure_ascii=False, indent=2),
            "reflection": state["reflection"],
            "next_action": "reflect",
            "final_answer": fallback,
        }

def reflect_node(state: AuditState):
    reflect_prompt = f"""
    你现在是审计复核智能体。

    请对下面这份结构化审计结果做复核，并输出修正后的最终 JSON。
    只能输出 JSON，不要输出解释文字，不要加 markdown 代码块。

    【用户目标】
    {state["user_input"]}

    【观察结果】
    {json.dumps(state["observations"], ensure_ascii=False, indent=2)}

    【初步结构化结果】
    {state["draft_answer"]}

    要求：
    1. 检查是否存在过度推断。
    2. 检查是否有遗漏的重要风险点。
    3. 如果证据不足，要降低判断强度。
    4. 输出字段仍必须保持：
       - inspection_results
       - risk_findings
       - additional_findings
       - overall_summary
    5. risk_findings 中必须保留以下字段：
       - issue_id
       - title
       - risk_level
       - resolution_status
       - description
       - amount_involved
       - evidence
       - suggested_actions
    6. status 只能是：compliant / non_compliant / not_applicable / insufficient_evidence
    7. risk_level 只能是：low / medium / high
    8. resolution_status 只能是：
       - open
       - partially_explained
       - pending_closure
       - insufficient_evidence
    9. 所有风险描述必须严格基于 observation 和 evidence 中已经出现的事实。
    10. 不得擅自改写日期、金额、次数、交易对象。
    11. 如果证据显示是“同一天多笔交易”，不得改写成“连续三天”或“连续多天”。
    12. 如果证据只显示“一笔交易”，不得改写成“多笔交易”。
    13. 如果 observation 中没有“长期”“频繁”“持续”等时间信息，不得自行补充这些表述。
    14. 如果某条风险描述超出了已有 evidence，应主动降级或删除该表述。
    15. 复核时优先修正事实错误，而不是润色措辞。
    16. 复核时必须检查 risk_findings 是否错误命中了 advanced 风险。
    17. 如果当前 evidence 仅支持模式异常，而不足以支持高阶合规判断，应将该风险降级为 pattern 层面的异常描述，或移出 risk_findings。
    18. 不要把“大额交易”“同日多笔交易”“报销交易”直接复核成“利益输送”“隐匿收入”“小金库”“虚假差旅”，除非 evidence 已经明确支持。

    【补充材料复核规则】
    19. 复核时必须检查补充材料是否已经对原有模式异常提供了解释。
    20. 如果补充材料能够解释交易安排、付款路径或业务背景，应降低风险等级或调整表述。
    21. 如果补充材料只能部分解释，应将 resolution_status 调整为 partially_explained，并在 description 中明确写出“已获得初步解释，但仍需补充资料闭环”。
    22. 如果补充材料已经基本解释了异常，仅缺发票、验收单、报销附件等最后一类关键资料，应将 resolution_status 调整为 pending_closure。
    23. 如果补充材料不足以解释，保留原风险，并将 resolution_status 保持为 open 或 insufficient_evidence。
    24. 如果补充材料与原始交易记录不一致，应明确指出矛盾并提高关注等级。

    【证据复核规则】
    25. 复核时应优先把 evidence 修正为“文件名：关键事实摘要”的形式。
    26. 不要只保留文件路径，除非当前确实无法提炼出支撑结论的关键事实。
    27. evidence 必须与 risk description 一一对应。
    28. evidence 示例：
       - data.xlsx：2026-01-03发生三笔设备采购付款，金额分别为120000、118000、119500
       - contract_b_company.txt：合同HT-B-2026-001总额357500元，约定三期付款
       - approval_b_company.txt：三笔付款均已于2026-01-02完成审批

    【复核输出目标】
    29. 如果补充材料已经提供初步业务解释，应优先让风险从“纯异常”收敛为“已部分解释”。
    30. 如果当前仍缺关键闭环资料，应在 suggested_actions 和 overall_summary 中明确写出还缺什么。
    31. overall_summary 应反映：哪些异常已获得初步解释，哪些仍待闭环，哪些仍证据不足。
    32. 复核时检查 not_applicable 是否被滥用。
    33. 如果某主题只是资料不足，而不是客观不适用，应将 status 从 not_applicable 调整为 insufficient_evidence。
    【overall_summary 规则】
    1. overall_summary.summary 应包括三层信息：
    - 本轮识别到的主要事项
    - 哪些事项已获得初步业务解释
    - 哪些事项仍需补充关键资料闭环
    2. recommended_next_steps 应尽量与 risk_findings 的 suggested_actions 对应。
    3. overall_summary.summary 除了说明已识别事项和已获得初步解释的事项外，还应概括说明：对资金管理制度、银行账户管理、会计政策等整体性主题，目前仍普遍处于证据不足状态。
    【当前 inspection_results】
   {json.dumps(state["inspection_results"], ensure_ascii=False, indent=2)}

    【当前 risk_findings】
   {json.dumps(state["risk_findings"], ensure_ascii=False, indent=2)}

    【当前 additional_findings】
   {json.dumps(state["additional_findings"], ensure_ascii=False, indent=2)}
    """

    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "你是审计复核智能体，职责是修正和完善结构化审计结果，并保持审慎。"
                },
                {
                    "role": "user",
                    "content": reflect_prompt
                }
            ],
            temperature=0.1
        )

        reflection_text = resp.choices[0].message.content

        try:
            parsed = safe_parse_json(reflection_text)
        except Exception:
            retry_prompt = f"""
        你刚才输出的内容不是合法 JSON。

        请基于下面相同任务，重新输出一次。
        要求：
        1. 只能输出合法 JSON
        2. 不要输出解释文字
        3. 不要输出 markdown 代码块
        4. 所有字符串必须正确闭合
        5. 输出字段必须完整

        原任务如下：

        {reflect_prompt}
        """
            retry_resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": "你是审计复核智能体，必须输出严格合法的 JSON。"
                    },
                    {
                        "role": "user",
                        "content": retry_prompt
                    }
                ],
                temperature=0.1
            )
            reflection_text = retry_resp.choices[0].message.content
            parsed = safe_parse_json(reflection_text)

        inspection_results = parsed.get("inspection_results", state["inspection_results"])
        risk_findings = parsed.get("risk_findings", state["risk_findings"])
        additional_findings = parsed.get("additional_findings", state["additional_findings"])

        for item in inspection_results:
            if item.get("status") == "insufficient_evidence":
                if not item.get("judgment"):
                    item["judgment"] = f"当前仅依据已提供材料，无法完成“{item.get('topic', '')}”的充分判断。"
                if not item.get("missing_documents"):
                    item["missing_documents"] = build_missing_documents_for_topic(item.get("topic", ""))

        inspection_results = fill_inspection_evidence_if_empty(inspection_results, state["observations"])
        inspection_results = normalize_inspection_judgment_text(inspection_results)
        additional_findings = deduplicate_additional_findings(risk_findings, additional_findings)
        risk_findings, additional_findings = post_validate_findings(risk_findings, additional_findings)
        risk_findings = normalize_risk_titles(risk_findings)

        parsed["inspection_results"] = inspection_results
        parsed["risk_findings"] = risk_findings
        parsed["additional_findings"] = additional_findings
        parsed = clean_summary_next_steps(parsed)
        parsed = normalize_final_answer_schema(parsed)

        return {
            "user_input": state["user_input"],
            "file_path": state.get("file_path"),
            "messages": state["messages"] + ["已完成复核与反思"],

            "observations": state["observations"],

            "inspection_framework": state["inspection_framework"],
            "issue_framework": state["issue_framework"],

            "inspection_results": inspection_results,
            "risk_findings": risk_findings,
            "additional_findings": additional_findings,

            "draft_answer": state["draft_answer"],
            "reflection": reflection_text,
            "next_action": "done",
            "final_answer": parsed
        }


    except Exception as e:

        fallback_final = {

            "inspection_results": state.get("inspection_results", []),

            "risk_findings": state.get("risk_findings", []),

            "additional_findings": state.get("additional_findings", []),

            "overall_summary": {

                "overall_risk_level": "medium",

                "summary": f"复核阶段失败，已返回初步结构化结果。错误信息：{str(e)}",

                "recommended_next_steps": [

                    "人工复核初步结果",

                    "检查反思节点输出格式"

                ]

            }

        }

        fallback_final = clean_summary_next_steps(fallback_final)

        fallback_final = normalize_final_answer_schema(fallback_final)

        return {

            "user_input": state["user_input"],

            "file_paths": state.get("file_paths", []),

            "messages": state["messages"] + [f"复核失败，返回初步结果: {str(e)}"],

            "material_types": state.get("material_types", []),

            "observations": state["observations"],

            "inspection_framework": state["inspection_framework"],

            "issue_framework": state["issue_framework"],

            "inspection_results": fallback_final["inspection_results"],

            "risk_findings": fallback_final["risk_findings"],

            "additional_findings": fallback_final["additional_findings"],

            "draft_answer": state["draft_answer"],

            "reflection": state.get("reflection", ""),

            "next_action": "done",

            "final_answer": fallback_final,

        }


builder = StateGraph(AuditState)

builder.add_node("planner", planner_node)
builder.add_node("load_framework", load_framework_node)
builder.add_node("observe", observe_node)
builder.add_node("inspect", inspect_node)
builder.add_node("risk", risk_node)
builder.add_node("reflect", reflect_node)

builder.set_entry_point("planner")
builder.add_edge("planner", "load_framework")
builder.add_edge("load_framework", "observe")
builder.add_edge("observe", "inspect")
builder.add_edge("inspect", "risk")
builder.add_edge("risk", "reflect")
builder.add_edge("reflect", END)

graph = builder.compile()