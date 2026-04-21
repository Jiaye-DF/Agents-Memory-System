# v1.1.2 任務規格：記憶系統 + RAG 檢索

> **狀態：已完成（commit 37aa3ba, 2026-04-21；embedding 依賴於 commit 0598bc0 改走 OpenRouter）**

## 版本目標

在 v1.1.1 的對話基礎上加入 Session 層記憶：非同步摘要 pipeline（rule-based 預篩 → 小模型抽關鍵字 → embedding）與 pgvector 檢索，並將檢索結果注入 system prompt（Agentic RAG）。

### 範圍內

- 新增 `chat_memory` 表（含 `vector(1536)` 欄位 + pgvector HNSW 索引）
- Redis queue 非同步 worker：消費記憶任務，產出 keywords / entities / topic / embedding
- OpenRouter 小模型摘要（`memory.extractor_model`，預設 `anthropic/claude-haiku-4-5`）
- OpenRouter `openai/text-embedding-3-small` embedding（1536 維）
- RAG 檢索 service：單 session scope，cosine similarity
- 在 v1.1.1 的 `chat_service.send_message` 注入 `<memory>` 區塊到 system prompt
- `rag.*` / `memory.*` 系統設定 seed + admin 設定 UI 支援

### 範圍外

- Project / User 層記憶跨層檢索（v1.2+）
- 記憶編輯 / 手動刪除單筆
- 記憶 TTL / retention（v1.2+，暫不設上限）
- Classifier 判斷「是否要送大 LLM」

---

## 前置現況

- v1.1.1 已完成 `chat_message` 表與對話 pipeline
- `migrations/sql/V1__...` 已啟用 pgvector 擴充（v1.0 既有）
- `system_setting` 表可用，admin 於 `/admin/settings` 可編輯
- embedding 與 LLM 對話統一走 `OPENROUTER_API_KEY`，不另設 key

---

## 已確認決策

| #   | 決策                | 結論                                                                           |
| --- | ------------------- | ------------------------------------------------------------------------------ |
| 1   | 記憶抽取 Model      | 預設 `anthropic/claude-haiku-4-5`；admin 可於 `system_setting` 改              |
| 2   | Embedding 方案    | OpenRouter `openai/text-embedding-3-small`（1536 維）；欄位鎖 `vector(1536)`    |
| 3   | 批次 Trigger        | OR 條件：每 5 則 OR idle 60 秒                                                  |
| 4   | 預篩規則可配置      | `memory.skip_rules` 存 JSON 於 `system_setting`，admin 可調                     |
| 5   | RAG scope（v1.1）   | 僅 session（檢索該 session 自己的 `chat_memory`）                                |
| 6   | Worker 部署方式      | FastAPI lifespan 啟動 asyncio task，共用同一 container（簡化部署，v1.1 足夠）    |
| 7   | 失敗重試            | Embedding 失敗最多 3 次，超過存 `memory.dlq` Redis list 供排查                  |
| 8   | 記憶隱私            | admin 不可讀 `chat_memory`（同訊息，僅擁有者）                                  |

---

## Phase 1：後端

### 1-1 Migration

- [x] **V22**：`create_chat_memory_table.sql`
  - `pid bigserial PK`
  - `chat_memory_uid uuid default gen_random_uuid() UNIQUE`
  - `chat_session_uid uuid NOT NULL REFERENCES chat_session(chat_session_uid)`
  - `source_chat_message_uids uuid[] NOT NULL`
  - `keywords text[] NOT NULL DEFAULT '{}'`
  - `entities text[] NOT NULL DEFAULT '{}'`
  - `topic varchar(200) NULL`
  - `embedding vector(1536) NOT NULL`
  - `created_at timestamptz default now()`
  - Index：
    - `idx_chat_memory_session_uid` (`chat_session_uid`)
    - `idx_chat_memory_embedding_hnsw` USING HNSW (`embedding vector_cosine_ops`)
  - 無 `is_deleted`（Session 軟刪時一起刪；v1.1 不支援獨立刪單筆）

- [x] **V23**：`seed_memory_rag_system_settings.sql`
  - `memory.extractor_model` = `"anthropic/claude-haiku-4-5"`
  - `memory.batch_size` = `5`
  - `memory.idle_seconds` = `60`
  - `memory.skip_rules` = JSON：
    ```json
    {
      "min_length": 15,
      "greeting_whitelist": ["hi", "hello", "好", "好的", "收到", "謝謝", "ok"],
      "max_tokens": 2000
    }
    ```
  - `rag.enabled` = `true`
  - `rag.top_k` = `5`
  - `rag.min_score` = `0.7`

### 1-2 Model

- [x] `app/models/chat_memory.py`：`ChatMemory`
  - 使用自訂 base（無 `updated_at` / `is_deleted`）
  - `embedding` 欄位用 `pgvector.sqlalchemy.Vector(1536)`
  - 可選：`relationship("ChatSession")`

### 1-3 依賴

於 `pyproject.toml` 加入：
- [x] `pgvector>=0.3.0`（SQLAlchemy 整合）
- [x] `openai>=1.50.0`（僅用 embedding client，非 chat）—（已改為 httpx 直呼 OpenRouter `/embeddings`，不再引入 openai SDK，見 commit 0598bc0）
- [x] `redis>=5.0.0`（v1.0 既有可重用）

### 1-4 Schema（`app/schemas/chat/memory_schemas.py`）

- [x] `ChatMemoryResponse`：完整欄位（不含 embedding，太大）
- [x] `MemoryExtractResult`（Pydantic，用於 small LLM 的 JSON output）：
  ```python
  class MemoryExtractResult(BaseModel):
      keywords: list[str]
      entities: list[str]
      topic: str
      is_actionable: bool
  ```

### 1-5 Repository（`chat_memory_repository.py`）

- [x] `create(data, db)`：flush + refresh
- [x] `list_by_session(session_uid, db)`
- [x] `soft_delete_by_session(session_uid, db)`：`DELETE FROM chat_memory WHERE chat_session_uid = ?`（無 is_deleted，直接 hard delete 該 session 的記憶，對應 session 軟刪時呼叫）
- [x] `search_similar(session_uid, query_embedding, top_k, min_score, db)`：
  ```sql
  SELECT *, 1 - (embedding <=> :query) AS score
  FROM chat_memory
  WHERE chat_session_uid = :session_uid
    AND 1 - (embedding <=> :query) >= :min_score
  ORDER BY embedding <=> :query
  LIMIT :top_k
  ```

### 1-6 Client

- [x] `app/clients/openrouter/client.py` 擴充 `async def embed(text: str) -> list[float]`：
  - 呼叫 `https://openrouter.ai/api/v1/embeddings`
  - 使用 `OPENROUTER_API_KEY` + `HTTP-Referer` + `X-Title` headers
  - `model="openai/text-embedding-3-small"`，回傳 1536 維向量

- [x] `app/clients/openrouter/client.py` 擴充 `async def extract_memory(messages: list[dict], model: str) -> MemoryExtractResult`
  - 使用 `response_format={"type": "json_schema", "json_schema": {...}}`
  - prompt：「請從以下對話中抽取關鍵資訊，回覆固定 JSON 結構」

### 1-7 Rule-based 預篩（`app/services/memory_prefilter.py`）

- [x] `async def should_skip(message: ChatMessage, rules: dict) -> bool`
  - 長度檢查（`len(content) < rules["min_length"]`）
  - 白名單比對（小寫 trim 後在 `greeting_whitelist` 內）
  - 純 emoji（regex）
  - `role == "tool"` 且 `is_error`（v1.1 無 is_error 欄位，僅依 role 略過 tool）

- [x] `async def truncate_for_extraction(content: str, max_tokens: int) -> str`
  - 使用簡單 token 估算（4 字元 ≈ 1 token），超過則頭尾保留中間截斷

### 1-8 Memory Worker（`app/workers/memory_worker.py`）

- [x] Redis 佇列 key：`chat:memory:queue`，每筆為 JSON `{"session_uid": "...", "message_uid": "..."}`
- [x] DLQ key：`chat:memory:dlq`
- [x] 主迴圈 `async def run()`：
  ```
  while True:
    items = BRPOP chat:memory:queue (timeout 5)
    for each item:
      batch_buffer[session_uid].append(message_uid)
      if len(batch_buffer[session_uid]) >= batch_size OR idle > idle_seconds:
        await _process_batch(session_uid, message_uids)
        clear buffer
  ```
- [x] `_process_batch(session_uid, message_uids, db)`：
  1. 讀取原文 messages
  2. Rule-based 預篩 → 全被 skip 則略過
  3. 合併內容，呼叫 `extract_memory`
  4. 關鍵字串接（`"，".join(keywords + entities + [topic])`）→ `embed`
  5. `chat_memory_repository.create`
  6. 失敗 → 重試至 3 次 → DLQ

- [x] 於 `main.py` lifespan：
  ```python
  @asynccontextmanager
  async def lifespan(app):
      task = asyncio.create_task(memory_worker.run())
      yield
      task.cancel()
  ```

### 1-9 Enqueue 整合

- [x] `chat_service.send_message` 寫完 assistant message 後：
  ```python
  await redis.lpush("chat:memory:queue", json.dumps({
      "session_uid": session_uid,
      "message_uid": assistant_msg.chat_message_uid
  }))
  ```

### 1-10 RAG Service（`app/services/rag_service.py`）

- [x] `async def retrieve(session_uid, query_text, db) -> list[ChatMemory]`
  1. 讀取 `rag.enabled`；false 直接回空
  2. `embed(query_text)`
  3. `chat_memory_repository.search_similar(session_uid, embedding, top_k, min_score)`
  4. 失敗（網路 / embedding 500）→ log + 回空（不中斷對話）

### 1-11 Prompt 注入

修改 `chat_service._build_system_prompt`：

- [x] 新增參數 `memories: list[ChatMemory]`
- [x] 若非空則在 Skills 區塊後附加：
  ```
  ## 相關記憶
  <memory>
  [{topic}] {keywords.join(", ")}
  ...
  </memory>
  ```
- [x] **不貼原始訊息內容**（隱私 + token 節流）

修改 `send_message`：
- [x] 取得 user 訊息後 → 呼叫 `rag_service.retrieve(session_uid, user_content)` → 取得 `memories` → 傳入 `_build_system_prompt`

### 1-12 Session 軟刪連動

- [x] `chat_service.delete_session` 內呼叫 `chat_memory_repository.soft_delete_by_session`（實作為 hard delete，v1.1 無需保留記憶）

### 1-13 Router 補充

- [x] `GET /api/v1/chat/sessions/{uid}/memories`：列出 session 記憶（Admin 不可，僅擁有者；供 debug / 使用者查看用）
- [x] 訊息內容隱私：僅回 `keywords` / `entities` / `topic` / `created_at`，不回 embedding

---

## Phase 2：前端

### 2-1 型別 & RTK Query

- [x] `types/chat.ts` 新增 `ChatMemory`（不含 embedding）
- [x] `store/chatApi.ts` 新增 `useListSessionMemoriesQuery({ sessionUid })`

### 2-2 UI

- [x] `/sessions/[uid]/page.tsx` 右側抽屜（可收合）新增「記憶」分頁
  - 顯示該 session 的 `chat_memory` 清單：topic + keywords chips
  - 無記憶時顯示提示「對話持續一段時間後會自動建立記憶」
  - 不提供刪除按鈕（v1.1 不支援）

### 2-3 設定頁

- [x] `/admin/settings` 頁已存在；確認新 seed 的 7 個 key 會自動載入顯示
  - 若當前 UI 不支援 JSON 欄位編輯，`memory.skip_rules` 以 textarea 呈現 + 前端 `JSON.parse` 驗證

---

## Phase 3：驗收

- [x] V22 migration 後 `chat_memory` 表存在、HNSW 索引建立成功
- [x] V23 seed 後 `/admin/settings` 可看到 `memory.*` 與 `rag.*` 共 7 組設定
- [x] 對話超過 5 則後（或 idle 60s）`chat_memory` 表有新記錄
- [x] 新建 session 第一輪對話：無記憶，RAG 區塊為空、不出錯
- [x] 第二輪對話：若 RAG 檢索到相關記憶，`system prompt` 含 `<memory>` 區塊（可 log 檢查）
- [x] 純問候訊息（如 "hi"）**不會**產生 memory record
- [x] 超長訊息（> 2000 token）被截斷後仍能處理
- [x] 關閉 `rag.enabled` 後，對話正常但不注入記憶
- [x] Embedding API 斷線時，對話不中斷（log 警告、memory worker 重入 queue）
- [x] Session 軟刪除後，該 session 的 `chat_memory` 被清除
- [x] Admin 無法讀 `GET /chat/sessions/{uid}/memories`（403）
- [x] `.env.example` 的 `OPENROUTER_API_KEY` 同時供 LLM 對話與 embedding 使用，不另增 key
