# Agents Memory System

以 **Agent 驅動 + 持久化記憶** 為核心的 AI 助手平台：使用者可自訂 Agent、組合 Skills，透過三層向量化記憶（Session / Project / User）實現 Agentic RAG，並以語意檢索打造 Skill 市集，經由 Web 管理介面與 Agent 對話互動。

---

## 核心功能

1. **三層持久化記憶**：背景 worker 將對話摘要為 Session → Project → User 三層記憶並向量化（PostgreSQL + pgvector，HNSW），對話時 RRF 融合檢索注入 system prompt（Agentic RAG）
2. **自定義 Agent**：表單化建立 Agent（角色 prompt、語言、模型、生成參數），組合 Skills 完成特定任務；單一 Session 可掛多個 Agent 協作
3. **Skills / Scripts 系統**：模組化技能與腳本資源（ZIP / 資料夾上傳、單檔線上編輯、公開市集、收藏 / 下載 / 標籤）
4. **Skills RAG 語意檢索**：每個 Skill 建 name / description / content 三條向量，AI 查詢以 per-skill MAX 召回並附 LLM 推薦理由，查詢全程稽核
5. **Agentic Skill 工廠**：從累積記憶中自學產出 Skill 候選，經人工審核入庫並推薦給適合的 Agent
6. **成本工程**：所有 LLM / embedding 呼叫強制走統一計量入口入帳；前置分類器將訊息分流 skip / cheap / expensive
7. **多平台整合**（規劃中）：透過 LINE、Telegram 等通訊平台與 Agent 互動，目前僅預留環境變數尚未實作

> 完整設計目標、版本路線、系統架構詳見 [docs/Design-Base/00-overview.md](docs/Design-Base/00-overview.md)；
> 圖文版整體介紹（含流程圖、版本演進、操作手冊）見 [docs/Agents-Memory-System-專案說明文件.html](docs/Agents-Memory-System-專案說明文件.html)。

---

## 技術棧速覽

| 層級 | 主要技術 |
| --- | --- |
| 前端 | Next.js 16 / React 19 / TailwindCSS 4 / Redux Toolkit + RTK Query / TypeScript 5 |
| 後端 | Python 3.14+ / FastAPI / SQLAlchemy 2 / Pydantic 2 / Uvicorn / httpx |
| 資料庫 | PostgreSQL 17（含 pgvector，HNSW 向量索引）/ Redis |
| 檔案儲存 | AWS S3（Skills / Scripts / 附件；tag 軟刪） |
| 第三方 | OpenRouter（LLM + embedding 統一入口）/ DF-SSO（OAuth2 單一登入）/ LINE / Telegram（規劃中） |
| 基礎設施 | Docker Compose / Flyway / Coolify（正式部署） |

各層級細部規範參閱 [docs/Design-Base/](docs/Design-Base/)。

---

## 目錄結構

```text
Agents-Memory-System/
├── backend/                # FastAPI 後端
├── frontend/               # Next.js 前端
├── migrations/sql/         # Flyway V{版號}__{描述}.sql
├── docs/
│   ├── Design-Base/        # 專案規範（衝突時最高權威）
│   └── Tasks/              # 各版本 propose / tasks / fixed.md
├── .claude/                # Claude Code 自訂指令與 skills
├── docker-compose.dev.yml  # 本機開發環境編排
├── .env.example            # 環境變數範本
├── CLAUDE.md               # Claude Code 共用基本規範
└── README.md
```

> 頂層**禁止**新增規範未登記的目錄；如需跨模組共用工具，先於 Design-Base 補規範再建立。

---

## 快速開始

### 1. 前置需求

- Docker Desktop（含 Docker Compose）
- Node.js 22（如需於 host 執行前端開發）
- Python 3.14+（如需於 host 執行後端開發）

### 2. 環境變數

```bash
cp .env.example .env
```

依序填入下列必填項：

- `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB`
- `SECRET_KEY`（後端 JWT 簽章金鑰，至少 32 字元）
- `OPENROUTER_API_KEY`（LLM / embedding 來源）
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `S3_BUCKET`（Skills / Scripts / 附件檔案儲存）
- `FLYWAY_USER` / `FLYWAY_PASSWORD`（通常等同 PG 帳密）
- 若使用 DF-SSO：填入 `SSO_URL` / `SSO_APP_ID` / `SSO_APP_SECRET` 等
- LINE / Telegram token 為規劃中功能的預留變數，可留空

### 3. 啟動本機開發環境

```bash
docker compose -f docker-compose.dev.yml up -d
```

啟動後：

- 前端：<http://localhost:3000>
- 後端 API：<http://localhost:8000/api/v1>
- API 文件（Swagger）：<http://localhost:8000/api/docs>
- PostgreSQL：`localhost:5433`（容器內 5432）
- Redis：`localhost:6379`

> 也可使用自訂指令 [`/dev-up`](.claude/commands/dev-up.md) 一鍵啟動。

---

## API 文件

- 統一路徑：**`/api/docs`**（禁用 `/swagger`、`/docs`、`/openapi` 等其他路徑）
- 新增 / 修改 API 時須同步維護 Request / Response Schema 與欄位說明

---

## 規範與文件導引

| 路徑 | 說明 |
| --- | --- |
| [docs/Agents-Memory-System-專案說明文件.html](docs/Agents-Memory-System-專案說明文件.html) | 圖文版專案說明（摘要、流程圖、架構、版本演進、操作手冊） |
| [CLAUDE.md](CLAUDE.md) | 跨專案通用規範（語言、敏感資訊、Git 流程、自訂指令） |
| [docs/Design-Base/00-overview.md](docs/Design-Base/00-overview.md) | 專案規範總覽（架構、技術棧、時間 / 時區、目錄結構） |
| [docs/Design-Base/10-frontend.md](docs/Design-Base/10-frontend.md) | 前端：目錄結構、API 呼叫、狀態管理、TypeScript、效能 |
| [docs/Design-Base/11-ui-ux.md](docs/Design-Base/11-ui-ux.md) | UI / UX：樣式主題、Header / Sidebar、Dialog、RWD、Loading |
| [docs/Design-Base/20-backend.md](docs/Design-Base/20-backend.md) | 後端：分層、API 路由、回應格式、例外處理、CORS、Logging |
| [docs/Design-Base/21-database.md](docs/Design-Base/21-database.md) | 資料庫：命名、必備欄位、軟刪除、pgvector、Redis、Migration |
| [docs/Design-Base/30-login.md](docs/Design-Base/30-login.md) | 認證：雙 Token、註冊 / 登入 / 忘記密碼流程 |
| [docs/Design-Base/40-permission.md](docs/Design-Base/40-permission.md) | 權限：角色定義、端點與資源存取控制 |
| [docs/Design-Base/90-code-fixed.md](docs/Design-Base/90-code-fixed.md) | `fixed.md` 撰寫格式 / 時機 / 與 tasks 分工 |
| [docs/Tasks/](docs/Tasks/) | 各版本 propose / tasks / fixed.md（事件 + 階段真相來源） |

**規範優先順序**：`docs/Design-Base/*` > `CLAUDE.md` > 其他。

---

## 自訂指令

| 指令 | 說明 |
| --- | --- |
| [`/dev-up`](.claude/commands/dev-up.md) | 一鍵啟動本機開發環境 |
| [`/commit-all`](.claude/commands/commit-all.md) | 一鍵提交並推送當前分支所有變更 |
| [`/merge-main`](.claude/commands/merge-main.md) | 合併當前分支至 `main` |
| [`/scan-project`](.claude/commands/scan-project.md) | 掃描專案結構並分析潛在問題 |

---

## 時間 / 時區

本專案所有人類可讀時間戳一律使用 **UTC+8（Asia/Taipei）**。host 預設時區即為 UTC+8，AI / 自動化指令直接使用 `date "+%Y-%m-%d %H:%M:%S"` 即可，**禁止** `TZ=Asia/Taipei date` 等再轉一次的寫法。詳見 [docs/Design-Base/00-overview.md § 時間 / 時區](docs/Design-Base/00-overview.md)。

---

## 開發流程約定

- 主分支 `main`，新功能從 `main` 切出 feature branch
- Commit Message 使用繁體中文，格式 `<類型>: <描述>`，類型：`Add` / `Modify` / `Fix` / `Refactor` / `Docs`
- AI 產生的 commit 一律加 `(AI)` 前綴，例：`(AI) Add: 新增使用者管理功能`
- 未經使用者允許，禁止破壞性操作（`--force`、`reset --hard`、`--no-verify`）
- 任務完成後**必須**回填對應 `docs/Tasks/v*/tasks-v*.md` 的 checkbox，並於完成版本頂部加狀態標題

---

## 敏感資訊

- Token / 密碼 / 連線字串 / API Key 一律透過環境變數注入
- `.gitignore` 已排除 `.env`、`credentials.json`、`*.key` 等檔案
- 發現疑似敏感資訊於程式碼或 commit 中，立即提醒並修正
