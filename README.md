# Agents Memory System

以 **Agent 驅動 + 持久化記憶** 為核心的 AI 助手平台：使用者可自訂 Agent、組合 Skills、並透過向量化記憶實現 Agentic RAG，最終經由 Web 管理介面或 LINE / Telegram 與 Agent 互動。

---

## 核心功能

1. **記憶管理**：為 AI Agent 提供持久化儲存與語意檢索（PostgreSQL + pgvector）
2. **自定義 Agent**：使用者可建立、設定 Agent，組合不同 Skills 完成特定任務
3. **Skills 系統**：模組化技能元件，Agent 依需求載入與執行
4. **Agentic RAG**：以 Agent 驅動的檢索增強生成，結合記憶與外部知識進行多步驟推理
5. **多平台整合**：透過 LINE、Telegram 等通訊平台與 Agent 互動

> 完整設計目標、版本路線、系統架構詳見 [docs/Design-Base/00-overview.md](docs/Design-Base/00-overview.md)。

---

## 技術棧速覽

| 層級 | 主要技術 |
| --- | --- |
| 前端 | Next.js 16 / React 19 / TailwindCSS 4 / Redux Toolkit + RTK Query / TypeScript 5 |
| 後端 | Python 3.14+ / FastAPI / SQLAlchemy 2 / Pydantic 2 / Uvicorn / httpx |
| 資料庫 | PostgreSQL 17（含 pgvector）/ Redis |
| 第三方 | OpenRouter（LLM + embedding 統一入口）/ LINE / Telegram |
| 基礎設施 | Docker Compose / Flyway |

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
- `SECRET_KEY`（後端 JWT 簽章金鑰）
- `OPENROUTER_API_KEY`（LLM / embedding 來源）
- `FLYWAY_USER` / `FLYWAY_PASSWORD`（通常等同 PG 帳密）
- 若使用 LINE / Telegram：填入對應 token

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
