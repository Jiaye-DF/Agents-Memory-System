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
| Next.js       | 15     | React 框架、App Router   |
| React         | 19     | UI 元件庫                |
| TailwindCSS   | 4      | Utility-first CSS        |
| Redux Toolkit | latest | 全域狀態管理             |
| RTK Query     | latest | 伺服器資料快取與同步     |
| TypeScript    | 5      | 型別安全                 |

> 前端細節參閱 [10-frontend.md](10-frontend.md)

### 後端

| 技術       | 版本     | 用途                 |
| ---------- | -------- | -------------------- |
| Python     | 3.12+    | 主要語言             |
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
agents-memory-system/
├── backend/                        # FastAPI 後端
│   ├── app/
│   │   ├── main.py                 # FastAPI 進入點
│   │   ├── api/
│   │   │   ├── deps.py             # 共用依賴（DB session、認證）
│   │   │   └── v1/                 # API v1 路由
│   │   │       ├── router.py       # v1 總路由
│   │   │       ├── agents/         # Agent 管理
│   │   │       ├── skills/         # Skills 管理
│   │   │       ├── memories/       # 記憶管理
│   │   │       ├── conversations/  # 對話管理
│   │   │       ├── auth/           # 登入驗證
│   │   │       └── health.py       # 健康檢查
│   │   ├── core/                   # 核心模組
│   │   │   ├── config.py           # 環境變數與設定
│   │   │   ├── database.py         # DB 連線池
│   │   │   ├── response.py         # 統一回應格式
│   │   │   └── exceptions.py       # 統一例外處理
│   │   ├── models/                 # SQLAlchemy 模型
│   │   ├── schemas/                # Pydantic Schema
│   │   ├── services/               # 業務邏輯層
│   │   ├── repositories/           # 資料存取層
│   │   ├── clients/                # 第三方服務 Client
│   │   │   ├── openrouter/         # OpenRouter API
│   │   │   ├── line/               # LINE Messaging API
│   │   │   └── telegram/           # Telegram Bot API
│   │   └── engine/                 # Agent 引擎
│   │       ├── agent_runner.py     # Agent 執行器
│   │       ├── skill_loader.py     # Skill 載入器
│   │       └── rag/                # RAG Pipeline
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/                       # Next.js 前端
│   ├── src/
│   │   ├── app/                    # App Router 頁面
│   │   ├── components/             # 共用元件
│   │   ├── lib/
│   │   │   └── api/                # API Client（禁止元件直接 fetch）
│   │   └── store/                  # Redux Store + RTK Query
│   ├── public/
│   ├── Dockerfile
│   ├── package.json
│   └── tsconfig.json
├── migrations/                     # Flyway DB Migration
│   └── sql/                        # V{版號}__{描述}.sql
├── docs/
│   ├── Design-Base/                # 設計規範
│   └── Tasks/                      # 版本任務規格
├── .claude/
│   └── commands/                   # Claude Code 自訂指令
├── docker-compose.dev.yml          # 開發環境
├── .env.example
├── .gitignore
├── CLAUDE.md
└── README.md
```

---

## 核心功能模組

### Agent 管理

- 建立、編輯、刪除自定義 Agent
- 為 Agent 指派 Skills 組合
- Agent 參數設定（系統提示詞、模型選擇、溫度等）

### Skills 系統

- 預定義 Skills（網路搜尋、檔案讀取、計算等）
- Skills 參數設定與輸入驗證
- Skills 執行結果回傳與錯誤處理

### 記憶管理

- 記憶 CRUD 操作
- 記憶向量化儲存與語意搜尋（pgvector）
- 記憶分類：短期 / 長期 / 情境
- 記憶自動摘要與整理

### Agentic RAG

- Agent 驅動的多步驟檢索流程
- 上下文組合與知識召回
- 透過 OpenRouter 串接多 LLM 模型生成回應

### 多平台整合

- LINE / Telegram Webhook 接收與回覆
- 統一訊息處理管線（平台無關的抽象層）
- 對話歷史記錄與追蹤

### 登入與權限

- 使用者登入驗證機制（細節參閱 [30-login.md](30-login.md)）
- 角色與權限控管（細節參閱 [40-permission.md](40-permission.md)）

---

## 規範約束

- 前端**禁止**直接呼叫第三方外部服務 API，所有外部服務呼叫須經由後端代理
- API Token、密碼、連線字串等敏感資訊一律透過環境變數注入，**禁止**寫死於程式碼
- 後端 API 統一前綴 `/api/v1`，Swagger 文件路徑固定為 `/api/docs`
- 後端分層架構：`api` → `services` → `repositories` → `models`，禁止跨層呼叫
- 資料庫 Migration 由 Flyway 管理，禁止手動修改已合併的 Migration 檔案
- 開發過程中若需安裝新套件，可自行執行安裝指令（前端 `npm install`、後端 `pip install` 或更新 `pyproject.toml`），無須額外確認
- 其餘前端、後端、資料庫、部署等細部規範，參閱對應的 Design-Base 文件
