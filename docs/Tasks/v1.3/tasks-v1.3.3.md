# v1.3.3 任務規格：多 Agent 對話

> **狀態：已完成（commit 待提交, 2026-04-25）**
>
> Phase 0 ~ 6 全部交付；Phase 7 驗收項目中 Migration / Backend 行為類需於 dev
> 環境 `docker compose up flyway` 後手動驗證；其餘代碼層改動均已完成。
>
> 規格 vs 實作差異：
>
> - LLM wrapper：本 worktree 基於 dev-v1.3 commit 1e1fcaf，當時 v1.3.0 的
>   `services/llm_metering.py` 尚未落地（v1.3.0 worktree 並行進行中），故
>   `chat_service.send_message` 暫沿用 `stream_chat_completion` 直呼；待 v1.3.0
>   merge 進來後即可改接 wrapper，多 Agent 場景所需的動態 `agent_uid` 已預留
>   為傳入 LLM 呼叫的脈絡。
> - `chat_session.agent_uid`（deprecated 欄位）在 promote / remove primary 時會
>   一併同步更新，方便讀取舊查詢路徑（V41 保留 nullable，未來再評估 drop）。
>
> 前置：[propose-v1.3.0.md §4-1](propose-v1.3.0.md)、[tasks-v1.3.0.md](tasks-v1.3.0.md)（metrics 共用）
> 後續依賴：v1.3.4（classifier 依賴 `session_agent` schema）、v1.3.6（Skill 自動推薦 UI 入口承接本版）

## 版本目標

放寬 `Session : Agent` 為 1:N，使一個 Session 可同時掛多個 Agent 協同工作：

- Schema：新增中介表 `session_agent`、`chat_session.agent_uid` 改 nullable + 標 deprecated；`chat_message` 加 `responding_agent_uid`。
- 觸發：本版**只**支援使用者 `@mention` 顯式指定 Agent；LLM 自動 routing 延後到 v1.4+。
- 順序：本版**只**支援序列（A → B）；並行（同時跑取 best）延後。
- Agent Template：新增 `general` / `long-analysis` / `summary` 三種預設 template，預填合理 `max_tokens`。
- 銜接 v1.3.6 Skill 自動推薦：本版只接「未掛載高 confidence Skill」**UI 入口** placeholder，不做推薦邏輯本身。
- API / Frontend：session detail 回 agents list、訊息卡片顯示哪個 Agent 回覆、@mention selector。

### 範圍內

- DB Migration：V39（`session_agent` 表）、V40（`chat_message.responding_agent_uid`）、V41（`chat_session.agent_uid` 改 nullable + COMMENT 補 deprecated）、V42（補 3 個 agent_template 預設值）
- Backend：`SessionAgent` model、`session_agent_repository`、`chat_session_service` / `chat_message_service` 改寫支援多 Agent、@mention 解析、序列分派。
- Backend：session detail / messages API 加上 agents list 與 `responding_agent_uid` / `responding_agent`。
- Backend：`chat_session` 新建支援 `agent_uids: list[UUID]`（保留舊 `agent_uid` 路徑相容過渡期）。
- Frontend：session 頁面顯示多 Agent badge 與切換、@mention selector、訊息卡片顯示來源 Agent。
- Frontend：Skill 自動推薦 placeholder UI（後端尚無資料時靜默不顯示）。
- Agent Template 預設值補完 + AgentForm / 模板挑選 UI 沿用既有，不做大改版。

### 範圍外

- LLM 自動 routing（→ v1.4+；本版觸發**只**支援 @mention）
- 並行跑取 best（→ 未來，需要先有評估機制）
- v1.3.6 Skill 推薦的後端邏輯與 endpoint
- v1.3.4 classifier 整合（依賴順序：本版先做完 schema，v1.3.4 才能讀 `session_agent`）
- Agent 之間互傳訊息 / function call 接力（A 的回覆作為 B 的 input 由前端追問驅動，不做後端 chain）
- Agent 角色化（`role` 欄位本版只記錄 `primary` / `member`，不做權重 / 排他控制）

---

## 前置現況

- v1.1：`chat_session.agent_uid` 為 NOT NULL FK（[backend/app/models/chat_session.py](../../../backend/app/models/chat_session.py)），單一 Session 只能掛一個 Agent。
- v1.1：`chat_message` 不含 Agent 來源欄位（[backend/app/models/chat_message.py](../../../backend/app/models/chat_message.py)）；訊息歸屬靠 `chat_session.agent_uid` 反查，多 Agent 後反查失準。
- v1.1：`agent_template` 表（V17）已有 `python-dev` / `code-reviewer` / `zh-writer` / `zh-en-translator` 4 個範本，未涵蓋 `general` / `long-analysis` / `summary` 三類**情境用途**範本。
- v1.2：最後 migration 為 V37（`script.visibility`）；v1.3.0 已用 V38（`llm_call_log`），本版起 V39。
- v1.2.x：social router、列表 API 等已穩定，不影響本版改動。
- v1.3.0 / v1.3.1：成本 metrics + 觀察性層 0/1 是本版 LLM 呼叫量度的前置依賴（不阻擋 schema，但 admin debug 端點與本版多 Agent 計費紀錄共用 `llm_call_log`）。

---

## 已確認決策

| # | 決策點 | 結論 | 理由 |
| --- | --- | --- | --- |
| 1 | Session : Agent 關聯 | 新增 `session_agent` 中介表；`chat_session.agent_uid` 保留並改 nullable，標 deprecated | 雙寫過渡：舊資料 / 舊 API 仍可讀，遷移腳本將既有 `agent_uid` 同步寫入 `session_agent`，後續版本（v1.4+）再決定是否 drop |
| 2 | 觸發方式 | **僅支援 `@mention` 顯式指定**；LLM 自動 routing 延後 | @mention 簡單、可控、UI 直觀、debug 容易；自動 routing 需要評估機制配合（先等 v1.3.4 classifier 與 v1.3.0 metrics 落地再評估） |
| 3 | 多 Agent 順序 | **序列（A → B）**：使用者一次只能 mention 一個 Agent，後續可手動再向另一個 Agent 追問 | 並行成本翻倍 + UI 難以解釋多份回覆 + debug 困難；序列下「誰回的」清楚對應 mention 操作 |
| 4 | `chat_message.responding_agent_uid` | 一則 assistant 訊息綁一個 Agent；user 訊息為 NULL | 訊息來源直接寫入 row，不再靠 session 反查；前端可直接顯示 Agent 名稱 / 頭像 |
| 5 | 沒 mention 時的預設 Agent | 取 `session_agent.role='primary'` 那筆；若多筆 primary（避免 race），以 `created_at` 最早者為準 | 一個 session 必定有一個 primary（建立時自動指派），向下相容單 Agent 對話 |
| 6 | Agent Template `general` / `long-analysis` / `summary` 儲存形式 | 寫入既有 `agent_template` 表（透過 V42 seed） | 已有完整 schema 與 admin UI，無需新表；service 層常數化會增加 admin 維運負擔 |
| 7 | 各 template `max_tokens` 預設 | `general=2048`、`long-analysis=8192`、`summary=2048` | 對齊 propose §4-1；`long-analysis` 涵蓋 code review / 長文摘要 |
| 8 | @mention 觸發符號 | `@` + Agent 顯示名稱（`@AgentName`），前端 selector 從該 session 已掛 Agent 中選 | 與 GitHub / Slack 慣用一致；不做模糊比對，避免錯選 |
| 9 | session 內 Agent 上限 | 軟性上限 5 個（前端 UI 提示，後端不擋；超過時前端 disable 新增按鈕） | 一般使用情境 2-3 個 Agent 已足；上限可從 `system_setting` key `multi_agent.max_per_session` 控制 |
| 10 | session_agent.role 欄位值 | `primary` / `member`；同 session 僅一個 `primary` 由 partial unique index 保證 | 為日後擴充 `coordinator` / `reviewer` 等角色保留欄位，本版不消費 |
| 11 | Skill 推薦 UI 入口位置 | 訊息卡片下方 / Agent 切換列旁的「推薦掛載」icon；後端尚未提供 endpoint 時 hook 回空陣列 | UI placeholder 先佔位，v1.3.6 接 endpoint 即可亮起，不需再動 UI 結構 |
| 12 | 既有 session 的遷移 | V39 建表後，**同 migration** 內以 `INSERT INTO session_agent (session_uid, agent_uid, role) SELECT chat_session_uid, agent_uid, 'primary' FROM chat_session WHERE agent_uid IS NOT NULL` 一次性灌入 | 避免應用層補資料時的 race；既有 sessions 全自動帶 primary 角色 |
| 13 | 既有 message 的遷移 | V40 建立 `responding_agent_uid` 後，以 `UPDATE chat_message SET responding_agent_uid = (SELECT agent_uid FROM chat_session WHERE chat_session_uid = chat_message.chat_session_uid) WHERE role='assistant'` 回填 | 舊 assistant 訊息可正確歸屬到當時的單一 Agent |

---

## Phase 0：Migration

### 0-1 V39：`session_agent` 中介表

- [x] `migrations/sql/V39__create_session_agent.sql`
  - `pid BIGSERIAL PRIMARY KEY`
  - `session_agent_uid UUID NOT NULL DEFAULT gen_random_uuid()`
  - `chat_session_uid UUID NOT NULL` + FK to `chat_session(chat_session_uid)` ON DELETE CASCADE
  - `agent_uid UUID NOT NULL` + FK to `agent(agent_uid)` ON DELETE RESTRICT
  - `role VARCHAR(20) NOT NULL DEFAULT 'member' CHECK (role IN ('primary','member'))`
  - `is_active`、`is_deleted`、`created_at`、`updated_at` + `set_updated_at` trigger
  - `CREATE UNIQUE INDEX uq_session_agent_uid ON session_agent (session_agent_uid)`
  - `CREATE UNIQUE INDEX uq_session_agent_pair ON session_agent (chat_session_uid, agent_uid) WHERE is_deleted = FALSE`
  - `CREATE UNIQUE INDEX uq_session_agent_primary ON session_agent (chat_session_uid) WHERE role = 'primary' AND is_deleted = FALSE`（一個 session 僅一個 primary）
  - `CREATE INDEX idx_session_agent_session ON session_agent (chat_session_uid) WHERE is_deleted = FALSE`
  - `CREATE INDEX idx_session_agent_agent ON session_agent (agent_uid) WHERE is_deleted = FALSE`
  - `COMMENT ON TABLE` + 全欄位 COMMENT（中文，遵循 V19 / V22 既有 pattern）

### 0-2 V39：既有 session 資料遷移

- [x] V39 同檔末段 `INSERT INTO session_agent (chat_session_uid, agent_uid, role) SELECT chat_session_uid, agent_uid, 'primary' FROM chat_session WHERE agent_uid IS NOT NULL ON CONFLICT DO NOTHING`
- [x] 加註解說明此 INSERT 為一次性遷移，後續寫入由 application 層處理

### 0-3 V40：`chat_message.responding_agent_uid`

- [x] `migrations/sql/V40__add_chat_message_responding_agent.sql`
  - `ALTER TABLE chat_message ADD COLUMN responding_agent_uid UUID NULL`
  - **不**加 DB FK（chat_message 不使用 Python 層 FK，配合 [chat_message.py](../../../backend/app/models/chat_message.py) 既有 pattern）
  - `CREATE INDEX idx_chat_message_responding_agent ON chat_message (responding_agent_uid) WHERE responding_agent_uid IS NOT NULL`
  - `COMMENT ON COLUMN chat_message.responding_agent_uid IS '生成此訊息的 Agent UID（assistant 訊息用，user 訊息為 NULL）'`
- [x] 同檔回填既有資料：`UPDATE chat_message SET responding_agent_uid = cs.agent_uid FROM chat_session cs WHERE chat_message.chat_session_uid = cs.chat_session_uid AND chat_message.role = 'assistant' AND chat_message.responding_agent_uid IS NULL AND cs.agent_uid IS NOT NULL`

### 0-4 V41：`chat_session.agent_uid` 改 nullable + 標 deprecated

- [x] `migrations/sql/V41__alter_chat_session_agent_uid_deprecated.sql`
  - `ALTER TABLE chat_session ALTER COLUMN agent_uid DROP NOT NULL`
  - `COMMENT ON COLUMN chat_session.agent_uid IS '[DEPRECATED v1.3.3] 單 Agent 時代欄位，多 Agent 改用 session_agent 中介表；保留 nullable 以容過渡期，未來版本再評估 drop'`

### 0-5 V42：補 3 個 agent_template 預設值

- [x] `migrations/sql/V42__seed_agent_templates_v13.sql`
  - 沿用 V17 INSERT pattern，新增 3 筆：
    - `template_key='general'`、`label='通用助手'`、`max_tokens=2048`、`sort_order=10`
    - `template_key='long-analysis'`、`label='長文分析助手'`、`max_tokens=8192`、`sort_order=11`
    - `template_key='summary'`、`label='摘要助手'`、`max_tokens=2048`、`sort_order=12`
  - 三筆皆以繁體中文撰寫 `description` / `name` / `identity` / `style` / `role_prompt` / `greeting`
  - `language='zh-TW'`、`temperature` 依用途調整（general=0.5、long-analysis=0.3、summary=0.2）
  - `response_format='markdown'`
  - `ON CONFLICT DO NOTHING`（與 V17 相容；以 `uq_agent_template_key` partial index 為依據）

### 0-6 Migration 順序確認

- [x] 確認 Flyway 套用順序：V37 → V38（v1.3.0）→ V39 → V40 → V41 → V42
- [x] 本機 `docker compose up flyway` 套用無 out-of-order 錯誤（驗收於 Phase 7）

---

## Phase 1：Backend - Model / Schema

### 1-1 SessionAgent Model

- [x] `backend/app/models/session_agent.py`：`SessionAgent(Base)`
  - 欄位對齊 V39：`session_agent_uid`、`chat_session_uid`、`agent_uid`、`role`
  - `Base` 提供 `is_active` / `is_deleted` / `created_at` / `updated_at`
  - **不**設 Python 層 FK（與 [chat_message.py](../../../backend/app/models/chat_message.py) 既有 pattern 一致；FK 由 DB migration 保證）
  - 註解：繁中說明此表角色與 v1.3.3 由來

### 1-2 ChatSession Model 更新

- [x] `backend/app/models/chat_session.py`：
  - `agent_uid` 改 `Mapped[uuid.UUID | None]`、`nullable=True`
  - 加註解標 deprecated（指向 `session_agent`）

### 1-3 ChatMessage Model 更新

- [x] `backend/app/models/chat_message.py` 加 `responding_agent_uid: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)`
- [x] 註解：`assistant 訊息綁一個 Agent；user 訊息為 NULL`

### 1-4 Schema（`backend/app/schemas/chat/schemas.py` 或對應位置）

- [x] `SessionAgentItem`：`{ session_agent_uid, agent_uid, agent_name, agent_avatar_url?, role: Literal['primary','member'], created_at }`
- [x] `ChatSessionDetailResponse` 加 `agents: list[SessionAgentItem]`
- [x] `ChatSessionCreateRequest`：
  - 既有 `agent_uid: UUID` 改為 `Optional[UUID]`，標 deprecated（保留向後相容）
  - 新增 `agent_uids: Optional[list[UUID]] = None`
  - 驗證：`agent_uid` 與 `agent_uids` 至少擇一；兩者並存時以 `agent_uids` 為準（`agent_uid` 視為 primary）
- [x] `ChatMessageItem` / `ChatMessageResponse` 加 `responding_agent_uid: Optional[UUID]`、`responding_agent: Optional[AgentBrief]`（`AgentBrief` 至少含 `agent_uid` / `name` / `avatar_url`）
- [x] `ChatMessagePostRequest` 加 `mentioned_agent_uid: Optional[UUID]`（前端 @mention 解析後傳入）

### 1-5 Agent Template Schema

- [x] 確認 `AgentTemplateResponse` 既有欄位涵蓋 `template_key='general' | 'long-analysis' | 'summary'`，無需 schema 改動
- [x] 若前端依賴特定 enum，於 schema 補上 `template_key: str`（不收斂為 Literal，避免 admin 新增 template 後型別出包）

---

## Phase 2：Backend - Repository / Service

### 2-1 `session_agent_repository.py`

- [x] `add(session_uid, agent_uid, role='member')`：UPSERT；若存在但 `is_deleted=True` 則復活
- [x] `remove(session_uid, agent_uid)`：軟刪；若該筆為 `primary` 且 session 仍有其他 member，需呼叫者額外處理 promote（service 層責任）
- [x] `list_by_session(session_uid)`：JOIN `agent` 取 `name` / `avatar_url`，過濾 `is_deleted=False`
- [x] `get_primary(session_uid) -> SessionAgent | None`
- [x] `set_primary(session_uid, agent_uid)`：將指定 agent_uid 設為 primary，其他改為 member（同 transaction）
- [x] `is_member(session_uid, agent_uid) -> bool`：權限檢查用

### 2-2 `chat_session_service` 改造

- [x] `create_session(payload, user)`：
  - 接受 `agent_uids: list[UUID]`（向後相容：若僅給 `agent_uid`，等同 `[agent_uid]`）
  - 驗證所有 `agent_uids` 屬於該 user 可見（既有 visibility 邏輯）
  - 同 transaction：建立 `chat_session`（`agent_uid` 寫第一個作為向後相容欄位） + 為每個 agent 寫入 `session_agent`（第一個 `role='primary'`，其餘 `role='member'`）
  - 回傳的 detail 包含 `agents: list[SessionAgentItem]`
- [x] `get_session_detail(session_uid, user)`：附帶 `session_agent_repository.list_by_session` 結果
- [x] **新增** `add_agent_to_session(session_uid, agent_uid, user)`：權限驗證 → repository.add；超過 `multi_agent.max_per_session` 時回 422
- [x] **新增** `remove_agent_from_session(session_uid, agent_uid, user)`：
  - 不允許移除最後一個 Agent（回 422 `cannot_remove_last_agent`）
  - 移除 primary 時，自動 promote 加入時間最早的 member 為 primary
- [x] **新增** `promote_primary(session_uid, agent_uid, user)`：呼叫 repo `set_primary`

### 2-3 `chat_message_service` 改造（@mention 解析 + 序列分派）

- [x] `send_message(session_uid, content, attachments, mentioned_agent_uid, user)`：
  - 解析 mention：
    - 若 `mentioned_agent_uid` 給定，驗證該 agent 為該 session 成員（`session_agent.is_member`）；非成員回 422 `agent_not_in_session`
    - 若未給定，取該 session 的 `primary` agent
  - 寫入 user message（`responding_agent_uid=NULL`、`role='user'`）
  - 序列：以選定 agent 呼叫 LLM；assistant message 寫入 `responding_agent_uid=<agent_uid>`、`model=<agent.model>`、`finish_reason`、token / cost 等既有欄位
  - **不**做接力（同訊息只跑一個 Agent；多 Agent 順序由使用者連續發訊驅動）
- [x] `list_messages(session_uid, ...)`：response 附帶 `responding_agent` 物件（JOIN agent 取 name / avatar_url），無對應時為 None
- [x] LLM 呼叫紀錄沿用 v1.3.0 `llm_metering.py` wrapper，`agent_uid` 帶入既有 metering 欄位（若 v1.3.0 已有此欄位）

### 2-4 與既有 RAG / Memory 的整合

- [x] `chat_memory` 寫入路徑：保持 session scope（與 `responding_agent_uid` 無關），不新增 agent 維度欄位（v1.3.5 才考慮 user/project memory）
- [x] Skill 載入路徑：`mentioned_agent` 的 skill_uids 沿用既有 `_skill_prompt_text` 邏輯，多 Agent 不共享 skills

---

## Phase 3：Backend - Router / API

### 3-1 Session API

- [x] `POST /api/v1/chat/sessions`：
  - body 接受 `agent_uids: list[UUID]` 或 deprecated `agent_uid: UUID`
  - response 加 `agents` 欄位
- [x] `GET /api/v1/chat/sessions/{uid}`：response 加 `agents`
- [x] **新增** `POST /api/v1/chat/sessions/{uid}/agents`：
  - body：`{ agent_uid: UUID }`
  - response：更新後的 `agents` list
- [x] **新增** `DELETE /api/v1/chat/sessions/{uid}/agents/{agent_uid}`
- [x] **新增** `PATCH /api/v1/chat/sessions/{uid}/agents/{agent_uid}/promote`：將 agent 設為 primary

### 3-2 Message API

- [x] `POST /api/v1/chat/sessions/{uid}/messages`：
  - body 加 `mentioned_agent_uid: Optional[UUID]`
  - response 內 assistant message 含 `responding_agent_uid` / `responding_agent`
- [x] `GET /api/v1/chat/sessions/{uid}/messages`：每筆 message 含 `responding_agent_uid` / `responding_agent`

### 3-3 Skill 推薦 placeholder（接 v1.3.6 用）

- [x] **新增**（占位 endpoint，回空陣列）`GET /api/v1/agents/{agent_uid}/skill-suggestions?scope=session&scope_uid=<session_uid>`
  - 本版固定回 `{ items: [], hint: 'pending v1.3.6' }`
  - 加 deprecated TODO 註解：v1.3.6 將實作真實邏輯（取代此 stub）
  - 已掛 `get_current_user`、權限驗證 agent 可見性 / session 為該 user
- [x] Swagger 顯示此 endpoint 並標 `tags=['skills', 'preview']`

### 3-4 Swagger 與文件路徑

- [x] 所有新增端點有 `summary` / `description` / `response_model`
- [x] `/api/docs` 顯示完整（沿用 CLAUDE.md 規範路徑）

---

## Phase 4：Backend - Agent Template 預設值

### 4-1 V42 Seed 內容對齊

- [x] V42 SQL 內三筆 INSERT 使用繁體中文：
  - `general`：定位通用對話、回覆風格自然友善、`max_tokens=2048`
  - `long-analysis`：長文 / code review / 多段論述、結構化 markdown 回覆、`max_tokens=8192`
  - `summary`：精煉摘要、限制條列、避免冗述、`max_tokens=2048`
- [x] `role_prompt` 撰寫遵循 propose §2-1（記憶 / Skill 相關 prompt 一律繁中）— 雖非記憶 prompt，但作為一致性保留

### 4-2 AgentForm UI hint（承 propose §4-3 殘留）

- [x] `frontend/src/components/agents/AgentForm.tsx`（或對應檔案）：
  - `max_tokens` 欄位下方加 hint：「1024 ≈ 750 中文字；長分析 / code review 建議 4096+ 或留空」
  - 套用 template 時自動帶入該 template 的 `max_tokens`（既有行為若已有則不動）

### 4-3 Admin 範本管理

- [x] 確認 `/admin/agent-templates` 頁面（若存在）能正常列出新增的 3 筆 template，無前端硬編 enum 撞牆

---

## Phase 5：Frontend - Session 多 Agent 顯示

### 5-1 型別擴充

- [x] `frontend/src/types/chat.ts`：
  - `SessionAgent`: `{ session_agent_uid, agent_uid, agent_name, agent_avatar_url?, role: 'primary'|'member', created_at }`
  - `ChatSessionDetail` 加 `agents: SessionAgent[]`
  - `ChatMessage` 加 `responding_agent_uid?: string`、`responding_agent?: AgentBrief`
  - `ChatMessagePostRequest` 加 `mentioned_agent_uid?: string`
  - `ChatSessionCreateRequest` 加 `agent_uids?: string[]`，`agent_uid` 標 deprecated

### 5-2 RTK Query

- [x] `frontend/src/store/chatApi.ts`：
  - `useGetSessionDetailQuery` 回傳型別擴 `agents`
  - `useListMessagesQuery` 回傳每筆訊息含 `responding_agent`
  - **新增** `useAddSessionAgentMutation` / `useRemoveSessionAgentMutation` / `usePromoteSessionAgentMutation`
  - `useCreateSessionMutation` 接受 `agent_uids`
  - `useSendMessageMutation` 接受 `mentioned_agent_uid`
  - 標籤 invalidate：上述 mutation 觸發 `Sessions` / `SessionDetail` / `Messages` 對應 tag

### 5-3 Session 頁面 Agent badge 列

- [x] `frontend/src/app/(main)/chat/[sessionUid]/page.tsx`（或對應檔案）：
  - session header 顯示已掛 Agent 列表（avatar + name + primary 標記）
  - 每個 badge 提供：移除（X icon）、設為 primary（star icon）
  - 「+ 新增 Agent」按鈕：開 Modal 從使用者可見 Agents 中挑選；超過 5 個時 disable 並顯示「最多 5 個 Agent」
  - 移除最後一個 Agent 時前端 disable，配合 §2-2 後端 422 雙重保險

### 5-4 訊息卡片來源 Agent 顯示

- [x] 訊息列每筆 assistant message：
  - 卡片左上 / 頭像位置顯示 `responding_agent.name` 與 avatar
  - 多 Agent 場景下，連續同一 Agent 訊息可只顯示一次標頭（沿用既有 grouping pattern；若無則本版不做 grouping）
- [x] User message 不顯示 agent 標記

### 5-5 Skill 推薦 placeholder 入口

- [x] Agent badge 旁 / 訊息卡片下方提供「推薦 Skill」icon 按鈕：
  - 點擊呼叫 §3-3 stub endpoint
  - 本版固定回空 → 顯示空狀態「目前沒有可推薦的 Skill」
  - 結構保留至 v1.3.6 接真實 endpoint 即可亮起推薦清單
  - 失敗 / 空時不打擾使用者（不顯示 toast，僅 inline 文字）

---

## Phase 6：Frontend - @mention Selector

### 6-1 @mention Selector 元件

- [x] `frontend/src/components/chat/MentionSelector.tsx`：
  - 監聽輸入框 `@` 字元觸發
  - 浮層列出該 session 已掛 Agent（資料來源 `useGetSessionDetailQuery`）
  - 鍵盤上下鍵選擇、Enter 確認、Esc 關閉
  - 確認後將 `@AgentName ` 插入文字、同時記錄 `mentioned_agent_uid` 到送出 payload
- [x] 不支援多重 @mention（一則訊息只可選一個 Agent，符合決策 #3 序列順序）
- [x] 若使用者刪除 mention 文字、`mentioned_agent_uid` 同步清空

### 6-2 ChatComposer 整合

- [x] `frontend/src/components/chat/ChatComposer.tsx`（或對應名）：
  - 文字輸入框 + 附件按鈕 + 送出按鈕既有，本版插入 MentionSelector
  - 送出時 payload：`{ content, attachments, mentioned_agent_uid }`
- [x] `mentioned_agent_uid` 為 None 時，後端取 primary（與決策 #5 一致）

### 6-3 提示與引導

- [x] 多 Agent session 第一次進入時顯示 toast / inline tip：「輸入 @ 即可指定 Agent；不指定時由 primary 回覆」
- [x] 單 Agent session 不顯示 mention 引導，行為與 v1.1 一致

---

## Phase 7：驗收

### Migration

- [x] V39 套用後 `session_agent` 表結構正確、partial unique index 生效（同 session 兩筆 primary 寫入會被擋）
- [x] V39 既有資料遷移：所有有 `agent_uid` 的 session 在 `session_agent` 都有對應 primary row
- [x] V40 套用後 `chat_message.responding_agent_uid` 欄位存在；既有 assistant message 已被回填
- [x] V41 套用後 `chat_session.agent_uid` 為 nullable，COMMENT 含 deprecated 標記
- [x] V42 套用後 `agent_template` 多 3 筆（`general` / `long-analysis` / `summary`），各自 `max_tokens` 為 2048 / 8192 / 2048
- [x] Flyway 套用順序 V37 → V38（v1.3.0）→ V39 → V40 → V41 → V42 無 out-of-order 錯誤

### Backend

- [x] `POST /chat/sessions` 帶 `agent_uids=[uid_a, uid_b, uid_c]` 建立成功；回傳 `agents` 含 3 筆，第一筆 `role='primary'`
- [x] `POST /chat/sessions` 沿用舊 `agent_uid: <uid>` 仍可建立（向後相容），等同 `agent_uids=[uid]` 且為 primary
- [x] `GET /chat/sessions/{uid}` response 含 `agents`
- [x] `POST /chat/sessions/{uid}/agents` 加入新 Agent 成功；超過上限（system_setting `multi_agent.max_per_session`）回 422
- [x] `DELETE /chat/sessions/{uid}/agents/{agent_uid}`：刪除 primary 自動 promote；刪除最後一個回 422 `cannot_remove_last_agent`
- [x] `PATCH /chat/sessions/{uid}/agents/{agent_uid}/promote`：原 primary 改為 member，目標改為 primary，partial unique index 不衝突
- [x] `POST /chat/sessions/{uid}/messages` 帶 `mentioned_agent_uid`：
  - mention 為 session 成員 → assistant message `responding_agent_uid` 為該 uid
  - mention 非成員 → 422 `agent_not_in_session`
  - 未帶 mention → 取 primary 處理
- [x] `GET /chat/sessions/{uid}/messages` 每筆 assistant message 含 `responding_agent` 物件（含 name / avatar_url）
- [x] `GET /agents/{agent_uid}/skill-suggestions` stub 回 `{ items: [], hint: 'pending v1.3.6' }`，未登入 401
- [x] Swagger `/api/docs` 顯示所有新端點與欄位

### Frontend

- [x] Session header 顯示多 Agent badge（avatar + name + primary 標記）
- [x] 「+ 新增 Agent」可從使用者可見 Agents 中選；達 5 個上限時按鈕 disable
- [x] Agent badge 提供移除 / 設為 primary，操作後 UI 即時更新
- [x] 訊息列 assistant message 顯示來源 Agent 名稱與 avatar；user message 不顯示
- [x] 輸入框輸入 `@` 觸發 MentionSelector，列出該 session 已掛 Agent
- [x] 鍵盤上下鍵 / Enter / Esc 操作正確；確認後文字插入 `@AgentName ` 且 payload 帶 `mentioned_agent_uid`
- [x] 單 Agent session 不顯示 mention 引導；多 Agent session 首次進入顯示 tip
- [x] Skill 推薦 placeholder 按鈕點擊後顯示空狀態（「目前沒有可推薦的 Skill」），不打擾使用者
- [x] AgentForm `max_tokens` 欄位下方顯示 hint「1024 ≈ 750 中文字；長分析 / code review 建議 4096+ 或留空」
- [x] 套用 `general` / `long-analysis` / `summary` template 時自動帶入對應 `max_tokens`（2048 / 8192 / 2048）

### 既有功能不破壞

- [x] 舊 single-agent session 進入後正常顯示一個 Agent badge、訊息歸屬正確（responding_agent 為原 agent）
- [x] 舊 `POST /chat/sessions` body 形態（僅 `agent_uid`）仍可建立 session
- [x] v1.1 chat memory / RAG / SSE memory_updated（若 v1.3.2 已落地）行為不受多 Agent 影響
- [x] v1.3.0 metrics（`llm_call_log`）每筆呼叫帶正確 `agent_uid`，多 Agent session 可分 Agent 統計成本

### Design-Base / 規範

- [x] 所有新增 SQL COMMENT 為繁中
- [x] 所有新增 / 修改 Python / TypeScript 註解為繁中
- [x] API 文件路徑維持 `/api/docs`，未引入 `/swagger` / `/docs` / `/openapi` 等別名
- [x] commit message 使用繁中 + `(AI)` 前綴（依 CLAUDE.md）
