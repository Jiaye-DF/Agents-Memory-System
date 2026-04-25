# v1.3.5 任務規格：User / Project 記憶 + 三層 RAG 融合

> 前置：[propose-v1.3.0.md §3-1 / §3-2 / §3-3](propose-v1.3.0.md)、[docs/Arch/00-memory-system.md §5 / §6](../../Arch/00-memory-system.md)、[tasks-v1.3.0.md](tasks-v1.3.0.md)（worker LLM 呼叫一律走 `llm_metering` wrapper）、[tasks-v1.3.1.md](tasks-v1.3.1.md)（worker log 升 info、trace 基礎）
>
> 後續依賴：v1.3.6（Skill 工廠正式版）需消費 `project_memory` / `user_memory` 做跨 session pattern 偵測

## 版本目標

把 v1.1 既有的 session-only 記憶擴展為三層架構，並以 RRF 融合三層檢索結果塞進 RAG prompt：

- 新增 `project_memory` / `user_memory` 兩張表（schema 結構類比 `chat_memory`，多 `source_session_uids UUID[]`）
- 新增 `project_memory_worker`（同 project 二次聚合）與 `user_memory_worker`（跨 project 長期偏好聚合）
- `chat_memory_repository.search_similar` 擴展為三層獨立檢索 + 新 service `rrf_fuse(results_per_layer, k=60)`
- `chat_service` 的 RAG 取記憶流程改為走三層融合
- 嚴格落實 propose §3-3 / Arch §5-2 跨層生命週期：`project_memory` / `user_memory` **不**建指向 session 的 FK cascade，刪除路徑由 service 層手動連動

### 範圍內

- DB Migration：`project_memory` / `user_memory` 兩表（HNSW vector index、無指向 session 的 FK cascade）
- Models：`ProjectMemory` / `UserMemory`（沿用 `MemoryBase`，無 `updated_at` / `is_deleted`）
- Repositories：`project_memory_repository` / `user_memory_repository`（含 vector 檢索 + scope 連動清除函式）
- 三層 RAG 融合 service：`rrf_fuse` + `rag_service.retrieve_three_layer`
- 兩個聚合 worker（複用 `extract_memory` LLM，**透過 v1.3.0 metered wrapper**）
- `chat_service.delete_session` / `delete_project` 與 `user_service` 停用 / 刪除路徑的跨層連動
- Admin 手動觸發端點：`POST /admin/memory/aggregate/project/{uid}` / `POST /admin/memory/aggregate/user/{uid}`
- 兩個 worker 的 LLM system prompt 顯式要求繁體中文輸出（propose §2-1）

### 範圍外

- mem0 風格的 add / update / delete / noop 衝突合併決策（v0.1 先 insert，後續版本演進）
- Reranker（→ v1.4+）
- Hybrid search（vector + BM25）（→ v1.4+）
- Agentic Skill 工廠正式版（→ v1.3.6）
- temporal validity / 記憶衰減（→ 未來 user_memory 演化）
- `user_memory` 全部塞 prompt 的策略（Arch §2-2 提到「< 50 筆通常全塞」），本版仍走 RAG top_k，待量產資料驗證後再改

---

## 前置現況

- v1.1：`chat_memory` 表已建立（V22），`chat_memory_repository.search_similar` 為單層 cosine 檢索
- v1.1：`memory_worker` 從 Redis queue 消費 → `extract_memory` 抽取 → embedding → 寫 `chat_memory`
- v1.1：`chat_service.delete_session` L572-578 連動 `chat_memory_repository.hard_delete_by_session`（行為保留，不變）
- v1.3.0：`llm_metering` wrapper 已就緒，所有 LLM 呼叫須透過它計費
- v1.3.1：worker log 升 info、admin debug endpoint `GET /admin/debug/memory/sessions/{uid}` 已就緒
- 既有最大 migration 版本：`V37__add_script_visibility.sql`；v1.3.x 系列 V 號分配：v1.3.0=V38、v1.3.3=V39–V42、v1.3.4=V43、**本版=V44–V46**
- `chat_session.chat_project_uid` 為 nullable（V24），`project_memory` 須能容忍 session 無 project（直接跳過聚合）

---

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | `project_memory` / `user_memory` 對 session 的 FK | **不建立 FK cascade**（propose §3-3 / Arch §5-2 硬規範）；session 刪除不連動清除 |
| 2 | RRF 公式與參數 | `score = Σ 1/(k + rank)`，**k=60**（Elasticsearch 慣例，Arch §8） |
| 3 | 各層 top_k | session=10、project=5、user=5；融合後取 top 5~10 塞 prompt（system_setting 可調） |
| 4 | RRF 是否使用相似度分數 | **僅看排名**，不混分數（跨層尺度不一致，propose §3-2） |
| 5 | 兩 worker 的觸發 | idle N 小時 + cross-session pattern 閾值（見 §6）+ 手動觸發 admin endpoint |
| 6 | `user_memory` 觸發閾值初始建議值 | **N ≥ 5 筆同主題**、**同主題占比 ≥ 60%**（M=60%）；於 `system_setting` 暴露為可調 |
| 7 | 衝突合併策略（v0.1） | **先 insert**，不做 mem0 四向決策；後續版本依量產資料再演進 |
| 8 | LLM 輸出語言 | 兩 worker system prompt 顯式要求**繁體中文**（propose §2-1） |
| 9 | LLM 計費 | 兩 worker 的 `extract_memory` / `embed` 呼叫**必須**走 `llm_metering` wrapper（v1.3.0） |
| 10 | min_score 預設 | session=0.7（沿用 v1.1）、project=0.65、user=0.6（跨層越廣允許越鬆，避免空集合） |
| 11 | embedding 維度 | 三層皆 `vector(1536)`，與 `chat_memory` 一致（text-embedding-3-small） |
| 12 | 索引型別 | HNSW（沿用 V22 既有 pattern，建檔時間長但查詢更穩） |
| 13 | Project / User 刪除的清除模式 | hard delete（與 v1.1 `chat_memory` 連動清除相同 pattern） |

---

## Phase 0：Migration

### 0-1 V44：建立 `project_memory` 表

- [x] `migrations/sql/V44__create_project_memory_table.sql`
  - `pid BIGSERIAL PRIMARY KEY`
  - `project_memory_uid UUID NOT NULL DEFAULT gen_random_uuid()`
  - `chat_project_uid UUID NOT NULL`（含 FK `REFERENCES chat_project (chat_project_uid)`，project 刪除可由 service 層 hard delete 連動）
  - `source_session_uids UUID[] NOT NULL`（**不**建立指向 chat_session 的 FK cascade，propose §3-3 硬規範）
  - `source_chat_message_uids UUID[] NOT NULL DEFAULT '{}'`（保留可追溯性，可空）
  - `keywords TEXT[] NOT NULL DEFAULT '{}'`
  - `entities TEXT[] NOT NULL DEFAULT '{}'`
  - `topic VARCHAR(200) NULL`
  - `embedding VECTOR(1536) NOT NULL`
  - `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  - `CREATE UNIQUE INDEX uq_project_memory_uid ON project_memory (project_memory_uid)`
  - `CREATE INDEX idx_project_memory_project_uid ON project_memory (chat_project_uid)`
  - `CREATE INDEX idx_project_memory_embedding_hnsw ON project_memory USING HNSW (embedding vector_cosine_ops)`
  - `COMMENT ON TABLE` / `COMMENT ON COLUMN` 全部欄位（中文）

### 0-2 V45：建立 `user_memory` 表

- [x] `migrations/sql/V45__create_user_memory_table.sql`
  - `pid BIGSERIAL PRIMARY KEY`
  - `user_memory_uid UUID NOT NULL DEFAULT gen_random_uuid()`
  - `owner_user_uid UUID NOT NULL`（含 FK `REFERENCES "user" (user_uid)`，user 停用 / 刪除可由 service 層 hard delete 連動）
  - `source_session_uids UUID[] NOT NULL`（**不**建立指向 chat_session 的 FK cascade）
  - `source_project_uids UUID[] NOT NULL DEFAULT '{}'`（追溯來源 project；project 刪除**不**連動）
  - `keywords TEXT[] NOT NULL DEFAULT '{}'`
  - `entities TEXT[] NOT NULL DEFAULT '{}'`
  - `topic VARCHAR(200) NULL`
  - `embedding VECTOR(1536) NOT NULL`
  - `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  - `CREATE UNIQUE INDEX uq_user_memory_uid ON user_memory (user_memory_uid)`
  - `CREATE INDEX idx_user_memory_owner_uid ON user_memory (owner_user_uid)`
  - `CREATE INDEX idx_user_memory_embedding_hnsw ON user_memory USING HNSW (embedding vector_cosine_ops)`
  - `COMMENT ON TABLE` / `COMMENT ON COLUMN` 全部欄位（中文）

### 0-3 V46：seed 三層 RAG / Aggregation 設定

- [x] `migrations/sql/V46__seed_three_layer_rag_settings.sql` 寫入 `system_setting`
  - `rag.session.top_k = 10`
  - `rag.session.min_score = 0.7`
  - `rag.project.top_k = 5`
  - `rag.project.min_score = 0.65`
  - `rag.user.top_k = 5`
  - `rag.user.min_score = 0.6`
  - `rag.fusion.k = 60`（RRF k 常數）
  - `rag.fusion.final_top_k = 8`（融合後塞 prompt 上限）
  - `memory.project.aggregate_idle_hours = 6`（idle 超過 N 小時觸發 project 二次聚合）
  - `memory.project.min_chat_memory_count = 5`（一個 project 累積 ≥ 5 筆 `chat_memory` 才聚合）
  - `memory.user.aggregate_idle_hours = 24`
  - `memory.user.min_session_count = 5`（同主題出現 ≥ N 筆才生 user_memory）
  - `memory.user.topic_concentration_pct = 60`（同主題占比 ≥ M%）
  - `memory.aggregation_extractor_model = anthropic/claude-haiku-4-5`
  - 全部含中文 description

---

## Phase 1：Backend — Models / Schemas

### 1-1 Models

- [x] `backend/app/models/project_memory.py`：`ProjectMemory(MemoryBase)`，欄位對齊 V44；複用 `chat_memory.py` 的 `MemoryBase`（無 `updated_at` / `is_deleted` / `is_active`）
- [x] `backend/app/models/user_memory.py`：`UserMemory(MemoryBase)`，欄位對齊 V45
- [x] `backend/app/models/__init__.py` export 兩個新 model（若該檔案有 export 慣例）

### 1-2 Schemas（`backend/app/schemas/memory/schemas.py` 新建或併入）

- [x] `ProjectMemoryItem`：`{ project_memory_uid, chat_project_uid, source_session_uids, keywords, entities, topic, created_at }`（不回 embedding）—（已改為 `backend/app/schemas/chat/three_layer_memory_schemas.py`，併入 chat schema 模組與既有 memory_schemas 一致）
- [x] `UserMemoryItem`：`{ user_memory_uid, owner_user_uid, source_session_uids, source_project_uids, keywords, entities, topic, created_at }`
- [x] `ThreeLayerRagResult`：`{ session: list[ChatMemoryItem], project: list[ProjectMemoryItem], user: list[UserMemoryItem], fused: list[FusedMemoryItem] }`（給 admin debug 用）
- [x] `FusedMemoryItem`：`{ scope: Literal["session","project","user"], memory_uid, topic, keywords, entities, rrf_score, source_rank }`

---

## Phase 2：Backend — Repositories（含 RRF 融合函式）

### 2-1 `project_memory_repository.py`

- [ ] `create(memory_data: dict, db) -> ProjectMemory`
- [ ] `list_by_project(chat_project_uid, db) -> list[ProjectMemory]`
- [ ] `search_similar(chat_project_uid, query_embedding, top_k, min_score, db) -> list[tuple[ProjectMemory, float]]`（沿用 `chat_memory_repository.search_similar` 形式 + scope filter）
- [ ] `hard_delete_by_project(chat_project_uid, db) -> int`（project 刪除連動清除）
- [ ] `count_by_project(chat_project_uid, db) -> int`（aggregation worker 用，判斷是否達聚合門檻）

### 2-2 `user_memory_repository.py`

- [ ] `create(memory_data: dict, db) -> UserMemory`
- [ ] `list_by_user(owner_user_uid, db) -> list[UserMemory]`
- [ ] `search_similar(owner_user_uid, query_embedding, top_k, min_score, db) -> list[tuple[UserMemory, float]]`
- [ ] `hard_delete_by_user(owner_user_uid, db) -> int`（user 停用 / 刪除連動清除）
- [ ] `count_by_user(owner_user_uid, db) -> int`

### 2-3 `chat_memory_repository.py` 擴充

- [ ] **不**改 `search_similar` 既有簽名（保持向後相容；rag_service 層改寫 retrieval pipeline）
- [ ] 新增 `list_by_project(chat_project_uid, db) -> list[ChatMemory]`：JOIN `chat_session` 取該 project 下所有 session 的 chat_memory（給 project_memory_worker 用）
- [ ] 新增 `list_by_user(owner_user_uid, db, since: datetime | None = None) -> list[ChatMemory]`：JOIN `chat_session` 取該 user 所有 session 的 chat_memory（給 user_memory_worker 用，含 idle 時間窗）
- [ ] 新增 `hard_delete_by_project(chat_project_uid, db) -> int`：刪除指定 project 下所有 session 的 chat_memory（project 刪除連動清除）
- [ ] 新增 `hard_delete_by_user(owner_user_uid, db) -> int`：刪除指定 user 全部 chat_memory（user 停用 / 刪除連動清除）

### 2-4 `rag_service` RRF 融合函式

- [ ] `backend/app/services/rag_service.py` 新增 `rrf_fuse(layers: dict[str, list[tuple[Any, float]]], k: int = 60, final_top_k: int = 8) -> list[FusedMemoryItem]`
  - input：`{"session": [(mem, score), ...], "project": [...], "user": [...]}`
  - 對每層內依分數排序得 rank（rank 從 1 起算）
  - 同一筆 memory 不會跨層出現（不同 scope 的 UID 不衝突），無需去重
  - `score = Σ 1/(k + rank)`（單筆只在自己那層算一次，等於 `1/(k + rank_in_layer)`）
  - 輸出依 `score` 降序，截 `final_top_k`
- [ ] 純算術，無 IO，可單測

### 2-5 `rag_service.retrieve_three_layer`（取代既有 `retrieve` 的呼叫點）

- [ ] 新增 `retrieve_three_layer(chat_session_uid, chat_project_uid, owner_user_uid, query_text, db) -> list[FusedMemoryItem]`
  - 讀 `rag.enabled`、各層 top_k / min_score、`rag.fusion.k` / `rag.fusion.final_top_k`
  - embedding 一次（query_text）
  - 並行三層 search：
    - session 層：`chat_memory_repository.search_similar(session_uid, ...)`
    - project 層：若 `chat_project_uid` 不為 None，`project_memory_repository.search_similar(project_uid, ...)`；否則跳過
    - user 層：`user_memory_repository.search_similar(owner_user_uid, ...)`
  - 任一層失敗 → log warning + 該層回空（其他層仍融合）
  - 呼叫 `rrf_fuse` 取 top N
- [ ] 既有 `retrieve(chat_session_uid, query_text, db)` 保留為 thin wrapper（給尚未升級的呼叫點），內部改呼叫 `retrieve_three_layer` 並只回 session 層；或標記 deprecation 待 §5 全面切換後刪除

---

## Phase 3：Backend — Project Memory Worker

> 設計依據：propose §3-1（從該 project 下所有 session 的 chat_memory 二次聚合，同主題合併）+ Arch §5（project 層生命週期跟隨 project 刪除）

### 3-1 Worker 主體

- [ ] `backend/app/workers/project_memory_worker.py`
  - 參考 `memory_worker.py` 結構（Redis queue + lifespan）
  - QUEUE_KEY = `project:memory:queue`、DLQ = `project:memory:dlq`
  - 主迴圈：
    - BRPOP 消費觸發訊號 `{ project_uid, owner_user_uid, trigger_at }`
    - 讀設定 `memory.project.aggregate_idle_hours` / `memory.project.min_chat_memory_count`
    - 撈該 project 下所有 session 的 `chat_memory`（`chat_memory_repository.list_by_project`），筆數低於 min 跳過
    - 依 `topic` 分群（同主題合併） → 每群輸入 `extract_memory`（**透過 v1.3.0 `llm_metering` wrapper**）做二次聚合
    - 聚合輸出產生 `embedding`
    - 寫入 `project_memory`（v0.1 先 insert，無 mem0 四向決策）
    - 同 transaction 寫入 `source_session_uids` = 該群涉及的 session_uid 集合
- [ ] 觸發來源：
  - 自動：`memory_worker` 寫完 `chat_memory` 後若該 project 距上次聚合 ≥ idle_hours，LPUSH 一筆觸發訊號
  - 手動：admin endpoint（§7）

### 3-2 LLM prompt（繁體中文硬規範）

- [ ] 在 `app/clients/openrouter/client.py` 或新檔 `prompts/memory_aggregation.py` 定義 `PROJECT_MEMORY_AGGREGATE_SYSTEM_PROMPT`
  - 明確指示「輸出一律使用**繁體中文**，禁止依輸入語言切換」（propose §2-1 硬規範）
  - 抽取目標：合併同主題的 keywords / entities / 重新生成 topic 摘要
  - response 格式對齊既有 `extract_memory` 的 pydantic schema
- [ ] worker 呼叫端點：`extract_memory(messages, model, system_prompt=PROJECT_MEMORY_AGGREGATE_SYSTEM_PROMPT)` — 須走 `llm_metering` wrapper（call_kind=`memory_aggregate_project`）

### 3-3 容錯與 DLQ

- [ ] MAX_RETRY = 3，重試之間 `sleep(1 + attempt)`
- [ ] 超過上限 → `project:memory:dlq`，log error
- [ ] 任一群聚合失敗不影響其他群（per-group try / except）

### 3-4 lifespan 整合

- [ ] `backend/app/main.py` lifespan 啟動 `project_memory_worker.run` 為 background task（與 `memory_worker` 並列）
- [ ] 健康檢查：`/health` endpoint 補回報 `project_memory_queue_depth` / `project_memory_dlq_depth`（沿用 v1.3.1 的 health 擴充慣例）

---

## Phase 4：Backend — User Memory Worker

> 設計依據：propose §3-1（跨 project 的長期偏好聚合）+ §5-2 升級 A（user_memory 用於 Skill 工廠 cross-session pattern）

### 4-1 Worker 主體

- [ ] `backend/app/workers/user_memory_worker.py`
  - QUEUE_KEY = `user:memory:queue`、DLQ = `user:memory:dlq`
  - 觸發訊號：`{ user_uid, trigger_at }`
  - 讀設定：`memory.user.aggregate_idle_hours` / `memory.user.min_session_count` / `memory.user.topic_concentration_pct`
  - 樣本來源：`chat_memory_repository.list_by_user(owner_user_uid, since=now - 30d)`（時間窗內全部 chat_memory）
  - 觸發條件（同時成立）：
    - 同主題 ≥ `min_session_count`（**N 預設 5**）
    - 同主題占比 ≥ `topic_concentration_pct`（**M 預設 60%**）
  - 達標主題群 → `extract_memory`（**走 metered wrapper**）做長期偏好抽取 → embedding → 寫 `user_memory`

### 4-2 LLM prompt（繁體中文硬規範）

- [ ] `USER_MEMORY_AGGREGATE_SYSTEM_PROMPT`：
  - 明確指示「輸出一律使用**繁體中文**」
  - 任務描述：從多 session 的對話片段抽取「使用者長期偏好」（語言、風格、領域、慣用工具等），不是事件性記憶
  - call_kind=`memory_aggregate_user`

### 4-3 觸發排程

- [ ] 自動：每日由 `memory_worker` 或新 scheduler tick 在達 `aggregate_idle_hours` 時 LPUSH 一筆訊號
- [ ] 手動：admin endpoint（§7）

### 4-4 容錯與 lifespan

- [ ] MAX_RETRY / DLQ / health 同 §3-3 / §3-4 模式
- [ ] `main.py` lifespan 啟動 `user_memory_worker.run`

---

## Phase 5：Backend — chat_service 整合三層 RAG

### 5-1 取記憶呼叫點切換

- [ ] 找 `chat_service` 內既有呼叫 `rag_service.retrieve(...)` 的位置（chat 串流回覆前的 RAG 注入）
- [ ] 改為呼叫 `rag_service.retrieve_three_layer(session_uid, project_uid, owner_user_uid, query_text, db)`
- [ ] `project_uid` 從 `chat_session.chat_project_uid` 取（nullable，None 時 project 層自動跳過）
- [ ] `owner_user_uid` 從 `chat_session.owner_user_uid` 取

### 5-2 Prompt 組裝

- [ ] 把 `FusedMemoryItem` list 拼成 system prompt 區段，每筆標 `[scope]` 標籤（session / project / user），方便 LLM 判斷時效
  - 範例：`[user 偏好] 使用者偏好繁體中文、學術風格回覆`
  - 範例：`[project 主題] 此專案討論 RAG 架構與 vector index 比較`
- [ ] 區段標題：「以下是相關的歷史記憶（依相關性排序）」

### 5-3 觀察性

- [ ] 寫入 v1.3.1 trace 結構（每次三層 retrieval 的 top_k / min_score / 命中數 / RRF 分布）— 由 v1.3.1 的 trace key 收

---

## Phase 6：Backend — 跨層生命週期連動

> 嚴格依 propose §3-3 / Arch §5-2 表格實作。三條刪除路徑各自獨立驗收。

### 6-1 Session 刪除路徑（既有，確認**不**連動 project / user）

- [ ] `chat_service.delete_session` 維持 v1.1 行為：呼叫 `chat_memory_repository.hard_delete_by_session`
- [ ] **明確**：**不**呼叫 `project_memory_repository` / `user_memory_repository` 的任何刪除函式
- [ ] 加註解：`# v1.3.5：不連動 project_memory / user_memory（propose §3-3 硬規範）`

### 6-2 Project 刪除路徑

- [ ] `chat_service.delete_project`（L336）擴充：
  - 取該 project 下所有 session 的 uid 列表
  - 同 transaction：
    1. `chat_memory_repository.hard_delete_by_project(project_uid, db)` — 清該 project 內所有 session 的 chat_memory
    2. `project_memory_repository.hard_delete_by_project(project_uid, db)` — 清 project_memory
    3. `chat_session_repository.soft_delete_by_project(project_uid, db)` — 軟刪 sessions（若既有路徑未做）
    4. `chat_project_repository.soft_delete(project, db)`
  - **不**呼叫 `user_memory_repository.hard_delete_by_user`（user_memory 不連動）
- [ ] 任一步失敗 → rollback 整個 transaction

### 6-3 User 停用 / 刪除路徑

- [ ] 找 `user_service.disable_user` / `delete_user`（若不存在則建立 admin 端點）
- [ ] 連動清除：
  1. `chat_memory_repository.hard_delete_by_user(owner_user_uid, db)`
  2. `project_memory_repository` 對該 user 所有 project 各自呼叫 `hard_delete_by_project`（先撈 project 列表）
  3. `user_memory_repository.hard_delete_by_user(owner_user_uid, db)`
- [ ] 同 transaction 完成

### 6-4 註解 / 文件

- [ ] 三個刪除路徑的 docstring 列出「連動 / 不連動」對照（複製 propose §3-3 表格）
- [ ] `docs/Design-Base/` 對應規範若有「跨層生命週期」段落，補連結到本版 task

---

## Phase 7：Backend — Admin / Manual Trigger Endpoint

### 7-1 手動觸發聚合

- [ ] `backend/app/api/v1/admin/memory_router.py`（或併入既有 admin router）：
  - `POST /admin/memory/aggregate/project/{chat_project_uid}` — 驗 admin role → LPUSH `project:memory:queue`
  - `POST /admin/memory/aggregate/user/{user_uid}` — 驗 admin role → LPUSH `user:memory:queue`
  - response：`{ "queued": true, "queue_depth": int }`

### 7-2 三層記憶讀取（給 admin debug 頁用）

- [ ] `GET /admin/memory/projects/{chat_project_uid}` — 列出 `project_memory` 全部（不含 embedding）
- [ ] `GET /admin/memory/users/{user_uid}` — 列出 `user_memory` 全部
- [ ] `GET /admin/debug/memory/retrieve?session_uid=&query=` — 回傳 `ThreeLayerRagResult`（含未融合三層 + 融合後）；給 propose §3-4 層 3「檢索診斷」用

### 7-3 Swagger

- [ ] 全部端點掛 `response_model` + `summary` + 中文 `description`
- [ ] `/api/docs` 顯示新 admin 端點

---

## Phase 8：驗收

### Migration

- [ ] V44 / V45 / V46 套用後表結構正確、HNSW index 建立成功
- [ ] V44 表 schema 不含指向 `chat_session` 的 FK（用 `\d project_memory` 驗證）
- [ ] V45 表 schema 不含指向 `chat_session` / `chat_project` 的 FK
- [ ] V46 seed 設定可由 `system_setting_service.get_int` / `get_float` 讀到

### Models / Repositories

- [ ] `ProjectMemory` / `UserMemory` 可正確 ORM 讀寫
- [ ] `project_memory_repository.search_similar` 對 1536 維 embedding 正確回排序結果
- [ ] `chat_memory_repository.list_by_project` / `list_by_user` 跨表 JOIN 正確
- [ ] 4 個 hard_delete_by_* 函式各自只清自己 scope 的資料（不誤刪其他層）

### RRF 融合

- [ ] `rrf_fuse` 單測：三層各 5 筆輸入 → 輸出長度 = `final_top_k`、score 降序、來自高 rank 的 item 排前面
- [ ] 邊界：某層為空 → 不報錯、其他層仍融合
- [ ] k=60 公式驗證：rank=1 → score = 1/61；rank=2 → score = 1/62

### Workers

- [ ] `project_memory_worker` 啟動後可消費 queue、寫入 `project_memory`
- [ ] `user_memory_worker` 啟動後對符合 N=5 / M=60% 的 user 寫入 `user_memory`
- [ ] 兩 worker 的 LLM 呼叫實際出現在 `llm_call_log` 表（v1.3.0 metered wrapper 計費生效）
- [ ] 兩 worker 的 system prompt 含「繁體中文」字樣（grep 驗證）
- [ ] DLQ 機制：人為注入錯誤訊號 → 重試 3 次後進 DLQ
- [ ] `/health` 顯示 4 個 queue 深度（chat / project / user 各自的 queue 與 DLQ）

### chat_service 三層 RAG 整合

- [ ] 對話訊息送出時三層 retrieval 都觸發，log 顯示 trace
- [ ] `chat_session.chat_project_uid` 為 None 時 project 層跳過、不報錯
- [ ] 三層任一失敗時其他層仍能融合（log warning，不中斷對話）
- [ ] Prompt 內可看到 `[session]` / `[project]` / `[user]` 標籤的記憶區段

### 跨層生命週期（**獨立驗收**，每路徑分別測）

- [ ] **Session 刪除**：刪除一個 session 後 `chat_memory` 該 session 部分歸零；該 project 的 `project_memory` 與該 user 的 `user_memory` **筆數不變**
- [ ] **Project 刪除**：刪除一個 project 後該 project 內所有 session 的 `chat_memory` 歸零、`project_memory` 該 project 部分歸零；其他 project 的 `project_memory` 與該 user 的 `user_memory` **筆數不變**
- [ ] **User 停用**：停用一個 user 後該 user 全部 `chat_memory` / 該 user 所有 project 的 `project_memory` / `user_memory` **皆歸零**
- [ ] DB schema 層驗證：直接從 `chat_session` 硬刪一筆 row（繞過 service）後，`project_memory.source_session_uids` 內仍保留該 session_uid（FK 不 cascade 確認）

### Admin 端點

- [ ] `POST /admin/memory/aggregate/project/{uid}` 觸發後 worker 在合理時間內處理
- [ ] `POST /admin/memory/aggregate/user/{uid}` 同上
- [ ] `GET /admin/debug/memory/retrieve?session_uid=&query=` 回傳完整三層 + 融合結果，可用於人工診斷
- [ ] Swagger `/api/docs` 顯示所有新 endpoint

### 整合

- [ ] Flyway V37 → V38（v1.3.0）→ V39–V42（v1.3.3）→ V43（v1.3.4）→ V44 → V45 → V46 順序套用無 out-of-order（前置 task 若部分未實作可跳過該段）
- [ ] `pytest backend/tests/` 全綠（`rrf_fuse` 純算術單測 + repository smoke）
- [ ] worker log 等級為 info（v1.3.1 規範），可從 log 讀到「project_memory_worker 寫入聚合 project=... groups=... cost=...」
