# v1.3.6 任務規格：Agentic Skill 工廠正式版（消費跨層記憶 + Skill 推薦給 Agent）

> **狀態：進行中（程式碼完成：commit c6debca, 2026-04-25；Phase 7 runtime smoke 待完成）**
> 已交付：Phase 0~6。Phase 7 驗收需依賴 docker compose 啟動實際環境
> （migration 套用、Redis 連線、實際 LLM 呼叫、SSE 即時驗證），程式碼層的驗收條件
> 已就位但需使用者執行 smoke test 完成最終勾選。
>
> 前置：[propose-v1.3.0.md §5-2](propose-v1.3.0.md)、[tasks-v1.1.7.md](../v1.1/tasks-v1.1.7.md)（PoC 基底）、[tasks-v1.3.0.md](tasks-v1.3.0.md)（`call_llm_metered` wrapper）、[tasks-v1.3.5.md](tasks-v1.3.5.md)（跨層記憶必備）
> 後續依賴：（無 — v1.3 系列最後一份）

## 版本目標

承接 [v1.1.7 PoC](../v1.1/tasks-v1.1.7.md) 的 Agentic Skill 工廠（單一 session `chat_memory` + Redis 暫存 + 人工審核入庫），升級為跨層消費 + 推薦提示的正式版：

1. analyzer 輸入由單一 session `chat_memory` 擴大至三層（`chat_memory` / `project_memory` / `user_memory`），識別跨 session 重複的使用習慣 / 領域偏好
2. Suggestion 從 Redis 暫存搬到 DB 表 `agentic_skill_suggestion`（保留 30 天供事後分析）
3. 新增 recommender service：訊息送達某 Agent 時，若該使用者有未掛載的高 confidence Skill 符合意圖，**提示**使用者（不自動掛載）
4. analyzer 的 LLM 呼叫一律走 v1.3.0 的 `call_llm_metered` wrapper，`purpose='skill_factory'`
5. 既有 v1.1.7 的 Redis `agentic:skill:log` stream 訊號續用於 threshold 調校（不退場）

### 範圍內

- **Migration**：新增 `agentic_skill_suggestion` 表、補種子設定（user / project scope 的 N / M 閾值與 recommender 開關）
- **Backend - Models / Schemas**：新增 `AgenticSkillSuggestion` model、Pydantic schemas（含 scope / status / confidence / source_memory_uids）
- **Backend - Analyzer 升級**：`skill_factory_service.analyze_session` 拆分為三個入口 — `analyze_session` / `analyze_project` / `analyze_user`，分別讀對應記憶表，產出 suggestion 寫入 DB（取代 Redis 暫存）
- **Backend - Worker 擴充**：`skill_factory_worker` 增加 project / user scope 的觸發來源（`project_memory_worker` / `user_memory_worker` 寫完 project / user memory 後 LPUSH）
- **Backend - Recommender Service**：訊息送達 Agent 時，依 user_uid + 訊息意圖比對 `pending` 狀態的 suggestion，回推薦清單
- **Backend - Suggestion API**：list / accept / reject / 來源詳情 endpoint，支援以 Agent 為入口的推薦查詢
- **Frontend - 推薦提示 UI**：v1.3.3 多 Agent 對話入口處掛載「未讀建議 N」徽章 + 抽屜
- **Frontend - Suggestion 列表頁**：使用者個人設定下「Skill 建議」分頁，顯示三 scope 全部 suggestion，支援接受 / 拒絕 / 查看來源記憶
- **LLM 輸出語言**：analyzer / recommender 的 system prompt 必須明確指示輸出**繁體中文**（[propose §2-1](propose-v1.3.0.md#2-1)）
- **既有 LLM 呼叫遷移**：v1.1.7 PoC 的 `generate_skill_suggestion` 改走 `call_llm_metered`

### 範圍外

- **Skill 自動入庫**（無人工審核） — propose §5-2 明確排除，永不實作
- **跨使用者共享 Skill** → v1.4 公開 API + API Key 管理
- **Skill 候選版本管理 / diff** → 後續觀察需求
- **Recommender 的 LLM 意圖分類** — 本版以「向量相似度 + 主題 keyword 比對 + confidence 門檻」做匹配，不另外呼叫 LLM 做意圖判定（避免每則訊息多一次 LLM 成本）
- **Suggestion 過期自動清理 worker** — 本版以 `expired` status 標記為主，定時清理留 v1.4
- v1.1.7 的 Redis 暫存路徑**保留唯讀相容**至本版上線後 7 天，期間並行寫入 DB；超過後 PoC 路徑下線

---

## 前置現況

- [v1.1.7 PoC](../v1.1/tasks-v1.1.7.md) 已上線：`skill_factory_service` / `skill_factory_worker` / `agentic:skill:log` Redis stream 皆運作；suggestion 暫存於 Redis（`skill:suggestion:{user_uid}:{session_uid}`，TTL 7 天）；前端 session 頁面側邊欄能列出 / approve / reject。
- [v1.3.0](tasks-v1.3.0.md) 已上線：`llm_call_log` 表 + `call_llm_metered` wrapper（[backend/app/services/llm_metering.py](../../../backend/app/services/llm_metering.py)），所有新增 LLM 呼叫一律經此入口。
- [v1.3.5](tasks-v1.3.5.md) 已上線：`project_memory` / `user_memory` 表、聚合 worker、三層 RAG 檢索融合（RRF）；本版 analyzer 直接讀對應 repository。
- [v1.3.3](tasks-v1.3.3.md) 已上線：`session_agent` 中介表，一個 session 可多 Agent；本版 recommender 以 (session_uid, agent_uid) 對為查詢入口。
- v1.3.x 系列 V 號分配已統一：v1.3.0=V38（llm_call_log）、v1.3.3=V39–V42（multi-agent）、v1.3.4=V43（classifier seed）、v1.3.5=V44–V46（project / user memory）、**本版=V47–V48**。實作時若前置 task 未完成可跳過該 V 段，但本版自身的 V47 / V48 順序須維持。
- v1.1.7 Redis stream `agentic:skill:log` 累積數百筆 approve / reject 訊號（PoC 期間，30 天 MAXLEN ~10000）；本版 §1-1 的 N / M 初始值已參考此實測數據設定。

---

## 已確認決策（重點）

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | 人工審核 | **保留**（[propose §5-2 非目標](propose-v1.3.0.md#5-2)）— 本版只新增「推薦提示」，不跳過 approve；任何 Skill 入庫仍走既有 `POST /api/v1/skills` |
| 2 | Suggestion 儲存 | 從 Redis 搬到 DB 表 `agentic_skill_suggestion`，保留 30 天 expired 後 status 標記，**不**做硬刪 |
| 3 | Recommender 不自動掛載 | 訊息送達 Agent 時僅**提示**使用者，由使用者一鍵 accept 才掛載；理由：避免權限膨脹、避免使用者察覺不到 Agent 行為突變 |
| 4 | analyzer LLM 走 metered wrapper | 一律 `call_llm_metered(purpose='skill_factory', scope=<session\|project\|user>, user_uid=..., resource_uid=<scope_uid>)`；`scope` 帶入子分類便於 admin SQL 拆桶分析 |
| 5 | analyzer LLM 輸出語言 | system prompt **強制繁體中文**（propose §2-1），對齊 v1.2 fixed.md 既有補修 |
| 6 | 三 scope 觸發條件（N / M 閾值） | 詳見下表「初始閾值建議」；可由 `system_setting` 覆寫 |
| 7 | suggestion scope FK 策略 | `scope_uid` 不綁 FK（容忍上游資源刪除）；scope 對應記憶刪除時，suggestion **不**連動硬刪，僅 status 改 `expired`（與 [propose §3-3 記憶生命週期](propose-v1.3.0.md#3-3) 對齊） |
| 8 | 重複觸發防護 | 同 (user_uid, scope, scope_uid) 在 cooldown 期間內，相同 signature（topics 集合 hash）**不**重複生成；signature 紀錄改用 DB `agentic_skill_signature` 輔助表或續用 Redis（決策見 §0-3） |
| 9 | recommender 比對策略 | 三段：(a) 訊息向量與 suggestion 來源記憶向量 cosine top-3 取最大；(b) suggestion 主題 keywords 與訊息 keywords 交集 ≥ 1；(c) `confidence ≥ recommender.min_confidence`（預設 0.75）三者皆滿足才上推薦清單 |
| 10 | recommender 不呼叫 LLM | 為避免每則訊息多一次 LLM 成本，僅以「向量相似度 + keyword 比對 + confidence 門檻」做匹配；若日後判定誤推率高再加 LLM rerank |
| 11 | v1.1.7 Redis 暫存退場 | 並行寫入 DB 7 天觀察期（API 同時讀 DB + Redis 合併）→ 退場後 `skill_factory_service` 移除 Redis 寫入路徑，僅保留 `agentic:skill:log` stream（後者用於閾值調校） |
| 12 | 推薦提示位置 | v1.3.3 多 Agent 對話頁面 Agent 切換器旁，顯示「建議 N」徽章；點擊開抽屜 |

### 初始閾值建議（可由 `system_setting` 覆寫）

| 設定 key | 初始值 | 說明 |
| --- | --- | --- |
| `agentic.skill_factory.session.min_memory_count` | 10 | 沿用 v1.1.7 PoC 設定（[V32](../../../backend/migrations/sql/V32__seed_agentic_skill_factory_settings.sql)） |
| `agentic.skill_factory.session.topic_concentration` | 0.30 | 沿用 v1.1.7 |
| `agentic.skill_factory.project.min_memory_count` | 20 | 跨 session 聚合後樣本量加倍，避免單 session 干擾 |
| `agentic.skill_factory.project.topic_concentration` | 0.40 | 比 session 嚴 — 主題聚焦度需更高才視為穩定模式 |
| `agentic.skill_factory.user.min_memory_count` | 30 | 跨 project 長期偏好需更多樣本（涵蓋多 project 才能去除單 project 偏誤） |
| `agentic.skill_factory.user.topic_concentration` | 0.50 | 最嚴 — 半數以上記憶集中於同主題才生成 user scope Skill |
| `agentic.skill_factory.cooldown_hours` | 24 | 沿用 v1.1.7 |
| `agentic.skill_factory.confidence_floor` | 0.60 | 低於此值的 LLM 候選**不**寫入 DB（PoC 期觀察到 < 0.6 多為雜訊） |
| `agentic.recommender.enabled` | true | 推薦功能總開關 |
| `agentic.recommender.min_confidence` | 0.75 | 進入推薦清單的 confidence 下限（比 confidence_floor 嚴：能寫進 DB 的不一定值得推薦） |
| `agentic.recommender.cosine_threshold` | 0.65 | 訊息向量 vs 來源記憶向量 cosine 相似度下限 |
| `agentic.recommender.max_per_request` | 3 | 單則訊息最多回幾筆推薦（避免抽屜爆量） |
| `agentic.skill_factory.suggestion_ttl_days` | 30 | suggestion 從 `created_at` 起 N 天後 status 自動標記為 `expired`（讀取時 lazy 標記，無需 worker） |

> N / M 初始值依據：v1.1.7 PoC 觀察**單 session min=10 / topic=0.30** 的 false positive 約 30%；本版 project / user scope 樣本範圍更大，閾值對應放嚴以維持 < 20% false positive。實際 approve 率上線後續監控 `agentic:skill:log` 並調校。

---

## Phase 0：Migration

### 0-1 V47：建立 `agentic_skill_suggestion` 表

- [x] `migrations/sql/V47__create_agentic_skill_suggestion.sql`（schema 對齊 [propose §5-2](propose-v1.3.0.md#5-2)）
  - `pid bigserial PRIMARY KEY`
  - `agentic_skill_suggestion_uid uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE`
  - `owner_user_uid uuid NOT NULL`（**不綁 FK**，泛型；user 刪除時連動由 application layer 處理）
  - `scope varchar(20) NOT NULL CHECK (scope IN ('session','project','user'))`
  - `scope_uid uuid NOT NULL`（**不綁 FK**，容忍 scope 對應資源刪除）
  - `name varchar(50) NOT NULL`
  - `description varchar(200) NOT NULL`
  - `system_prompt text NOT NULL`
  - `confidence numeric(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1)`
  - `source_memory_uids uuid[] NOT NULL DEFAULT ARRAY[]::uuid[]`（記錄哪幾筆 memory 觸發本次生成）
  - `signature varchar(64) NOT NULL`（`sha256(sorted(set(topics)))`，用於同 scope_uid + signature 去重）
  - `status varchar(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','expired'))`
  - `created_skill_uid uuid`（status=approved 時填入；不綁 FK 容忍 skill 後續刪除）
  - `is_active boolean NOT NULL DEFAULT true`
  - `is_deleted boolean NOT NULL DEFAULT false`
  - `created_at timestamptz NOT NULL DEFAULT now()`
  - `updated_at timestamptz NOT NULL DEFAULT now()`
  - Trigger：套用既有 `set_updated_at` 函式
  - Partial Unique：`UNIQUE (owner_user_uid, scope, scope_uid, signature) WHERE is_deleted = FALSE AND status = 'pending'`（同 scope 同 signature 同時間至多一筆 pending；approved / rejected / expired 不限）
  - Index：
    - `idx_agentic_skill_suggestion_owner_status ON (owner_user_uid, status)`（list API）
    - `idx_agentic_skill_suggestion_scope ON (owner_user_uid, scope, scope_uid) WHERE is_deleted = FALSE`
    - `idx_agentic_skill_suggestion_created ON (created_at DESC)`（30 天 expired 掃描）
  - `COMMENT ON TABLE` / `COMMENT ON COLUMN` 全部欄位（繁體中文）

### 0-2 V48：種子設定（補三 scope 閾值與 recommender）

- [x] `migrations/sql/V48__seed_skill_factory_v1_3_6_settings.sql`
  - 對齊 [V32](../../../backend/migrations/sql/V32__seed_agentic_skill_factory_settings.sql) 寫法（`INSERT ... ON CONFLICT DO NOTHING`），新增「初始閾值建議」表中所有 key
  - 既有 v1.1.7 設定（`agentic.skill_factory.min_memory_count` 等）**不動**；本版 session scope 同步沿用該 key（程式端讀取時優先抓 `*.session.*`，未設則 fallback 既有 key 以避免破壞 v1.1.7）

### 0-3 Signature 去重儲存決策

- [x] **決策**：signature 改隨 suggestion 一起存於 DB（§0-1 已加 `signature` 欄位 + Partial Unique），**廢除** v1.1.7 的 Redis `skill:signature:{user_uid}:{session_uid}` key
- [x] `skill_factory_service` 移除 Redis signature 讀寫，改 query DB
- [x] cooldown 判定改為：`SELECT 1 FROM agentic_skill_suggestion WHERE owner_user_uid=:u AND scope=:s AND scope_uid=:sid AND signature=:sig AND created_at > now() - interval ':cooldown_hours hours'`

---

## Phase 1：Backend - Models / Schemas

### 1-1 SQLAlchemy Model

- [x] `backend/app/models/agentic_skill_suggestion.py`（新檔）
  - `class AgenticSkillSuggestion(Base)` 對應 V47 schema
  - 繼承 `Base` mixin（`is_active` / `is_deleted` / `created_at` / `updated_at`）
  - `source_memory_uids: Mapped[list[UUID]]` 對應 `ARRAY(UUID)`
  - `confidence: Mapped[Decimal]` 使用 `Numeric(4, 3)`
- [x] `backend/app/models/__init__.py` 補匯出

### 1-2 Pydantic Schemas

- [x] `backend/app/schemas/agentic/skill_suggestion_schemas.py`（新檔；既有 `chat/skill_suggestion_schemas.py` 為 PoC 用，**不動**）
  - `SuggestionScope = Literal["session", "project", "user"]`
  - `SuggestionStatus = Literal["pending", "approved", "rejected", "expired"]`
  - `AgenticSkillSuggestionItem`：`{ uid, scope, scope_uid, name, description, system_prompt, confidence, source_memory_uids, status, created_skill_uid?, created_at, updated_at }`
  - `AgenticSkillSuggestionListResponse`：`{ items: list[...], page, size, total }`
  - `AgenticSkillSuggestionAcceptResponse`：`{ skill_uid, agent_uid, mounted: bool }`（accept 同時掛到指定 Agent 時 mounted=true）
  - `RecommendSuggestionItem`（給 recommender API 用）：簡化欄位，省略 `system_prompt` 細節，前端展開時再走 detail API
- [x] **重要**：所有 schema **不**回傳任何 internal pid；`uid` 欄位改用 `agentic_skill_suggestion_uid` 並別名為 `uid`（對齊 [Design-Base 10-frontend.md § 識別碼](../../Design-Base/10-frontend.md)）

### 1-3 Repository

- [x] `backend/app/repositories/agentic_skill_suggestion_repository.py`（新檔）
  - `create(...)`：寫入新 suggestion（含 signature）
  - `find_active_signature(owner_user_uid, scope, scope_uid, signature, cooldown_hours) -> bool`：cooldown 判定
  - `list_by_owner(owner_user_uid, *, scope=None, status=None, page, size)`
  - `list_pending_by_user(owner_user_uid)`：給 recommender 用，僅取 `status='pending'`
  - `mark_approved(uid, created_skill_uid, db)` / `mark_rejected(uid, db)` / `mark_expired_bulk(cutoff_at, db)`
  - `get_by_uid(uid, owner_user_uid)`：含擁有者驗證
- [x] **不**新增 service / repo 的 cross-concern：本表的軟刪僅在 user 帳號刪除時連動（沿用既有 user 刪除流程，後續 v1.4 評估）

---

## Phase 2：Backend - Analyzer 升級（消費三層記憶）

### 2-1 拆分 analyzer 入口

- [x] `backend/app/services/skill_factory_service.py` 重構：
  - 既有 `analyze_session(session_uid, user_uid, db)` **保留**並改寫為內部呼叫共用 `_analyze_scope`
  - 新增 `analyze_project(project_uid, user_uid, db)`：取 `project_memory_repository.list_by_project(project_uid)`
  - 新增 `analyze_user(user_uid, db)`：取 `user_memory_repository.list_by_user(user_uid)`
  - 共用 `_analyze_scope(scope, scope_uid, user_uid, memories, db)`：
    1. Rule 檢查（`min_memory_count` / `topic_concentration` 依 scope 取對應 settings key）
    2. signature = `sha256(sorted(set(topics)))`；查 DB cooldown（§0-3）
    3. 組 payload → `call_llm_metered(purpose='skill_factory', scope=scope, user_uid=..., resource_uid=scope_uid)` 包裝既有 `generate_skill_suggestion`
    4. 過濾 `confidence < confidence_floor`
    5. 寫入 DB（§1-3 `create`）並回傳新增的 suggestion list
    6. 寫 `agentic:skill:log` Redis stream（沿用 v1.1.7，type=`generated_v2`，新增 `scope` / `scope_uid` 欄位以區分 PoC）

### 2-2 LLM 呼叫遷移到 metered wrapper

- [x] `backend/app/clients/openrouter/client.py::generate_skill_suggestion` 既有 callsite 改為透過 `call_llm_metered` 包裝（[v1.3.0 §3](tasks-v1.3.0.md) 規範）
- [x] system prompt 補繁體中文宣告（對齊 v1.2 fixed.md，若該補修已合併則確認本檔同樣帶有；缺則補）：
  - 「請以**繁體中文（zh-TW）**輸出 `name` / `description` / `system_prompt` 三個欄位的內容；不論輸入記憶語言為何，輸出統一使用繁體中文。」
- [x] `purpose='skill_factory'`、`scope='session'|'project'|'user'`、`user_uid` / `resource_uid` 帶入 metering metadata，方便 admin SQL 依 scope 拆桶觀察成本

### 2-3 Worker 觸發來源擴充

- [x] `backend/app/workers/skill_factory_worker.py` 重構：
  - queue payload 擴充為 `{ scope: 'session'|'project'|'user', scope_uid, user_uid }`（向後相容：缺 `scope` 時當作 `session` 處理）
  - dispatcher 依 scope 路由到 `analyze_session` / `analyze_project` / `analyze_user`
- [x] `backend/app/workers/memory_worker.py`（session scope 觸發）：原 LPUSH 行為不動，但 payload 增加 `scope='session'`
- [x] 改寫 `backend/app/workers/project_memory_worker.py` / `backend/app/workers/user_memory_worker.py`：聚合完一輪 project_memory / user_memory 後，LPUSH `skill_factory_queue`：
  - project 聚合完成 → `{ scope: 'project', scope_uid: project_uid, user_uid }`
  - user 聚合完成 → `{ scope: 'user', scope_uid: user_uid, user_uid }`
- [x] `_handle` 失敗策略沿用既有（重試 2 次，純失敗只 log，不阻塞其他）

### 2-4 既有 PoC 路徑相容過渡

- [x] `skill_factory_service.list_suggestions` 改為**雙讀合併**：
  - DB query（§1-3 `list_by_owner` scope='session', scope_uid=session_uid）
  - 既有 Redis `skill:suggestion:{user_uid}:{session_uid}` 仍讀（標記為 PoC legacy）
  - 兩邊以 (signature, scope_uid) 去重，DB 優先
- [x] **保留 7 天**：上線後第 8 天移除 Redis 讀路徑（commit 註明 `Refactor: 移除 v1.1.7 Skill Suggestion Redis 暫存路徑`，本任務驗收**不**包含此移除步驟）

---

## Phase 3：Backend - Recommender Service

### 3-1 Service 主體

- [x] `backend/app/services/skill_recommender_service.py`（新檔）
  - `recommend_for_message(user_uid, agent_uid, message_text, message_embedding, db) -> list[RecommendSuggestionItem]`：
    1. 若 `agentic.recommender.enabled=false` → 回 `[]`
    2. 列出該 user 所有 `status='pending'` 且 `confidence >= recommender.min_confidence` 的 suggestion（§1-3 `list_pending_by_user`）
    3. 過濾掉**已掛載到該 agent**的 suggestion（query `agent.skill_uids` 含 `created_skill_uid` 即剔除）
    4. 對每筆 suggestion，撈其 `source_memory_uids` 對應的 embedding（取至多 3 筆代表向量）
    5. 計算 message_embedding 與代表向量的 cosine 相似度，取 max；若 max < `cosine_threshold` 剔除
    6. keyword 比對：suggestion 來源記憶的 keywords 與訊息提取 keywords（用既有 `extract_memory` 的 keyword 邏輯，輕量）交集 ≥ 1；無 keyword 提取時略過此檢查
    7. 取 top `recommender.max_per_request` 回傳

### 3-2 Hook 至訊息 pipeline

- [x] `backend/app/services/chat_service.py::send_message`（既有訊息流）在使用者訊息存檔、embedding 算完後（embed worker 完成的回調或 inline embed 後），呼叫 `skill_recommender_service.recommend_for_message`
  - **不阻塞回覆生成**：recommender 結果寫入 Redis pub/sub `chat:session:{uid}:skill_recommendation`
  - 訊息 SSE pipeline 並行推 `event: skill_recommendation\ndata: { items: [...] }\n\n`（v1.3.2 SSE channel 擴充新事件類型）
- [x] 若 inline embed 不存在（v1.1 仍走 worker 非同步），則改在 memory_worker 寫完 embedding 後 LPUSH `skill_recommender_queue`，由獨立 worker 消費
  - **決策**：本版優先採方案 A（inline 訊息送達後即時呼叫 recommender，因僅向量比對 + DB read，延遲應 < 100ms）；若實測 P95 > 200ms 再退方案 B
- [x] **重要**：recommender 不寫任何 LLM call（§已確認決策 #10），故**不**經 `call_llm_metered`

### 3-3 推薦緩存

- [x] 同一 (user_uid, agent_uid, suggestion_uid) 在 1 小時內**不**重複推（避免使用者反覆收到同一張卡）：
  - Redis key `skill_rec:dedup:{user_uid}:{agent_uid}:{suggestion_uid}`，TTL 3600
  - 觸發推薦前先 SETNX，已存在則跳過

---

## Phase 4：Backend - Suggestion API

### 4-1 Suggestion CRUD（使用者個人視角）

- [x] `backend/app/api/v1/agentic/skill_suggestions/router.py`（新檔；router prefix `/api/v1/skill-suggestions`）
  - `GET /api/v1/skill-suggestions?scope=&status=&page=&size=` → `list_by_owner`（current user）
    - 預設 status=`pending`，scope 不傳則回三 scope 全部
  - `GET /api/v1/skill-suggestions/{uid}` → 詳情（含 source_memory_uids 對應記憶摘要 inline 展開）
  - `POST /api/v1/skill-suggestions/{uid}/accept` body：`{ agent_uid?: uuid }`
    - 打包 system_prompt 為 `prompt.md` 進單檔 zip → 呼叫 `skill_service.upload_skill`（沿用 v1.1.7 流程）
    - `mark_approved(uid, created_skill_uid)`
    - 若帶入 `agent_uid` 則同步將 `created_skill_uid` 加入該 agent 的 `skill_uids`（驗證 agent 屬於 current user）
    - 寫 `agentic:skill:log` type=`approved_v2`
  - `POST /api/v1/skill-suggestions/{uid}/reject` → `mark_rejected` + log type=`rejected_v2`
- [x] 全部端點掛 `get_current_user`，所有 query / mutation 驗證 ownership（owner_user_uid == current_user.uid）

### 4-2 Recommender API（Agent 入口）

- [x] `backend/app/api/v1/agents/router.py` 新增：
  - `GET /api/v1/agents/{uid}/skill-suggestions` → 列出**該 user 對該 agent**的 active 推薦（從 §3-1 結果讀近期快取或即時計算 — **決策**：即時計算但無 message context；當前端進入 Agent 詳情頁時呼叫，不強制需要訊息向量，改以「該 user pending 中、未掛 agent、confidence >= recommender.min_confidence」為過濾，跳過 §3-1 第 4-6 步的訊息比對）
  - `POST /api/v1/agents/{uid}/skill-suggestions/{sid}/accept` → 同 §4-1 accept，但 `agent_uid` 強制為 path 中 `{uid}`
  - `POST /api/v1/agents/{uid}/skill-suggestions/{sid}/reject` → 同 §4-1 reject

### 4-3 Admin debug

- [x] 既有 `GET /api/v1/admin/debug/skill-factory/recent`（v1.1.7）擴充：支援 `?scope=session|project|user` filter
- [x] 新增 `GET /api/v1/admin/debug/skill-factory/stats`：依 scope / status 拆桶計數，approve / reject 比率（用於閾值調校監控）

### 4-4 Swagger 文件

- [x] 所有新增端點以 Pydantic `response_model` + `summary` / `description`（繁體中文）宣告
- [x] `/api/docs`（[CLAUDE.md § 後端 API 文件](../../../CLAUDE.md)）顯示完整 schema 與欄位說明

---

## Phase 5：Frontend - 推薦提示 UI

### 5-1 SSE event 處理

- [x] `frontend/src/hooks/useSessionEvents.ts`（v1.3.2 既有）擴 `skill_recommendation` event handler：
  - 收到 `event: skill_recommendation\ndata: {...}` → dispatch 到 `skillSuggestionSlice` 暫存當前 session 的最新推薦（不 invalidate RTK query，避免 race）
- [x] 推薦資料形態與 §1-2 `RecommendSuggestionItem` 對齊

### 5-2 多 Agent 對話頁面提示徽章

- [x] [v1.3.3 多 Agent 對話頁面](tasks-v1.3.3.md)（`frontend/src/app/(main)/sessions/[uid]/page.tsx` 或多 Agent 切換器元件）：
  - Agent 切換器旁加「建議 N」徽章（N = 該 user 對該 agent 的 active 推薦數）
  - 點徽章開抽屜：列每筆 suggestion 的 name / description / confidence 徽章
  - 抽屜內按鈕：✅「掛載到此 Agent」→ `POST /agents/{uid}/skill-suggestions/{sid}/accept`；❌「拒絕」→ reject
  - confidence 徽章配色沿用 v1.1.7：≥0.8 綠 / 0.6-0.8 黃 / <0.6 灰（本版實際只會顯示 ≥ `recommender.min_confidence`=0.75）

### 5-3 RTK Query

- [x] `frontend/src/store/agenticApi.ts`（新檔）：
  - `useListSkillSuggestionsQuery({ scope?, status?, page?, size? })` → `GET /api/v1/skill-suggestions`
  - `useGetSkillSuggestionQuery(uid)` → 詳情
  - `useListAgentSkillSuggestionsQuery(agentUid)` → `GET /api/v1/agents/{uid}/skill-suggestions`
  - `useAcceptSkillSuggestionMutation` / `useRejectSkillSuggestionMutation`
  - tags：`SkillSuggestions`、`AgentSkillSuggestions-{agentUid}`；accept / reject invalidate 對應 tag + `Skills` + `Agents-{agentUid}`

### 5-4 互動細節

- [x] accept 成功後 toast：「已建立 Skill 並掛載到 {agentName}」（若帶 agent_uid）或「已建立 Skill，可至 Skill 列表掛載」（純 accept 不掛 agent）
- [x] reject 後該卡片移除（樂觀更新）
- [x] 抽屜空狀態：「目前沒有針對此 Agent 的 Skill 建議。系統會在你跨 session / project 形成穩定使用習慣後自動推薦。」
- [x] **禁止**顯示任何 uid（含 suggestion uid、source_memory_uids — 後者僅以「來源記憶 N 則」摘要呈現）— 對齊 [Design-Base 10-frontend.md](../../Design-Base/10-frontend.md)

---

## Phase 6：Frontend - Suggestion 列表頁

### 6-1 路由與入口

- [x] 新增 `frontend/src/app/(main)/skill-suggestions/page.tsx`：使用者個人「Skill 建議」分頁
- [x] 主導航 / 個人選單加入口連結：「Skill 建議 ({pendingCount})」
- [x] `pendingCount` 由 `useListSkillSuggestionsQuery({ status: 'pending' })` 派生（首頁載入 prefetch 一次）

### 6-2 列表 UI

- [x] 上方頁籤：`待處理 (N)` / `已接受 (N)` / `已拒絕 (N)` / `已過期 (N)`（依 status）
- [x] 上方 filter chip：`全部 / Session / Project / User` 三 scope 切換（沿用 v1.2.5 排序 chip 慣例 — 平鋪、單選、無方向箭頭）
- [x] 卡片顯示：
  - `name` 大字、`description` 副標
  - confidence 徽章（同 §5-2 配色）
  - scope 徽章（藍：session / 紫：project / 金：user — 與 v1.3.5 跨層記憶 UI 配色對齊）
  - 來源記憶展開：「來源 N 則記憶 ⌄」點開顯示主題 / 摘要（**不**顯示 memory uid）
  - 操作：`接受` / `接受並掛到 Agent ⌄` / `拒絕`
- [x] 「接受並掛到 Agent ⌄」展開 user 的 agent 列表（`useListAgentsQuery({ scope: 'mine' })`），單選後 accept

### 6-3 Admin 視角（可選）

- [x] **不**做 admin 跨 user 視角（沿用 v1.1.7 範圍外原則：admin 不能看其他使用者的 suggestion，回 403）
- [x] Admin 用既有 `/admin/debug/skill-factory/recent` + `/stats`（§4-3）做系統觀察

---

## Phase 7：驗收

> Runtime 行為驗收統一彙整於 [runtime-acceptance.md](runtime-acceptance.md)。
> 本檔案 Phase 0 ~ 6 的程式碼層 checkbox 即為實作交付清單；smoke / curl / 瀏覽器互動類驗證請見 acceptance 檔案對應章節。

