# 目標

本專案建立 **Agents 記憶管理系統**，提供以下核心能力：

1. **記憶管理**：為 AI Agent 提供持久化記憶儲存與語意檢索（基於向量資料庫）
2. **自定義 Agent**：使用者可建立、設定 Agent，組合不同 Skills 以完成特定任務
3. **Skills 系統**：模組化技能元件，Agent 依需求載入與執行
4. **Agentic RAG**：以 Agent 驅動的檢索增強生成，結合記憶與外部知識進行多步驟推理
5. **多平台整合**：透過 LINE、Telegram 等通訊平台與 Agent 互動

---

## 系統架構

```text
┌────────────┐  ┌──────────────┐
│  LINE Bot  │  │ Telegram Bot │
└─────┬──────┘  └──────┬───────┘
      │                │
      └───────┬────────┘
              │ Webhook
     ┌────────▼─────────┐
     │   Next.js 前端    │  ← 管理介面（Agent / Skills / 記憶）
     └────────┬─────────┘
              │ REST API
     ┌────────▼─────────┐
     │   FastAPI 後端    │
     ├──────────────────┤
     │  Agent Engine    │  ← Agent 排程、Skills 載入
     │  Memory Manager  │  ← 記憶 CRUD、向量化
     │  RAG Pipeline    │  ← 檢索增強生成
     └────────┬─────────┘
              │
  ┌───────────┼───────────┬────────────┐
  │           │           │            │
┌─▼──────┐ ┌─▼────────┐ ┌▼──────┐ ┌───▼───────┐
│PostgreSQL│ │ pgvector │ │ Redis │ │ OpenRouter│
│ 主資料庫 │ │ 向量索引  │ │ 快取  │ │  LLM API  │
└─────────┘ └──────────┘ └───────┘ └───────────┘
```

---

## 技術棧

### 前端

| 技術          | 版本   | 用途                     |
| ------------- | ------ | ------------------------ |
| Next.js       | 16     | React 框架、App Router   |
| React         | 19     | UI 元件庫                |
| TailwindCSS   | 4      | Utility-first CSS        |
| Redux Toolkit | latest | 全域狀態管理             |
| RTK Query     | latest | 伺服器資料快取與同步     |
| TypeScript    | 5      | 型別安全                 |

> 前端細節參閱 [10-frontend.md](10-frontend.md)、[11-ui-ux.md](11-ui-ux.md)

### 後端

| 技術       | 版本     | 用途                 |
| ---------- | -------- | -------------------- |
| Python     | 3.14+    | 主要語言             |
| FastAPI    | latest   | Web 框架             |
| SQLAlchemy | 2        | ORM                  |
| Pydantic   | 2        | 資料驗證與序列化     |
| Uvicorn    | latest   | ASGI 伺服器          |
| httpx      | latest   | 非同步 HTTP Client   |

> 後端細節參閱 [20-backend.md](20-backend.md)

### 資料庫

| 技術       | 版本     | 用途                           |
| ---------- | -------- | ------------------------------ |
| PostgreSQL | 17       | 主要關聯式資料庫               |
| pgvector   | latest   | 向量索引擴充（記憶語意搜尋）   |
| Redis      | latest   | 快取、Session、佇列            |

> 資料庫細節參閱 [21-database.md](21-database.md)

### 第三方服務

| 服務       | 用途                           |
| ---------- | ------------------------------ |
| OpenRouter | LLM API 統一入口（多模型切換） |
| LINE       | LINE Messaging API 整合        |
| Telegram   | Telegram Bot API 整合          |

### 基礎設施

| 技術            | 用途             |
| --------------- | ---------------- |
| Docker          | 容器化           |
| Docker Compose  | 本機開發環境編排 |
| Flyway          | 資料庫 Migration |

---

## Monorepo 目錄結構

```text
Agents-Memory-System/
├── backend/                # FastAPI 後端（詳見 20-backend.md § 目錄結構與分層）
│   └── app/
│       └── config/         # 慢變動設定 YAML（如 LLM 模型價目表）；不適合放 DB 的對照表
├── frontend/               # Next.js 前端（詳見 10-frontend.md § 目錄結構）
├── migrations/             # Flyway 資料庫 Migration
│   ├── sql/                # V{版號}__{描述}.sql 檔（詳見 21-database.md § Migration）
│   ├── scripts/            # Migration 輔助 script（手動還原 / dump 用）
│   └── snapshot/           # 開發期 schema 快照（非版控真相，僅供查閱）
├── docs/                   # 規範與任務文件
│   ├── Design-Base/        # 專案規範（本目錄）
│   └── Tasks/              # 版本任務規格與 fixed.md
│       ├── v{X.Y}/         # 各版本資料夾（含 propose / tasks / fixed.md）
│       └── scan-project/   # `/scan-project` 指令輸出的歷次掃描報告
├── .claude/                # Claude Code 自訂指令與 skills
├── .agents/                # 專案內 AI agent skill / prompt 素材（與 .claude 分離）
├── docker-compose.dev.yml  # 本機開發環境編排（postgres / redis / flyway / backend / frontend）
├── .env.example            # 環境變數範本（供新開發者複製為 .env）
├── .env                    # 實際環境變數（gitignored）
├── .gitignore
├── .axe-linter.yml         # axe a11y linter 規則覆寫
├── CLAUDE.md               # Claude Code 共用基本規範
├── AGENTS.md               # 給 LLM agent（如 OpenAI Codex）讀的精簡專案說明
└── README.md
```

- 頂層**禁止**新增規範未登記的目錄；如有跨模組共用工具（scripts、tools 等），先於 Design-Base 補規範再建立。
- `data/`（執行期儲存）由後端服務於 runtime 自動建立，已被 `.gitignore` 排除，不屬版控結構。
- `backend/app/config/`：放慢變動的 **YAML 設定**（如 OpenRouter 模型價目）；變動頻率低、需 code review 留痕、不需後台編輯的對照表優先用 YAML，**不**為了一張表造一個 admin CRUD。

---

## 時間 / 時區

本專案所有「人類可讀的時間戳」一律以 **UTC+8（Asia/Taipei）** 表記，包含但不限於：

- `docs/Tasks/**/fixed.md` 條目尾端的 `〔YYYY-MM-DD HH:MM:SS〕`
- commit message body 中提及的時間
- 後端 / 前端輸出顯示給使用者的 ISO 字串
- log 中 user-facing 的時間敘述

### 取得當前時間（給 AI / 自動化指令）

本專案 host 預設時區即為 **UTC+8**，**直接使用 `date "+%Y-%m-%d %H:%M:%S"` 即可拿到 UTC+8 時間**。

**禁止**以下寫法（在本專案 host 上會誤算）：

- `TZ=Asia/Taipei date "+..."` — 部分 shell（如 git bash on Windows）會反向把 local 當 UTC 再轉一次，結果倒退 8 小時
- `date -u` 後再人腦 +8 — 容易加錯日期邊界
- 任何「再轉一次」的寫法

需要明確 UTC 時，才使用 `date -u`。

### 儲存層

- PostgreSQL：時間欄位一律使用 `TIMESTAMPTZ`；應用層讀取後透過 `app/core/datetime.py::to_taipei_iso()` helper 統一輸出為 UTC+8 ISO 字串給前端 / log。**禁止**在多處自行實作時區轉換。
- Redis：若需時間戳，存 epoch second（int）即可，不涉時區。

### 例外

- DB schema migration（`migrations/sql/V*__*.sql`）內的 `created_at` / `updated_at` `DEFAULT NOW()` 由 PG 自動填當前時間，無需手動處理。
- 「機器對機器」的 ISO 8601 時間（如 OpenRouter API、Webhook）保留原時區資訊（含 `+00:00` / `+08:00` suffix），不主動剝奪。

---

## 細部規範索引

| 文件 | 涵蓋範圍 |
| --- | --- |
| [10-frontend.md](10-frontend.md) | 前端目錄結構、API 呼叫、狀態管理、TypeScript 規則、渲染效能 |
| [11-ui-ux.md](11-ui-ux.md) | 樣式主題、Header / Sidebar 佈局、Dialog、RWD、Loading |
| [20-backend.md](20-backend.md) | 後端分層架構、API 路由、回應格式、例外處理、CORS、Logging |
| [21-database.md](21-database.md) | 資料庫命名、必備欄位、軟刪除、pgvector、Redis、Migration |
| [30-login.md](30-login.md) | 認證機制（雙 Token）、註冊 / 登入 / 忘記密碼流程 |
| [40-permission.md](40-permission.md) | 角色定義、端點權限對照、資源存取控制 |
| [90-code-fixed.md](90-code-fixed.md) | 程式碼修正記錄規範（fixed.md 撰寫格式 / 時機 / 與 tasks 分工） |

---

## 開發注意事項

- 開發過程中若需安裝新套件，可自行執行安裝指令（前端 `npm install`、後端 `pip install` 或更新 `pyproject.toml`），無須額外確認
