# v1.0 任務規格

## 版本目標

建立系統基礎架構，完成**登入/權限系統**與 **Agents / Skills 管理**功能。

### 範圍內

- 專案基礎建設（Docker、後端/前端骨架、DB Migration）
- 登入系統（註冊、登入、登出、Token 刷新、重設密碼）
- 角色權限管理（admin / member RBAC）
- Agents 基本設定（CRUD、公開/私人/刪除、下載 AGENTS.md）
- Skills 管理（CRUD、上傳/下載、公開/私人/刪除）

### 範圍外（後續版本）

- 記憶管理（Memory CRUD、向量化、語意搜尋）
- Agentic RAG Pipeline
- Agent Engine（排程、Skill 載入器）
- 多平台整合（LINE、Telegram）
- 對話管理

---

## 已確認決策

| #   | 決策                | 結論                                                                        |
| --- | ------------------- | --------------------------------------------------------------------------- |
| 1   | Skills 檔案儲存     | 專案內 `data/skills/`，已加入 `.gitignore`                                  |
| 2   | 重設密碼機制        | 使用者輸入帳號＋使用者名稱驗證身分，通過後直接設定新密碼（雙重確認）        |
| 3   | Skills 檔案大小上限 | 50MB                                                                        |
| 4   | 初始 admin 帳號     | 不做 Seed，手動註冊後由 DB 修改角色                                         |
| 5   | 分頁規格            | Cursor-based（keyset），以 `pid` 排序；前端提供 select/options 選擇每頁筆數 |

---

## 共用規格：Cursor-based 分頁

所有列表 API 採用 **Cursor-based（keyset）分頁**，避免 OFFSET 全表掃描：

### API 參數

| 參數     | 型別          | 說明                                                        |
| -------- | ------------- | ----------------------------------------------------------- |
| `limit`  | `int`         | 每頁筆數，前端 select/options 可選（10 / 20 / 50），預設 20 |
| `cursor` | `str \| null` | 上一頁回傳的 opaque token，首頁不傳                         |

### 回應格式（包裝於 `data` 內）

```json
{
  "items": [...],
  "next_cursor": "eyJwaWQiOjQyfQ==",
  "has_next": true
}
```

### 實作要點

- 後端以 `pid` 排序，cursor 為 opaque token（Base64 編碼 pid），前端不需理解其內容
- 查詢邏輯：`WHERE pid > :decoded_cursor ORDER BY pid ASC LIMIT :limit + 1`（多取一筆判斷 `has_next`）
- 前端分頁元件提供 select/options 讓使用者選擇每頁筆數

---

## Multi-Agent 拆分

依模組依賴關係分三波執行，每波內的 Agent 可並行：

```text
Wave 1（基礎建設，無依賴）
├── Agent A：後端基礎    → Phase 0-1, 0-2, 0-5
└── Agent B：前端基礎    → Phase 0-3, 0-4

Wave 2（認證與權限，依賴 Wave 1）
├── Agent C：認證/權限 後端 → Phase 1-1, 1-2, 2-1, 2-2
└── Agent D：認證/權限 前端 → Phase 1-3, 2-3

Wave 3（功能模組，依賴 Wave 2，彼此獨立）
├── Agent E：Agents 功能  → Phase 3-1, 3-2, 3-3
└── Agent F：Skills 功能  → Phase 4-1, 4-2, 4-3
```

### Agent 間介面約定

| 依賴關係        | 說明                                                                                                                 |
| --------------- | -------------------------------------------------------------------------------------------------------------------- |
| Wave 1 → Wave 2 | Agent C/D 依賴 Agent A 的核心模組（`core/`、Base model、`deps.py`）與 Agent B 的 UI 元件（Dialog、Layout、分頁元件） |
| Wave 2 → Wave 3 | Agent E/F 依賴 Agent C 的認證依賴（`get_current_user`、`require_role`）與 Agent D 的共用頁面模式                     |
| Agent E ↔ F     | `agent_skill` 多對多表由 Agent E 建立；Agent F 完成後再整合 Skills 關聯與 AGENTS.md 下載功能                         |

---

## Phase 0：專案基礎建設

> 所有後續功能的前置條件，必須先完成。

### 0-1 Docker 開發環境

- [ ] 建立 `docker-compose.dev.yml`，包含：
  - PostgreSQL 17（含 pgvector 擴充）
  - Redis
  - Flyway（Migration runner）
  - FastAPI 後端（hot reload）
  - Next.js 前端（hot reload）
- [ ] 確認 `.env.example` 所有變數可正確注入各容器
- [ ] `.gitignore` 加入 `data/` 目錄（Skills 檔案儲存用）

### 0-2 後端骨架

- [ ] 初始化 FastAPI 專案（`backend/app/main.py`）
  - Lifespan 管理（`@asynccontextmanager`，非 deprecated `@on_event`）
  - Swagger 文件路徑設定為 `/api/docs`
  - CORS 設定（讀取 `CORS_ORIGINS` 環境變數）
- [ ] 建立核心模組（`backend/app/core/`）
  - `config.py`：Pydantic Settings 讀取環境變數
  - `database.py`：SQLAlchemy 2 async engine + session factory
  - `redis.py`：Redis 連線管理
  - `response.py`：統一回應格式 `ApiResponse`（success / data / detail / response_code）
  - `exceptions.py`：自訂例外 `AppError` + 全域 handler
  - `pagination.py`：Cursor-based 分頁工具（cursor 編解碼、通用查詢 helper）
- [ ] 建立 v1 路由入口（`backend/app/api/v1/router.py`，前綴 `/api/v1`）
- [ ] 建立健康檢查端點 `GET /api/v1/health`（回傳 DB / Redis 連線狀態）
- [ ] `backend/app/api/deps.py`：DB session 依賴注入

### 0-3 前端骨架

- [ ] 初始化 Next.js 15 專案（App Router, TypeScript 5, TailwindCSS 4）
- [ ] Route Group 結構：`(auth)` 登入相關、`(main)` 認證後頁面
- [ ] 建立 Redux Store + RTK Query 骨架（`frontend/src/store/`）
- [ ] 建立 API Client 層（`frontend/src/lib/api/`）
  - 基礎 fetch 封裝（禁止使用 axios），baseURL 讀取 `NEXT_PUBLIC_API_URL`
  - Request wrapper：自動附加 `Authorization: Bearer <token>`
  - Response wrapper：401 時自動呼叫 refresh → 重試原請求
- [ ] 建立 Error Boundary（`error.tsx` / `global-error.tsx`）

### 0-4 UI / UX 基礎建設

> 參照設計文件 `11-ui-ux.md`，建立全站共用的視覺與互動基礎。

#### 整體風格

- [ ] 全站圓角設計：所有卡片、按鈕、輸入框、Dialog 統一 `rounded-xl`
- [ ] 所有可點選元素加上 `hover:cursor-pointer`（按鈕、連結、卡片、圖示按鈕）
- [ ] 間距系統使用 Tailwind spacing scale（`p-4`、`gap-6` 等），禁止任意數值

#### 佈景主題

- [ ] `globals.css` 定義 CSS Variables 色彩系統
  - 預設：Light / Dark 兩組
  - 自訂：冷色系（cool）/ 暖色系（warm）/ 粉紫色（purple）
- [ ] `data-theme` 屬性切換機制，使用者偏好存入 `localStorage`，重新載入自動套用
- [ ] 禁止元件內寫死 hex 色碼，一律引用 CSS Variable

#### Layout 系統

- [ ] Header 元件（固定頂部，高度固定，背景色跟隨主題）
  - 左側：Sidebar 切換按鈕（☰）+ SVG 圖示 + 「Agents-Platform」文字，點擊回主頁
  - 右側：`{Username}` + 登出按鈕
  - 響應式：`sm` 以下隱藏「Agents-Platform」文字，僅保留 SVG 圖示
- [ ] Sidebar 元件（三態循環：完整展開 → 收合僅圖示 → 完全隱藏 → 循環）
  - `md` 以下預設隱藏，點擊以 overlay 方式展開，可關閉
- [ ] 統一頁面版型（`(main)/layout.tsx` 控制）
  - 每頁包含 Page Title 區塊 + Main Content 圓角卡片容器（`rounded-xl` + 背景色 + 陰影）
  - 各頁面禁止自行定義外層佈局，僅填充 Main Content 內部

#### 共用元件

- [ ] Dialog 元件（禁用 browser `alert()` / `confirm()` / `prompt()`）
  - 三種類型：Info（藍色，確認）、Warning（黃色，取消/確認）、Error（紅色，確認）
  - 提供 `useDialog` Hook 或全域 store，任何元件可程式觸發
- [ ] Loading 元件
  - 頁面級：全頁 Skeleton 或 Spinner
  - 元件級：局部 Skeleton，避免整頁閃爍
  - 按鈕級：操作中顯示 Spinner 並禁用，防止重複觸發
- [ ] 表單驗證回饋元件
  - 欄位錯誤即時顯示於欄位下方，紅色文字
  - 伺服器錯誤透過 Dialog（Error 類型）呈現
  - 送出按鈕請求期間顯示 loading 並禁用
- [ ] 分頁元件（共用，供列表頁使用）
  - 支援 cursor-based 分頁（上一頁 / 下一頁）
  - 每頁筆數 select/options（10 / 20 / 50）
- [ ] 表格元件（小螢幕支援水平捲動或改為卡片式呈現）

#### 響應式設計（RWD）

- [ ] Mobile First 為基礎，依序向上擴展
  - 預設（< 640px）：單欄、Sidebar 隱藏為漢堡選單
  - `sm`（≥ 640px）：單欄、間距微調
  - `md`（≥ 768px）：Sidebar 展開、雙欄佈局
  - `lg`（≥ 1024px）：Main Content 加寬
  - `xl`（≥ 1280px）：最大內容寬度，置中顯示
- [ ] 所有互動元素觸控區域至少 44x44px（無障礙標準）

### 0-5 資料庫初始化

- [ ] Flyway 初始 Migration：啟用 pgvector 擴充（`CREATE EXTENSION IF NOT EXISTS vector`）
- [ ] 建立 `updated_at` 自動更新的 Trigger function（共用）
- [ ] SQLAlchemy Base model（含必備欄位：pid, uid, is_active, is_deleted, created_at, updated_at）

---

## Phase 1：登入系統

> 參照設計文件 `30-login.md`。

### 1-1 資料庫

- [ ] Migration：建立 `user_role` 表
  - `pid`, `user_role_uid`, `name`, `description`, `is_active`, `is_deleted`, `created_at`, `updated_at`
- [ ] Migration：建立 `user` 表
  - `pid`, `user_uid`, `username`, `account`, `hashed_password`, `role_uid`（FK → user_role）
  - `is_active`, `is_deleted`, `created_at`, `updated_at`
  - `login_fail_count`, `locked_until`（登入鎖定機制）
- [ ] Seed data：初始角色 `admin`、`member`
- [ ] SQLAlchemy Model：`UserRole`, `User`

### 1-2 後端 API

| 端點                               | 說明                                                              |
| ---------------------------------- | ----------------------------------------------------------------- |
| `POST /api/v1/auth/register`       | 使用者註冊（預設角色 member）                                     |
| `POST /api/v1/auth/login`          | 登入，回傳 Access Token（body）+ Refresh Token（HttpOnly Cookie） |
| `POST /api/v1/auth/logout`         | 登出，清除 Cookie + Redis 黑名單                                  |
| `POST /api/v1/auth/refresh`        | 刷新 Access Token                                                 |
| `POST /api/v1/auth/reset-password` | 驗證帳號＋使用者名稱後重設密碼                                    |

- [ ] 分層實作：`api/v1/auth/` → `services/auth_service.py` → `repositories/user_repository.py`
- [ ] Pydantic Schemas：RegisterRequest, LoginRequest, TokenResponse, ResetPasswordRequest（account + username + new_password + confirm_password）
- [ ] JWT 工具模組（Access Token 15 分鐘、Refresh Token 7 天）
- [ ] 密碼 bcrypt 加密（禁止明文儲存或記錄 log）
- [ ] 登入失敗鎖定：5 次（鎖 15 分鐘）→ 10 次（鎖 1 小時）→ 15 次以上（永久鎖定，需 admin 解鎖）
- [ ] 錯誤訊息不區分「帳號不存在」與「密碼錯誤」（防帳號列舉）
- [ ] Redis：Refresh Token 黑名單
- [ ] `api/deps.py`：`get_current_user()` 依賴（從 Bearer Token 解析 user_uid + role）

### 1-3 前端頁面

- [ ] 登入頁（`/`，掛載於 `(auth)/page.tsx`）
  - 帳號 + 密碼表單，置中卡片佈局（`rounded-xl`）
  - 欄位驗證錯誤 inline 紅色文字顯示
  - 登入按鈕送出時顯示 loading 並禁用
  - 伺服器錯誤透過 Dialog（Error）呈現
- [ ] 註冊頁（`/register`）
  - 使用者名稱 + 帳號 + 密碼 + 確認密碼
  - 前端即時驗證：帳號 ≥8 字元（含字母+數字）、密碼 ≥8 字元（含大小寫+數字）
  - 密碼強度即時回饋（紅/綠色提示）
- [ ] 重設密碼頁（`/reset-password`）
  - 輸入帳號 + 使用者名稱驗證身分
  - 驗證通過後輸入新密碼 + 確認密碼（同註冊密碼規則）
- [ ] 登入後導向 `/dashboard`；未登入訪問受保護頁面導向 `/`
- [ ] 所有 auth 頁面響應式適配（Mobile First，小螢幕單欄置中）
- [ ] RTK Query：auth API endpoints

---

## Phase 2：權限管理

> 參照設計文件 `40-permission.md`。

### 2-1 後端 Middleware

- [ ] `require_role(*roles)` 依賴：驗證 Token 中 role 是否符合端點要求（403 若不符）
- [ ] 錯誤訊息不洩漏角色資訊

### 2-2 後端 API（admin 專用）

| 端點                                 | 說明                                 |
| ------------------------------------ | ------------------------------------ |
| `GET /api/v1/admin/users`            | 查詢使用者列表（cursor-based 分頁）  |
| `GET /api/v1/admin/users/{user_uid}` | 查詢單一使用者                       |
| `PUT /api/v1/admin/users/{user_uid}` | 更新使用者資訊（角色指派、解除鎖定） |
| `GET /api/v1/admin/roles`            | 查詢角色列表                         |

- [ ] 分層實作：`api/v1/admin/` → `services/` → `repositories/`
- [ ] 所有 admin 端點套用 `require_role("admin")`

### 2-3 前端頁面（admin 專用）

- [ ] 使用者管理頁（`/admin/users`）
  - 表格列表 + 搜尋欄 + 分頁元件（cursor-based，每頁筆數可選）
  - 小螢幕表格水平捲動或改為卡片式呈現
  - 可查看使用者資訊、指派角色（下拉選單）、解除登入鎖定（Warning Dialog 確認）
- [ ] 403 頁面：非 admin 角色訪問 admin 路由時顯示
- [ ] 前端路由守衛：非 admin 角色自動導向 403 頁面

---

## Phase 3：Agents 基本設定

### 3-1 資料庫

- [ ] Migration：建立 `agent` 表
  - `pid`, `agent_uid`, `owner_uid`（FK → user）, `name`, `description`
  - `language`（語言偏好）, `style`（風格）, `identity`（身分）, `role_prompt`（角色設定）
  - `visibility`（ENUM: public / private）
  - `is_active`, `is_deleted`, `created_at`, `updated_at`
- [ ] Migration：建立 `agent_skill`（多對多關聯表）
  - `agent_uid`, `skill_uid`
- [ ] SQLAlchemy Model：`Agent`, `AgentSkill`

### 3-2 後端 API

| 端點                                          | 說明                                                    |
| --------------------------------------------- | ------------------------------------------------------- |
| `GET /api/v1/agents`                          | 查詢自己的 Agent 列表 + 公開 Agent（cursor-based 分頁） |
| `POST /api/v1/agents`                         | 建立 Agent                                              |
| `GET /api/v1/agents/{agent_uid}`              | 查詢 Agent 詳情                                         |
| `PUT /api/v1/agents/{agent_uid}`              | 更新 Agent 設定                                         |
| `DELETE /api/v1/agents/{agent_uid}`           | 軟刪除 Agent                                            |
| `PATCH /api/v1/agents/{agent_uid}/visibility` | 切換公開 / 私人                                         |
| `GET /api/v1/agents/{agent_uid}/download`     | 下載 AGENTS.md + 關聯 Skills                            |

- [ ] 分層實作：`api/v1/agents/` → `services/agent_service.py` → `repositories/agent_repository.py`
- [ ] 資源存取控制：member 僅操作 `owner_uid` 為自己的 Agent；admin 可操作全部
- [ ] 即使 admin 也不可修改他人 Agent 的公開/私人/刪除狀態（僅能透過 DB）
- [ ] 下載功能：動態組合 Agent 設定 + 關聯 Skills 為 AGENTS.md 格式（無關聯 Skills 時僅匯出 Agent 設定）
      /fu

### 3-3 前端頁面

- [ ] Agent 列表頁（`/agents`）
  - 我的 Agent + 公開 Agent 分頁切換（Tab 或篩選）
  - 卡片式排列，響應式格線（mobile 單欄 → md 雙欄 → lg 三欄）
  - 每張卡片顯示名稱、描述摘要、公開/私人狀態、操作按鈕
  - 分頁元件（cursor-based，每頁筆數可選）
- [ ] Agent 建立/編輯頁（`/agents/new`, `/agents/{uid}/edit`）
  - 表單：名稱、描述、語言偏好、風格、身分、角色設定
  - Skills 選擇器（從已有 Skills 中勾選，Checkbox 或 Tag 式）
  - 欄位驗證 inline 紅色提示，送出按鈕 loading 狀態
- [ ] Agent 詳情頁（`/agents/{uid}`）：檢視設定 + 下載按鈕
- [ ] 公開/私人切換操作（列表頁中操作，即時更新狀態）
- [ ] 軟刪除操作（Warning Dialog 確認後執行）

---

## Phase 4：Skills 管理

### 4-1 資料庫

- [ ] Migration：建立 `skill` 表
  - `pid`, `skill_uid`, `owner_uid`（FK → user）, `name`, `description`
  - `file_path`（伺服器端儲存路徑）, `original_filename`, `file_size`
  - `visibility`（ENUM: public / private）
  - `is_active`, `is_deleted`, `created_at`, `updated_at`
- [ ] SQLAlchemy Model：`Skill`

### 4-2 後端 API

| 端點                                          | 說明                                                 |
| --------------------------------------------- | ---------------------------------------------------- |
| `GET /api/v1/skills`                          | 查詢自己的 Skills + 公開 Skills（cursor-based 分頁） |
| `POST /api/v1/skills`                         | 上傳 Skill（接收檔案 + metadata）                    |
| `GET /api/v1/skills/{skill_uid}`              | 查詢 Skill 詳情（含檔案目錄結構）                    |
| `PUT /api/v1/skills/{skill_uid}`              | 更新 Skill metadata                                  |
| `DELETE /api/v1/skills/{skill_uid}`           | 軟刪除 Skill                                         |
| `PATCH /api/v1/skills/{skill_uid}/visibility` | 切換公開 / 私人                                      |
| `GET /api/v1/skills/{skill_uid}/download`     | 下載 Skill .zip 檔案                                 |
| `GET /api/v1/skills/{skill_uid}/tree`         | 取得檔案目錄樹（供前端 GitHub 風格顯示）             |

- [ ] 分層實作：`api/v1/skills/` → `services/skill_service.py` → `repositories/skill_repository.py`
- [ ] 上傳處理：
  - 接收檔案後轉為 .zip 格式儲存至 `data/skills/`（此目錄已加入 `.gitignore`）
  - 支援 .md 與相關檔案上傳（必須附帶描述）
  - **拒絕 .exe 檔案**（驗證副檔名 + MIME type）
  - 檔案大小上限 50MB
- [ ] 資源存取控制：同 Agents 規則
- [ ] 即使 admin 也不可修改他人 Skill 的公開/私人/刪除狀態

### 4-3 前端頁面

- [ ] Skills 列表頁（`/skills`）
  - 我的 Skills + 公開 Skills 分頁切換
  - 卡片式排列（同 Agents 響應式格線）
  - 每張卡片顯示名稱、描述、檔案大小、公開/私人狀態
  - 分頁元件（cursor-based，每頁筆數可選）
- [ ] Skills 上傳頁（`/skills/upload`）
  - 拖曳上傳區域（`rounded-xl` 虛線框）或點擊選擇檔案
  - 填寫名稱、描述（必填，inline 驗證）
  - 上傳前檢查：禁止 .exe（前端即時提示）、顯示檔案大小、超過 50MB 提示
  - 上傳進度條 + 完成後 Info Dialog 提示
- [ ] Skills 詳情頁（`/skills/{uid}`）
  - GitHub 風格目錄階層瀏覽（樹狀展開/收合，圖示區分資料夾與檔案）
  - 下載按鈕
- [ ] 公開/私人切換、軟刪除操作（同 Agents UI 行為）
