# v1.0.1 任務規格

## 版本目標

新增 **LLM 模型清單管理**功能：由 admin 維護系統可用模型清單，統一以 **OpenRouter** 作為 provider 來源；member 僅能唯讀（於建立/編輯 Agent 時透過下拉選單選取），無新增/編輯/刪除權限。

### 範圍內

- Admin 管理 LLM 模型清單（新增、編輯、啟用/停用、軟刪除）
- Provider 統一為 `OpenRouter`，`model_id` 對應 OpenRouter 的模型 slug（如 `anthropic/claude-sonnet-4`）
- Member 透過既有 `GET /api/v1/models` 唯讀取得啟用中的模型清單
- 前端 admin 管理頁：`/admin/models`
- 前端路由守衛：非 admin 訪問 `/admin/models` 導向 403

### 範圍外（後續版本）

- 模型可用性即時檢測（打 OpenRouter API 驗證模型是否存在）
- 模型定價/額度顯示
- 多 provider 並存（OpenAI、Anthropic 直連等）
- 使用者自備金鑰（BYOK）

---

## 前置現況

v1.0 已完成以下基礎，v1.0.1 於此之上擴充：

- `llm_model` 表（`migrations/sql/V9__create_llm_model_table.sql`）含 `provider` / `model_id` / `display_name` / `is_active` / `is_deleted`
- `backend/app/models/llm_model.py` SQLAlchemy model
- `backend/app/repositories/llm_model_repository.py::get_all_active`
- `backend/app/api/v1/models/router.py::list_models`（member 唯讀端點）
- `frontend/src/store/modelsApi.ts`

---

## 已確認決策

| #   | 決策                      | 結論                                                                                        |
| --- | ------------------------- | ------------------------------------------------------------------------------------------- |
| 1   | Provider 統一             | 固定為 `OpenRouter`；新增/編輯時 provider 欄位由後端預設帶入，不開放前端選擇                |
| 2   | `model_id` 格式           | 必須符合 OpenRouter 格式 `<vendor>/<model-slug>`（如 `anthropic/claude-sonnet-4`），後端驗證 |
| 3   | 刪除策略                  | 僅軟刪除（`is_deleted = true`）；已被 Agent 引用的模型不禁止刪除，但前端需提示              |
| 4   | 啟用/停用                 | `is_active` 控制 member 下拉是否列出；停用不視為刪除                                        |
| 5   | Member 讀取端點           | 沿用既有 `GET /api/v1/models`，僅回傳 `is_active = true AND is_deleted = false` 的模型      |
| 6   | Admin 管理端點路徑        | `/api/v1/admin/llm-models`（遵循 v1.0 admin 路由前綴慣例）                                  |
| 7   | `model_id` 唯一性         | DB 已存在 `uq_llm_model_model_id` 唯一索引；後端需回傳友善錯誤訊息而非 500                  |
| 8   | Seed data 處理            | V9 Migration 既有 seed 保留；v1.0.1 不追加 seed                                             |

---

## Phase 1：後端

### 1-1 資料庫

- [ ] 無新增 Migration（沿用 V9 表結構）
- [ ] 若未來需追加欄位（如 `context_window`、`cost_input`、`cost_output`），另開 Migration 並更新本規格

### 1-2 Schema

於 `backend/app/schemas/models/schemas.py` 補齊：

- [ ] `LlmModelCreateRequest`
  - `model_id: str`（必填，validator 驗證 `<vendor>/<slug>` 格式，長度 ≤ 100）
  - `display_name: str`（必填，trim，長度 1–100）
- [ ] `LlmModelUpdateRequest`
  - `display_name: str | None`
  - `is_active: bool | None`
  - （`model_id` 建立後不可變更；需要變更請刪除後重建）
- [ ] `LlmModelAdminResponse`
  - `llm_model_uid`, `provider`, `model_id`, `display_name`, `is_active`, `is_deleted`, `created_at`, `updated_at`

### 1-3 Repository

於 `backend/app/repositories/llm_model_repository.py` 新增：

- [ ] `list_all(cursor, limit, db)`：含 `is_deleted = false` 的全部（不論 `is_active`），cursor-based 分頁
- [ ] `get_by_uid(llm_model_uid, db)`
- [ ] `get_by_model_id(model_id, db)`：唯一性檢查用
- [ ] `create(data, db)`：`flush` 後 `await db.refresh(obj)`（避免 `onupdate` 欄位 MissingGreenlet 問題，沿用 v1.0 修正慣例）
- [ ] `update(obj, update_data, db)`：同上 refresh
- [ ] `soft_delete(obj, db)`

### 1-4 Service

新增 `backend/app/services/llm_model_service.py`：

- [ ] `list_models_admin(cursor, limit, db)`：回傳 admin 視角（含停用/未軟刪的全部）
- [ ] `create_model(data, db)`：
  - provider 固定填入 `"OpenRouter"`
  - 先查 `get_by_model_id`，若已存在則回傳 409 `AppError`：「模型 ID 已存在」
- [ ] `update_model(llm_model_uid, data, db)`：找不到則 404
- [ ] `delete_model(llm_model_uid, db)`：軟刪除

### 1-5 Router

新增 `backend/app/api/v1/admin/llm_models.py`（或掛在既有 `admin/router.py`）：

| 方法   | 端點                                    | 說明                                    |
| ------ | --------------------------------------- | --------------------------------------- |
| GET    | `/api/v1/admin/llm-models`              | 列表（cursor-based，含停用）            |
| POST   | `/api/v1/admin/llm-models`              | 新增（provider 固定為 OpenRouter）      |
| GET    | `/api/v1/admin/llm-models/{uid}`        | 詳情                                    |
| PUT    | `/api/v1/admin/llm-models/{uid}`        | 更新 `display_name` / `is_active`       |
| DELETE | `/api/v1/admin/llm-models/{uid}`        | 軟刪除                                  |

- [ ] 全端點套用 `require_role("admin")`
- [ ] 既有 `GET /api/v1/models`（member 唯讀）不變動

### 1-6 Swagger

- [ ] `/api/docs` 需顯示全部新端點及 Request/Response Schema

---

## Phase 2：前端

### 2-1 型別

於 `frontend/src/types/` 新增或擴充：

- [ ] `LlmModel`（admin 視角完整欄位）
- [ ] `LlmModelCreateRequest` / `LlmModelUpdateRequest`

### 2-2 RTK Query

於 `frontend/src/store/modelsApi.ts` 新增 admin hooks：

- [ ] `useListAdminModelsQuery({ cursor, limit })`
- [ ] `useCreateModelMutation`
- [ ] `useUpdateModelMutation`
- [ ] `useDeleteModelMutation`
- [ ] 既有 `useListModelsQuery`（member 用）保留不動

### 2-3 頁面

新增 `frontend/src/app/(main)/admin/models/page.tsx`：

- [ ] 表格式列表：顯示 `provider`（固定 OpenRouter）/ `model_id` / `display_name` / `is_active` 狀態 / 操作按鈕
- [ ] 分頁元件（cursor-based，沿用 v1.0 共用元件）
- [ ] 新增按鈕 → Dialog 表單：`model_id`（input，placeholder `anthropic/claude-sonnet-4`）、`display_name`
  - 前端即時驗證 `model_id` 格式（regex `^[a-z0-9-]+\/[a-z0-9.-]+$`）
  - 送出 loading / 錯誤透過 Error Dialog
- [ ] 編輯 → Dialog 表單：`display_name` 可改、`is_active` toggle（`model_id` 顯示為唯讀文字）
- [ ] 刪除 → Warning Dialog 確認：「確定刪除？已設定此模型的 Agent 將無法使用。」

### 2-4 路由守衛

- [ ] Non-admin 訪問 `/admin/models` → 導向 403（沿用 v1.0 共用機制）

### 2-5 Sidebar

- [ ] admin 角色於 Sidebar「管理」分類下新增入口「模型管理」，連結至 `/admin/models`

### 2-6 Agent 表單

- [ ] 既有 Agent 建立/編輯頁的模型下拉，保持使用 `useListModelsQuery`（member 唯讀端點）
- [ ] 確認若使用者原本選擇的模型已被 admin 停用/刪除，表單需顯示「此模型已停用」提示並允許重新選擇

---

## Phase 3：驗收

- [ ] Admin 可於 `/admin/models` 新增 / 編輯 / 停用 / 刪除 OpenRouter 模型
- [ ] Member 訪問 `/admin/models` 被導向 403
- [ ] Member 於 Agent 表單只看到啟用中的模型
- [ ] 重複新增相同 `model_id` 回傳 409 並以 Error Dialog 提示
- [ ] `model_id` 格式不符（未含 `/`、含非法字元）前端阻擋，後端亦回傳 422
- [ ] Swagger 於 `/api/docs` 可看到四個新端點與既有 member 端點
- [ ] 所有更新端點 flush 後 refresh，無 `MissingGreenlet` 例外
