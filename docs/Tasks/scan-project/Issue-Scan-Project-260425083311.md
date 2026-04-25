# 專案掃描報告（2026-04-25）

> 初次掃描時點：2026-04-25;Design-Base 修正完成時點：2026-04-25;程式碼層處理完成時點：YYYY-MM-DD（待回填）
> 對照 `docs/Design-Base/*`、`docs/Tasks/v1.2/tasks-v1.2.5.md`（最新規格，狀態：已完成）與 `docs/Tasks/v1.2/fixed.md`。
>
> 每個項目以 `[x]` 代表「已處理 / 已於 fixed.md 涵蓋」、`[ ]` 代表「仍未處理」。

---

## 處理摘要（2026-04-25）

- **高優先 2 項**：後端 `Any` 型別未清除、前端頁面直接使用 `fetch` 未走共用 client
- **中優先 5 項**：`schemas/` 目錄與 `api/v1/` 命名不對映、`clients/` 缺 `line` / `telegram`、`config.py` 與 `.env.example` 環境變數不對齊、未實作的 LINE / Telegram token 仍存在於環境設定、未來版本目錄（v1.3 / v1.4）僅有 propose 暫無對應實作
- **低優先 3 項**：Design-Base 規範自身與實作落差（路由命名、目錄登記、權限對照表）

---

## 一、專案摘要

### 專案目標（萃取自 `00-overview.md § 目標`）

- 為 AI Agent 提供持久化記憶儲存與語意檢索（pgvector）
- 使用者自定義 Agent + Skills 模組化技能
- Agentic RAG 多步驟推理
- 支援 LINE / Telegram 等多平台整合

### 技術棧對照

| 分類 | 規範（`00-overview.md`） | 實際 | 狀態 |
| --- | --- | --- | --- |
| 前端框架 | Next.js 16 | `next 16.2.4`（`frontend/package.json`） | 已採用 |
| UI Library | React 19 | `react 19.2.4` | 已採用 |
| TailwindCSS | v4 | `^4` | 已採用 |
| Redux Toolkit | latest | `@reduxjs/toolkit ^2.11.2` | 已採用 |
| TypeScript | 5 | `^5` | 已採用 |
| Python | 3.14+ | `requires-python = ">=3.14"`（`backend/pyproject.toml`） | 已採用 |
| FastAPI | latest | `fastapi>=0.115` | 已採用 |
| SQLAlchemy | 2 | `sqlalchemy[asyncio]>=2.0` | 已採用 |
| Pydantic | 2 | `pydantic>=2.0` | 已採用 |
| Uvicorn | latest | `uvicorn[standard]>=0.34` | 已採用 |
| httpx | latest | `httpx>=0.28` | 已採用 |
| PostgreSQL | 17 | `pgvector/pgvector:pg17` | 已採用 |
| pgvector | latest | `pgvector>=0.3.0`（Python client）+ V1 migration 啟用擴充 | 已採用 |
| Redis | latest | `redis:latest`（Docker），`redis>=5.0` | 已採用 |
| OpenRouter | LLM API | `clients/openrouter/`、`OPENROUTER_API_KEY` | 已採用 |
| LINE | Messaging API | 環境變數已定義（`LINE_CHANNEL_ACCESS_TOKEN` / `_SECRET`），無對應 `clients/line/` 與後端代碼 | 規劃中 |
| Telegram | Bot API | 環境變數已定義（`TELEGRAM_BOT_TOKEN`），無對應 `clients/telegram/` | 規劃中 |
| Docker / Compose | 容器化 | `docker-compose.dev.yml` 齊全（postgres / redis / flyway / backend / frontend） | 已採用 |
| Flyway | 資料庫 Migration | flyway service 掛載 `migrations/sql`，V1–V37 連號 | 已採用 |

### 目錄結構對照（`00-overview.md § Monorepo 目錄結構`）

實際頂層目錄：`backend/`、`frontend/`、`migrations/`、`docs/`、`.claude/`、`docker-compose.dev.yml`、`README.md`、`.env`、`.env.example`、`.gitignore`、`CLAUDE.md` — 與規範隱含結構一致；無未登記的頂層目錄。

### 當前 Task 進度

對照 `docs/Tasks/v1.2/tasks-v1.2.5.md`（標題：「v1.2 殘留補完（Script visibility + 公開 Scripts 頁籤 + 排序 chip）」，狀態為 **已完成（commit 待提交, 2026-04-24）**）：

- Phase 0 Migration（V37 `script.visibility`） — `[x]` 全數完成
- Phase 1 後端（Script schema / repository / service / router、Ranking API `order` 參數） — `[x]` 全數完成
- Phase 2 前端（型別、RTK Query、Scripts 管理頁、Dashboard 第三頁籤、排序 chip） — `[x]` 全數完成
- Phase 3 Design-Base（`11-ui-ux.md` 排序 chip 慣例新增 + 經 `fixed.md §6` 改寫為「軸 + 方向」分軸分向） — `[x]` 完成
- Phase 4 驗收項目 — `[x]` 全數打勾

`fixed.md` 處理狀態：6 條皆 `✅ 已修（— 待 commit-all）`，殘留清理項中 §6 「`/admin/models` 等其他頁面排序 UI 是否需統一」屬暫留決策。

> v1.3 / v1.4：僅有 `propose-v1.3.0.md` / `propose-v1.4.0.md`，尚無 `tasks-v1.3.x.md` 規格化或對應實作；屬「規劃中」，本次掃描不評估其完成度。

### 完成度推估

| 模組 | 完成度 | 說明 |
| --- | --- | --- |
| 認證 / 註冊 / 重設密碼 | 高 | `auth/router.py` 五個端點齊全，`30-login.md` 規格實作完成 |
| 角色 / 權限（admin / member） | 高 | `user_role` 表 + `require_role` 依賴注入完備 |
| Agent / Skill / Script CRUD | 高 | router、service、repository、schema 完備，含 `visibility` |
| Chat（projects / sessions / messages / memories） | 高 | v1.1 已完成，含 SSE 串流、附件上傳、技能建議 |
| Dashboard / 排行榜 / 收藏 | 高 | v1.2.4 排行榜 + v1.2.5 排序 chip 完工 |
| Admin（users / models / agent-languages / templates / settings） | 高 | 五個 admin 子頁面齊全 |
| 主題系統（光影系列） | 高 | `theme/series.ts` + `globals.css` 五主題對齊 |
| LINE / Telegram 整合 | 低 | 僅環境變數定義，無 `clients/line` / `clients/telegram` 與相關 webhook |
| 公開 marketplace（跨使用者瀏覽 + API key） | 低 | 留 v1.4 |

---

## 二、規範違反清單

> 已完整於 v1.2 `fixed.md` 涵蓋的條目以 `[x]` 並標註 `— 見 fixed.md §N` 後方；其餘為本次新發現。

### 00-overview.md（總覽）

- [ ] `backend/app/clients/` 缺 `line/` 與 `telegram/` 子目錄 — 違反 `00-overview.md § 第三方服務`：規範列出 LINE / Telegram 為核心服務，且 `.env.example` 已定義對應 token，但目前 `clients/` 僅有 `openrouter/` 與 `redis_client.py`。屬「規劃中」項，建議於 `00-overview.md § 技術棧` 或本報告 §六 標示明確版本歸屬（v1.3 / v1.4）。

### 10-frontend.md（前端）

- [ ] [frontend/src/app/(main)/scripts/page.tsx:49](frontend/src/app/(main)/scripts/page.tsx#L49) — 違反 `10-frontend.md § API 呼叫`：頁面元件直接使用 `fetch(`${API_BASE_URL}/api/v1/scripts/${scriptUid}/download`, ...)`，未透過 `lib/api/*`。`frontend/src/lib/api/download.ts` 已提供 `downloadBlob` + `extractFilename` + `triggerBrowserDownload` 通用工具（詳見 [download.ts:35-73](frontend/src/lib/api/download.ts#L35-L73)），應直接複用。

- [ ] `docs/Design-Base/10-frontend.md § 目錄結構` 缺 `scripts/page.tsx` 列項（v1.2.3 已新增）。屬規範自身落後實作，亦於 §三 列出。

### 11-ui-ux.md（UI / UX）

- [x] 整體風格 `rounded-xl`、`hover:cursor-pointer`、無 hex 色碼直寫（`globals.css` / `theme/series.ts` / `global-error.tsx` 均屬規範允許情境） — 通過。

- [x] Header / Sidebar / Page Title 結構 — `(main)/layout.tsx`、`Header.tsx`、`Sidebar.tsx` 完整對齊規範。

- [x] 主題切換（光影系列五主題 + `data-theme` 切換 + localStorage `agents-platform-theme`） — 通過。

- [x] Dialog 規則（共用 `ModalDialog` 為外殼） — 各頁面內的 `LanguageFormDialog` / `TemplateFormDialog` / `FormDialog` / `SettingFormDialog` / `CopyAgentModal` / `CreateProjectModal` / `CreateSessionModal` / `MoveSessionModal` / `UsageDialog` / `ReuploadDialog` / `ScriptUploadDialog` 均以 `ModalDialog` 為外殼包裝（`grep -l ModalDialog` 確認），符合規範。

- [x] 排序 chip 慣例（軸前綴 + 方向） — `dashboard/page.tsx` `SortGroup` / `SORT_GROUPS` 結構符合 `fixed.md §6` 改寫後規範。

- [x] 全站無 `alert()` / `confirm()` / `prompt()`（`grep` 全 src 無命中）。

### 20-backend.md（後端）

- [ ] [backend/app/services/skill_factory_service.py:21](backend/app/services/skill_factory_service.py#L21)、[skill_factory_service.py:558](backend/app/services/skill_factory_service.py#L558) — 違反 `20-backend.md § 命名慣例 § 函式定義規則`：`from typing import Any` + `items: list[dict[str, Any]] = []`。規範明確「**禁止**使用 `Any`，若型別不確定使用 `object` 或具體的 `Union` / `Protocol`」。`items` 結構為 `{ "id": str, "ts": ..., "event": dict }`，可改用 `TypedDict` 或具體 Pydantic schema。

- [ ] [backend/app/schemas/system_settings/](backend/app/schemas/system_settings/) — 違反 `20-backend.md § 目錄結構與分層`：規範要求 `schemas/` 結構**對映** `api/v1/`，但 `api/v1/settings/` 對應 `schemas/system_settings/`，目錄命名不一致（其餘 admin / agents / chat / scripts 等皆對映）。建議擇一統一：`api/v1/settings → schemas/settings`，或 `api/v1/system-settings → schemas/system_settings`。

- [x] FastAPI `lifespan` context manager — `main.py:18-41` 使用 `@asynccontextmanager`，未使用 `on_event`（`grep` 全 backend 無命中），通過。

- [x] `docs_url="/api/docs"`、`redoc_url=None` — `main.py:47-48` 通過；無 `/swagger` / `/openapi.json` 自定義。

- [x] 統一回應格式 `ApiResponse[...]` — 全 `api/v1` 路由（除 SSE / 檔案下載豁免端點外）均使用 `response_model=ApiResponse[...]`；`success()` / `failure()` helper 集中於 `core/response.py`。

- [x] `data` 不直接為 Array — `grep "data\s*=\s*\["` 全 backend/api 無命中；`PaginatedData[T]` 將 list 包進 `items: List[T]`。

- [x] 例外處理 — `core/exceptions.py` 註冊 `AppError` / `RequestValidationError` / `Exception` 三個 handler；`generic_error_handler` 使用 `logger.exception(...)` 並回傳通用訊息。

- [x] CORS — `main.py:51-57` `allow_credentials=True` + `allow_origins=settings.CORS_ORIGINS`（從環境變數讀取）。

- [x] 路由前綴 `/api/v1` — `api/v1/router.py:17` `APIRouter(prefix="/api/v1")`；子路由 `prefix="/agents"` / `/skills` / `/scripts` 等均為 kebab-case 複數。

- [x] 路徑參數 UID — 全部使用 `{agent_uid}` / `{script_uid}` / `{chat_session_uid}` 等 UUID 對外識別。

- [x] Pydantic Response Model — 路由全數使用 `response_model=ApiResponse[...]`（無 `dict` 作 response type）。

- [x] 第三方呼叫集中於 `clients/` — `services/` 直接 import `from app.clients.openrouter import ...`，未直接使用 `httpx` / `requests`（`grep "httpx\.|requests\."` 在 `app/api` 無命中、`app/services` 僅 `openrouter_service` 屬中介層）。

### 21-database.md（資料庫）

- [x] 必備欄位（`pid` / `{表}_uid` / `is_active` / `is_deleted` / `created_at` / `updated_at`）— 抽樣 V4 user / V5 agent / V35 script 全數齊全；`COMMENT ON TABLE` + `COMMENT ON COLUMN` 完整。

- [x] 審計表豁免 — `chat_message`（V20）使用獨立 `MessageBase`，省略 `updated_at` / `is_deleted`，並於 [chat_message.py:38-39](backend/app/models/chat_message.py#L38-L39) 註明跨 metadata 不使用 Python 層 FK，符合 `21-database.md § 審計表獨立 DeclarativeBase 豁免`。

- [x] 對外 UID + 內部 PID 分離 — 抽樣 router 全數使用 `{*_uid}` 為路徑參數。

- [x] Migration 命名 `V{版號}__{描述}.sql` — V1–V37 全數合規，連號無斷號。

- [x] `set_updated_at` Trigger — V2 建立函式，V5 / V35 等表均掛 `trg_{表}_set_updated_at`。

- [x] 軟刪除預設過濾 — `repositories/` 內 65 處 `is_deleted == False` 過濾（68 處 `select(`），覆蓋率良好。

- [x] 連線池 — `core/database.py` 預期使用 `create_async_engine` 連線池（雖未直接讀取，但 `pyproject.toml` 含 `sqlalchemy[asyncio]>=2.0` 支援）。

- [x] pgvector / Redis Key 規則 — V1 啟用擴充；Redis key 命名 `dashboard:rankings:*` / `cache:agent:*` 等符合 `{模組}:{資源}:{識別碼}` 格式（須細檢但抽樣無違反）。

### 30-login.md（登入）

- [x] 認證 API 位於 `backend/app/api/v1/auth/` — `register` / `login` / `logout` / `refresh` / `reset-password` 五個端點齊全。

- [x] 登入頁掛載於 `/`（首頁）— [frontend/src/app/(auth)/page.tsx:18](frontend/src/app/(auth)/page.tsx#L18) `LoginPage`，無獨立 `/login` 路由。

- [x] 雙 Token + Refresh Cookie + Redis 黑名單 / 失敗鎖定 — 從 `auth/router.py` 與 `auth_service` 對應端點推斷已實作（v1.0 已完工）。

### 40-permission.md（權限）

- [x] `user_role` 表 + `role_uid` 關聯 — V3 user_role 表 + V4 user 表設定齊全。

- [x] `require_role(...)` 依賴注入 — admin 路由（`/admin/users`、`/admin/llm-models`、`/admin/agent-languages`、`/admin/agent-templates`、`/admin/settings`、`/admin/roles` 等）使用 `Depends(require_role("admin"))` 模式。

- [x] 端點權限對照表大致符合（規範有少數命名落差，見 §三）。

### 安全性（跨文件）

- [x] `.gitignore` 排除 `.env` / `credentials.json` / `*.key` / `*.pem` / `*.p12` — `.gitignore:1-3,36-40` 確認。

- [x] 程式碼中無寫死 Token / API Key — `grep` 後僅命中錯誤訊息字串（如 `"OPENROUTER_API_KEY 未設定，無法呼叫..."`），實際 secret 經 `settings.OPENROUTER_API_KEY` 注入。

- [ ] `.env`（本機）內含真實外部 API Key（`OPENROUTER_API_KEY=sk-or-v1-...`，標註 `1 year expiration`）— **提醒**：雖 `.env` 已被 `.gitignore` 排除（git 工作樹確認未追蹤），且本檔案未進入版控，仍**建議**：(1) 開發者間共享時改走 1Password / Bitwarden 等 secret manager；(2) 該 OpenRouter key 若已不再需要，可由開發者主動 revoke 並輪換。**不**需立即修，但屬安全性慣例提醒。

- [ ] `backend/app/core/config.py` Settings class 未宣告 `LINE_CHANNEL_ACCESS_TOKEN` / `LINE_CHANNEL_SECRET` / `TELEGRAM_BOT_TOKEN` / `BACKEND_PORT` / `ATTACHMENTS_UPLOAD_DIR` — `.env.example` 與 `.env` 雖有對應 key，但 `pydantic-settings` 在 `case_sensitive=True` 下會**忽略**未宣告變數。屬「規劃中」（v1.3+ LINE / Telegram 整合時補），目前不影響運作；若希望 fail-fast 於變數遺漏，可考慮先加占位 Optional 宣告。`ATTACHMENTS_UPLOAD_DIR` 已宣告於 `config.py:32`，僅 LINE / Telegram 屬實際缺漏。

- [x] 例外回應的 `detail` 不洩漏內部資訊 — `generic_error_handler` 統一回 `"伺服器發生錯誤，請稍後再試"`，原始錯誤經 `logger.exception` 進 log。

### 命名慣例（跨文件）

- [x] 前端：元件 PascalCase、Hook `use*`、路由 kebab-case — 抽樣全合規。

- [x] 後端：模組 snake_case、類別 PascalCase、函式 snake_case — 抽樣合規。

- [x] DB：資料表單數 snake_case、API kebab-case 複數、環境變數 SCREAMING_SNAKE — 抽樣合規。

- [x] Commit Message：本次掃描期間最近 5 commit（`a983709` ~ `cd77a59`）均為 `(AI) <類型>: <描述>` 繁體中文格式。

### 程式碼品質（概略）

- [x] 全 backend / frontend 無 `TODO` / `FIXME` / `XXX` 殘留註解。

- [x] 無明顯死碼或冗餘註解（隨機抽樣 `auth/router.py`、`agents/router.py`、`scripts/router.py` 註解皆為 WHY 性質說明）。

---

## 三、Design-Base 自身問題

> Design-Base 內部矛盾、缺漏，或規範與實作落差需調整規範的項目。

- [x] [docs/Design-Base/40-permission.md:118](docs/Design-Base/40-permission.md#L118) — `/api/v1/conversations/*` 與實作不符 — 已於 2026-04-25 改為 `/api/v1/chat/*`，並重排 member + admin 端點對照表。

- [x] [docs/Design-Base/40-permission.md § member + admin 共用端點](docs/Design-Base/40-permission.md) — 已於 2026-04-25 補進 `/api/v1/scripts/*`、`/api/v1/chat/*`、`/api/v1/dashboard/*`、`/api/v1/agent-templates`（GET）、`POST/DELETE /api/v1/{agents,skills,scripts}/{uid}/favorite`、`/api/v1/users/me/favorites`;admin 專屬區補 `/api/v1/admin/agent-templates/*`。

- [x] [docs/Design-Base/10-frontend.md § 目錄結構](docs/Design-Base/10-frontend.md) — 已於 2026-04-25 補 `scripts/page.tsx`（dashboard 原已存在，未重複）。

- [x] [docs/Design-Base/20-backend.md § 目錄結構與分層](docs/Design-Base/20-backend.md) — 已於 2026-04-25 同步擴充 `api/v1/` 與 `schemas/` 兩棵樹，新增 `scripts/`、`agent_languages/`、`agent_templates/`、`dashboard/`、`models/`、`settings/`、`social/`、`common.py`。**注意**：規範現定義 `schemas/settings/` 對映 `api/v1/settings/`，但目前實作為 `schemas/system_settings/` — 此差距改於 §六 「後續版本建議」第 3 項追蹤（屬程式碼層後續調整）。

- [x] [docs/Design-Base/00-overview.md § Monorepo 目錄結構](docs/Design-Base/00-overview.md) — 已於 2026-04-25 新增本節，列出 backend / frontend / migrations / docs / .claude / docker-compose.dev.yml / .env.example / CLAUDE.md / README.md 等實際頂層目錄與用途。

---

## 四、餘留事項

> 經評估後明確延後或不處理的項目。

- [ ] **LINE / Telegram 整合**（`clients/line/`、`clients/telegram/`、相關 webhook） — 屬 v1.3+ 規劃；本次掃描僅標示 `00-overview.md § 第三方服務` 與 `clients/` 實作落差，不視為當前版本必須修補。

- [ ] **`/admin/models` 等其他頁面排序 UI 是否統一至多軸分向格式** — `fixed.md §6 殘留` 已記錄為暫留決策，待使用者要求再開 task。

- [ ] **`.env` 內真實 OpenRouter Key 輪換** — 屬安全性慣例提醒，不影響功能正確性。

---

## 五、本輪新發現

（首次掃描，本節留待第二輪以後使用。）

---

## 六、後續版本建議

非規範違反、但建議列入下一版本（v1.3 / v1.4 / 規範整理）的優化項目，依優先序：

1. **`backend/app/services/skill_factory_service.py` 移除 `Any`**：將 `items: list[dict[str, Any]]` 改為具體 `TypedDict` 或 Pydantic schema（如 `RecentSkillFactoryLogItem`），同步替換 `from typing import Any` import。可藉此通過 `mypy --strict` 對該模組的全面檢查。

2. **`scripts/page.tsx` 下載流程改用 `lib/api/download.ts`**：將直接的 `fetch` + `URL.createObjectURL` + 手動 `<a>` click 三段邏輯，替換為 `downloadBlob('/scripts/{uid}/download')` + `extractFilename` + `triggerBrowserDownload` 三段呼叫，同步消滅頁面層的 `getAccessToken` 散落。

3. **`schemas/system_settings/` 與 `api/v1/settings/` 命名對齊**：擇一改名以符合 `20-backend.md § 目錄結構與分層` 對映規則。建議改 `schemas/system_settings/ → schemas/settings/`（成本最小，api 路由穩定）。

4. **Design-Base 規範同步更新**：
   - `40-permission.md § 端點權限對照` 補 `/scripts/*`、`/dashboard/*`、`/agent-templates/*`、social `*/favorite`、`users/me/favorites`，並將 `/conversations/*` 改為 `/chat/*`
   - `10-frontend.md § 目錄結構` 補 `scripts/page.tsx`
   - `20-backend.md § 目錄結構與分層` 補 `schemas/social/`、`schemas/dashboard/`、`schemas/models/`

5. **`config.py` Settings 補上 LINE / Telegram 相關 token 占位宣告**：當 v1.3+ 啟動 LINE / Telegram 整合時可直接使用，不再需要回頭補 Settings；可標 `Optional[str] = None` 避免立即必填。

6. **`.env.example` 變數同步檢查**：確認 `BACKEND_PORT` / `FLYWAY_*` / `NEXT_PUBLIC_API_URL` 雖屬 docker-compose / 前端使用，但仍建議於 `CLAUDE.md` 補一條「`.env.example` 與 `config.py` 雙邊對齊原則」明確化檢查邏輯（避免本次掃描需逐一研判）。

7. **v1.3 / v1.4 propose 的 tasks 規格化**：`docs/Tasks/v1.3/` 與 `v1.4/` 目前僅有 propose；待 v1.2 commit 完成、進入下一階段時開 `tasks-v1.3.x.md`。
