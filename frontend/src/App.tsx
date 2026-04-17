import { useEffect, useMemo, useRef, useState } from "react";

const API_BASE = "http://127.0.0.1:8000";
const UPLOAD_ENDPOINT = `${API_BASE}/upload`;
const CHAT_ENDPOINT = `${API_BASE}/chat`;
const PROJECTS_ENDPOINT = `${API_BASE}/projects`;

type Workpaper = {
  workpaper_id: number;
  risk_title: string;
  filename: string;
  download_url: string;
  file_type?: "pdf" | "docx";
  pdf_error?: string;
};

type RiskFinding = {
  issue_id?: string;
  title: string;
  risk_level: string;
  resolution_status?: string;
  description: string;
  amount_involved?: number | null;
  evidence?: string[];
  suggested_actions?: string[];
};

type AdditionalFinding = {
  title: string;
  risk_level: string;
  description: string;
  evidence?: string[];
  suggested_actions?: string[];
};

type InspectionResult = {
  area: string;
  topic: string;
  status: string;
  judgment: string;
  evidence?: string[];
  missing_documents?: string[];
  remark?: string;
};

type OverallSummary = {
  overall_risk_level?: string;
  summary?: string;
  recommended_next_steps?: string[];
};

type FinalResult = {
  inspection_results?: InspectionResult[];
  risk_findings?: RiskFinding[];
  additional_findings?: AdditionalFinding[];
  overall_summary?: OverallSummary;
};

type AuditResponse = {
  task_id?: number;
  project_id?: number;
  parent_task_id?: number | null;
  user_input?: string;
  file_paths?: string[];
  messages?: string[];
  observations?: unknown[];
  inspection_results?: InspectionResult[];
  risk_findings?: RiskFinding[];
  additional_findings?: AdditionalFinding[];
  final_result?: FinalResult | string;
  workpapers?: Workpaper[];
};

type Project = {
  project_id: number;
  audited_entity_name: string;
  project_name: string;
  audit_items: string[];
  description?: string;
  created_at: string;
};

type ProjectDetail = Project & {
  tasks?: { task_id: number; parent_task_id?: number | null; created_at: string }[];
};


function safeParseFinalResult(input: AuditResponse["final_result"]): FinalResult | null {
  if (!input) return null;
  if (typeof input === "object") return input as FinalResult;
  if (typeof input === "string") {
    try {
      return JSON.parse(input) as FinalResult;
    } catch {
      return null;
    }
  }
  return null;
}

function basename(path: string) {
  if (!path) return "";
  return path.split("\\").pop()?.split("/").pop() ?? path;
}

function toTitleCase(value?: string) {
  if (!value) return "Low";
  return value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();
}

function countMissingDocuments(items: InspectionResult[]) {
  const set = new Set<string>();
  items.forEach((item) => {
    (item.missing_documents ?? []).forEach((doc) => set.add(doc));
  });
  return set.size;
}

export default function TraeInspiredAuditWorkbench() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const rerunFileInputRef = useRef<HTMLInputElement | null>(null);

  const [taskText, setTaskText] = useState("帮我检查这些材料是否存在异常交易，并给出结构化审计分析。");
  const [rerunText, setRerunText] = useState("结合补充资料继续复查这个任务");
  const [parentTaskId, setParentTaskId] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadedFilePaths, setUploadedFilePaths] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const [rerunSelectedFiles, setRerunSelectedFiles] = useState<File[]>([]);
  const [rerunUploadedFilePaths, setRerunUploadedFilePaths] = useState<string[]>([]);
  const [rerunDragging, setRerunDragging] = useState(false);

  const [result, setResult] = useState<AuditResponse | null>(null);
  const [workpapers, setWorkpapers] = useState<Workpaper[]>([]);

  const [analyzing, setAnalyzing] = useState(false);
  const [rerunning, setRerunning] = useState(false);
  const [fetchingTask, setFetchingTask] = useState(false);

  const [projects, setProjects] = useState<Project[]>([]);
 const [currentProject, setCurrentProject] = useState<Project | null>(null);

 const [projectModalOpen, setProjectModalOpen] = useState(false);
 const [creatingProject, setCreatingProject] = useState(false);

 const [auditedEntityName, setAuditedEntityName] = useState("");
 const [projectName, setProjectName] = useState("");
 const [auditItemsText, setAuditItemsText] = useState("");
 const [projectDescription, setProjectDescription] = useState("");

  const finalResult = useMemo(() => safeParseFinalResult(result?.final_result) ?? null, [result]);

  const inspectionResults: InspectionResult[] =
    finalResult?.inspection_results ?? result?.inspection_results ?? [];

  const riskFindings: RiskFinding[] =
    finalResult?.risk_findings ?? result?.risk_findings ?? [];

  const additionalFindings: AdditionalFinding[] =
    finalResult?.additional_findings ?? result?.additional_findings ?? [];

  const overallSummary: OverallSummary =
    finalResult?.overall_summary ?? {
      overall_risk_level: "low",
      summary: "本轮主要事项已获得初步业务解释，但仍需补发票、验收资料、差旅申请单等关键材料完成闭环核查。",
      recommended_next_steps: [
        "补充发票与验收资料",
        "补充工程验收单与立项资料",
        "补充差旅申请单与住宿明细",
        "补充资金管理制度与账户资料",
      ],
    };

  const currentFiles = useMemo(() => {
    if (selectedFiles.length > 0) return selectedFiles.map((f) => f.name);
    if ((result?.file_paths ?? []).length > 0) return (result?.file_paths ?? []).map(basename);
    return [
      "data.xlsx",
      "contract_b_company.txt",
      "approval_b_company.txt",
      "travel_reimbursement_d_company.txt",
      "contract_c_company.txt",
    ];
  }, [selectedFiles, result?.file_paths]);

  const riskCards = useMemo(() => {
    const merged = [
      ...riskFindings.map((item) => ({
        title: item.title,
        level: toTitleCase(item.risk_level),
        status: item.resolution_status
          ? item.resolution_status
              .replaceAll("_", " ")
              .replace(/\b\w/g, (c) => c.toUpperCase())
          : "Open",
        amount:
          typeof item.amount_involved === "number"
            ? `¥${item.amount_involved.toLocaleString("zh-CN")}`
            : "—",
        description: item.description,
        evidence: item.evidence ?? [],
      })),
      ...additionalFindings.map((item) => ({
        title: item.title,
        level: toTitleCase(item.risk_level),
        status: "Additional Finding",
        amount: "—",
        description: item.description,
        evidence: item.evidence ?? [],
      })),
    ];

    if (merged.length > 0) return merged;

    return [
      {
        title: "同日多笔付款待闭环核查",
        level: "Low",
        status: "Pending Closure",
        amount: "¥357,500",
        description:
          "B 公司三笔设备采购付款已获得合同与审批单的初步解释，当前重点是补发票与验收资料。",
        evidence: ["合同 HT-B-2026-001", "审批单 APP-B-2026-001", "2026-01-03 三笔付款"],
      },
      {
        title: "大额交易待闭环核查",
        level: "Low",
        status: "Pending Closure",
        amount: "¥300,000",
        description:
          "C 公司工程款与合同金额一致，仍需补工程验收单、付款审批单与项目立项资料。",
        evidence: ["合同 HT-C-2026-003", "一次性支付", "工程款 300000"],
      },
      {
        title: "差旅报销待闭环核查",
        level: "Low",
        status: "Pending Closure",
        amount: "¥8,000",
        description:
          "D 公司差旅报销已有业务背景说明，下一步核查申请单、发票和住宿明细。",
        evidence: ["TR-D-2026-001", "客户拜访差旅", "财务复核完成"],
      },
    ];
  }, [riskFindings, additionalFindings]);

  const inspectionRows = useMemo(() => {
    if (inspectionResults.length > 0) {
      return inspectionResults.map((item) => [
        item.topic,
        item.status,
        (item.missing_documents ?? []).join(" / ") || "—",
      ] as const);
    }

    return [
      ["资金管理制度建设与执行情况", "Insufficient Evidence", "制度文件 / 内控流程 / 审批流程"],
      ["银行账户资金管理情况", "Insufficient Evidence", "开户资料 / 余额调节表 / 检查记录"],
      ["财务人员配备与管理情况", "Insufficient Evidence", "岗位职责 / 轮岗记录 / 交接记录"],
      ["网银U盾、印鉴及重要票证管理", "Insufficient Evidence", "管理台账 / 保管记录 / 使用记录"],
    ] as const;
  }, [inspectionResults]);

  const currentTaskId = result?.task_id ? String(result.task_id) : "task_0016";
  const currentParentTaskId =
    result?.parent_task_id !== undefined && result?.parent_task_id !== null
      ? String(result.parent_task_id)
      : parentTaskId || "15";

  const overallRiskLevel = toTitleCase(overallSummary.overall_risk_level);
  const riskCount = riskCards.length;
  const missingDocCount = inspectionResults.length > 0 ? countMissingDocuments(inspectionResults) : 8;
  const isRerunMode = rerunning || !!result?.parent_task_id;

useEffect(() => {
  fetchProjects()
    .then((data) => {
      setProjects(data);

      if (data.length > 0 && !currentProject) {
        setCurrentProject(data[0]);
      }
    })
    .catch((error) => {
      console.error(error);
    });
}, []);

  function openFilePicker() {
    fileInputRef.current?.click();
  }

  function addFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    const incoming = Array.from(fileList);

    setSelectedFiles((prev) => {
      const map = new Map<string, File>();
      [...prev, ...incoming].forEach((file) => {
        map.set(`${file.name}_${file.size}_${file.lastModified}`, file);
      });
      return Array.from(map.values());
    });
  }

  function onInputFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    addFiles(event.target.files);
    event.target.value = "";
  }

  function onDragOver(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(true);
  }

  function onDragLeave(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
  }

  function onDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    addFiles(event.dataTransfer.files);
  }
function openRerunFilePicker() {
  rerunFileInputRef.current?.click();
}

function addRerunFiles(fileList: FileList | null) {
  if (!fileList || fileList.length === 0) return;
  const incoming = Array.from(fileList);

  setRerunSelectedFiles((prev) => {
    const map = new Map<string, File>();
    [...prev, ...incoming].forEach((file) => {
      map.set(`${file.name}_${file.size}_${file.lastModified}`, file);
    });
    return Array.from(map.values());
  });
}

function onRerunInputFileChange(event: React.ChangeEvent<HTMLInputElement>) {
  addRerunFiles(event.target.files);
  event.target.value = "";
}

function onRerunDragOver(event: React.DragEvent<HTMLDivElement>) {
  event.preventDefault();
  setRerunDragging(true);
}

function onRerunDragLeave(event: React.DragEvent<HTMLDivElement>) {
  event.preventDefault();
  setRerunDragging(false);
}

function onRerunDrop(event: React.DragEvent<HTMLDivElement>) {
  event.preventDefault();
  setRerunDragging(false);
  addRerunFiles(event.dataTransfer.files);
}
  async function uploadFiles(filesToUpload: File[]): Promise<string[]> {
  if (filesToUpload.length === 0) {
    return [];
  }

  const formData = new FormData();
  filesToUpload.forEach((file) => formData.append("files", file));

  const response = await fetch(UPLOAD_ENDPOINT, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`上传失败：${text}`);
  }

  const data = await response.json();
  const serverPaths: string[] =
    data.file_paths ?? data.paths ?? data.data?.file_paths ?? [];

  if (!Array.isArray(serverPaths) || serverPaths.length === 0) {
    throw new Error("上传接口未返回 file_paths。");
  }

  return serverPaths;
}

async function uploadSelectedFiles(): Promise<string[]> {
  if (selectedFiles.length === 0) {
    return uploadedFilePaths.length > 0 ? uploadedFilePaths : result?.file_paths ?? [];
  }

  const serverPaths = await uploadFiles(selectedFiles);
  setUploadedFilePaths(serverPaths);
  return serverPaths;
}

async function uploadRerunSelectedFiles(): Promise<string[]> {
  if (rerunSelectedFiles.length === 0) {
    return rerunUploadedFilePaths.length > 0 ? rerunUploadedFilePaths : [];
  }

  const serverPaths = await uploadFiles(rerunSelectedFiles);
  setRerunUploadedFilePaths(serverPaths);
  return serverPaths;
}

  async function postJson<T>(url: string, body: unknown): Promise<T> {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `请求失败：${response.status}`);
    }

    return (await response.json()) as T;
  }

  async function fetchTaskById(taskId: string): Promise<AuditResponse> {
    const response = await fetch(`${API_BASE}/tasks/${taskId}`, {
      method: "GET",
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `读取任务失败：${response.status}`);
    }

    return (await response.json()) as AuditResponse;
  }

  async function handleAnalyze() {
  try {
    if (!currentProject) {
      alert("请先创建或选择审计项目。");
      return;
    }

    setAnalyzing(true);

    let filePaths = await uploadRerunSelectedFiles();

    if (filePaths.length === 0) {
      filePaths = await uploadSelectedFiles();
    }

    if (filePaths.length === 0) {
      filePaths = result?.file_paths ?? [];
    }

    const data = await postJson<AuditResponse>(
      `${API_BASE}/projects/${currentProject.project_id}/chat`,
      {
        text: taskText,
        file_paths: filePaths,
      }
    );

    setResult(data);
    setParentTaskId(String(data.task_id ?? ""));
    setWorkpapers(data.workpapers ?? []);
  } catch (error) {
    console.error(error);
    alert(error instanceof Error ? error.message : "开始分析失败。");
  } finally {
    setAnalyzing(false);
  }
}

  async function handleRerun() {
    try {
      const targetTaskId = parentTaskId || (result?.task_id ? String(result.task_id) : "");
      if (!targetTaskId) {
        alert("请先分析一次，或输入 Parent Task ID。");
        return;
      }

      setRerunning(true);
      const filePaths = await uploadSelectedFiles();

      const data = await postJson<AuditResponse>(`${API_BASE}/tasks/${targetTaskId}/rerun`, {
        text: rerunText,
        file_paths: filePaths,
      });

      setResult(data);
      setParentTaskId(String(data.parent_task_id ?? targetTaskId));
      setWorkpapers(data.workpapers ?? []);

    } catch (error) {
      console.error(error);
      alert(error instanceof Error ? error.message : "继续复查失败。");
    } finally {
      setRerunning(false);
    }
  }

  async function handleOpenTask() {
  const id = window.prompt("请输入要查看的 task_id");
  if (!id) return;

  try {
    setFetchingTask(true);
    const data = await fetchTaskById(id.trim());

    setResult(data);
    setParentTaskId(String(data.parent_task_id ?? data.task_id ?? ""));
    setTaskText(data.user_input ?? taskText);
    setUploadedFilePaths(data.file_paths ?? []);
    setSelectedFiles([]);
    setWorkpapers(data.workpapers ?? []);

    if (data.project_id) {
      const matched = projects.find((p) => p.project_id === data.project_id);

      if (matched) {
        setCurrentProject(matched);
      } else {
        try {
          const response = await fetch(`${API_BASE}/projects/${data.project_id}`);
          if (response.ok) {
            const project = (await response.json()) as ProjectDetail;
            setCurrentProject(project);
            setProjects((prev) => [
              project,
              ...prev.filter((p) => p.project_id !== project.project_id),
            ]);
          }
        } catch (error) {
          console.error(error);
        }
      }
    }
  } catch (error) {
    console.error(error);
    alert(error instanceof Error ? error.message : "读取任务失败。");
  } finally {
    setFetchingTask(false);
  }
}

async function fetchProjects(): Promise<Project[]> {
  const response = await fetch(PROJECTS_ENDPOINT, { method: "GET" });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "读取项目列表失败");
  }
  return (await response.json()) as Project[];
}

async function createProject() {
  if (!auditedEntityName.trim() || !projectName.trim() || !auditItemsText.trim()) {
    alert("请填写被审单位名称、审计项目名称和审计事项。");
    return;
  }

  try {
    setCreatingProject(true);

    const auditItems = auditItemsText
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);

    const response = await fetch(PROJECTS_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        audited_entity_name: auditedEntityName.trim(),
        project_name: projectName.trim(),
        audit_items: auditItems,
        description: projectDescription.trim(),
      }),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || "创建项目失败");
    }

    const project = (await response.json()) as Project;

    setProjects((prev) => [project, ...prev]);
    setCurrentProject(project);

    setProjectModalOpen(false);
    setAuditedEntityName("");
    setProjectName("");
    setAuditItemsText("");
    setProjectDescription("");

    handleResetNewAnalysis();
  } catch (error) {
    console.error(error);
    alert(error instanceof Error ? error.message : "创建项目失败。");
  } finally {
    setCreatingProject(false);
  }
}

  function handleResetNewAnalysis() {
  setResult(null);
  setWorkpapers([]);
  setTaskText("帮我检查这些材料是否存在异常交易，并给出结构化审计分析。");
  setRerunText("结合补充资料继续复查这个任务");
  setParentTaskId("");
  setSelectedFiles([]);
  setUploadedFilePaths([]);
  setRerunSelectedFiles([]);
  setRerunUploadedFilePaths([]);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

  return (
    <div className="min-h-screen bg-[#0A0B10] text-white">
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={onInputFileChange}
      />
      <input
       ref={rerunFileInputRef}
       type="file"
       multiple
       className="hidden"
       onChange={onRerunInputFileChange}
      />

      <div className="relative overflow-hidden border-b border-white/10 bg-[radial-gradient(circle_at_top,rgba(214,116,255,0.22),transparent_35%),radial-gradient(circle_at_80%_20%,rgba(255,110,110,0.16),transparent_28%),linear-gradient(180deg,#0D0F16_0%,#0A0B10_100%)]">
        <div className="mx-auto max-w-7xl px-6 py-8 lg:px-8">
          <div className="mb-8 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white/10 text-lg font-semibold backdrop-blur">
                A
              </div>
              <div>
                <div className="text-sm text-white/60">Audit Agent</div>
                <div className="text-base font-medium">智能审计工作台</div>
              </div>
            </div>
            <div className="hidden items-center gap-3 md:flex">
              <button
                onClick={handleOpenTask}
                disabled={fetchingTask}
                className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/80 backdrop-blur hover:bg-white/10 disabled:opacity-60"
              >
                {fetchingTask ? "读取中..." : "任务历史"}
              </button>
               <button
                onClick={() => setProjectModalOpen(true)}
                className="rounded-xl bg-gradient-to-r from-[#FF6B6B] to-[#C77DFF] px-4 py-2 text-sm font-medium text-white shadow-lg shadow-fuchsia-900/30 transition hover:brightness-110 hover:shadow-[0_0_24px_rgba(217,167,255,0.24)] active:scale-[0.99]"
               >
                新建项目
               </button>
              </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr] lg:items-stretch">
            <div className="flex h-full min-h-[320px] flex-col pt-2 lg:min-h-[360px] lg:pt-4">
              <div className="mb-4 inline-flex items-center rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/70 backdrop-blur">
                Multi-material Audit · Inspection + Risk + Rerun
              </div>
              <h1 className="max-w-5xl pb-2 text-5xl font-semibold leading-[1.02] tracking-tight md:text-7xl lg:text-[92px]">
                <span className="block text-white">让复杂审计</span>
                <span className="mt-2 block bg-gradient-to-r from-[#FF8F8F] to-[#D9A7FF] bg-clip-text text-transparent">
                  更快形成判断
                </span>
              </h1>
              <div className="mt-auto flex flex-wrap gap-3 pt-8">
                <button
                 onClick={handleAnalyze}
                 disabled={analyzing}
                 className="rounded-2xl bg-gradient-to-r from-[#FF6B6B] to-[#C77DFF] px-5 py-3 text-sm font-medium text-white shadow-xl shadow-fuchsia-900/30 transition hover:brightness-110 hover:shadow-[0_0_28px_rgba(217,167,255,0.28)] active:scale-[0.99] disabled:opacity-60 disabled:hover:brightness-100 disabled:hover:shadow-xl"
                >
                 {analyzing ? "分析中..." : "开始分析"}
                </button>
                <button
                 onClick={handleRerun}
                 disabled={rerunning}
                 className="rounded-2xl border border-white/10 bg-white/5 px-5 py-3 text-sm text-white/80 backdrop-blur transition hover:border-white/20 hover:bg-white/10 hover:text-white active:scale-[0.99] disabled:opacity-60 disabled:hover:border-white/10 disabled:hover:bg-white/5 disabled:hover:text-white/80"
                >
                {rerunning ? "复查中..." : "继续复查"}
                </button>
              </div>
            </div>

            <div className="rounded-[28px] border border-white/10 bg-white/5 p-4 shadow-2xl shadow-black/40 backdrop-blur-xl">
              <div className="rounded-[24px] border border-white/10 bg-[#0F1118] p-4">
                <div className="mb-4 flex items-start justify-between">
                 <div className="space-y-3">
                  <div>
                   <div className="text-xs text-white/45">Current Task</div>
                    <div className="mt-1 text-sm font-medium">
                     {currentTaskId
                       ? `${currentTaskId}${result?.parent_task_id ? ` · parent ${currentParentTaskId}` : ""}`
                        : "task_0016 · 补充材料复查"}
                  </div>
               </div>

             <div>
               <div className="text-xs text-white/45">Current Project</div>
               <div className="mt-1 text-sm font-medium">
                  {currentProject ? currentProject.project_name : "未选择项目"}
               </div>
                 {currentProject && (
                 <div className="mt-1 text-xs text-white/55">
                  {currentProject.audited_entity_name}
               </div>
                )}
              </div>
             </div>

             <div className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs text-emerald-300">
                {analyzing || rerunning ? "Running" : "Stable"}
             </div>
          </div>
                <div className="grid grid-cols-3 gap-3">
                  <Metric title="风险等级" value={overallRiskLevel} />
                  <Metric title="风险事项" value={String(riskCount)} />
                  <Metric title="待补材料" value={String(missingDocCount)} />
                </div>
                <div className="mt-4 rounded-2xl border border-white/10 bg-black/25 p-4">
                  <div className="text-xs text-white/45">Overall Summary</div>
                  <p className="mt-2 text-sm leading-6 text-white/80">
                    {overallSummary.summary ||
                      "本轮主要事项已获得初步业务解释，但仍需补发票、验收资料、差旅申请单等关键材料完成闭环核查。"}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto grid max-w-7xl gap-6 px-6 py-6 lg:grid-cols-[260px_minmax(0,1fr)_360px] lg:px-8">
        <aside className="rounded-[28px] border border-white/10 bg-white/5 p-4 backdrop-blur-xl">
          <SectionTitle eyebrow="Workspace" title="任务与材料" />
          <div className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4">
             <div className="text-xs text-white/45">当前项目</div>
             {currentProject ? (
               <div className="mt-3 space-y-2">
                <div className="text-sm font-medium text-white">{currentProject.project_name}</div>
                <div className="text-xs text-white/60">被审单位：{currentProject.audited_entity_name}</div>
                <div className="text-xs text-white/60">
                  审计事项：{currentProject.audit_items.join(" / ")}
                </div>
              </div>
           ) : (
               <div className="mt-3 text-xs text-white/50">尚未创建审计项目</div>
            )}
        </div>
          <div className="mt-4 space-y-3">
           <NavItem active onClick={handleResetNewAnalysis}>新建分析</NavItem>
           <NavItem onClick={() => document.getElementById("rerun-panel")?.scrollIntoView({ behavior: "smooth" })}>
            继续复查
           </NavItem>
           <NavItem onClick={handleOpenTask}>历史任务</NavItem>
           <NavItem onClick={() => document.getElementById("risk-panel")?.scrollIntoView({ behavior: "smooth" })}>
           风险库
           </NavItem>
          </div>

          <div className="mt-6 rounded-2xl border border-white/10 bg-black/20 p-4">
            <div className="text-sm font-medium">本轮材料</div>
            <div className="mt-3 space-y-2">
              {currentFiles.map((file) => (
                <div
                 key={file}
                 className="max-w-full break-all rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs leading-5 text-white/70"
                >
                 {file}
                </div>
              ))}
            </div>
          </div>
        </aside>

        <main className="space-y-6">
          <section className="rounded-[28px] border border-white/10 bg-white/5 p-5 backdrop-blur-xl">
            <SectionTitle eyebrow="Input" title="任务输入区" />
            <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_220px]">
              <div className="space-y-4">
                <div>
                  <label className="mb-2 block text-sm text-white/65">任务描述</label>
                  <textarea
                    className="min-h-[120px] w-full rounded-2xl border border-white/10 bg-black/25 px-4 py-3 text-sm text-white outline-none placeholder:text-white/30"
                    value={taskText}
                    onChange={(e) => setTaskText(e.target.value)}
                  />
                </div>
                <div>
                  <label className="mb-2 block text-sm text-white/65">审计材料</label>
                  <div
                    onClick={openFilePicker}
                    onDragOver={onDragOver}
                    onDragLeave={onDragLeave}
                    onDrop={onDrop}
                    className={`rounded-2xl border border-dashed p-4 text-sm transition ${
                      dragging
                        ? "border-fuchsia-400/40 bg-fuchsia-400/10 text-white/80"
                        : "border-white/10 bg-black/20 text-white/50"
                    } cursor-pointer`}
                  >
                    {selectedFiles.length === 0 ? (
                      <div className="space-y-2">
                        <div>拖拽文件到这里，或点击选择文件</div>
                        <div className="text-xs text-white/35">
                          支持多材料输入，文件会先上传到后端，再进入智能体分析。
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <div className="text-white/75">已添加 {selectedFiles.length} 份材料</div>
                        <div className="space-y-1">
                          {selectedFiles.map((file) => (
                            <div key={`${file.name}_${file.size}`} className="text-xs text-white/55">
                              {file.name}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="text-sm font-medium">当前模式</div>
                <div className="mt-3 space-y-2 text-sm text-white/65">
                <ModeChip active={!isRerunMode}>Inspection</ModeChip>
                <ModeChip active={!isRerunMode}>Risk</ModeChip>
                <ModeChip active={isRerunMode}>Rerun</ModeChip>
                </div>
                <button
                 onClick={handleAnalyze}
                 disabled={analyzing}
                 className="mt-6 w-full rounded-2xl bg-gradient-to-r from-[#FF6B6B] to-[#C77DFF] px-4 py-3 text-sm font-medium text-white shadow-lg shadow-fuchsia-900/20 transition hover:brightness-110 hover:shadow-[0_0_24px_rgba(217,167,255,0.24)] active:scale-[0.99] disabled:opacity-60 disabled:hover:brightness-100 disabled:hover:shadow-lg"
                 >
                 {analyzing ? "运行中..." : "运行分析"}
               </button>
              </div>
            </div>
          </section>

          <section
           id="risk-panel"
           className="rounded-[28px] border border-white/10 bg-white/5 p-5 backdrop-blur-xl"
          >
           <SectionTitle eyebrow="Risk Findings" title="风险事项" />
            <div className="mt-4 grid gap-4 xl:grid-cols-2">
              {riskCards.map((card) => (
                <article key={`${card.title}_${card.amount}`} className="rounded-[24px] border border-white/10 bg-black/20 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-medium leading-6 text-white">{card.title}</h3>
                      <p className="mt-1 text-xs text-white/45">{card.amount}</p>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <Pill>{card.level}</Pill>
                      <Pill subtle>{card.status}</Pill>
                    </div>
                  </div>
                  <p className="mt-4 break-words text-sm leading-6 text-white/72">{card.description}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {card.evidence.map((item) => (
                      <span
                       key={item}
                       className="max-w-full break-all rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs leading-5 text-white/60"
                      >
                       {item}
                       </span>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="rounded-[28px] border border-white/10 bg-white/5 p-5 backdrop-blur-xl">
            <SectionTitle eyebrow="Inspection" title="检查项结果" />
            <div className="mt-4 overflow-hidden rounded-2xl border border-white/10">
              <table className="w-full text-left text-sm">
                <thead className="bg-white/5 text-white/50">
                  <tr>
                    <th className="px-4 py-3 font-medium">主题</th>
                    <th className="w-[170px] px-4 py-3 font-medium">状态</th>
                    <th className="px-4 py-3 font-medium">缺失材料</th>
                  </tr>
                </thead>
                <tbody>
                  {inspectionRows.map(([topic, status, missing]) => (
                    <tr key={topic} className="border-t border-white/10 bg-black/15 text-white/80">
                      <td className="px-4 py-3">{topic}</td>
                      <td className="w-[170px] px-4 py-3">
                        <span className="inline-flex min-w-[148px] justify-center whitespace-nowrap rounded-full border border-amber-400/20 bg-amber-400/10 px-3 py-1 text-xs text-amber-300">
                         {status}
                         </span>
                      </td>
                      <td className="px-4 py-3 text-white/58">{missing}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </main>

        <aside className="space-y-6">
          <section
           id="rerun-panel"
           className="rounded-[28px] border border-white/10 bg-white/5 p-4 backdrop-blur-xl"
          >
           <SectionTitle eyebrow="Rerun" title="补充材料复查" />
            <div className="mt-4 space-y-3">
              <Field
                label="Parent Task ID"
                value={parentTaskId || currentParentTaskId}
                editable
                onChange={setParentTaskId}
              />
              <Field
                label="Current Task ID"
                value={result?.task_id ? String(result.task_id) : "—"}
              />
              <Field
                label="复查说明"
                value={rerunText}
                large
                editable
                onChange={setRerunText}
              />
              <div>
  <div className="mb-2 text-xs text-white/45">补充材料</div>
  <div
    onClick={openRerunFilePicker}
    onDragOver={onRerunDragOver}
    onDragLeave={onRerunDragLeave}
    onDrop={onRerunDrop}
    className={`rounded-2xl border border-dashed p-4 text-sm transition ${
      rerunDragging
        ? "border-fuchsia-400/40 bg-fuchsia-400/10 text-white/80"
        : "border-white/10 bg-black/20 text-white/50"
    } cursor-pointer`}
  >
    {rerunSelectedFiles.length === 0 ? (
      <div className="space-y-2">
        <div>拖拽补充材料到这里，或点击选择文件</div>
        <div className="text-xs text-white/35">
          这批文件将优先用于当前任务的复查分析。
        </div>
      </div>
    ) : (
      <div className="space-y-2">
        <div className="text-white/75">已添加 {rerunSelectedFiles.length} 份补充材料</div>
        <div className="space-y-1">
          {rerunSelectedFiles.map((file) => (
            <div
              key={`${file.name}_${file.size}_${file.lastModified}`}
              className="text-xs text-white/55"
            >
              {file.name}
            </div>
          ))}
        </div>
      </div>
    )}
  </div>
</div>
              <button
               onClick={handleRerun}
               disabled={rerunning}
               className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white/80 transition hover:border-white/20 hover:bg-white/10 hover:text-white active:scale-[0.99] disabled:opacity-60 disabled:hover:border-white/10 disabled:hover:bg-white/5 disabled:hover:text-white/80"
              >
               {rerunning ? "继续复查中..." : "继续复查"}
              </button>
            </div>
          </section>

                    <section className="rounded-[28px] border border-white/10 bg-white/5 p-4 backdrop-blur-xl">
            <SectionTitle eyebrow="Next Steps" title="建议动作" />
            <div className="mt-4 space-y-3">
              {(overallSummary.recommended_next_steps ?? []).map((step) => (
                <div
                  key={step}
                  className="rounded-2xl border border-white/10 bg-black/20 p-3 text-sm leading-6 text-white/72"
                >
                  {step}
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-[28px] border border-white/10 bg-white/5 p-4 backdrop-blur-xl">
            <SectionTitle eyebrow="Workpapers" title="审计底稿" />
            <div className="mt-4 space-y-3">
              {workpapers.length > 0 ? (
                workpapers.map((wp) => (
                  <div
                    key={wp.workpaper_id}
                    className="rounded-2xl border border-white/10 bg-black/20 p-3"
                  >
                    <div className="text-sm font-medium text-white break-words">
                      {wp.risk_title}
                    </div>
                    <div className="mt-1 text-xs text-white/55 break-all">
                      {wp.filename}
                    </div>
                    <a
                     href={`${API_BASE}${wp.download_url}`}
                     target="_blank"
                     rel="noreferrer"
                     className="mt-3 inline-block rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/80 transition hover:bg-white/10"
                    >
                     下载 {wp.file_type?.toUpperCase() || "PDF"}
                   </a>
                   {wp.pdf_error && (
                  <div className="mt-2 text-[11px] leading-5 text-amber-300/80">
                   PDF 转换失败，当前提供 DOCX 下载。
                  </div>
                  )}
                  </div>
                ))
              ) : (
                <div className="rounded-2xl border border-white/10 bg-black/20 p-3 text-sm text-white/50">
                  当前任务尚未生成审计底稿
                </div>
              )}
            </div>
          </section>
        </aside>
      </div>
      {projectModalOpen && (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 backdrop-blur-sm">
    <div className="w-full max-w-2xl rounded-[28px] border border-white/10 bg-[#12141D] p-6 shadow-2xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.18em] text-white/35">Project</div>
          <h2 className="mt-1 text-2xl font-semibold text-white">新建审计项目</h2>
        </div>
        <button
          onClick={() => setProjectModalOpen(false)}
          className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white/70"
        >
          关闭
        </button>
      </div>

      <div className="space-y-4">
        <div>
          <label className="mb-2 block text-sm text-white/65">被审单位名称</label>
          <input
            value={auditedEntityName}
            onChange={(e) => setAuditedEntityName(e.target.value)}
            className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none"
          />
        </div>

        <div>
          <label className="mb-2 block text-sm text-white/65">审计项目名称</label>
          <input
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none"
          />
        </div>

        <div>
          <label className="mb-2 block text-sm text-white/65">审计事项（每行一项）</label>
          <textarea
            value={auditItemsText}
            onChange={(e) => setAuditItemsText(e.target.value)}
            className="min-h-[120px] w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none"
          />
        </div>

        <div>
          <label className="mb-2 block text-sm text-white/65">项目说明（可选）</label>
          <textarea
            value={projectDescription}
            onChange={(e) => setProjectDescription(e.target.value)}
            className="min-h-[88px] w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none"
          />
        </div>
      </div>

      <div className="mt-6 flex justify-end gap-3">
        <button
          onClick={() => setProjectModalOpen(false)}
          className="rounded-2xl border border-white/10 bg-white/5 px-5 py-3 text-sm text-white/75"
        >
          取消
        </button>
        <button
          onClick={createProject}
          disabled={creatingProject}
          className="rounded-2xl bg-gradient-to-r from-[#FF6B6B] to-[#C77DFF] px-5 py-3 text-sm font-medium text-white disabled:opacity-60"
        >
          {creatingProject ? "创建中..." : "创建项目"}
        </button>
      </div>
    </div>
  </div>
)}
    </div>
  );
}

function SectionTitle({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-[0.18em] text-white/35">{eyebrow}</div>
      <h2 className="mt-1 text-lg font-medium text-white">{title}</h2>
    </div>
  );
}

function NavItem({
  children,
  active = false,
  onClick,
}: {
  children: React.ReactNode;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full rounded-2xl px-4 py-3 text-left text-sm transition ${
        active
          ? "border border-white/10 bg-gradient-to-r from-white/10 to-white/5 text-white"
          : "border border-transparent bg-black/10 text-white/60 hover:border-white/10 hover:bg-white/5 hover:text-white/85"
      }`}
    >
      {children}
    </button>
  );
}

function ModeChip({ children, active = false }: { children: React.ReactNode; active?: boolean }) {
  return (
    <div
      className={`rounded-xl border px-3 py-2 ${
        active ? "border-fuchsia-400/20 bg-fuchsia-400/10 text-fuchsia-200" : "border-white/10 bg-white/5 text-white/55"
      }`}
    >
      {children}
    </div>
  );
}

function Metric({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/25 p-4">
      <div className="text-xs text-white/45">{title}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
}

function Pill({ children, subtle = false }: { children: React.ReactNode; subtle?: boolean }) {
  return (
    <span
      className={`rounded-full px-2.5 py-1 text-xs ${
        subtle
          ? "border border-white/10 bg-white/5 text-white/60"
          : "border border-emerald-400/20 bg-emerald-400/10 text-emerald-300"
      }`}
    >
      {children}
    </span>
  );
}

function Field({
  label,
  value,
  large = false,
  editable = false,
  onChange,
}: {
  label: string;
  value: string;
  large?: boolean;
  editable?: boolean;
  onChange?: (value: string) => void;
}) {
  return (
    <div>
      <div className="mb-2 text-xs text-white/45">{label}</div>
      {editable ? (
        large ? (
          <textarea
            value={value}
            onChange={(e) => onChange?.(e.target.value)}
            className="min-h-[88px] w-full rounded-2xl border border-white/10 bg-black/20 px-3 py-3 text-sm text-white/75 outline-none"
          />
        ) : (
          <input
            value={value}
            onChange={(e) => onChange?.(e.target.value)}
            className="w-full rounded-2xl border border-white/10 bg-black/20 px-3 py-3 text-sm text-white/75 outline-none"
          />
        )
      ) : (
        <div className={`rounded-2xl border border-white/10 bg-black/20 px-3 py-3 text-sm text-white/75 ${large ? "min-h-[88px]" : ""}`}>
          {value}
        </div>
      )}
    </div>
  );
}