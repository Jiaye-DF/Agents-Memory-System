# v1.3 fixed.md

> 本檔記錄 v1.3 系列上線後 / 開發過程中發現並修復的問題。
> 條目格式遵循 [docs/Design-Base/90-code-fixed.md](../../Design-Base/90-code-fixed.md)。

---

## 1. RTK Query 重複註冊 listSkillSuggestions / rejectSkillSuggestion endpoint warning〔2026-04-25 23:50:00〕

**問題**

前端啟動 / 切換 session 頁面時 console 出現：

```text
called `injectEndpoints` to override already-existing endpointName listSkillSuggestions without specifying `overrideExisting: true`
```

`rejectSkillSuggestion` 同樣 warning。

**根因**

`chatApi.ts`（v1.1.7 PoC，session 範疇）與 `agenticApi.ts`（v1.3.6 正版，跨三 scope）皆 `injectEndpoints` 到同一個 `baseApi`，且註冊了**相同的 endpoint 名稱** — 後注入會覆蓋前注入，導致 hook 行為不可預期（呼叫端拿到的是 v1.3.6 介面，但傳入的是 v1.1.7 的 `{ sessionUid }`，造成執行期錯誤）。

兩者目的不同：v1.1.7 撈該 session 的 suggestions，v1.3.6 撈該 user 全部 scope 的 suggestions，**不能合併**。

**修正**

`chatApi.ts` 的 v1.1.7 三個 endpoint 全部加 `Session` 前綴，避開命名衝突；`agenticApi.ts` 維持原名作為主路徑。session 頁面改用新 hook 名稱：

- `listSkillSuggestions` → `listSessionSkillSuggestions`
- `approveSkillSuggestion` → `approveSessionSkillSuggestion`
- `rejectSkillSuggestion` → `rejectSessionSkillSuggestion`

過渡期 7 天並存（v1.3.6 規格規劃，2026-05-02 後可移除 v1.1.7 路徑）。

**影響檔案**

- [frontend/src/store/chatApi.ts](../../../frontend/src/store/chatApi.ts)
- [frontend/src/app/(main)/sessions/[uid]/page.tsx](../../../frontend/src/app/(main)/sessions/[uid]/page.tsx)

> 對應 commit：`c509a24`

---

## 2. MentionSelector 下拉行為失準（dropdown 未隨 caret 移動更新 / 關閉後反覆彈出）〔2026-04-25 23:55:00〕

**問題**

多 Agent 對話頁輸入 `@` 觸發 mention 下拉時：

- 移動 caret（方向鍵 / 點擊）後下拉內容不更新
- ESC 或選擇後關閉，但下一次輸入又立刻彈出（即使 query 還沒重新觸發）
- 在某些瀏覽器組合鍵情境下下拉「卡住」不消失

**根因**

原實作以 `useEffect([value, candidates.length])` 監聽變化計算 `open` / `context`，但：

- `value` 變化只反映輸入內容，**不反映 caret 移動**（方向鍵、點擊 textarea 不觸發 re-render）
- `setOpen` 與 `setContext` 雙 state 同步管理導致閉合 race（state 更新非同步，可能某次 keystroke 後 open=true 但 context 已被 reset）
- 沒有「使用者已關閉但 query 不變」的 dismiss 記憶，造成關閉後同 query 又彈出

**修正**

- 改以 textarea 的 `input` / `keyup` / `click` / `select` DOM 事件直接更新 `context`，確保 caret 移動即時反映
- 移除 `open` state，改為 `derived` 從 `context` + `dismissedKey` + `candidates.length` 算出（避免 state race）
- 新增 `dismissedKey`（`${value}:${trigger}:${query}` 雜湊）：使用者主動 dismiss 後，同 query 不再彈出，直到 query 變動才重置

**影響檔案**

- [frontend/src/components/chat/MentionSelector.tsx](../../../frontend/src/components/chat/MentionSelector.tsx)

---

## 3. AgentTemplate 編輯送出含 template_key 等不應更新欄位〔2026-04-25 23:56:00〕

**問題**

Admin 編輯 Agent Template 時，前端 `AgentTemplateUpdateRequest` body 透過 `const { template_key: _discard, ...rest } = base` 解構排除 `template_key`，再 `{ ...rest, is_active }` 重組。

此寫法依賴 `base` 物件結構**正好**等於 `AgentTemplateUpdateRequest`（去掉 `template_key`），但 `base` 來自 form state，可能含其他不該送出的欄位（如未來新增 form-only 計算欄位），導致：

- 後端可能收到未定義欄位 → 422 或意外覆寫
- TypeScript 沒有靜態保證 `rest` 結構與 `AgentTemplateUpdateRequest` 一致

**根因**

destructure-spread pattern 把欄位範圍交給「`base` 當下長什麼樣」決定，缺乏 schema-explicit 的契約；新增 form 欄位時會悄悄洩漏到 API 請求。

**修正**

改為**逐欄位顯式列出** `AgentTemplateUpdateRequest`：

```ts
const update: AgentTemplateUpdateRequest = {
  label: base.label,
  description: base.description,
  name: base.name,
  identity: base.identity,
  language: base.language,
  style: base.style,
  role_prompt: base.role_prompt,
  greeting: base.greeting,
  temperature: base.temperature,
  max_tokens: base.max_tokens,
  response_format: base.response_format,
  response_format_example: base.response_format_example,
  sort_order: base.sort_order,
  is_active: values.is_active,
};
```

未來 form 欄位增減時 TypeScript 會直接報錯，避免靜默洩漏。

**影響檔案**

- [frontend/src/app/(main)/admin/agent-templates/page.tsx](../../../frontend/src/app/(main)/admin/agent-templates/page.tsx)

---

## 4. /skill-suggestions 頁 layout 與其他管理頁不一致〔2026-04-26 00:04:00〕

**問題**

開啟 `/skill-suggestions` 頁面，內容被夾在頁面中央窄欄（max-w-4xl），左右兩側留大片空白；H1 字級偏小、區塊間距與 `/skills` `/agents` 等管理頁不一致；scope chip 列無「範疇：」前綴標籤，使用者看不出 chip 是切什麼維度。

**根因**

外層 wrapper 寫成 `<div className="mx-auto flex max-w-4xl flex-col gap-4 p-4 md:p-6">`：

- `mx-auto max-w-4xl` 限制寬度 + 置中，與其他頁未做此限制不符
- `p-4 md:p-6` 與 [layout.tsx](../../../frontend/src/app/(main)/layout.tsx) 的 `<main className="flex-1 overflow-y-auto p-4 lg:p-6">` 重複套 padding
- H1 用 `text-2xl`，[skills](../../../frontend/src/app/(main)/skills/page.tsx) / [agents](../../../frontend/src/app/(main)/agents/page.tsx) 等用 `text-3xl`
- 依賴外層 flex `gap-4` 控制區塊間距，與其他頁明確 `mb-4` 寫法不一致
- scope chip 缺前綴標籤，違反 [Design-Base/11-ui-ux.md 排序 chip 慣例](../../Design-Base/11-ui-ux.md)（chip 列前綴應有 `<span className="shrink-0 text-sm text-muted">`）

**修正**

- 外層 wrapper 改為純 `<div>`（讓 `<main>` 的 padding 接管）
- H1 改 `text-3xl`，外層用 `<div className="mb-4">` 包 header（移除語意 `<header>` 對齊 skills 寫法）
- 各區塊獨立加 `mb-4` 取代外層 flex gap
- scope chip 列前面加「範疇：」`<span>` 前綴
- 空狀態卡片改用 `shadow-sm`（取代 `border border-border`）對齊其他頁卡片風格

**影響檔案**

- [frontend/src/app/(main)/skill-suggestions/page.tsx](../../../frontend/src/app/(main)/skill-suggestions/page.tsx)

---

## 5. /skill-suggestions 字體 / chip 風格仍與管理頁不一致（§4 未完）〔2026-04-26 00:09:00〕

**問題**

§4 修了外層 wrapper 與 H1 大小，但細看仍與 [skills](../../../frontend/src/app/(main)/skills/page.tsx) / [agents](../../../frontend/src/app/(main)/agents/page.tsx) / [scripts](../../../frontend/src/app/(main)/scripts/page.tsx) 三個「我的資源」管理頁不對齊：

- 狀態頁籤用 `border-b-2` 底線 tab + `text-sm` — 其他頁用 segmented button + `text-base`
- scope chip 用自寫 `rounded-full border` style（藍底淡色 active）— 其他頁統一用 [`<FilterChip>`](../../../frontend/src/components/ui/FilterChip.tsx) 元件（`bg-primary text-white` active）
- 卡片每張獨立 `border` — 其他頁用單一外層 `rounded-xl bg-card-bg shadow-sm` + `divide-y divide-border` 內部分隔
- 卡片內 H3 為 `text-base`、scope/confidence 徽章 `text-[11px]` / `text-xs` — 其他頁 row H3 為 `text-lg`、徽章 `text-sm`
- 卡片無 `hover:bg-muted-bg/40` — 其他頁有 hover 反饋

**根因**

v1.3.6 sub-agent 實作此頁時自行寫 button class 而非沿用既有 `<FilterChip>` 元件；卡片設計也未對齊「我的資源」三頁的 row + divide-y pattern。

**修正**

- 狀態頁籤改 segmented button（`bg-primary text-white shadow-sm` active / `bg-muted-bg text-muted` inactive；`text-base font-medium`）對齊 [`<FilterNav>`](../../../frontend/src/components/social/FilterNav.tsx) 風格
- scope chip 改用既有 `<FilterChip>` 元件，移除自寫 button
- 列表外層改單一 `rounded-xl bg-card-bg shadow-sm overflow-hidden`，內部 `divide-y divide-border`，卡片 row 加 `hover:bg-muted-bg/40` 對齊 SkillRow / AgentRow
- 卡片 H3 改 `text-lg font-semibold`，scope / confidence 徽章 `text-sm font-medium`
- a11y 修：移除 `role="tablist"` wrapper（與 `aria-pressed` 衝突 — tablist children 應為 `role="tab"` 而非 toggle button）；`aria-pressed` 值改字面字串 `"true"/"false"`（lint 對 boolean expression 嚴格）；`<select>` 補 `aria-label` + `title`

**影響檔案**

- [frontend/src/app/(main)/skill-suggestions/page.tsx](../../../frontend/src/app/(main)/skill-suggestions/page.tsx)

---

## 6. /admin/models「供應商」顯示與語言不一致 + 新增模型可自由輸入易 typo〔2026-04-26 00:25:00〕

**問題**

[admin/models](../../../frontend/src/app/(main)/admin/models/page.tsx) 頁面有兩個 UI / 流程缺陷：

- 表格 Provider 欄位全列顯示 "OpenRouter"（gateway 名），但「供應商」篩選 chip 卻顯示 `anthropic / google / openai`（從 `model_id` 第一段派生），同一概念兩個來源 → 使用者看不懂哪個才是真實 vendor
- 表頭 `Provider`（英）與篩選 label `供應商`（中）對同一欄位用兩種語言
- 新增模型對話框讓使用者自由輸入 Model ID 字串，雖有 regex 驗證，但仍會打錯 vendor / slug，提交後才被後端 `verify_model_id` 拒絕，UX 差

**根因**

- 後端 [llm_model_service.create_model](../../../backend/app/services/llm_model_service.py) 把 `provider` 硬寫成 `DEFAULT_PROVIDER = "OpenRouter"`，與 model_id 隱含的真實 vendor 脫鉤；前端篩選又改用 `model_id.split("/")[0]` 派生，兩條路 → 顯示不一致
- 表頭 label 沿用 v1.0 早期英文 placeholder，沒回頭跟篩選 / 表單對齊中文化
- 新增模型 UX 缺一個「從 OpenRouter 官方清單挑選」的入口；既有 [openrouter_service.verify_model_id](../../../backend/app/services/openrouter_service.py) 與 [client.fetch_model_ids](../../../backend/app/clients/openrouter/client.py) 已能取得清單，但只用於 server-side 驗證，沒暴露給前端

**修正**

- 後端
  - [client.py](../../../backend/app/clients/openrouter/client.py)：拆出 `_fetch_models_payload()`，新增 `fetch_models_catalog()` 回傳 `id / name / context_length` 精簡欄位
  - [openrouter_service.py](../../../backend/app/services/openrouter_service.py)：新增 `list_openrouter_models()` 含 1 小時 cache（與既有 `get_valid_model_ids` 同 TTL）
  - [admin/router.py](../../../backend/app/api/v1/admin/router.py)：新增 `GET /admin/llm-models/openrouter-catalog`（路由放在 `/{llm_model_uid}` 之前避免被 path param 吃掉）
  - [llm_model_service.py](../../../backend/app/services/llm_model_service.py)：移除 `DEFAULT_PROVIDER` 硬寫，新增 `_derive_provider(model_id)` helper；`_to_dict` / `create_model` 一律以 `model_id` 第一段為準。舊資料的 `provider="OpenRouter"` 由 `_to_dict` 派生覆寫，不需 migration
- 前端
  - [models.ts](../../../frontend/src/types/models.ts) / [modelsApi.ts](../../../frontend/src/store/modelsApi.ts)：新增 `OpenRouterModelInfo` 與 `useListOpenRouterCatalogQuery`
  - [admin/models/page.tsx](../../../frontend/src/app/(main)/admin/models/page.tsx)：
    - 表頭 `Provider` → `供應商`；列值改用 `deriveVendor(model.model_id)` 與篩選對齊
    - 新增 inline `ModelCombobox`：trigger 顯示已選 `model_id`，下拉含搜尋框 + 篩選後清單（vendor tag / id / name / context_length）；最多渲染前 200 筆避免長清單卡頓
    - FormDialog create 模式以 Combobox 取代 `<Input>`；選定後自動帶入 OpenRouter `name` 至「顯示名稱」欄位（使用者後續手改則不再覆寫，由 `lastAutoFilledNameRef` 判定）
    - `useListOpenRouterCatalogQuery` 用 `skip: !isCreateMode` 避免關閉對話框時無謂呼叫

**影響檔案**

- [backend/app/clients/openrouter/client.py](../../../backend/app/clients/openrouter/client.py)
- [backend/app/clients/openrouter/\_\_init\_\_.py](../../../backend/app/clients/openrouter/__init__.py)
- [backend/app/services/openrouter_service.py](../../../backend/app/services/openrouter_service.py)
- [backend/app/services/llm_model_service.py](../../../backend/app/services/llm_model_service.py)
- [backend/app/schemas/models/schemas.py](../../../backend/app/schemas/models/schemas.py)
- [backend/app/api/v1/admin/router.py](../../../backend/app/api/v1/admin/router.py)
- [frontend/src/types/models.ts](../../../frontend/src/types/models.ts)
- [frontend/src/types/index.ts](../../../frontend/src/types/index.ts)
- [frontend/src/store/modelsApi.ts](../../../frontend/src/store/modelsApi.ts)
- [frontend/src/app/(main)/admin/models/page.tsx](../../../frontend/src/app/(main)/admin/models/page.tsx)

---

## 7. Script 公開資源讀 / 下載被擁有者鎖死，且 admin 無法跨擁有者代管〔2026-04-27 10:38:01〕

**問題**

`/scripts/public` 端點與 Dashboard 公開 Scripts 頁籤已對所有登入使用者列出 `visibility='public'` 的 Script，並顯示「下載」按鈕；但 `GET /scripts/{uid}` 與 `GET /scripts/{uid}/download` 服務層用 `_ensure_owner` 強制擁有者，**非擁有者點擊下載 / 點開公開 Script 詳情一律 404**。Snapshot row、收藏列表內的公開 Script 同樣無法下載。

同時 `update_script` / `soft_delete_script` 也僅擁有者可操作 — `admin` 連讀都不行，與 [40-permission.md § 資源存取控制](../../Design-Base/40-permission.md#資源存取控制) 「`admin` 可存取所有使用者的資源」原則不一致；Agent / Skill 已分別用 `ensure_readable` / `ensure_modifiable` / `ensure_owner` 三段式分權，Script 漏跟。

**根因**

v1.2.5 [§1-3](../v1.2/tasks-v1.2.5.md) 加 `/scripts/public` 與 `visibility` 切換時，列表端點走 `stmt_public()` 開放查詢，但**詳情 / 下載**端點沒同步開放；且 Script 服務層為 v1.2 自寫 `_ensure_owner` helper，未沿用 [`core/access.py`](../../../backend/app/core/access.py) 的三段式 helper（`ensure_readable` / `ensure_modifiable` / `ensure_owner`），加上 `Script.owner_user_uid` 欄位名與 Agent / Skill 的 `owner_uid` 不一致，無法直接套用 `core/access.py`（其 Protocol 期望 `owner_uid`）。歷次掃描未察。

另一個隱藏副作用：`update_script` 中的 `exists_name_for_owner(user_uid, ...)` 用「請求者 uid」做名稱查重 — admin 代改別人 Script 時會誤以 admin 自己的 Script 集合查重，可能放行已重複的名稱。

**修正**

1. [backend/app/services/script_service.py](../../../backend/app/services/script_service.py)：
    - 拆分 `_ensure_owner` 為三段式 helper，與 [`core/access.py`](../../../backend/app/core/access.py) 同語意但讀 `owner_user_uid` 欄位：
        - `_ensure_readable(script, user_uid, role)`：admin 全通，否則需擁有者或 `visibility='public'`
        - `_ensure_modifiable(script, user_uid, role)`：admin 可改，否則僅擁有者
        - `_ensure_owner(script, user_uid)`：刪除 / 切可見性等擁有者專用，admin 亦不特權
    - `get_script` / `download_script` → 改 `_ensure_readable`
    - `update_script` → 改 `_ensure_modifiable`；name 查重改用 `script.owner_user_uid`（不是請求者 uid）
    - `soft_delete_script` → 改 `_ensure_owner`，**仍走軟刪（`is_deleted=True`）**，admin 亦不能代刪
2. [backend/app/api/v1/scripts/router.py](../../../backend/app/api/v1/scripts/router.py)：四個端點補傳 `current_user.role`
3. [docs/Design-Base/40-permission.md](../../Design-Base/40-permission.md)：
    - `member + admin 共用端點` 表格內三個資源（agent / skill / script）的描述改為明示「讀 / 下載 / 改 / 刪 / 切可見性」各自的權限切片
    - `資源存取控制` 段補「可見性開放」與「軟刪除規則」兩條原則，並加四象限對照表

**影響檔案**

- [backend/app/services/script_service.py](../../../backend/app/services/script_service.py)
- [backend/app/api/v1/scripts/router.py](../../../backend/app/api/v1/scripts/router.py)
- [docs/Design-Base/40-permission.md](../../Design-Base/40-permission.md)

**驗證方式**

1. admin 登入 → `GET /api/v1/scripts/{他人 script_uid}` 應回 200（admin 可讀）
2. 一般使用者 A 登入 → `GET /api/v1/scripts/{B 的 visibility=public script_uid}/download` 應回 200 zip（公開可下載）
3. 一般使用者 A 登入 → `GET /api/v1/scripts/{B 的 visibility=private script_uid}` 應回 404
4. admin 登入 → `DELETE /api/v1/scripts/{他人 script_uid}` 應回 403（admin 不代刪）
5. admin 登入 → `PATCH /api/v1/scripts/{他人 script_uid}` 修改 name 應成功，且 name 查重以實際擁有者為準

---

## 8. 上線前安全 / 可觀測性基線補強（一次性批次）〔2026-04-27 11:13:04〕

**問題**

[scan-project 報告 Issue-Scan-Project-260427100515.md](../scan-project/Issue-Scan-Project-260427100515.md) 指出多項上線阻擋 / 高優先風險：Skill 上傳缺 zip bomb 防線、`SECRET_KEY` 無強度驗證、`CORS_ORIGINS` 上線值未強制、無 rate-limit、無結構化 log / request id、無 readiness 探活、三頁與 `ScriptUploadDialog` 重複實作 `FilterChip`、`update_file_content` path 未過濾 `..`。屬於 v1.0~v1.3 系列累積、跨版本長期存在的基礎設施 / 安全缺口，使用者要求一次性補齊。

**根因**

開發過程聚焦業務功能（Agent / Skill / Script CRUD、收藏、Agentic skill suggestion 等），基礎設施層（middleware、log、rate-limit、上傳安全閘）一直延後。`script_service._check_zip_bomb` 已在 v1.2.3 寫好，但 Skill 服務沒同步抄；`SECRET_KEY` / `CORS_ORIGINS` 在 dev 環境誤填不會被擋；rate-limit 從 v1.0 起一直沒掛。

**修正**

1. **安全閘**
    - [skill_service.py](../../../backend/app/services/skill_service.py)：新增 `_check_zip_bomb()`（與 `script_service._check_zip_bomb` 同邏輯，N=10 倍解壓上限），`upload_skill` / `reupload_skill` 落盤後立即執行
    - [skill_service.py::update_file_content](../../../backend/app/services/skill_service.py)：規範化後檢查 path 段不可含 `..` 或空段（防 zip-slip 未來面，目前未解壓所以無實漏）
2. **Settings 強度檢查**
    - [config.py](../../../backend/app/core/config.py)：`SECRET_KEY` 加 `@field_validator`（< 32 字元拒啟動）；新增 `@model_validator(mode="after")` 在 `APP_ENV=production` 下檢查 `CORS_ORIGINS` 不含 `*` / localhost / 127.0.0.1 / 0.0.0.0
3. **Rate-limit**
    - 新增 [core/rate_limit.py](../../../backend/app/core/rate_limit.py)：Redis fixed-window middleware；規則註冊 `auth/login` (10/min)、`auth/register` (5/5min)、`auth/reset-password` (5/5min)、`POST /skills` (20/5min)、`POST /scripts` (20/5min)
    - Redis 不可用時 fail-open（記 warning，不阻斷請求 — 安全 / 可用權衡，與 `download_service` 等多處原則一致）
    - 限流命中回 `429` + `Retry-After` header + `ApiResponse` 格式 `detail`
4. **可觀測性**
    - 新增 [core/logging_config.py](../../../backend/app/core/logging_config.py)：JSON formatter（`request_id` / `user_uid` 自 contextvars 取用）+ `setup_logging()` + `RequestContextMiddleware`（讀 X-Request-ID 或自產 uuid4，access log 含 method / path / status / duration_ms）
    - [main.py](../../../backend/app/main.py)：import 階段呼叫 `setup_logging("INFO")`，覆寫 root handler；CORS 後加 `RateLimitMiddleware` 與 `RequestContextMiddleware`
    - [api/deps.py::get_current_user](../../../backend/app/api/deps.py)：成功驗證後 `set_user_uid(user_uid)`，供後續 log 取用
    - [api/v1/health.py](../../../backend/app/api/v1/health.py)：新增 `GET /api/v1/health/ready`，輕量 DB + Redis 探活（不含 queue / DLQ 計數）
5. **前端共用元件統一**
    - [agents/page.tsx](../../../frontend/src/app/(main)/agents/page.tsx)、[skills/page.tsx](../../../frontend/src/app/(main)/skills/page.tsx)、[scripts/page.tsx](../../../frontend/src/app/(main)/scripts/page.tsx)：刪除 local `FilterChip`，改 import [`@/components/ui/FilterChip`](../../../frontend/src/components/ui/FilterChip.tsx)
    - [scripts/ScriptUploadDialog.tsx](../../../frontend/src/app/(main)/scripts/ScriptUploadDialog.tsx)：上傳模式（選檔案 / 選資料夾）與可見性切換（私人 / 公開）改用 `<FilterChip>`，移除自寫 button class

**影響檔案**

- [backend/app/services/skill_service.py](../../../backend/app/services/skill_service.py)
- [backend/app/core/config.py](../../../backend/app/core/config.py)
- [backend/app/core/rate_limit.py](../../../backend/app/core/rate_limit.py)（新檔）
- [backend/app/core/logging_config.py](../../../backend/app/core/logging_config.py)（新檔）
- [backend/app/main.py](../../../backend/app/main.py)
- [backend/app/api/deps.py](../../../backend/app/api/deps.py)
- [backend/app/api/v1/health.py](../../../backend/app/api/v1/health.py)
- [frontend/src/app/(main)/agents/page.tsx](../../../frontend/src/app/(main)/agents/page.tsx)
- [frontend/src/app/(main)/skills/page.tsx](../../../frontend/src/app/(main)/skills/page.tsx)
- [frontend/src/app/(main)/scripts/page.tsx](../../../frontend/src/app/(main)/scripts/page.tsx)
- [frontend/src/app/(main)/scripts/ScriptUploadDialog.tsx](../../../frontend/src/app/(main)/scripts/ScriptUploadDialog.tsx)

**驗證方式**

1. `curl -i http://localhost:8000/api/v1/health/ready` 應回 200 + `X-Request-ID` header + JSON body `{"status":"ready"}`
2. backend log 應為 JSON line，含 `ts` / `level` / `logger` / `msg` / `request_id`（已在啟動 log 確認）
3. 連續 11 次 `POST /api/v1/auth/login` 同 IP 應於第 11 次回 429 + `Retry-After`
4. Skill 上傳一個壓縮比 > 10 倍的惡意 zip（`dd if=/dev/zero bs=1M count=100 | gzip → 上傳 zip`）應 400「壓縮後內容異常」
5. 將 `.env` 的 `SECRET_KEY` 改成 < 32 字元，重啟 backend 應 ValidationError 拒啟動
6. 將 `.env` 的 `APP_ENV=production` + `CORS_ORIGINS=["http://localhost:3000"]`，重啟應 ValidationError
7. `update_file_content` 帶 `path=../etc/passwd` 應 400「不允許的路徑」
8. 三個列表頁切換 visibility / 排序 chip 應與 `/skill-suggestions` chip 視覺完全一致

**殘留 / 後續**

- Skill 服務的同步檔案 IO（`Path.write_bytes()`）改 `aiofiles` — 留 v1.4
- 上傳端點 `Content-Length` 入口層強制 — 建議 reverse-proxy / Uvicorn 層處理，本任務不動程式
- 三 service `_ensure_owner` 重複 → `core/access.py` 共用整合 — 留 v1.4 純 refactor
- v1.1.7 Redis Skill suggestion 暫存退場 — 時間驅動（2026-05-02 後）
- Phase 7 v1.3.6 runtime smoke — 需使用者於 docker compose 起動環境執行
