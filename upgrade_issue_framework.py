import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
FRAMEWORK_FILE = BASE_DIR / "framework" / "issue_framework.json"
BACKUP_FILE = BASE_DIR / "framework" / "issue_framework_backup.json"


PATTERN_RISKS = [
    {
        "framework_id": "ISSUE-P001",
        "seq_no": "P001",
        "risk_type": "pattern",
        "risk_title": "同日多笔近似金额交易",
        "check_goal": "检查是否存在同一日期、同一对手方、金额接近的多笔交易，识别疑似拆分支付或规避审批的情况",
        "expected_documents": ["交易流水", "付款审批单", "合同", "发票"],
        "check_methods": ["数据分析", "核对"],
        "output_fields": [
            "has_issue",
            "status",
            "issue_description",
            "amount_involved",
            "risk_level",
            "rectification_suggestion",
            "evidence",
            "missing_documents",
            "remark"
        ],
        "hidden_source": {
            "source_type": "internal_pattern_extension"
        }
    },
    {
        "framework_id": "ISSUE-P002",
        "seq_no": "P002",
        "risk_type": "pattern",
        "risk_title": "大额异常交易",
        "check_goal": "检查是否存在金额明显较大、超出常规水平、需重点核查的大额交易",
        "expected_documents": ["交易流水", "合同", "付款依据", "审批资料"],
        "check_methods": ["数据分析", "抽查"],
        "output_fields": [
            "has_issue",
            "status",
            "issue_description",
            "amount_involved",
            "risk_level",
            "rectification_suggestion",
            "evidence",
            "missing_documents",
            "remark"
        ],
        "hidden_source": {
            "source_type": "internal_pattern_extension"
        }
    },
    {
        "framework_id": "ISSUE-P003",
        "seq_no": "P003",
        "risk_type": "pattern",
        "risk_title": "集中支付风险",
        "check_goal": "检查是否存在短时间内集中向同一对手方或同类摘要支付款项的情况",
        "expected_documents": ["交易流水", "付款申请单", "合同"],
        "check_methods": ["数据分析", "核对"],
        "output_fields": [
            "has_issue",
            "status",
            "issue_description",
            "amount_involved",
            "risk_level",
            "rectification_suggestion",
            "evidence",
            "missing_documents",
            "remark"
        ],
        "hidden_source": {
            "source_type": "internal_pattern_extension"
        }
    },
    {
        "framework_id": "ISSUE-P004",
        "seq_no": "P004",
        "risk_type": "pattern",
        "risk_title": "单一对手方集中交易",
        "check_goal": "检查是否存在交易高度集中于单一对手方的情况",
        "expected_documents": ["交易流水", "供应商/客户资料", "合同"],
        "check_methods": ["数据分析", "核对"],
        "output_fields": [
            "has_issue",
            "status",
            "issue_description",
            "amount_involved",
            "risk_level",
            "rectification_suggestion",
            "evidence",
            "missing_documents",
            "remark"
        ],
        "hidden_source": {
            "source_type": "internal_pattern_extension"
        }
    },
    {
        "framework_id": "ISSUE-P005",
        "seq_no": "P005",
        "risk_type": "pattern",
        "risk_title": "疑似拆分支付",
        "check_goal": "检查是否存在为规避审批、限额或授权而拆分支付的情况",
        "expected_documents": ["交易流水", "付款审批单", "授权审批制度", "合同"],
        "check_methods": ["数据分析", "核对"],
        "output_fields": [
            "has_issue",
            "status",
            "issue_description",
            "amount_involved",
            "risk_level",
            "rectification_suggestion",
            "evidence",
            "missing_documents",
            "remark"
        ],
        "hidden_source": {
            "source_type": "internal_pattern_extension"
        }
    },
    {
        "framework_id": "ISSUE-P006",
        "seq_no": "P006",
        "risk_type": "pattern",
        "risk_title": "高频报销异常",
        "check_goal": "检查是否存在短期内频繁发生报销类交易、摘要相似或金额异常的情况",
        "expected_documents": ["交易流水", "报销单", "审批记录", "发票"],
        "check_methods": ["数据分析", "核对"],
        "output_fields": [
            "has_issue",
            "status",
            "issue_description",
            "amount_involved",
            "risk_level",
            "rectification_suggestion",
            "evidence",
            "missing_documents",
            "remark"
        ],
        "hidden_source": {
            "source_type": "internal_pattern_extension"
        }
    },
    {
        "framework_id": "ISSUE-P007",
        "seq_no": "P007",
        "risk_type": "pattern",
        "risk_title": "重复摘要或重复金额交易",
        "check_goal": "检查是否存在摘要重复、金额重复、日期接近的可疑重复交易",
        "expected_documents": ["交易流水", "合同", "发票", "付款申请"],
        "check_methods": ["数据分析", "核对"],
        "output_fields": [
            "has_issue",
            "status",
            "issue_description",
            "amount_involved",
            "risk_level",
            "rectification_suggestion",
            "evidence",
            "missing_documents",
            "remark"
        ],
        "hidden_source": {
            "source_type": "internal_pattern_extension"
        }
    },
    {
        "framework_id": "ISSUE-P008",
        "seq_no": "P008",
        "risk_type": "pattern",
        "risk_title": "长期挂账或账龄异常",
        "check_goal": "检查是否存在长期挂账、账龄异常、长期未清理往来的情况",
        "expected_documents": ["往来明细账", "账龄分析表", "催收记录", "签认记录"],
        "check_methods": ["数据分析", "审阅"],
        "output_fields": [
            "has_issue",
            "status",
            "issue_description",
            "amount_involved",
            "risk_level",
            "rectification_suggestion",
            "evidence",
            "missing_documents",
            "remark"
        ],
        "hidden_source": {
            "source_type": "internal_pattern_extension"
        }
    }
]


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def upgrade_issue_framework():
    if not FRAMEWORK_FILE.exists():
        raise FileNotFoundError(f"找不到文件: {FRAMEWORK_FILE}")

    original_items = load_json(FRAMEWORK_FILE)

    if not isinstance(original_items, list):
        raise ValueError("issue_framework.json 必须是 JSON 数组（list）")

    # 先备份原文件
    save_json(BACKUP_FILE, original_items)

    upgraded_items = []

    # 先插入新增的 pattern 风险
    upgraded_items.extend(PATTERN_RISKS)

    # 再处理原有项目，统一加 risk_type=advanced
    for item in original_items:
        new_item = dict(item)
        new_item["risk_type"] = "advanced"

        # 保证字段顺序更整齐
        ordered_item = {
            "framework_id": new_item.get("framework_id", ""),
            "seq_no": new_item.get("seq_no", ""),
            "risk_type": new_item.get("risk_type", "advanced"),
            "risk_title": new_item.get("risk_title", ""),
            "check_goal": new_item.get("check_goal", ""),
            "expected_documents": new_item.get("expected_documents", []),
            "check_methods": new_item.get("check_methods", []),
            "output_fields": new_item.get("output_fields", [
                "has_issue",
                "status",
                "issue_description",
                "amount_involved",
                "risk_level",
                "rectification_suggestion",
                "evidence",
                "missing_documents",
                "remark"
            ]),
            "hidden_source": new_item.get("hidden_source", {})
        }

        upgraded_items.append(ordered_item)

    save_json(FRAMEWORK_FILE, upgraded_items)

    print("升级完成")
    print(f"原文件备份到: {BACKUP_FILE}")
    print(f"新文件写入到: {FRAMEWORK_FILE}")
    print(f"pattern 风险条数: {len(PATTERN_RISKS)}")
    print(f"advanced 风险条数: {len(original_items)}")
    print(f"总条数: {len(upgraded_items)}")


if __name__ == "__main__":
    upgrade_issue_framework()