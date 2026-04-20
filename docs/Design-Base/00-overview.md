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

## 細部規範索引

| 文件 | 涵蓋範圍 |
| --- | --- |
| [10-frontend.md](10-frontend.md) | 前端目錄結構、API 呼叫、狀態管理、TypeScript 規則、渲染效能 |
| [11-ui-ux.md](11-ui-ux.md) | 樣式主題、Header / Sidebar 佈局、Dialog、RWD、Loading |
| [20-backend.md](20-backend.md) | 後端分層架構、API 路由、回應格式、例外處理、CORS、Logging |
| [21-database.md](21-database.md) | 資料庫命名、必備欄位、軟刪除、pgvector、Redis、Migration |
| [30-login.md](30-login.md) | 認證機制（雙 Token）、註冊 / 登入 / 忘記密碼流程 |
| [40-permission.md](40-permission.md) | 角色定義、端點權限對照、資源存取控制 |

---

## 開發注意事項

- 開發過程中若需安裝新套件，可自行執行安裝指令（前端 `npm install`、後端 `pip install` 或更新 `pyproject.toml`），無須額外確認
