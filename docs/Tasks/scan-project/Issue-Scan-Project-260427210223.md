# 專案掃描報告（2026-04-27）

> 初次掃描時點：2026-04-27 21:02；處理完成時點：2026-04-27 21:24（中優先 6 項全部收斂、Design-Base 5 份規範同步補強，詳見 [v1.3/fixed.md §9](../v1.3/fixed.md)）
> 對照 [docs/Design-Base/\*](../../Design-Base/)、[docs/Tasks/v1.3/tasks-v1.3.6.md](../v1.3/tasks-v1.3.6.md) 與 [docs/Tasks/v1.3/fixed.md](../v1.3/fixed.md)。
>
> 本次為 v1.3.6 程式碼完成、上線前安全 / 可觀測性基線補強（fixed.md §7、§8）合併後的覆掃。同日上午另有 [Issue-Scan-Project-260427100515.md](Issue-Scan-Project-260427100515.md)，其高 / 中優先項目已大半收斂；本報告只回頭驗收前次條目，並列出**新發現**與**Design-Base 自身問題**。
>
> 每個項目以 `[x]` 代表「已處理」、`[ ]` 代表「仍未處理」。

---

## 處理摘要（2026-04-27 21:24 完成）

- **高優先 0 項** — 無新增的安全 / 敏感資訊外洩 / 必須規範違反。
- **中優先 6 項** — 已處理 5 項（§1 V47 命名→V49 重命名、§2 `ApiResponse.response_code` 改 `number`、§3 後端 `Any` 全清、§4 CSS variable 補定義並移除元件 hex fallback、§5 docker-compose env 補齊 + `.env.example` 預設清空）；§6 `owner_uid` / `owner_user_uid` 命名統一**已建立 [tasks-v1.3.7.md](../v1.3/tasks-v1.3.7.md)** 純 refactor 規格，與 `_ensure_owner` 三 service 整合一併做，待 review 後實作。
- **低優先 3 項** — `.env.example` 範本含 dev 預設值（**已處理**，與中優先 §5 合併）；LINE / Telegram clients 尚未實作（規劃中，留 v1.4+）；`backend/app/config/` 規範未登記（**已處理**，與 Design-Base §1 合併補登記）。
- **Design-Base 自身問題 6 項** — 已處理 5 項（00 / 11 / 20 / 21 / 90 五份規範補強）；保留 1 項：`### 擴充協議` 重複標題與既有 RWD 表對齊瑕疵屬既有 markdown lint 警告，不在本輪掃描出來的清單範圍內。

---

## 一、專案摘要

- **專案目標**：建立 Agents 記憶管理系統，提供記憶管理、自定義 Agent、Skills 系統、Agentic RAG、多平台整合（LINE / Telegram）。萃取自 [00-overview.md § 目標](../../Design-Base/00-overview.md)。

- **技術棧對照**（實際 vs `00-overview.md § 技術棧`）：

  | 分類 | 規範 | 實際 | 狀態 |
  | --- | --- | --- | --- |
  | Next.js | 16 | `frontend/package.json` `next: 16.2.4` | 已採用 |
  | React | 19 | `react: 19.2.4`、`react-dom: 19.2.4` | 已採用 |
  | TailwindCSS | 4 | `tailwindcss: ^4`、`@tailwindcss/postcss: ^4` | 已採用 |
  | Redux Toolkit / RTK Query | latest | `@reduxjs/toolkit: ^2.11.2`、`store/api.ts` baseApi + 各 *Api.ts injectEndpoints | 已採用 |
  | TypeScript | 5 | `typescript: ^5` | 已採用 |
  | Python | 3.14+ | `pyproject.toml` `requires-python = ">=3.14"`、`Dockerfile` `python:3.14-slim` | 已採用 |
  | FastAPI | latest | `fastapi>=0.115`，`docs_url="/api/docs"` 正確 | 已採用 |
  | SQLAlchemy 2 | 2 | `sqlalchemy[asyncio]>=2.0`、`mapped_column` / async engine | 已採用 |
  | Pydantic 2 | 2 | `pydantic>=2.0`、`pydantic-settings>=2.0` | 已採用 |
  | PostgreSQL 17 | 17 | `docker-compose.dev.yml` `pgvector/pgvector:pg17` | 已採用 |
  | pgvector | latest | `pgvector>=0.3.0`、V1 migration 啟用 | 已採用 |
  | Redis | latest | `redis:latest`、`redis>=5.0` | 已採用 |
  | OpenRouter | — | `clients/openrouter/`、`llm_metering` wrapper 統一入口 | 已採用 |
  | LINE | — | 僅 `.env.example` / `core/config.py` 預留環境變數，**`clients/line/` 不存在** | 未開始 |
  | Telegram | — | 同上，**`clients/telegram/` 不存在** | 未開始 |
  | Flyway | — | docker compose `flyway:migrate`，48 個 V*.sql | 已採用 |

- **目錄結構對照**（對照 [00-overview.md § Monorepo 目錄結構](../../Design-Base/00-overview.md)）：
  - 缺漏 / 額外目錄：
    - `backend/app/config/`（含 [model_prices.yaml](../../../backend/app/config/model_prices.yaml)）— **規範未登記**，但符合「慢變動設定 YAML」使用者偏好
    - `.agents/`、[AGENTS.md](../../../AGENTS.md)、`.axe-linter.yml` — **規範未登記**，AI 工具相關產物，建議於 Design-Base 補一句說明或排除
    - `migrations/scripts/` / `migrations/snapshot/` — 規範僅列 `migrations/sql/`，子目錄未註明
    - `backend/data/` — runtime 儲存目錄（已被 `.gitignore` 排除，不屬版控結構，符合 [00-overview.md](../../Design-Base/00-overview.md) 註解）
  - 缺少（待專案發展補上）：`backend/app/clients/line/`、`backend/app/clients/telegram/`

- **當前 Task 進度**（對照 [tasks-v1.3.6.md](../v1.3/tasks-v1.3.6.md) Phase 0–7）：
  - Phase 0 (V47 / V48 migration)：✅ 程式碼層完成
  - Phase 1 (Models / Schemas / Repository)：✅
  - Phase 2 (Analyzer 三 scope 升級 + metered wrapper + worker 擴充)：✅
  - Phase 3 (Recommender + SSE channel + 1h cooldown)：✅
  - Phase 4 (Suggestion / Recommender / Admin debug API)：✅
  - Phase 5 (推薦提示 UI + RTK Query)：✅
  - Phase 6 (Suggestion 列表頁)：✅
  - Phase 7 (runtime smoke)：⏳ 仍待使用者於 docker compose 起動環境執行
  - 安全 / 可觀測性基線補強（[fixed.md §8](../v1.3/fixed.md)）：✅ rate-limit / JSON log / readiness / Skill zip bomb / SECRET_KEY 強度驗證 / production CORS 強制全部就位
  - Script 公開讀 / 下載解鎖（[fixed.md §7](../v1.3/fixed.md)）：✅

- **完成度推估**：
  - 後端核心（auth / agent / skill / script / chat / memory / dashboard / social / agentic）：**高**
  - 前端核心（dashboard / agents / skills / scripts / projects / sessions / admin / skill-suggestions）：**高**
  - 多 Agent 對話（v1.3.3）+ 三層記憶（v1.3.5）+ Skill 工廠正式版（v1.3.6）：**程式碼層完成**，runtime smoke 待測
  - LINE / Telegram 整合：**未開始**（規劃中）

---

## 二、規範違反清單

項目格式：`- [ ] 檔案路徑:行號 — 違反 <檔名> § <章節>：說明`

### 00-overview.md

- [x] `backend/app/config/` — 違反 [00-overview.md § Monorepo 目錄結構](../../Design-Base/00-overview.md)：頂層規範未登記此目錄。實質為慢變動設定 YAML（`model_prices.yaml`），符合使用者偏好（YAML > DB）；建議於 Design-Base 補登記，而非搬移 — 已於 [00-overview.md § Monorepo 目錄結構](../../Design-Base/00-overview.md) 補登記為「YAML 慢變動設定」
- [x] [AGENTS.md](../../../AGENTS.md)、`.agents/`、[.axe-linter.yml](../../../.axe-linter.yml) — 違反 [00-overview.md § Monorepo 目錄結構](../../Design-Base/00-overview.md)：頂層出現規範未登記檔案 / 目錄。需確認用途並補規範或排除 — 已補登記為合法頂層檔案 / 目錄

### 10-frontend.md

- [x] 元件 `fetch` / `axios` 使用情況 — 已驗證：`fetch` 僅出現於 [lib/api/client.ts](../../../frontend/src/lib/api/client.ts:94)、[lib/api/stream.ts](../../../frontend/src/lib/api/stream.ts)、[lib/api/download.ts](../../../frontend/src/lib/api/download.ts) 三處基礎封裝，無元件直呼，符合 § API 呼叫
- [x] `process.env.NEXT_PUBLIC_*` 規範 — 已驗證：客戶端環境變數均使用 `NEXT_PUBLIC_API_URL`，無漏前綴
- [x] `any` 型別 — 已驗證：`grep -n "\bany\b"` 在 `frontend/src` 無命中
- [x] [frontend/src/types/api.ts:5](../../../frontend/src/types/api.ts#L5) — 違反 [20-backend.md § 統一回應格式](../../Design-Base/20-backend.md)：`ApiResponse.response_code` 宣告為 `string`，而後端 schema / [core/response.py](../../../backend/app/core/response.py) 一律回 `int`（如 `200` / `404`）— 已改為 `number`，見 [v1.3/fixed.md §9](../v1.3/fixed.md)
- [x] [frontend/src/lib/api/client.ts:117](../../../frontend/src/lib/api/client.ts#L117) — 違反 [20-backend.md § 統一回應格式](../../Design-Base/20-backend.md)：refresh 失敗的 fallback 物件回傳 `response_code: "UNAUTHORIZED"` 字串，與後端規定的 `int` 不符 — 已改為 `401`，見 [v1.3/fixed.md §9](../v1.3/fixed.md)

### 11-ui-ux.md

- [x] [frontend/src/app/(main)/skill-suggestions/page.tsx:239-247](../../../frontend/src/app/(main)/skill-suggestions/page.tsx#L239-L247) — 違反 [11-ui-ux.md § 實作方式](../../Design-Base/11-ui-ux.md)：confidence 徽章與 scope 徽章使用 `bg-[color:var(--color-success-bg,#dcfce7)]` 等寫法，將 hex 寫於 CSS Variable fallback — 已於 [globals.css](../../../frontend/src/app/globals.css) 5 主題補 4 個變數定義 + 元件移除 hex fallback，見 [v1.3/fixed.md §9](../v1.3/fixed.md)
- [x] [frontend/src/components/chat/AgentSkillSuggestionsDrawer.tsx:147-156](../../../frontend/src/components/chat/AgentSkillSuggestionsDrawer.tsx#L147-L156) — 同上違反 — 已修，見 [v1.3/fixed.md §9](../v1.3/fixed.md)
- [x] [frontend/src/app/(main)/sessions/[uid]/page.tsx:1467-1469](../../../frontend/src/app/(main)/sessions/[uid]/page.tsx#L1467-L1469) — 同上違反（confidence 徽章），來源為 v1.1.7 PoC 路徑 — 已修，見 [v1.3/fixed.md §9](../v1.3/fixed.md)

### 20-backend.md

- [x] [backend/app/workers/memory_worker.py:61,649](../../../backend/app/workers/memory_worker.py#L61) — `**extra: Any` → `object`、`session_obj: Any` → `ChatSession | None`，見 [v1.3/fixed.md §9](../v1.3/fixed.md)
- [x] [backend/app/workers/user_memory_worker.py:63,188,317](../../../backend/app/workers/user_memory_worker.py#L63) — `db: Any` → `AsyncSession`，其他 `Any` → `object`
- [x] [backend/app/workers/project_memory_worker.py:61,192,311](../../../backend/app/workers/project_memory_worker.py#L61) — 同上
- [x] [backend/app/services/rag_service.py:146](../../../backend/app/services/rag_service.py#L146) — `mem: Any` → `object`（依靠 `getattr` 取欄位，無需 Protocol）
- [x] [backend/app/services/skill_factory_service.py:102](../../../backend/app/services/skill_factory_service.py#L102) — `memory_obj: Any` → `object`
- [x] [backend/app/services/llm_metering.py:142,249](../../../backend/app/services/llm_metering.py#L142) — `**call_kwargs: Any` / `-> Any` / `dict[str, Any]` 全改 `object`
- [x] **掃描漏列補修**：[classifier_service.py](../../../backend/app/services/classifier_service.py)、[memory_trace_service.py](../../../backend/app/services/memory_trace_service.py)、[skill_recommender_service.py](../../../backend/app/services/skill_recommender_service.py)、[llm_call_log_repository.py](../../../backend/app/repositories/llm_call_log_repository.py)、[logging_config.py](../../../backend/app/core/logging_config.py)、[schemas/admin/memory_debug.py](../../../backend/app/schemas/admin/memory_debug.py) — 一同清掉所有 `Any`，全 backend `grep -n "\bAny\b"` 已歸零
- [x] FastAPI `lifespan` / `docs_url="/api/docs"` — 已驗證 [main.py:26-66](../../../backend/app/main.py#L26-L66) 正確
- [x] 例外處理三 handler — 已驗證 [core/exceptions.py:67-70](../../../backend/app/core/exceptions.py#L67-L70) 註冊 `AppError` / `RequestValidationError` / `Exception`
- [x] CORS `allow_credentials=True`、origins 從環境變數 — 已驗證 [main.py:68-74](../../../backend/app/main.py#L68-L74)
- [x] `data` 欄位非 Array、`response_code` 為 int — 已驗證 [core/response.py](../../../backend/app/core/response.py) 與全站 schema
- [x] 路由 `dict` response_model — `grep "response_model.*dict|response_model.*Dict"` 在 `backend/app` 無命中

### 21-database.md

- [x] [migrations/sql/V47__create_agentic_skill_suggestion.sql:44](../../../migrations/sql/V47__create_agentic_skill_suggestion.sql#L44) — 違反 [21-database.md § 命名慣例](../../Design-Base/21-database.md)：unique index 命名為 `uq_agentic_skill_suggestion_uid`，屬規範**明確禁止**的 `uq_{表}_uid` 簡寫格式 — 已新增 [V49 migration](../../../migrations/sql/V49__rename_agentic_skill_suggestion_uid_index.sql) 透過 `ALTER INDEX RENAME TO` 修正，見 [v1.3/fixed.md §9](../v1.3/fixed.md)
- [x] V47 trigger 命名 `trg_agentic_skill_suggestion_set_updated_at` — 已驗證符合慣例
- [x] V47 必備欄位（pid / uid / is_active / is_deleted / created_at / updated_at）+ Trigger + COMMENT — 已驗證齊備
- [x] `Base` 必備欄位 — 已驗證 [models/base.py:7-18](../../../backend/app/models/base.py#L7-L18)
- [x] 連線池 — 已驗證 [core/database.py:9-14](../../../backend/app/core/database.py#L9-L14) 使用 `pool_size=10` / `max_overflow=20` / `pool_recycle=300`

### 30-login.md

- [x] 雙 Token 機制（access in body、refresh in HttpOnly Cookie）— 已驗證 [api/v1/auth/router.py:25-44](../../../backend/app/api/v1/auth/router.py#L25-L44)
- [x] Cookie 設定 `httponly=True` / `samesite="lax"` / `secure=APP_ENV=="production"` / `path="/api/v1/auth"` — 已驗證
- [x] 登入頁面掛 `/`，無獨立 `/login` — 已驗證 [(auth)/page.tsx](../../../frontend/src/app/(auth)/page.tsx) 存在；目錄列示無 `login`
- [x] 認證 API 位於 `backend/app/api/v1/auth/` — 已驗證

### 40-permission.md

- [x] `require_role` Depends 工廠 — 已驗證 [api/deps.py:62-70](../../../backend/app/api/deps.py#L62-L70)
- [x] Token payload `role` + `user_uid` — 已驗證 [api/deps.py:33-40](../../../backend/app/api/deps.py#L33-L40)
- [x] 三段式存取控制 helper（admin / public / 擁有者）— 已驗證 [core/access.py](../../../backend/app/core/access.py) 提供 `ensure_readable` / `ensure_modifiable` / `ensure_owner`，Script service 已對齊（`fixed.md §7`）

### 安全性

- [x] `.env`、`credentials.json`、`*.key`、`*.pem`、`data/`、`logs/` — 已於 [.gitignore](../../../.gitignore) 排除
- [x] OpenRouter / LINE / Telegram Token 僅透過環境變數注入 — 已驗證
- [x] `SECRET_KEY` 長度強度（≥ 32）— 已驗證 [core/config.py:32-39](../../../backend/app/core/config.py#L32-L39)
- [x] `APP_ENV=production` 下 `CORS_ORIGINS` 禁 `*` / localhost — 已驗證 [core/config.py:41-55](../../../backend/app/core/config.py#L41-L55)
- [x] [docker-compose.dev.yml:60-78](../../../docker-compose.dev.yml#L60-L78) — 違反 [CLAUDE.md § 開發前必檢查](../../../CLAUDE.md)：backend service env 區段缺少以下 `.env.example` 已登記的 key — 已補齊 5 個 passthrough（`LLM_BASELINE_EXPENSIVE_MODEL`、`ATTACHMENTS_UPLOAD_DIR`、`LINE_CHANNEL_ACCESS_TOKEN`、`LINE_CHANNEL_SECRET`、`TELEGRAM_BOT_TOKEN`），見 [v1.3/fixed.md §9](../v1.3/fixed.md)
- [x] [.env.example:31](../../../.env.example#L31) — 違反 [CLAUDE.md § 敏感資訊](../../../CLAUDE.md)（精神面）：`OPENROUTER_HTTP_REFERER=http://localhost:3000` 直接寫入範本 — 已改空白 + 中文註解說明，見 [v1.3/fixed.md §9](../v1.3/fixed.md)

### 命名慣例

- [x] `Agent.owner_uid` / `Skill.owner_uid` 與 `Script.owner_user_uid` / `ChatProject.owner_user_uid` / `ChatSession.owner_user_uid` / `UserFavorite.owner_user_uid` 等不一致 — 違反 [21-database.md § 命名慣例](../../Design-Base/21-database.md)（隱含一致性）。**已建立獨立 task spec [tasks-v1.3.7.md](../v1.3/tasks-v1.3.7.md)** — 純 refactor、Phase 0–3 完整盤點 24 檔影響面（V50 migration / 16 backend 檔 / 8 frontend 檔），與 `core/access.py` 三 service `_ensure_owner` 整合一起做；待使用者 review 後依規格實作。原 [v1.3/fixed.md §7 殘留 / 後續](../v1.3/fixed.md) 由「留 v1.4」收編入 v1.3.7
- [x] API kebab-case 複數 — 已驗證 v1.3.6 新增 `/api/v1/skill-suggestions`、`/api/v1/agents/{uid}/skill-suggestions` 符合慣例
- [x] commit message 中文 + AI 前綴 — 近 5 commit 均符合（如 `(AI) Fix: 上線前安全 / 可觀測性基線補強...`）

### 程式碼品質

- [x] `TODO` / `FIXME` / `XXX` 未處理註解 — `grep -n "TODO:|FIXME:|XXX:"` 在 `backend/app` 與 `frontend/src` 無命中

---

## 三、Design-Base 自身問題

- [x] [00-overview.md § Monorepo 目錄結構](../../Design-Base/00-overview.md)：未列 `backend/app/config/`（YAML 慢變動設定） — 已補登記為「YAML 形式的慢變動設定（如 LLM 價目）」
- [x] [00-overview.md § Monorepo 目錄結構](../../Design-Base/00-overview.md)：未列 [AGENTS.md](../../../AGENTS.md)、`.agents/`、[.axe-linter.yml](../../../.axe-linter.yml) — 已補登記為合法頂層檔案 / 目錄
- [x] [11-ui-ux.md § 佈景主題 § 實作方式](../../Design-Base/11-ui-ux.md)：未列出主題系統**必須**支援的次階色彩變數 — 已新增「CSS Variable 一覽（必備）」表（14 大類 30+ 變數），並補「禁以 hex 作 CSS Variable fallback」原則
- [x] [21-database.md § 命名慣例](../../Design-Base/21-database.md)：規範句式對表名長度長 / 含 `uid` 字尾的情境會產生超長索引名 — 採嚴格做法（不開放例外），規範內補引 V49 範例與 `grep "uq_{表}"` 直接定位的單一規則理由
- [x] [90-code-fixed.md](../../Design-Base/90-code-fixed.md)：缺「跨版本既存問題」標註慣例 — 已新增 §8（既存自 vX.Y 標註 + 同類追蹤連結）
- [x] [20-backend.md § 命名慣例](../../Design-Base/20-backend.md)：「禁止使用 `Any`」缺實務例外清單 — 已補 4 類處理規範（異質容器 dict / list 用 `object`、`**kwargs` 用 `object`、DB session 用 `AsyncSession`、跨型別 ORM 用具名 `Protocol`）

---

## 四、餘留事項

- [ ] tasks-v1.3.6 Phase 7 runtime smoke — 需使用者於 docker compose 起動環境執行，程式碼層已就位
- [ ] v1.1.7 Redis 暫存退場 — 時間驅動，上線後第 8 天移除（[fixed.md §1](../v1.3/fixed.md) 對應 c509a24，2026-05-02 後可清）
- [ ] Skill / Script / Agent 三 service `_ensure_owner` 整合 `core/access.py` — [v1.3/fixed.md §7 殘留 / 後續](../v1.3/fixed.md)，留 v1.4 純 refactor
- [ ] Skill 服務同步 IO 改 `aiofiles` — [v1.3/fixed.md §8 殘留 / 後續](../v1.3/fixed.md)，留 v1.4
- [ ] LINE / Telegram clients 實作 — `00-overview.md § 第三方服務` 列為核心整合，目前僅 env 預留；待 v1.4 / v2.0 規劃

---

## 五、本輪新發現

（相對於 [Issue-Scan-Project-260427100515.md](Issue-Scan-Project-260427100515.md) 而言；皆於 [v1.3/fixed.md §9](../v1.3/fixed.md) 一次性處理）

- [x] V47 unique index 命名違反 `uq_{表}_{表}_uid` 慣例（§ 二·21-database.md）
- [x] Frontend `ApiResponse.response_code: string` 與後端 `int` 契約不符（§ 二·10-frontend.md）
- [x] Frontend `client.ts` refresh fallback 回傳 `"UNAUTHORIZED"` 字串（§ 二·10-frontend.md）
- [x] 後端 `: Any` 型別違反（初掃 12 處，深掃補修共 ~24 處 / 11 檔，全 backend 已歸零）
- [x] CSS Variable fallback 寫死 hex，且 `--color-success-bg` / `--color-purple*` 在 `globals.css` 未定義（§ 二·11-ui-ux.md）
- [x] `OPENROUTER_HTTP_REFERER` 範本預填 dev URL（§ 二·安全性）

前次報告中**已透過 [v1.3/fixed.md §7、§8](../v1.3/fixed.md) 解決**的高 / 中優先項目（zip bomb、SECRET_KEY 強度、production CORS、rate-limit、JSON log、readiness、`update_file_content` path 過濾、Script 公開讀 / 下載解鎖、`<FilterChip>` 統一）皆已驗收。

---

## 六、後續版本建議

依優先序：

1. 為 `globals.css` 補完狀態色 / 次階色 CSS Variable（5 主題 × 4–6 變數），並移除元件內 hex fallback；同步在 [11-ui-ux.md § 佈景主題](../../Design-Base/11-ui-ux.md) 列「狀態色變數一覽表」做為規範 source of truth
2. 統一前後端 `ApiResponse.response_code` 型別（建議改前端 [types/api.ts](../../../frontend/src/types/api.ts) 為 `number`），並更新 `client.ts` fallback 用 `401`
3. 為 V47 unique index 增建 V49 migration（`ALTER INDEX uq_agentic_skill_suggestion_uid RENAME TO uq_agentic_skill_suggestion_agentic_skill_suggestion_uid;`），同步檢查其他 v1.3.x 既有 migration 是否有同類簡寫，一併修正
4. 收斂後端 12 處 `: Any`：`**kwargs` 改 `object`、`db` 用 `AsyncSession`、Worker 與 RAG 的 memory-like 物件改 `Protocol`
5. 補 [docker-compose.dev.yml](../../../docker-compose.dev.yml) backend env passthrough，與 [.env.example](../../../.env.example) 對齊；並把 `OPENROUTER_HTTP_REFERER` 預設改空白 + 註解
6. 三 service 的 `_ensure_owner` 重複（Agent / Skill / Script）整合至 [core/access.py](../../../backend/app/core/access.py)；Script `owner_user_uid` 與 Agent / Skill `owner_uid` 命名統一（建議統一為 `owner_user_uid` 或 `owner_uid`，擇一全站套用）
7. 補 LINE / Telegram clients 骨架（即使僅 stub），至少建立 `clients/line/__init__.py`、`clients/telegram/__init__.py`，避免 `00-overview.md` 列示與實作差距持續擴大
8. 在 Design-Base 規範頂層補 `backend/app/config/` 與 `AGENTS.md` / `.agents/` / `.axe-linter.yml` 的定位說明
