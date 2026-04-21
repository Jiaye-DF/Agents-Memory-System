# v1.1.1 任務規格：對話 + Session / Project 基礎

> **狀態：已完成（commit 37aa3ba, 2026-04-21）**

## 版本目標

建立對話功能的資料基底與最小可用流程：`chat_project` 容器、`chat_session` 對話區、`chat_message` 訊息表；支援單一 Session 與單一 Agent 的 SSE streaming 對話，對話歷史持久化至 PG。

### 範圍內

- 新增 `chat_project` / `chat_session` / `chat_message` 三張表（遵循 `chat_` 前綴命名規則）
- Project / Session CRUD API + 前端頁面
- Session 對話端點：送訊息 → 組 prompt → OpenRouter SSE streaming → 寫 assistant message
- Skills 內容以純 prompt 文本注入 system prompt（不做 tool call）
- 對話上下文管理（最近 N 則 + context window 截斷，尚未接記憶 / RAG）
- 容量上限設定 `chat.max_sessions_per_project` / `chat.max_projects_per_user`
- 前端：`/projects` 列表、`/projects/{uid}` 詳情（含 session 列表）、`/sessions/{uid}` 對話畫面

### 範圍外

- 記憶系統 / RAG 檢索 → `tasks-v1.1.2.md`
- Skills 編輯（重上傳 / 線上編輯）→ `tasks-v1.1.3.md`
- 訊息編輯 / 重送 / 分支
- 附件 / 多模態（v1.1 僅純文字）
- Tool call 機制（Skills 執行引擎）
- BYOK（使用者自備金鑰），v1.1 共用 admin 於 `.env` 設定的 `OPENROUTER_API_KEY`

---

## 前置現況

- v1.0 / v1.0.* 已完成：Agents / Skills / LLM 模型管理、`system_setting` 表、RBAC、cursor 分頁
- `app/clients/openrouter.py` 已有 `fetch_model_ids`（只用於驗證），本版需擴充為可呼叫 Chat Completions + SSE
- `app/services/openrouter_service.py` 負責 verify_model_id（保留）

---

## 已確認決策

| #   | 決策                         | 結論                                                                         |
| --- | ---------------------------- | ---------------------------------------------------------------------------- |
| 1   | Session : Agent 關係          | 1:1。`chat_session.agent_uid` 建立後不可變更                                 |
| 2   | Session 必須隸屬 Project      | ~~不支援游離 Session，`chat_project_uid` NOT NULL~~ — **superseded by v1.1.4**，現為 nullable，游離 session 規格見 [tasks-v1.1.4.md](tasks-v1.1.4.md) |
| 3   | Skills 在對話中的角色         | **純 prompt 文本注入**；tool call 留 v1.2+                                    |
| 4   | 成本模型                     | 全系統共用 admin 的 `OPENROUTER_API_KEY`；Token / cost 仍記錄於 `chat_message` |
| 5   | 訊息永久保存                 | `chat_message` **不軟刪除**（審計用）；Session 軟刪時 message 保留不動       |
| 6   | Session 標題生成             | 首則 user 訊息截斷前 30 字作為初值；允許使用者手動改名                        |
| 7   | 多模態                       | v1.1 僅純文字 `text`                                                          |
| 8   | Streaming 協議               | SSE（Server-Sent Events），FastAPI `StreamingResponse`                        |

---

## Phase 1：後端

### 1-1 Migration

- [x] **V18**：`create_chat_project_table.sql`
  - `pid bigserial PK`、`chat_project_uid uuid default gen_random_uuid() UNIQUE`
  - `owner_user_uid uuid NOT NULL REFERENCES user(user_uid)`
  - `name varchar(100) NOT NULL`、`description text NULL`
  - `is_active bool default true`、`is_deleted bool default false`
  - `created_at timestamptz default now()`、`updated_at timestamptz default now()`
  - Trigger：`trg_chat_project_set_updated_at`
  - Index：`idx_chat_project_owner_user_uid`、`uq_chat_project_uid`
  - `COMMENT ON COLUMN` 全部欄位

- [x] **V19**：`create_chat_session_table.sql`
  - `pid`、`chat_session_uid`、`chat_project_uid FK`、`agent_uid FK`
  - `title varchar(200)`、`is_active`、`is_deleted`、`created_at` / `updated_at` + Trigger
  - Index：`idx_chat_session_project_uid`、`idx_chat_session_agent_uid`、`uq_chat_session_uid`

- [x] **V20**：`create_chat_message_table.sql`
  - `pid`、`chat_message_uid`、`chat_session_uid FK`
  - `role varchar(20) NOT NULL CHECK (role IN ('user','assistant','system','tool'))`
  - `content text NOT NULL`
  - `token_in int NULL`、`token_out int NULL`、`cost_usd numeric(10,6) NULL`
  - `model varchar(100) NULL`（記當次實際呼叫 model，user / system 訊息為 NULL）
  - `created_at timestamptz default now()`
  - **不加 `is_deleted` / `updated_at`**（訊息不可編輯、不軟刪除）
  - Index：`idx_chat_message_session_uid_created_at`（session 內時序查詢）、`uq_chat_message_uid`

- [x] **V21**：`seed_chat_system_settings.sql`
  - `chat.max_sessions_per_project` = `3`
  - `chat.max_projects_per_user` = `5`

### 1-2 Model

- [x] `app/models/chat_project.py`：`ChatProject`（繼承 `Base`，`chat_project_uid` / `owner_uid` / `name` / `description`；`relationship("User")` 可選）
- [x] `app/models/chat_session.py`：`ChatSession`（`chat_session_uid` / `chat_project_uid` / `agent_uid` / `title`）
- [x] `app/models/chat_message.py`：`ChatMessage`（自訂 base，**不繼承** `app/models/base.py`，因為沒有 `updated_at` / `is_deleted`）

### 1-3 Schema（`app/schemas/chat/schemas.py`）

- [x] `ChatProjectCreateRequest`：`name`（必填 1-100）、`description`（可選）
- [x] `ChatProjectUpdateRequest`：`name` / `description` 皆可選
- [x] `ChatProjectResponse`：完整欄位 + `session_count`（聚合）
- [x] `ChatSessionCreateRequest`：`chat_project_uid`、`agent_uid`、`title`（可選，空則用首則訊息填）
- [x] `ChatSessionUpdateRequest`：`title` 可選（允許改名）
- [x] `ChatSessionResponse`：完整欄位 + `agent_name`、`last_message_at`、`message_count`
- [x] `ChatMessageCreateRequest`：`content`（必填，1-10000 字）、`role` 固定 `user`（後端強制）
- [x] `ChatMessageResponse`：完整欄位

### 1-4 Repository

- [x] `chat_project_repository.py`：`list_by_owner`、`get_by_uid`、`create`、`update`、`soft_delete`、`count_by_owner`
- [x] `chat_session_repository.py`：`list_by_project`、`get_by_uid`、`create`、`update`、`soft_delete`、`count_by_project`
- [x] `chat_message_repository.py`：`list_by_session(cursor, limit)`（cursor-based，按 `pid ASC`）、`get_by_uid`、`create`、`get_last_n(session_uid, n)`（組 prompt 用）、`sum_tokens_cost(session_uid)`（聚合）

所有 `create` / `update` flush 後 `await db.refresh(obj)`（沿用 v1.0 慣例）。

### 1-5 OpenRouter Chat Client

於 `app/clients/openrouter.py` 新增：

- [x] `async def stream_chat_completion(messages: list[dict], model: str, temperature: float | None, max_tokens: int | None) -> AsyncIterator[dict]`
  - 呼叫 `POST https://openrouter.ai/api/v1/chat/completions`，`stream=true`
  - Header：`Authorization: Bearer {OPENROUTER_API_KEY}`、`HTTP-Referer` / `X-Title`（可選）
  - yield 每個 SSE event 的 delta chunk（`{role?, content?}` + 結尾 `usage` 區塊）
  - 錯誤處理：httpx timeout 60s，失敗拋 `AppError(500)`

### 1-6 Service：`chat_service.py`

- [x] `list_projects(user_uid, cursor, limit, db)` / `get_project(...)` / `create_project(...)` / `update_project(...)` / `delete_project(...)`
  - `create_project` 前檢查 `chat.max_projects_per_user` 上限（透過 `system_setting_service`）

- [x] `list_sessions(project_uid, user_uid, cursor, limit, db)` / `get_session(...)` / `create_session(...)` / `update_session(...)` / `delete_session(...)`
  - `create_session` 前檢查 `chat.max_sessions_per_project` 上限
  - 驗證 `agent_uid` 存在且使用者可見（owner or public）

- [x] `list_messages(session_uid, user_uid, cursor, limit, db)`
  - 存取權限：僅 session 擁有者可讀（admin **不能**讀，對應 propose §3-5）

- [x] `async def send_message(session_uid, user_uid, content, db) -> AsyncIterator[dict]`
  - 流程：
    1. 驗證 session 擁有權
    2. 寫 user message（同步）
    3. 取 agent 設定 + skills 文本 → 組 system prompt
    4. `get_last_n(session_uid, 20)` 取對話歷史
    5. 估算 token，超過 model 上限 70% 則裁切最舊（v1.1 簡化：固定取最後 20 則，不做智能截斷；智能截斷 v1.1.2 配合記憶做）
    6. 呼叫 `stream_chat_completion`
    7. 累積 delta，全程 yield 給前端
    8. 完成後寫 assistant message（含 `token_in` / `token_out` / `cost_usd` / `model`）
    9. （記憶 worker enqueue 留 v1.1.2）
  - 錯誤：呼叫失敗重試 2 次（指數 backoff），仍失敗則 **不寫 assistant message**，yield 錯誤 event 後關閉

- [x] `_build_system_prompt(agent, skills) -> str`：
  ```
  [Agent: {name}]
  {agent.role_prompt or identity}

  Language: {agent.language}
  Style: {agent.style}

  ## Skills
  {for each skill: 取 skill 的 zip 內 README.md / skill.md，若無則僅列名稱與描述}
  ```

- [x] `_auto_title_from_first_message(content) -> str`：截斷前 30 字，去除換行，作為 session 初始 title

### 1-7 Router：`app/api/v1/chat/router.py`

| 方法   | 端點                                                              | 說明                                 |
| ------ | ----------------------------------------------------------------- | ------------------------------------ |
| GET    | `/api/v1/chat/projects`                                           | 列表（cursor 分頁，只回使用者自己）  |
| POST   | `/api/v1/chat/projects`                                           | 建立                                 |
| GET    | `/api/v1/chat/projects/{uid}`                                     | 詳情                                 |
| PUT    | `/api/v1/chat/projects/{uid}`                                     | 更新 name / description              |
| DELETE | `/api/v1/chat/projects/{uid}`                                     | 軟刪除                               |
| GET    | `/api/v1/chat/projects/{uid}/sessions`                            | 列表該 project 下的 sessions          |
| POST   | `/api/v1/chat/sessions`                                           | 建立 session                          |
| GET    | `/api/v1/chat/sessions/{uid}`                                     | 詳情                                 |
| PUT    | `/api/v1/chat/sessions/{uid}`                                     | 更新 title                           |
| DELETE | `/api/v1/chat/sessions/{uid}`                                     | 軟刪除                               |
| GET    | `/api/v1/chat/sessions/{uid}/messages`                            | 訊息歷史（cursor 分頁）              |
| POST   | `/api/v1/chat/sessions/{uid}/messages`                            | **SSE streaming** 回應；body 傳 `content` |

- [x] 全部端點掛 `get_current_user`
- [x] 存取權限：僅 owner 可操作；admin **不可**讀訊息內容（對應 propose §3-5）
- [x] `POST sessions/{uid}/messages` 回傳 `StreamingResponse(media_type="text/event-stream")`
- [x] 註冊 `chat_router` 於 `api/v1/router.py`

### 1-8 錯誤格式

- SSE 中途錯誤 → 發送 `event: error\ndata: {"detail": "..."}\n\n` 後關閉
- 超過 session 上限 → 400「已達上限，admin 設定 3/project」

---

## Phase 2：前端

### 2-1 型別（`types/chat.ts` + `types/index.ts` re-export）

- [x] `ChatProject` / `ChatProjectCreateRequest` / `ChatProjectUpdateRequest`
- [x] `ChatSession` / `ChatSessionCreateRequest` / `ChatSessionUpdateRequest`
- [x] `ChatMessage`（含 `token_in/out`、`cost_usd`、`model`）

### 2-2 RTK Query（`store/chatApi.ts`）

- [x] `useListProjectsQuery({ cursor, limit })`
- [x] `useGetProjectQuery(uid)`
- [x] `useCreateProjectMutation` / `useUpdateProjectMutation` / `useDeleteProjectMutation`
- [x] `useListSessionsQuery({ projectUid, cursor, limit })`
- [x] `useGetSessionQuery(uid)`
- [x] `useCreateSessionMutation` / `useUpdateSessionMutation` / `useDeleteSessionMutation`
- [x] `useListMessagesQuery({ sessionUid, cursor, limit })`
- [x] Streaming 送訊息**不走 RTK Query**，自建 `fetch` + `ReadableStream` 解析 SSE（見 2-4）
- [x] `tagTypes` 加入 `ChatProjects` / `ChatSessions` / `ChatMessages`

### 2-3 頁面

- [x] `/projects/page.tsx`：Project 卡片列表 + 「新增 Project」
- [x] `/projects/[uid]/page.tsx`：Project 詳情 + Session 列表 + 「新增 Session」（開 modal，選 Agent）
- [x] `/sessions/[uid]/page.tsx`：對話畫面
  - 左側（可收合）：session 列表或 Project 導航
  - 主區：訊息氣泡（user / assistant 區分）+ 輸入框
  - 訊息用 `react-markdown` 渲染（沿用 v1.0.2 Agent 系統提示預覽套件）
  - Token / cost 小字顯示於 assistant 訊息底部

### 2-4 SSE 消費 hook（`hooks/useChatStream.ts`）

- [x] `sendMessage(sessionUid, content, onDelta, onDone, onError)`
  - `fetch('/api/v1/chat/sessions/{uid}/messages', { method: 'POST', body: JSON.stringify({ content }), headers: { Authorization, Content-Type }})`
  - 讀 `response.body.getReader()`，解析 SSE 區塊 (`data: ...\n\n`)
  - 累積 assistant 內容，呼叫 `onDelta(partial)`
  - 結束時 `onDone(finalMessage)`，失敗時 `onError(detail)`
  - 同時維護「正在發送」loading 旗標

### 2-5 Sidebar 入口

- [x] `components/layout/Sidebar.tsx` 追加：
  - `{ label: "對話", href: "/projects", icon: <svg ... /> }`（放 Dashboard 下方、Agent 上方）

### 2-6 路由守衛

- [x] 全部 `/projects` / `/sessions` 頁面：登入即可，無需 admin

---

## Phase 3：驗收

- [x] 新 migration 套用後，三張表均存在且 COMMENT 齊全
- [x] member 可建立 project → session → 開啟對話，assistant 回應以 streaming 逐字顯示
- [x] 訊息歷史正確持久化（F5 重整後可載回）
- [x] 容量上限生效：超過 `chat.max_sessions_per_project` 或 `chat.max_projects_per_user` 時回 400
- [x] admin 呼叫 `GET /api/v1/chat/sessions/{uid}/messages` 會被擋（權限 403）
- [x] `chat_message.token_in/out/cost_usd/model` 有值
- [x] session title 在首則訊息送出後自動帶入截斷前 30 字
- [x] 對話首字延遲 P95 < 2s（本機測量）
- [x] Swagger `/api/docs` 顯示所有 `/api/v1/chat/*` 端點
- [x] Sidebar「對話」入口可見且導向 `/projects`
