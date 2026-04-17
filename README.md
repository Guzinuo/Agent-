# Audit Agent README

面向第一次接触本项目的新手用户的完整上手文档。

这份 README 的目标只有一个：

**让你从 0 开始，把项目成功跑起来。**

无论你是队友、评委老师、测试同学，还是第一次接手这个项目的人，都可以按照这份文档完成：

- 下载项目源码
- 配置开发环境
- 安装依赖
- 启动前后端
- 创建审计项目
- 上传材料并运行分析
- 进行补充材料复查
- 下载审计底稿

---

# 1. 项目简介

Audit Agent 是一个面向审计场景的项目型智能体系统，支持：

- 审计项目创建
- 多材料上传
- 初步分析
- 风险事项识别
- 检查项结果输出
- 补充材料复查（Rerun）
- 审计底稿自动生成与下载

本项目包含两部分：

## 1.1 前端
前端负责页面展示与交互，主要用于：

- 新建审计项目
- 上传审计材料
- 查看风险事项
- 发起 rerun
- 下载底稿

## 1.2 后端
后端负责：

- 接收前端请求
- 调用智能体分析流程
- 管理项目与任务
- 保存上传文件
- 生成审计底稿
- 返回分析结果

---

# 2. 项目目录结构（建议了解）

项目常见结构大致如下：

```text
Agent/
├─ app_main.py                  # FastAPI 后端主入口
├─ app_graph.py                 # 智能体图流程入口
├─ models.py                    # 数据库模型
├─ schemas.py                   # 请求/响应结构定义
├─ database.py                  # 数据库连接
├─ services/
│  └─ workpaper_generator.py    # 底稿生成逻辑
├─ framework/
│  └─ issue_framework.json      # 风险框架
├─ frontend/                    # React 前端
│  ├─ src/
│  │  └─ App.tsx
│  └─ package.json
├─ templates/                   # 底稿模板目录
├─ uploads/                     # 用户上传材料目录
├─ generated_workpapers/        # 自动生成底稿目录
└─ README.md
```

说明：
- `uploads/` 和 `generated_workpapers/` 一般是运行过程中自动生成的。
- `frontend/` 是前端工程目录。

---

# 3. 运行本项目需要准备什么

建议使用：

## 3.1 操作系统
推荐：

- Windows 10 / 11

原因：
- 当前版本的审计底稿 PDF 生成依赖本机 Word 环境
- Windows 环境兼容性最好

## 3.2 必需软件
你需要提前安装：

### （1）Git
用于下载项目源码。

### （2）Miniconda 或 Anaconda
用于创建 Python 运行环境。

推荐：Miniconda。

### （3）Node.js
用于运行前端项目。

### （4）Microsoft Word
如果你要生成 PDF 版审计底稿，建议安装桌面版 Word。

如果没有 Word，通常仍可先生成 DOCX 底稿。

### （5）PyCharm（可选）
方便查看和修改代码。

不用 PyCharm 也能运行，命令行就可以。

---

# 4. 第一步：下载项目源码

如果你已经拿到了 GitHub 仓库地址，例如：

```bash
git clone https://github.com/你的用户名/audit-agent.git
```

然后进入项目目录：

```bash
cd audit-agent
```

如果你不是通过 Git 获取，而是直接拿到压缩包：

1. 解压压缩包
2. 找到项目根目录
3. 用终端进入该目录

例如项目在：

```text
D:\Agent
```

那么在 PowerShell 中进入：

```powershell
cd D:\Agent
```

---

# 5. 第二步：配置 Python 环境

## 5.1 打开终端
建议使用：

- PowerShell
- Anaconda Prompt

## 5.2 创建 Conda 环境

在项目目录外或项目目录内执行都可以：

```powershell
conda create -n Agent python=3.11 -y
```

说明：
- `Agent` 是环境名称
- `python=3.11` 是 Python 版本

## 5.3 激活环境

```powershell
conda activate Agent
```

激活成功后，你会看到终端前面出现：

```text
(Agent)
```

---

# 6. 第三步：安装后端依赖

## 6.1 如果项目里有 requirements.txt
直接执行：

```powershell
pip install -r requirements.txt
```

## 6.2 如果没有 requirements.txt
你可以手动安装当前项目常用依赖：

```powershell
pip install fastapi uvicorn sqlalchemy pydantic python-multipart openai langgraph langchain docxtpl python-docx docx2pdf pywin32
```

说明：
- `fastapi`：后端框架
- `uvicorn`：后端服务启动器
- `sqlalchemy`：数据库 ORM
- `python-multipart`：处理上传文件
- `docxtpl` / `python-docx`：生成 Word 底稿
- `docx2pdf` / `pywin32`：将 Word 转为 PDF

如果安装过程中有单个包报错，可以先记下来，安装完成后再处理。

---

# 7. 第四步：安装前端依赖

## 7.1 进入前端目录

```powershell
cd D:\Agent\frontend
```

## 7.2 安装依赖

```powershell
npm install
```

如果 `npm` 命令无法识别，说明你的 Node.js 还没有安装成功，需要先重新安装 Node.js。

---

# 8. 第五步：确认前后端地址

本地开发模式下，当前项目一般使用：

- 前端地址：`http://localhost:5173`
- 后端地址：`http://127.0.0.1:8000`

也就是说，前端代码中的接口地址通常应该是：

```ts
const API_BASE = "http://127.0.0.1:8000";
```

如果你现在是本机运行，不要改成 ngrok 地址，也不要改成 `/api`。

---

# 9. 第六步：启动后端

回到项目根目录：

```powershell
cd D:\Agent
conda activate Agent
```

然后启动后端：

```powershell
uvicorn app_main:app --reload
```

正常情况下你会看到类似输出：

```text
INFO:     Uvicorn running on http://127.0.0.1:8000
```

这说明后端已经启动成功。

## 9.1 测试后端是否正常
在浏览器打开：

```text
http://127.0.0.1:8000/health
```

如果看到：

```json
{"ok": true}
```

说明后端服务正常。

---

# 10. 第七步：启动前端

打开一个新的终端窗口，进入前端目录：

```powershell
cd D:\Agent\frontend
```

启动前端：

```powershell
npm run dev
```

正常情况下你会看到类似输出：

```text
Local:   http://localhost:5173/
```

然后用浏览器打开：

```text
http://localhost:5173
```

如果页面能正常打开，说明前端启动成功。

---

# 11. 第八步：如何使用系统

## 11.1 新建审计项目
进入页面后，点击右上角“新建项目”。

按提示填写：

- 被审单位名称
- 审计项目名称
- 审计事项（每行一项）
- 项目说明（可选）

点击“创建项目”。

创建成功后，页面会显示当前项目。

---

## 11.2 上传材料并运行分析
在“任务输入区”中：

1. 填写任务描述
2. 拖拽或点击上传材料
3. 点击“开始分析”或“运行分析”

系统会自动：

- 上传材料
- 调用智能体分析
- 返回风险事项、检查项结果和建议动作

---

## 11.3 查看分析结果
分析完成后，你可以在页面中查看：

- 风险事项
- 检查项结果
- 当前风险等级
- 建议动作

如果已经启用了底稿生成，还会看到“审计底稿”下载区。

---

## 11.4 补充材料并进行复查（Rerun）
如果首轮分析后需要进一步补证：

1. 在右侧“补充材料复查”区域上传补充材料
2. 填写复查说明
3. 点击“继续复查”

系统会基于原任务上下文重新分析，输出新的复查结果。

---

## 11.5 下载审计底稿
如果后端已经启用审计底稿生成功能，分析完成后会在右侧看到“审计底稿”区域。

每条风险事项对应一份底稿。

如果 PDF 转换成功，会显示：

- 下载 PDF

如果 PDF 转换失败但 DOCX 已生成，则可能显示：

- 下载 DOCX

---

# 12. 数据与文件保存在哪里

## 12.1 上传材料
默认会保存在：

```text
uploads/
```

## 12.2 自动生成底稿
默认会保存在：

```text
generated_workpapers/
```

## 12.3 数据库
如果项目用的是 SQLite，数据库一般会在项目根目录下，例如：

```text
audit.db
```

建议定期备份：

- `audit.db`
- `uploads/`
- `generated_workpapers/`

---

# 13. 常见问题与解决办法

## 13.1 前端能打开，但分析按钮点了没反应
常见原因：

- 后端没启动
- 前端 `API_BASE` 地址写错
- 浏览器控制台报错

解决方法：

1. 确认后端正在运行
2. 打开 `http://127.0.0.1:8000/health` 检查健康状态
3. 确认 `App.tsx` 中 `API_BASE` 是本地地址

---

## 13.2 点击上传后报错
常见原因：

- 后端缺少 `python-multipart`

解决方法：

```powershell
pip install python-multipart
```

---

## 13.3 PDF 底稿生成失败
常见原因：

- 本机未安装 Microsoft Word
- Word 未正确初始化
- `docx2pdf` 调用 Word COM 失败

解决方法：

1. 确认已安装桌面版 Word
2. 手动打开一次 Word 后再关闭
3. 重新运行分析
4. 若仍失败，先下载 DOCX 版本底稿

---

## 13.4 npm 命令无法识别
说明 Node.js 未安装成功。

请重新安装 Node.js，然后重开终端。

---

## 13.5 Git 命令无法识别
说明 Git 未安装成功。

请重新安装 Git for Windows。

---

## 13.6 前端页面打开是空白页或样式错乱
常见原因：

- 前端依赖没装好
- `npm install` 没完成
- `App.tsx` 改动后语法出错

解决方法：

1. 执行 `npm install`
2. 执行 `npm run dev`
3. 看终端是否有报错
4. 按报错位置修复代码

---

# 14. 推荐启动顺序（很重要）

每次使用项目时，推荐按这个顺序：

## 14.1 先启动后端

```powershell
cd D:\Agent
conda activate Agent
uvicorn app_main:app --reload
```

## 14.2 再启动前端

```powershell
cd D:\Agent\frontend
npm run dev
```

## 14.3 最后打开浏览器

```text
http://localhost:5173
```

---

# 15. 如果要给同学或队友使用

如果只是你自己本机用，上面步骤就够了。

如果要让同一个局域网内的队友访问，你可以额外这样做：

## 15.1 后端

```powershell
uvicorn app_main:app --host 0.0.0.0 --port 8000
```

## 15.2 前端
打包后执行：

```powershell
serve -s dist -l 5173
```

## 15.3 把前端里的 API_BASE 改成你这台固定电脑的 IP，例如：

```ts
const API_BASE = "http://192.168.1.50:8000";
```

## 15.4 其他人访问：

```text
http://192.168.1.50:5173
```

注意：
- 这台电脑必须一直开机
- 前后端服务必须一直运行
- Windows 防火墙要放行相关端口

---

# 16. 版本维护建议

建议你在每次完成一个稳定版本后：

1. 提交 Git
2. 推送到 GitHub
3. 备份数据库和生成文件

常用命令：

```bash
git add .
git commit -m "update: 描述本次改动"
git push
```

---

# 17. 新手最简启动清单

如果你什么都不想看，只想最快跑起来，请按下面操作：

## 第一步
安装：
- Git
- Miniconda
- Node.js
- Microsoft Word

## 第二步
下载代码并进入目录：

```powershell
cd D:\Agent
```

## 第三步
创建环境并安装依赖：

```powershell
conda create -n Agent python=3.11 -y
conda activate Agent
pip install fastapi uvicorn sqlalchemy pydantic python-multipart openai langgraph langchain docxtpl python-docx docx2pdf pywin32
```

## 第四步
安装前端依赖：

```powershell
cd D:\Agent\frontend
npm install
```

## 第五步
启动后端：

```powershell
cd D:\Agent
conda activate Agent
uvicorn app_main:app --reload
```

## 第六步
启动前端：

```powershell
cd D:\Agent\frontend
npm run dev
```

## 第七步
打开：

```text
http://localhost:5173
```

---

# 18. 结语

如果你是第一次接触这个项目，不要担心。

你只需要记住：

- 后端负责分析
- 前端负责页面
- 先开后端，再开前端
- 页面打不开先看终端报错
- 上传失败先查后端依赖
- PDF 失败先保留 DOCX

按照这份 README，一步一步来，基本都可以顺利跑起来。

如果你是项目维护者，建议在后续版本中继续补充：

- requirements.txt
- 环境变量说明
- 数据库初始化说明
- 底稿模板配置说明
- 云端部署说明

这样团队成员上手会更快。

