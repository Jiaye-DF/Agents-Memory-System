# 專案掃描報告（v1.0.2 後）

> 初次掃描時點：2026-04-20；處理完成時點：2026-04-20
> 對照 `docs/Design-Base/*` 與 `docs/Tasks/v1.0/tasks-v1.0.md`、`tasks-v1.0.1.md`、`tasks-v1.0.2.md`。
>
> 每個項目以 `[x]` 代表「已處理」、`[ ]` 代表「仍未處理」。

---

## 處理摘要（2026-04-20）

- **高優先 6 項全數處理完成**（router response_model 泛型化、Token 規範衝突、`require_role` 型別、`_current_user: dict`、OpenRouter 搬家至 `clients/`、前端原生 `fetch` 改走 `lib/api/download`）。
- **中優先 6 項全數處理完成**（V15 Migration 補命名、Next.js 版本、`40-permission.md` 端點對照、`.env.example`、`11-ui-ux.md` 例外條款、`21-database.md` 索引命名條款）。
- **低優先 5 項已完成 4 項**，僅 OpenRouter 快取改 Redis（依賴未來整體快取策略）保留未做。

---

## 一、專案摘要

- **專案目標**：Agents 記憶管理系統（記憶管理、自定義 Agent、Skills、Agentic RAG、多平台整合）。
- **技術棧對照**（實際 vs `00-overview.md § 技術棧`）：

  | 分類 | 規範 | 實際 | 狀態 |
  | --- | --- | --- | --- |
  | Next.js | 16 | 16.2.4 | 已對齊（規範已同步更新為 16） |
  | React | 19 | 19.2.4 | 已採用 |
  | TailwindCSS | 4 | ^4 | 已採用 |
  | Redux Toolkit / RTK Query | latest | ^2.11.2 | 已採用 |
  | TypeScript | 5 | ^5 | 已採用 |
  | Python | 3.14+ | >=3.14 | 已採用 |
  | FastAPI | latest | >=0.115 | 已採用 |
  | SQLAlchemy 2 / Pydantic 2 | — | >=2.0 | 已採用 |
  | PostgreSQL 17 / pgvector / Redis | — | V1 Migration 已啟用 pgvector | 已採用 |

- **目錄結構對照**：`backend/app/`、`frontend/src/` 結構完全匹配規範。`backend/app/clients/openrouter/` 已建立並承接 OpenRouter HTTP 呼叫；`engine/` 為 v1.0 範圍外，未建立屬合理狀態。
- **當前 Task 進度**：
  - v1.0 / v1.0.1 / v1.0.2：全數交付並完成合規修正。
- **完成度推估**：v1.0.2 範圍內模組屬「高」完成度；`memories`、`conversations`、`engine/`、`clients/line`、`clients/telegram` 為後續版本。

---

## 二、規範違反清單

### 00-overview.md

- [x] `frontend/package.json:14` / `docs/Design-Base/00-overview.md` — Next.js 版本已於規範更新為 16，實際 16.2.4 對齊。

### 10-frontend.md

- [x] `frontend/src/app/(main)/agents/[uid]/page.tsx` — 原 `fetch` 已改走 `@/lib/api/download` 的 `downloadText + triggerBrowserDownload`。
- [x] `frontend/src/app/(main)/skills/[uid]/page.tsx` — 原 `fetch` 已改走 `@/lib/api/download` 的 `downloadBlob + extractFilename + triggerBrowserDownload`。
- [x] `frontend/src/store/api.ts` — 已移除 `customBaseQuery` / `fakeBaseQuery` 死碼。

### 11-ui-ux.md

- [x] `frontend/src/app/global-error.tsx` — 因 Next.js global-error 會取代 RootLayout、`globals.css` 無法載入，`11-ui-ux.md § 佈景主題` 已補上例外條款允許其 inline style + hex。

### 20-backend.md

- [x] **所有 router 的回傳型別** — 雖內部仍回傳 `JSONResponse`（以便 `set_cookie` 與 `status_code` 控制），但每個 endpoint 已於 decorator 加上 `response_model=ApiResponse[...]`（泛型 wrapper），Swagger `/api/docs` 可正常顯示完整 schema。影響檔案：
  - `backend/app/schemas/response.py`（新增泛型 `ApiResponse[T]` / `PaginatedData[T]` / `MessageData` / `HealthData` / `TokenData`）
  - `backend/app/api/v1/admin/router.py`
  - `backend/app/api/v1/agents/router.py`
  - `backend/app/api/v1/skills/router.py`（含新增 `FileTreeData`）
  - `backend/app/api/v1/auth/router.py`
  - `backend/app/api/v1/models/router.py`（含新增 `LlmModelListData`）
  - `backend/app/api/v1/agent_languages/router.py`（含新增 `AgentLanguageListData`）
  - `backend/app/api/v1/settings/router.py`（含新增 `PublicSettingsData`）
  - `backend/app/api/v1/health.py`
- [x] `backend/app/api/deps.py:41` — `require_role` 回傳型別改為 `params.Depends`，`# noqa: ANN201` 已移除。
- [x] `backend/app/api/v1/models/router.py` — `_current_user: dict` 已改為 `TokenPayload`。
- [x] `backend/app/services/openrouter_service.py` → `backend/app/clients/openrouter/client.py` — HTTP 呼叫邏輯搬至 `clients/`；services 層只保留 `verify_model_id` 業務邏輯並呼叫 `clients.openrouter.fetch_model_ids`。
- [ ] `backend/app/services/openrouter_service.py` 模組級快取 — 仍為記憶體字典，未改為 Redis。低優先保留，待未來整體快取策略統一時處理。
- [x] `backend/app/services/agent_service.py` — `f"## 描述"` 等 5 處無插值 f-string 已改為一般字串。
- [ ] `llm_model_service.py` / `agent_language_service.py` / `system_setting_service.py` 等 service 層回傳型別仍為裸 `dict`；嚴格 Pydantic 化屬下一版優化範圍，因 router response_model 已能展示 Swagger schema，不再是緊急項。

### 21-database.md

- [x] `migrations/sql/V15__fix_naming_conventions.sql`（新增）— 修正以下命名並保留 V9/V11/V12/V14 不動：
  - `uq_llm_model_uid` → `uq_llm_model_llm_model_uid`
  - `uq_agent_language_uid` → `uq_agent_language_agent_language_uid`
  - `uq_system_setting_uid` → `uq_system_setting_system_setting_uid`
  - `trg_llm_model_updated_at` → `trg_llm_model_set_updated_at`
  - `trg_agent_language_updated_at` → `trg_agent_language_set_updated_at`
  - `trg_system_setting_updated_at` → `trg_system_setting_set_updated_at`
  - `llm_model.provider` 既有 `OpenAI/Anthropic/Google` seed 批次更新為 `OpenRouter`
  - `llm_model.provider` 欄位註解重寫為 `OpenRouter` 版
- [x] `backend/app/models/user.py` — `BigInteger`、`Boolean`、`func` 等未使用 import 已移除。

### 30-login.md

- [x] `docs/Design-Base/30-login.md § Token 規範` — 已重寫，明文允許 payload 含 `role`（role name）供 RBAC 使用，並指明僅禁止密碼 / 權限明細等真正敏感資訊；與 `40-permission.md` 對齊。
- `backend/app/core/security.py` 程式碼不需變動（原實作已正確放入 role / username）。

### 40-permission.md

- [x] `docs/Design-Base/40-permission.md § 端點權限對照` 已補齊 v1.0.1 / v1.0.2 新增端點：
  - member+admin 共用：`GET /api/v1/models`、`GET /api/v1/agent-languages`、`GET /api/v1/settings/public`
  - admin 專屬：`/api/v1/admin/llm-models/*`、`/api/v1/admin/agent-languages/*`、`/api/v1/admin/settings/*`

### 安全性

- [x] `.env.example`、`.env` 已補登 `SKILLS_UPLOAD_DIR=data/skills`、`SKILLS_MAX_FILE_SIZE=52428800`。
- `.gitignore`、credentials 排除維持正確。未發現 hardcoded 敏感資訊。

### 命名慣例

- [x] 資料庫索引 / Trigger 命名經 V15 修正。
- [x] `21-database.md` 已新增 `{表}_uid` 與 `set_updated_at` 命名條款。

### 程式碼品質

- [x] `docs/Tasks/v1.0/tasks-v1.0.md:318` 殘留「/fu」字串已刪除。
- [x] `frontend/src/store/api.ts` 死碼已清理。
- [x] `backend/app/models/user.py` 未使用 import 已清理。
- [x] `backend/app/services/agent_service.py` 無插值 f-string 已清理。

---

## 三、Design-Base 自身問題

- [x] **`30-login.md § Token 規範` vs `40-permission.md § 請求驗證流程` 互相矛盾** — 已於 30-login 明文化例外（role name 非敏感資訊）。
- [x] `00-overview.md § 技術棧 - 前端` — Next.js 版本已同步為 16。
- [x] `40-permission.md § 端點權限對照` — 已涵蓋 v1.0.1/1.0.2 新增端點。
- [x] `21-database.md § 命名慣例` — 已明文要求 `{表}_uid` 索引使用 `uq_{表}_{表}_uid`、Trigger 須含 `set_` 中綴。
- [x] `docs/Tasks/v1.0/tasks-v1.0.md:318` 殘留「/fu」已刪除。

---

## 四、餘留事項

僅一項低優先：

- [ ] `backend/app/services/openrouter_service.py` 的記憶體快取搬至 Redis（跨 worker 一致性）。延後至整體快取策略統一時處理，不影響當前功能。

---

## 五、本輪新發現（v1.0.2 相關）— 已處理

- [x] `backend/app/services/openrouter_service.py` — 已搬家至 `clients/openrouter/`。
- [x] `migrations/sql/V12` / `V14` — 索引與 Trigger 命名由 V15 統一修正。
- [x] `backend/app/api/v1/admin/router.py` / `agent_languages/router.py` / `settings/router.py` — `response_model` 已套用。
- [x] `40-permission.md` v1.0.2 新端點已補齊。

---

## 六、後續版本建議

1. service 層函式回傳型別以 Pydantic 模型取代裸 `dict`，讓 router 可直接 `return PydanticInstance` 並由 FastAPI 自動序列化（搭配 `response_model` 一致）。此調整可逐步進行，不影響現況。
2. OpenRouter / 未來的 LINE / Telegram client 納入 Redis 快取層，並建立 `clients/` 的統一錯誤轉換慣例（第三方 HTTP 錯誤 → `AppError`）。
3. v1.0.2 前端 `AgentForm.tsx` 達 1123 行，建議拆分為更小的區塊元件；此為品質優化，非規範違反。
