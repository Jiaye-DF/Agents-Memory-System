# v1.1.4 任務規格：游離 Session 與 ChatGPT 風格雙區導航

## 版本目標

放寬 v1.1.1 的「Session 必須隸屬 Project」限制，讓對話改成 ChatGPT 風格：側欄上方為「最近對話」（游離 session，不屬於任何 project）、下方為「Projects」區塊（每個 project 內有自己的 sessions）。使用者可以直接開新對話，也可以在 project 內開對話，並能把既有 session 移入 / 移出 project。

### 範圍內

- `chat_session.chat_project_uid` 由 NOT NULL 改為 nullable
- 對話 CRUD API 容許建立「不帶 project_uid」的游離 session
- 新增 `POST /api/v1/chat/sessions/{uid}/move`：變更 session 所屬 project（含 null = 移出）
- 列表 API 拆分：
  - `GET /api/v1/chat/sessions?orphan=true`：只回游離 sessions
  - `GET /api/v1/chat/projects/{uid}/sessions`：project 內 sessions（既有）
- 前端側欄分兩區：「最近對話」+「Projects」
- 前端路由：`/sessions/new` 直開新對話（游離）；`/projects/{uid}/sessions/new` 在 project 內開
- Project session 上限（`chat.max_sessions_per_project`）只計 project 內；游離 session 另設 `chat.max_orphan_sessions_per_user` 上限

### 範圍外

- Project 層記憶 / 跨層 RAG 檢索（v1.2+，本版游離 session 僅檢索自己的 memory）
- 「把 project 內 session 批次移出」的批次 UI（僅提供單筆 move）
- Session 排序自訂 / 置頂
- Project 共用 system prompt 覆寫（ChatGPT Project 有的「project instructions」，留 v1.2）

---

## 前置現況

- v1.1.1 尚未實作（tasks-v1.1.1.md 仍為 TODO），可直接修改 migration V19 與相關 schema，不需要新增 alter migration
- 若 v1.1.1 已 release，本版需改以 `ALTER TABLE chat_session ALTER COLUMN chat_project_uid DROP NOT NULL;` 追加處理（見 §Phase 0）
- propose-v1.1.0.md §3-1 需同步更新描述

---

## 已確認決策

| #   | 決策                            | 結論 |
| --- | ------------------------------- | ---- |
| 1   | Session ↔ Project 關係          | 0..1：session 可不屬於任何 project |
| 2   | Session 一旦建立能否改 Project   | 可。透過 `POST /chat/sessions/{uid}/move` 變更或設為 null |
| 3   | 游離 session 的容量上限          | 新設 `chat.max_orphan_sessions_per_user`，預設 `10`、最大 `30`；與 project session 分開計算 |
| 4   | 游離 session 的 RAG scope        | 僅該 session 自己的 `chat_memory`（與 project session 的 session scope 相同） |
| 5   | Session 歸屬權限                 | 只有擁有者可以 move（admin 也不行，隱私一致） |
| 6   | 刪除 project 時其下 sessions    | 連同 sessions 一併軟刪（既有決策保留）；**游離 sessions 不受影響** |
| 7   | URL 結構                        | `/sessions/{uid}` 對所有 session 都適用，不因是否屬於 project 而改變；project 只決定側欄分類與容量計算 |

---

## Phase 0：schema 調整

### 0-1 若 v1.1.1 尚未 release（預期情境）

直接改 `tasks-v1.1.1.md` 的 V19：

- [ ] **V19**：`create_chat_session_table.sql` 將 `chat_project_uid` 欄位改為 `UUID NULL REFERENCES chat_project(chat_project_uid)`
- [ ] 對應 `ChatSession` model 欄位：`chat_project_uid: Mapped[uuid.UUID | None]`
- [ ] Seed / 測試資料同步

### 0-2 若 v1.1.1 已 release（fallback）

- [ ] 新增 **V22**：`alter_chat_session_project_uid_nullable.sql`
  - `ALTER TABLE chat_session ALTER COLUMN chat_project_uid DROP NOT NULL;`
  - `COMMENT ON COLUMN chat_session.chat_project_uid IS '所屬 Project uid（NULL 代表游離對話）';`

---

## Phase 1：後端

### 1-1 Schema / Model

- [ ] `app/models/chat_session.py`：`chat_project_uid` type 改為 `Mapped[uuid.UUID | None]`
- [ ] `app/schemas/chat/session_schemas.py`
  - `ChatSessionCreateRequest.chat_project_uid: str | None = None`
  - `ChatSessionResponse.chat_project_uid: str | None`
  - 新增 `ChatSessionMoveRequest { chat_project_uid: str | None }`

### 1-2 Repository

- [ ] `chat_session_repository.stmt_orphan_by_owner(user_uid)`：`WHERE chat_project_uid IS NULL AND owner_user_uid = ... AND is_deleted = FALSE`
- [ ] `chat_session_repository.count_orphan_by_owner(user_uid)`：計算使用者的游離 session 數，用於容量檢查
- [ ] `chat_session_repository.update_project(chat_session_uid, new_project_uid_or_none, db)`

### 1-3 Service

- [ ] `chat_service.create_session`：
  - `chat_project_uid` 為 None → 檢查 `chat.max_orphan_sessions_per_user`
  - 有 `chat_project_uid` → 既有邏輯（檢查 project 擁有者、檢查 `chat.max_sessions_per_project`）
- [ ] `chat_service.move_session(user_uid, chat_session_uid, new_project_uid_or_none)`：
  - 僅擁有者可呼叫
  - 移入 project：驗證 target project 擁有者一致 + 未超上限
  - 移出 project（設 None）：檢查游離 session 上限
- [ ] `chat_service.list_orphan_sessions(user_uid, cursor, limit, db)`

### 1-4 API Router

- [ ] `GET /api/v1/chat/sessions?orphan=true`
  - 擁有者讀自己的游離 sessions（cursor 分頁）
  - 不帶 `orphan` 時維持既有行為（列全部自己的 sessions，含 project 內 + 游離）
- [ ] `POST /api/v1/chat/sessions`
  - body 可不帶 `chat_project_uid`
- [ ] `POST /api/v1/chat/sessions/{uid}/move`
  - body: `{ "chat_project_uid": string | null }`
  - 回 200 + 更新後的 `ChatSessionResponse`

### 1-5 System Setting

- [ ] seed 新增 `chat.max_orphan_sessions_per_user = 10`（max 30，admin 可調）
- [ ] 在 `/admin/settings` 編輯器顯示與其他 `chat.*` 一起

### 1-6 Delete Project 行為確認

- [ ] 刪除 project 時僅 cascade 屬於該 project 的 sessions；游離 sessions 不受影響（既有 `chat_project_uid IS NULL` filter 天然排除）

---

## Phase 2：前端

### 2-1 型別

- [ ] `types/chat.ts`：
  - `ChatSession.chat_project_uid: string | null`
  - 新增 `ChatSessionMoveRequest`

### 2-2 RTK Query

- [ ] `chatApi.ts` 新增：
  - `useListOrphanChatSessionsQuery`（cursor 分頁）
  - `useMoveChatSessionMutation`
- [ ] 調整 `useCreateChatSessionMutation` 型別：`chat_project_uid?: string | null`
- [ ] tag：`ChatSessions` 保留，新增 tag `OrphanChatSessions` 以便只對列表精準 invalidate

### 2-3 側欄導航（`components/layout/ChatSidebar.tsx` 新檔或拆分既有）

- [ ] 上方區塊「最近對話」：列 `useListOrphanChatSessionsQuery` 結果（限最近 N 筆，點擊 see all 進 `/sessions`）
- [ ] 下方區塊「Projects」：列 `useListChatProjectsQuery` 結果
- [ ] 每個 project 可展開顯示其 sessions（既有）
- [ ] 頂部「新對話」按鈕 → 導向 `/sessions/new`

### 2-4 路由

- [ ] `app/(main)/sessions/new/page.tsx`：選 Agent → 建立游離 session → 導向 `/sessions/{uid}`
- [ ] `app/(main)/sessions/page.tsx`：列出所有游離 sessions（cursor 分頁，搜尋 / 排序沿用共用 hook）
- [ ] `app/(main)/projects/{uid}/sessions/new/page.tsx`：在 project 內開 session（保留既有流程）
- [ ] `/sessions/{uid}` 對話頁面顯示所屬 project badge（有的話可點進 project）

### 2-5 Session 詳情

- [ ] 加入「移至 project」操作（dropdown 或按鈕）：
  - 空選項「（無，設為游離）」
  - 列出使用者自己的 projects
  - 呼叫 `useMoveChatSessionMutation`

---

## Phase 3：文件 / propose 同步

- [ ] `propose-v1.1.0.md` §3-1 改寫為「Session 可選擇屬於 Project 或游離」，並補上雙區導航描述
- [ ] `propose-v1.1.0.md` §3-2 容量上限表新增 `chat.max_orphan_sessions_per_user`
- [ ] `tasks-v1.1.1.md` 已確認決策 #2「Session 必須隸屬 Project」標為 superseded，指向本檔
- [ ] `tasks-v1.1.2.md` RAG 段落補註：游離 session 僅檢索自己的 session memory（與 project session 的 session scope 一致，v1.1 層不擴展）

---

## 驗收

- [ ] 建立游離 session 不帶 `chat_project_uid`，成功並出現在側欄「最近對話」
- [ ] 在 project 內建的 session 出現在 project 展開列表，不出現在「最近對話」
- [ ] `move` 端點：游離 → project、project → 游離、project A → project B 全部可行
- [ ] 超過 `chat.max_orphan_sessions_per_user` 時建立 / move-to-null 會被拒（400 + 明確訊息）
- [ ] 刪除 project 不影響游離 sessions
- [ ] admin 不能 move 他人 session（403）
- [ ] 游離 session 對話流程（送訊息、streaming、memory worker 寫入、RAG 檢索）完整可用
