# v1.0.2 任務規格

## 版本目標

強化 Agent 建立／編輯表單的使用體驗與資料結構：

- 語言偏好改以 **DB 表**驅動的 Select（非 Enum）
- 補齊 Skills 多選器
- 加入 system prompt 即時預覽
- Temperature 滑桿 + preset、max_tokens preset + 模型上限警告
- 欄位分區（基本 / 角色 / 模型 / 互動）
- 模型下拉預設為系統預設模型（由後端標記，非空字串）
- 範本套用 + 從既有 Agent 複製
- 草稿自動儲存（localStorage）

### 範圍內

- 後端：新增 `agent_language` 表與 CRUD 端點（admin 管理，member 唯讀）
- 後端：`llm_model` 表增加 `is_default`、`max_output_tokens` 欄位
- 前端：`/agents/new`、`/agents/[uid]/edit` 表單全面改版
- 前端：`agent_language` 讀取、範本常數、localStorage 草稿

### 範圍外（後續版本）

- Agent Templates 存至 DB（本版先用前端常數）
- 試聊 / Preview Chat 功能
- 多語系 agent（單一 agent 支援多語切換）

---

## 前置現況

- `agent` 表：`language VARCHAR(50)`（自由文字）— v1.0.2 改為儲存 `agent_language.code`
- `llm_model` 表：已有 `provider / model_id / display_name / is_active / is_deleted`
- Agent 新增頁已預留「Skills（尚未開放）」佔位區塊
- Skills API `useListSkillsQuery` 回傳「自己的 + 公開」Skills，可直接用於多選
- `agentsApi.useCreateAgentMutation` 已支援 `skill_uids` 欄位，目前前端只送空陣列

---

## 已確認決策

| #   | 項目                 | 結論                                                                                                     |
| --- | -------------------- | -------------------------------------------------------------------------------------------------------- |
| 1   | 語言偏好儲存格式     | `agent.language` 儲存 `agent_language.code`（如 `zh-TW`、`en`），**非** display name                     |
| 2   | 語言表管理權限       | admin 可增刪改；member 只能讀                                                                            |
| 3   | 預設語言             | Seed `zh-TW` 並設為 `is_default = TRUE`；Agent 建立表單自動選此語言                                      |
| 4   | 預設模型             | `llm_model.is_default` 單一筆為 `TRUE`（以 partial unique index 保證）                                   |
| 5   | 模型 max_tokens 上限 | `llm_model.max_output_tokens INTEGER NULL`，NULL 代表未設定（前端不做上限警告）                          |
| 6   | Templates            | 本版存於前端 `frontend/src/utils/agentTemplates.ts` 常數；提供 4 個起手式                                |
| 7   | 從既有 Agent 複製    | `/agents/new?from={agent_uid}` 進入時預填，需使用者在該 agent 有可見權限                                 |
| 8   | 草稿自動儲存         | localStorage key `agent-draft`；每 2 秒節流儲存；表單成功送出或取消後清除；編輯模式不啟用草稿            |
| 9   | System prompt 組裝   | 後端實際組裝順序（在 service 內）：`identity → language → style → role_prompt`；前端預覽面板依此順序顯示 |
| 10  | Skills 多選上限      | 預設 10 個（admin 可調）；存於新建的 `system_setting` 表，key = `agent.max_skills`                       |
| 11  | 草稿載入行為         | 進入新增頁若有草稿，**直接自動載入**（不彈確認 dialog）；表單上方顯示 banner：「已恢復上次草稿 [清除]」  |
| 12  | 草稿唯一性           | 每位使用者同時僅 **一份**新增草稿；localStorage key 固定（不帶 timestamp）                               |
| 13  | 系統設定儲存         | 新增 `system_setting` 表（key/value），供未來其他可調參數擴充                                            |

---

## Phase 1：後端

### 1-1 資料庫 Migration

#### V12：建立 `agent_language` 表

- [ ] `migrations/sql/V12__create_agent_language_table.sql`
- 必備欄位遵循 `21-database.md §必備欄位`
- 額外欄位：
  - `code VARCHAR(20) NOT NULL`（語系碼，如 `zh-TW`、`en`、`ja`）
  - `name VARCHAR(50) NOT NULL`（顯示名稱，如 `繁體中文`）
  - `sort_order INTEGER NOT NULL DEFAULT 0`（下拉排序）
  - `is_default BOOLEAN NOT NULL DEFAULT FALSE`（預設語言）
- 約束：
  - `UNIQUE INDEX uq_agent_language_code ON agent_language(code) WHERE is_deleted = FALSE`
  - `UNIQUE INDEX uq_agent_language_default ON agent_language(is_default) WHERE is_default = TRUE AND is_deleted = FALSE`（保證只有一筆 default）
- 每欄位加上 `COMMENT ON COLUMN`
- 掛 `trg_agent_language_updated_at`
- Seed：

```sql
INSERT INTO agent_language (code, name, sort_order, is_default) VALUES
  ('zh-TW', '繁體中文', 10, TRUE),
  ('en',    'English',  20, FALSE),
  ('ja',    '日本語',   30, FALSE),
  ('zh-CN', '简体中文', 40, FALSE),
  ('ko',    '한국어',   50, FALSE)
ON CONFLICT DO NOTHING;
```

#### V13：`llm_model` 增欄位

- [ ] `migrations/sql/V13__extend_llm_model.sql`
- 增加：
  - `is_default BOOLEAN NOT NULL DEFAULT FALSE`
  - `max_output_tokens INTEGER NULL`
- 約束：`UNIQUE INDEX uq_llm_model_default ON llm_model(is_default) WHERE is_default = TRUE AND is_deleted = FALSE`
- `COMMENT ON COLUMN`：
  - `is_default`：系統預設模型（全表唯一）
  - `max_output_tokens`：單次回覆最大 Token 數（NULL 表示未設定）
- Seed 更新：將 `anthropic/claude-sonnet-4` 標記為 `is_default = TRUE`，並補上各模型的 `max_output_tokens`（claude-sonnet-4=8192、claude-haiku-4=8192、gpt-4o=16384、gpt-4o-mini=16384、gemini-2.5-flash=8192，以官方文件為準）

#### V14：建立 `system_setting` 表

- [ ] `migrations/sql/V14__create_system_setting_table.sql`
- 必備欄位遵循 `21-database.md §必備欄位`
- 額外欄位：
  - `key VARCHAR(100) NOT NULL`（設定鍵）
  - `value TEXT NOT NULL`（設定值，統一以字串儲存，由服務層按型別解析）
  - `value_type VARCHAR(20) NOT NULL DEFAULT 'string'`（`string` / `integer` / `boolean` / `json`，供前後端解析）
  - `description TEXT`（說明）
  - `is_public BOOLEAN NOT NULL DEFAULT FALSE`（是否可由 member 讀取；`TRUE` 的 key 會出現在 `GET /api/v1/settings/public`）
- 約束：`UNIQUE INDEX uq_system_setting_key ON system_setting(key) WHERE is_deleted = FALSE`
- 掛 `trg_system_setting_updated_at`
- 每欄位加上 `COMMENT ON COLUMN`
- Seed：

```sql
INSERT INTO system_setting (key, value, value_type, description, is_public) VALUES
  ('agent.max_skills', '10', 'integer', 'Agent 可關聯的 Skills 數量上限', TRUE)
ON CONFLICT DO NOTHING;
```

### 1-2 Model（SQLAlchemy）

- [ ] 新增 `backend/app/models/agent_language.py`：`AgentLanguage` class，繼承 `Base`
- [ ] 新增 `backend/app/models/system_setting.py`：`SystemSetting` class，繼承 `Base`
- [ ] `backend/app/models/llm_model.py` 增加 `is_default`、`max_output_tokens` 欄位
- [ ] `backend/app/models/__init__.py` 匯出 `AgentLanguage`、`SystemSetting`

### 1-3 Schema

- [ ] `backend/app/schemas/agent_languages/schemas.py`（新目錄）
  - `AgentLanguageResponse`：`agent_language_uid / code / name / sort_order / is_default / is_active / created_at / updated_at`
  - `AgentLanguageCreateRequest`：`code / name / sort_order / is_default`
  - `AgentLanguageUpdateRequest`：`name / sort_order / is_default / is_active`（`code` 建立後不可變）
- [ ] `backend/app/schemas/models/schemas.py` 擴充：
  - `LlmModelResponse` 追加 `is_default: bool`、`max_output_tokens: int | None`
  - `LlmModelCreateRequest` / `LlmModelUpdateRequest` 追加同樣欄位
- [ ] `backend/app/schemas/agents/schemas.py`：
  - `language` 仍為 `str | None`（儲存 code）
  - `skill_uids` 上限由 service 層動態讀 `system_setting.agent.max_skills` 後驗證（schema 不做硬編碼）
- [ ] `backend/app/schemas/system_settings/schemas.py`（新目錄）
  - `SystemSettingResponse`：`system_setting_uid / key / value / value_type / description / is_public / is_active / created_at / updated_at`
  - `SystemSettingUpdateRequest`：`value / description / is_public / is_active`（`key` 與 `value_type` 建立後不可變）
  - `SystemSettingPublicDict`：`dict[str, str | int | bool]`（按 `value_type` 解析後的 key/value 對照）

### 1-4 Repository

- [ ] `backend/app/repositories/agent_language_repository.py`：
  - `list_active(db)`：member 唯讀；`is_active = TRUE AND is_deleted = FALSE`，按 `sort_order ASC, pid ASC`
  - `list_all(cursor, limit, db)`：admin 用
  - `get_by_uid(uid, db)`
  - `get_by_code(code, db)`：唯一性檢查
  - `get_default(db)`：取 `is_default = TRUE` 的語言
  - `create / update / soft_delete`：`await db.refresh(obj)`
- [ ] `backend/app/repositories/llm_model_repository.py` 擴充：
  - `get_default(db)`：取 `is_default = TRUE AND is_active = TRUE` 的模型
- [ ] `backend/app/repositories/system_setting_repository.py`：
  - `list_public(db)`：`is_public = TRUE AND is_active = TRUE AND is_deleted = FALSE`
  - `list_all(db)`：admin 用（含非 public）
  - `get_by_key(key, db)`
  - `update(obj, update_data, db)`：`await db.refresh(obj)`

### 1-5 Service

- [ ] `backend/app/services/agent_language_service.py`
  - `list_languages()`：member 用，回傳啟用中清單
  - `list_languages_admin(cursor, limit)`
  - `create_language(data)`：
    - 檢查 `code` 重複 → 409
    - 若 `is_default = TRUE`，先把所有其他語言的 `is_default` 設為 FALSE（單一 transaction）
  - `update_language(uid, data)`：同上 default 切換邏輯
  - `delete_language(uid)`：禁止刪除 `is_default = TRUE` 的語言（400）
- [ ] `backend/app/services/llm_model_service.py` 擴充：
  - `create/update` 處理 `is_default` 切換（同語言邏輯，全表唯一）
- [ ] `backend/app/services/agent_service.py` 調整：
  - 建立/更新 Agent 時，若 `language` 非空，驗證其為 `agent_language.code` 中啟用的語言
  - 建立/更新 Agent 時，`skill_uids` 數量以 `system_setting.agent.max_skills` 為上限（超過 → 400，訊息帶回當前上限）
  - system prompt 組裝順序已於決策 #9 確定，若未來有組裝服務再套用
- [ ] `backend/app/services/system_setting_service.py`
  - `get_public_dict()`：回傳 `is_public = TRUE` 的 `{ key: 按 value_type 解析過的值 }`
  - `list_admin()`：admin 檢視全部
  - `update_setting(key, data)`：找不到 key 則 404；驗證 `value` 符合 `value_type`（e.g. `integer` 必須可 parseInt）
  - `get_int(key, default)` / `get_bool(key, default)`：內部工具，由 agent_service 呼叫
  - 讀取可加短 TTL 快取（Redis 或程序內 LRU），避免每次建 Agent 都查 DB

### 1-6 Router

#### Member 唯讀

| 方法 | 端點                       | 說明                                     |
| ---- | -------------------------- | ---------------------------------------- |
| GET  | `/api/v1/agent-languages`  | 啟用語言清單                             |
| GET  | `/api/v1/settings/public`  | 公開系統設定（`{ key: 解析後值 }` 字典） |

#### Admin 管理

Agent 語言管理：

| 方法   | 端點                                  | 說明           |
| ------ | ------------------------------------- | -------------- |
| GET    | `/api/v1/admin/agent-languages`       | 列表（含停用） |
| POST   | `/api/v1/admin/agent-languages`       | 新增           |
| GET    | `/api/v1/admin/agent-languages/{uid}` | 詳情           |
| PUT    | `/api/v1/admin/agent-languages/{uid}` | 更新           |
| DELETE | `/api/v1/admin/agent-languages/{uid}` | 軟刪除         |

系統設定管理：

| 方法 | 端點                           | 說明                                 |
| ---- | ------------------------------ | ------------------------------------ |
| GET  | `/api/v1/admin/settings`       | 列出全部系統設定（含非 public）      |
| PUT  | `/api/v1/admin/settings/{key}` | 更新指定 key 的值 / 說明 / is_public |

- [ ] Admin 端點套用 `require_role("admin")`
- [ ] `PUT /api/v1/admin/settings/{key}` 會驗證 value 是否能依 `value_type` 解析成功
- [ ] Swagger `/api/docs` 顯示完整 Schema

### 1-7 Swagger

- [ ] 新端點 Request / Response 皆可於 `/api/docs` 正常顯示

---

## Phase 2：前端

### 2-1 型別

- [ ] `frontend/src/types/agent-languages.ts`：`AgentLanguage`、`AgentLanguageCreateRequest`、`AgentLanguageUpdateRequest`
- [ ] `frontend/src/types/models.ts`：`LlmModel` 加 `is_default`、`max_output_tokens`
- [ ] `frontend/src/types/system-settings.ts`：`SystemSetting`、`SystemSettingUpdateRequest`、`PublicSettings = Record<string, string | number | boolean>`
- [ ] `frontend/src/types/index.ts` re-export

### 2-2 RTK Query

- [ ] 新增 `frontend/src/store/agentLanguagesApi.ts`
  - `useListAgentLanguagesQuery`（member）
  - `useListAdminAgentLanguagesQuery` / `useCreate...` / `useUpdate...` / `useDelete...`
- [ ] 新增 `frontend/src/store/systemSettingsApi.ts`
  - `useGetPublicSettingsQuery`（member，回傳 `PublicSettings` 字典）
  - `useListAdminSettingsQuery` / `useUpdateSettingMutation`
- [ ] `modelsApi.ts`：如前端查詢 models 的地方都要 provide `is_default` 與 `max_output_tokens`，原 hook 不需變

### 2-3 共用工具 / 常數

- [ ] `frontend/src/utils/agentTemplates.ts`
  - 匯出 `AGENT_TEMPLATES: AgentTemplate[]`
  - 4 個範本：`Python 開發助手` / `Code Reviewer` / `中文寫作助手` / `中英翻譯`
  - 型別：`{ key: string; label: string; description: string; values: Partial<FormState> }`
- [ ] `frontend/src/utils/agentPrompt.ts`
  - `composeSystemPrompt({ identity, language, style, role_prompt })`：依決策 #9 順序組字串（語言以 code 查表後以 name 呈現）
- [ ] `frontend/src/hooks/useAgentDraft.ts`
  - 讀/寫 localStorage（key `agent-draft`），throttle 2 秒
  - 提供 `loadDraft / saveDraft / clearDraft`

### 2-4 共用 UI 元件

- [ ] `frontend/src/components/ui/Slider.tsx`
  - props: `min / max / step / value / onChange / marks?`
  - 用原生 `<input type="range">` + Tailwind 即可；必要時後續升級
- [ ] `frontend/src/components/ui/MultiSelect.tsx`（可選，若不複用就內嵌於表單）
  - 輸入搜尋 + chip 呈現已選項目

### 2-5 頁面改版：`/agents/new` 與 `/agents/[uid]/edit`

兩頁共用元件化區塊，抽成 `frontend/src/app/(main)/agents/_components/AgentForm.tsx`：

#### 表單分區（摺疊卡片或 heading）

##### 基本資訊

- [ ] 名稱 / 描述 / 可見性

##### 角色設定

- [ ] 身分（input）
- [ ] 語言偏好（Select，options 來自 `useListAgentLanguagesQuery`；新增表單預設選 `is_default` 的語言）
- [ ] 風格（input）
- [ ] 角色設定（textarea）

##### 模型參數

- [ ] 模型（Select，options 來自 `useListModelsQuery`；新增表單預設選 `is_default` 的模型）
- [ ] 溫度：
  - 滑桿 0.0 – 2.0，step 0.1
  - Preset 按鈕：`保守 0.2` / `平衡 0.7` / `發散 1.2`
  - 右側顯示當前數值
- [ ] 最大 Token 數：
  - Preset 按鈕：`1K / 4K / 8K / 32K`
  - 自訂 input（整數）
  - 當選定模型有 `max_output_tokens` 時，超過上限顯示警告（紅字）但不阻擋送出
- [ ] 回覆格式（Select：Markdown / 純文字 / JSON）

##### 互動

- [ ] 開場白（textarea）
- [ ] Skills 多選：
  - 搜尋框 + 可選清單
  - 來源：`useListSkillsQuery`（自己的 + 公開）
  - 已選以 chip 顯示（可移除）
  - 上限讀取自 `GET /api/v1/settings/public` 的 `agent.max_skills`（預設 10，admin 可調）

#### 頁首控制列

- [ ] `套用範本` 按鈕（下拉選擇 4 個範本 + `空白`；僅新增頁顯示）
- [ ] `從既有 Agent 複製` 按鈕（僅新增頁顯示）
  - 進入 modal，列出使用者可見的 agents（自己的 + 公開），點擊後呼叫 `useGetAgentQuery` 取詳情並預填
- [ ] 網址帶 `?from={uid}` 亦觸發同樣流程

#### System Prompt 預覽區

- [ ] 右側（或下方）卡片，標題「📄 實際送出的 System Prompt」
- [ ] 依 `composeSystemPrompt` 即時渲染 `<pre>`
- [ ] 空欄位顯示為灰色 placeholder 文字，不呈現空段

#### 草稿自動儲存

- [ ] 新增頁進入時讀取 localStorage，若有草稿**直接自動載入**到表單
- [ ] 草稿已載入時，表單上方顯示提示 banner：「已恢復上次未完成的草稿」+ `清除草稿` 按鈕
- [ ] 表單變動 throttle 2 秒寫入 localStorage（單一 key：`agent-draft`，每使用者僅一份）
- [ ] 成功送出後 / 使用者按「取消」→ 清除草稿
- [ ] 編輯頁不啟用草稿

### 2-6 Admin 頁面（語言管理）

- [ ] 新增 `frontend/src/app/(main)/admin/agent-languages/page.tsx`
  - 表格列出：code / name / sort_order / is_default（徽章） / is_active / 操作
  - 新增 / 編輯 Dialog
  - 刪除 Warning Dialog
  - 路由守衛：非 admin 導向 403
- [ ] Sidebar admin 區增加「語言管理」入口

### 2-7 Admin 頁面（系統設定）

- [ ] 新增 `frontend/src/app/(main)/admin/settings/page.tsx`
  - 表格列出：key / value（依 `value_type` 用適當輸入元件）/ description / is_public（徽章）/ is_active / 操作
  - 編輯 Dialog：`value_type = integer` 用數字 input、`boolean` 用 toggle、其餘用 text；`value_type` 唯讀
  - 前端於送出前依 `value_type` 驗證 value 可解析
  - 路由守衛：非 admin 導向 403
- [ ] Sidebar admin 區增加「系統設定」入口

### 2-8 既有頁面調整

- [ ] `/admin/models` 頁新增欄位編輯：`is_default` toggle、`max_output_tokens` 輸入
- [ ] Dashboard / Agents 列表詳情頁如有顯示「語言」欄位，改為依 code 查表呈現 `name`

---

## Phase 3：驗收

### 後端

- [ ] V12 / V13 / V14 Migration 可正常套用到空 DB 與既有 DB
- [ ] `GET /api/v1/agent-languages` 回傳啟用語言清單（按 sort_order）
- [ ] 新增/更新 `agent_language` 時，若 `is_default = TRUE` 會自動把其他項設為 FALSE
- [ ] 嘗試刪除 `is_default` 語言 → 400
- [ ] `llm_model` 新 `is_default` / `max_output_tokens` 欄位於 admin 端點可編輯
- [ ] 系統預設語言與預設模型可由 `get_default` 正確取出
- [ ] `GET /api/v1/settings/public` 只回傳 `is_public = TRUE` 的 key，且值依 `value_type` 解析
- [ ] `PUT /api/v1/admin/settings/agent.max_skills` 將值改為 `5` 後，建立 Agent 超過 5 個 skill → 400（訊息顯示當前上限為 5）
- [ ] `PUT /api/v1/admin/settings/{key}` 收到無法解析的值 → 422
- [ ] `/api/docs` 顯示所有新端點

### 前端

- [ ] `/agents/new` 開啟時：
  - 語言預設為 `zh-TW`
  - 模型預設為 `is_default` 的模型
  - Temperature 預設 0.7、max_tokens 預設 4096
- [ ] Temperature 滑桿與 preset 按鈕雙向同步
- [ ] Max Token 超過選定模型上限時顯示警告
- [ ] System prompt 預覽區即時反映 identity / language / style / role_prompt 的變更
- [ ] Skills 多選可搜尋、加入、移除；上限動態反映 `GET /api/v1/settings/public` 的 `agent.max_skills`
- [ ] admin 於 `/admin/settings` 調整 `agent.max_skills` 後，使用者重新整理 `/agents/new` 新上限即時生效
- [ ] 範本套用後所有欄位正確填入
- [ ] `?from={uid}` 或點選「從既有 Agent 複製」後表單預填正確
- [ ] 關閉 Tab 再開啟 `/agents/new`，草稿**直接自動載入**並顯示 banner 提示
- [ ] banner 「清除草稿」按鈕可清除當前草稿並重置表單
- [ ] 成功建立 / 按取消後草稿清除
- [ ] 編輯頁不出現草稿 banner
- [ ] 非 admin 訪問 `/admin/agent-languages` 或 `/admin/settings` 被導向 403

### 回歸

- [ ] 既有 Agent（language 為自由文字如 `繁體中文`）於詳情頁 / 列表仍可正常顯示（找不到對應 code 時 fallback 顯示原值）
- [ ] 既有建立流程不因新欄位預設值缺失而報錯
- [ ] 所有 Migration / API / UI 遵守 `21-database.md` 時區規範（UTC+8）
