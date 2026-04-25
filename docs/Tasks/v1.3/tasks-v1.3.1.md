# v1.3.1 任務規格：記憶 pipeline 可觀察性層 1 + Skill 多 md 拼接 + AgentForm max_tokens hint

> **狀態：進行中（程式碼完成：commit c5ec5f7, 2026-04-25；runtime smoke / 測試驗證待完成）**

> 前置：[propose-v1.3.0.md §3-4 / §5-1 / §4-3](propose-v1.3.0.md)、[tasks-v1.3.0.md](tasks-v1.3.0.md)（共用 admin endpoint 規範）
> 後續依賴：v1.3.2 依賴本版的 worker log 基礎

## 版本目標

針對「記憶 pipeline 可觀察性層 1」（§3-4）+ 兩個小型補完（§5-1、§4-3）做最低成本落地，不動資料庫 schema：

- `memory_worker.py` 各階段升級為 info 級別結構化 log，欄位涵蓋 `session_uid` / `message_uids` / `step` / `duration_ms` / `outcome`
- 新增 admin endpoint `GET /api/v1/admin/debug/memory/sessions/{uid}`，回傳該 session 全程 trace（時間軸 + 各階段成功 / 失敗 / 耗時）
- 既有 `/health` endpoint 擴充 Redis queue（`chat:memory:queue`） / DLQ（`chat:memory:dlq`）長度欄位
- `chat_service._skill_prompt_text` 改為「讀 zip 內所有 .md，按檔名排序拼接」，並在單個 md 超過 `skill.md_max_chars`（預設 8000 字）時 log warning
- `AgentForm` 的 `max_tokens` 欄位旁加說明 hint：「1024 ≈ 750 中文字；長分析 / code review 建議 4096+ 或留空」

### 範圍內

- Backend：memory_worker log 改寫、admin trace endpoint、health 擴充、skill 多 md 拼接 service 層
- Frontend：AgentForm 在既有 `max_tokens` 欄位下方插入單行 hint 文字
- Design：admin trace endpoint 採 in-memory ring buffer + Redis stream 雙通道（不新增 DB 表）

### 範圍外

- 層 0 metrics（→ v1.3.0）
- 層 2 評估（→ 後續，含 `backend/app/evals/memory/` 與 LLM-as-judge CLI）
- 層 3 檢索診斷（→ 後續，含 `chat_memory_hit` Redis stream 與 admin retrieve test 頁面）
- SSE 即時推播（→ v1.3.2 §3-5）
- Skill 工廠正式版（→ v1.3.6 §5-2）
- Skill 規範類命名強制（本版僅於 README / docstring 建議）

---

## 前置現況

- v1.1 已落地：memory_worker 走 Redis BRPOP（`chat:memory:queue`） + DLQ（`chat:memory:dlq`）+ 三段重試（見 [memory_worker.py L25-298](../../../backend/app/workers/memory_worker.py#L25-L298)）
- 既有 log：多為 `logger.warning` / `logger.exception`，**缺 info 級成功事件**、**缺結構化欄位**、**缺單階段耗時**
- `_skill_prompt_text`（[chat_service.py L176-208](../../../backend/app/services/chat_service.py#L176-L208)）目前只挑單一 md：優先 README.md → `{skill_name}.md` → 第一個 .md
- `/health`（[health.py](../../../backend/app/api/v1/health.py)）目前回 `{database, redis}` 連線狀態，**不含 queue 長度**
- `AgentForm`（[AgentForm.tsx L962-1004](../../../frontend/src/app/(main)/agents/_components/AgentForm.tsx#L962-L1004)）目前僅顯示 `exceedsModelLimit` 警告，**未提供使用者選擇 token 數的直觀建議**
- v1.3.0 已建立 admin endpoint 規範（路徑前綴 `/api/v1/admin`、`require_role("admin")`、ApiResponse 回包），本版沿用

---

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | trace 儲存層 | Redis stream `memory:trace:{session_uid}`（XADD + MAXLEN ~ 200），TTL 7 天；不新增 DB 表 |
| 2 | trace 寫入時機 | worker 每階段（prefilter / buffer_flush / extract / embedding / write / dlq）開始與結束各 XADD 一筆 |
| 3 | trace endpoint 行為 | 讀取 Redis stream 全部訊息 → 依時間排序 → 標準化為 JSON timeline；找不到回 200 + `items: []` |
| 4 | log 結構化策略 | 沿用標準 `logging`，extra 帶 dict（`session_uid` / `message_uids` / `step` / `duration_ms` / `outcome`）；不引入 structlog 等新套件 |
| 5 | log 級別 | 成功事件 info、可重試失敗 warning、最終失敗 / 例外 exception；DEBUG 僅供本機開發切 |
| 6 | health queue / DLQ 長度策略 | `LLEN chat:memory:queue` 與 `LLEN chat:memory:dlq`；Redis 連線異常時欄位為 `null`，整體 503 由既有邏輯判定 |
| 7 | skill md 拼接順序 | 全部 `.md`（含子目錄）按 `info.filename` 字典序排序；每份前加 `### {filename}` 標題 |
| 8 | skill md 字數上限 | 設定 key `skill.md_max_chars`，預設 8000；超過僅 log warning，不截斷 |
| 9 | skill md 個數上限 | 不設硬上限（拼接後若過長交由 LLM 端截斷處理；warning 已能讓 admin 察覺） |
| 10 | AgentForm hint 位置 | 於 `errors.max_tokens` 與 `exceedsModelLimit` 訊息之上、`<input>` 之下單行顯示，常駐不條件渲染 |

---

## Phase 1：Backend - Memory Worker Log 升級

### 1-1 共用結構化 log helper

- [x] `backend/app/workers/memory_worker.py` 頂部新增 `_log_event(step, session_uid, *, message_uids=None, outcome="ok", duration_ms=None, **extra)` 內部 helper
  - 將 `step` / `session_uid` / `message_uids` / `outcome` / `duration_ms` 加到 `extra` dict 後呼叫 `logger.info(...)`（warning / exception 走專屬 helper 或直接帶 `extra`）
  - 訊息格式：`"memory_worker step=%s session=%s outcome=%s duration_ms=%s"`，避免 logging f-string
- [x] log message 一律使用既有 `logger`（`logging.getLogger(__name__)`），不新增 logger 實例

### 1-2 主迴圈 log

- [x] 啟動 log 由 `logger.info("memory_worker 啟動")` 改帶 `extra={"step": "boot"}`
- [x] BRPOP 取到 item 後新增 info：`step=enqueue`，欄位含 `session_uid` / `message_uid`
- [x] BRPOP 解析失敗保留 warning，`extra={"step": "enqueue", "outcome": "parse_error"}`

### 1-3 Buffer / Batch flush log

- [x] 進入 `_process_batch` 前加 info：`step=buffer_flush`、欄位含 `session_uid` / `message_uids` / `reason`（`full` 或 `idle`）
- [x] `_process_batch` 失敗的 `logger.exception` 改帶 `extra={"step": "buffer_flush", "outcome": "exception"}`

### 1-4 Prefilter 階段 log

- [x] `_process_batch` 內 `kept` 計算前後加 info：`step=prefilter`，欄位 `total` / `kept` / `skipped`
- [x] 「全數被預篩掉」訊息升 info（從 debug），`extra={"step": "prefilter", "outcome": "all_skipped"}`

### 1-5 Extract / Embedding / Write 階段 log

- [x] 每次重試 attempt 前後分別記錄 `step=extract` 與 `step=embedding`，欄位含 `attempt`、`duration_ms`、`outcome`
- [x] `chat_memory_repository.create` 完成後既有 info 訊息保留，`extra={"step": "write", "outcome": "ok", "src_count": len(kept)}`
- [x] 重試失敗的 warning 統一帶 `extra={"step": "extract" 或 "embedding", "attempt": i+1, "outcome": "retry"}`

### 1-6 DLQ 階段 log

- [x] 推入 DLQ 成功 log 由既有 error 改為 `logger.error(... extra={"step": "dlq", "outcome": "pushed"})`
- [x] 推入 DLQ 失敗保留 exception，`extra={"step": "dlq", "outcome": "push_failed"}`

### 1-7 Image describe 階段 log

- [x] `_describe_image_attachments` 內單張失敗 warning 帶 `extra={"step": "image_describe", "attachment_uid": ...}`
- [x] 單張成功不額外 log（避免噪音），整體完成在呼叫端帶 `step=image_describe`、`outcome=ok`、`count=描述張數`（單則訊息一筆）

---

## Phase 2：Backend - Admin Trace Endpoint

### 2-1 Trace 寫入封裝

- [x] 新增 `backend/app/services/memory_trace_service.py`：
  - `TRACE_KEY = "memory:trace:{session_uid}"`
  - `TRACE_MAX_LEN = 200`
  - `TRACE_TTL_SECONDS = 7 * 86400`
  - `record(session_uid, step, *, outcome="ok", duration_ms=None, message_uids=None, extra=None)`：
    - 透過 `get_redis()` 對 `memory:trace:{uid}` 做 `XADD MAXLEN ~ 200`
    - payload 欄位：`step` / `outcome` / `duration_ms` / `message_uids`（JSON 字串）/ `ts`（unix ms）/ `extra`（JSON 字串）
    - `EXPIRE` TTL 7 天（每次 XADD 後重設）
    - Redis 連線失敗 → log warning 後吞例外，**不影響 worker 主流程**
  - `read(session_uid, limit=200)`：`XRANGE - +` 後解析回 list[dict]
- [x] `memory_worker.py` 各 log point 同步呼叫 `memory_trace_service.record(...)`（與 §1-2~1-7 同欄位、同 step）

### 2-2 Admin Trace Endpoint

- [x] 於既有 admin router（[backend/app/api/v1/admin/router.py](../../../backend/app/api/v1/admin/router.py)）新增 endpoint：
  - 路徑：`GET /api/v1/admin/debug/memory/sessions/{session_uid}`
  - 依賴：`require_role("admin")`
  - Query：`limit: int = Query(200, ge=1, le=500)`
  - Service：呼叫 `memory_trace_service.read(session_uid, limit)`
- [x] 回傳 schema（新增於 `app/schemas/admin/schemas.py` 或新檔 `app/schemas/admin/memory_debug.py`）：
  - `MemoryTraceItem`：`{ ts: str(ISO UTC+8), step: str, outcome: str, duration_ms: int|null, message_uids: list[str]|null, extra: dict|null }`
  - `MemoryTraceData`：`{ session_uid: str, count: int, items: list[MemoryTraceItem] }`
  - 回包走 `ApiResponse[MemoryTraceData]`
- [x] Trace 取出後 `ts` 統一以 `to_taipei_iso` 轉為 `Asia/Taipei`（依 CLAUDE.md 時區規範）
- [x] Swagger `/api/docs` 顯示該端點及 Schema、`summary` 寫「查詢 session 的記憶 pipeline trace」

### 2-3 Service 層

- [x] `app/services/admin_service.py`（或同檔內補函式）新增 `get_memory_trace(session_uid, limit, db)`，包裝 `memory_trace_service.read` 並補 schema 轉型 —（已改為 `get_memory_trace(session_uid, limit)`，trace 純走 Redis 不需 db session，未保留 db 參數）
- [x] 找不到 trace 時不報 404，回 `MemoryTraceData(session_uid, count=0, items=[])`，避免 admin 端 UI 處理 404

---

## Phase 3：Backend - Health 擴充

### 3-1 Schema 擴充

- [x] `app/schemas/response.HealthData` 新增可選欄位：
  - `memory_queue_len: int | None`
  - `memory_dlq_len: int | None`
  - 若 Redis 不通則為 `null`，避免 schema 違例
- [x] 確認 `HealthData` 既有欄位與型別不破壞 v1.1 / v1.2 既有呼叫者

### 3-2 Health endpoint 行為

- [x] `backend/app/api/v1/health.py`：
  - 在既有 `redis.ping()` 區塊後增加 `LLEN chat:memory:queue` 與 `LLEN chat:memory:dlq`
  - 任一 LLEN 失敗則該欄位回 `null`，**不影響整體 503 判斷**（仍以 db_ok / redis_ok 為準）
  - 將 `memory_queue_len` / `memory_dlq_len` 併入 status dict 回包
- [x] Constants 統一：`memory_worker.py` 既有 `QUEUE_KEY` / `DLQ_KEY` 抽到 `app/core/redis.py` 或新檔 `app/core/queue_keys.py`，`health.py` 直接 import，避免字串 hardcode 散落 —（已新增 `app/core/queue_keys.py`，worker 既有 `QUEUE_KEY` / `DLQ_KEY` 改為 import 後 alias 以維持原引用）

---

## Phase 4：Backend - Skill 多 md 拼接

### 4-1 Setting key

- [x] `backend/app/services/system_setting_service.py` 既有設定機制下新增預設常數 `DEFAULT_SKILL_MD_MAX_CHARS = 8000`（於 `chat_service.py` 或新建 `skill_constants.py` 集中常數，與既有 memory 常數風格一致） —（已置於 `chat_service.py` 與既有 `DEFAULT_MAX_AGENTS_PER_SESSION` 同列；setting key `skill.md_max_chars`）
- [x] admin 設定畫面**本版不新增 UI**（沿用 system_setting_service 預設值機制，未來 admin 設定頁有需要再補）

### 4-2 `_skill_prompt_text` 改寫

- [x] `backend/app/services/chat_service.py`：
  - 改 `_skill_prompt_text(skill: Skill)` 為 `async def _skill_prompt_text(skill: Skill, db: AsyncSession)`（需讀設定）
  - 流程：
    1. header 維持 `### {name}\n{description}\n`
    2. 列出 zip 內所有 `*.md`（含子目錄、忽略目錄項）
    3. 依 `info.filename` 字典序排序
    4. 逐份讀取 → 若單份 `len(content) > md_max_chars` 則 `logger.warning("skill md 過長 skill_uid=%s file=%s len=%d", ...)`
    5. 拼接：每份前加 `### {filename}`（取相對路徑去前綴後的純檔名 + 子目錄相對路徑）+ 換行 + 內容 + 兩個換行分隔
  - 例外處理保留：zip 開不起來 / 讀失敗 → log warning + 回 header
- [x] 呼叫端改為 `await _skill_prompt_text(skill, db)`（影響範圍以 IDE 全找替換為準，預期不超過 3 處） —（實際只有 `_build_system_prompt` 一處呼叫；已改）

### 4-3 README / Docstring 命名建議

- [x] 於 `_skill_prompt_text` docstring 補命名建議，例：
  > 建議 Design-Base 規範類 Skill 採 `design-base-frontend` / `design-base-backend` / `design-base-auth` 命名（無強制）
- [x] 若有 `backend/README.md` 或 `docs/Design-Base/skills.md` 之類的位置，於同段落補一句「v1.3 起 Skill zip 支援多 .md 拼接」（找不到合適位置可省略，避免新增孤立檔案） —（找不到合適位置，省略以免新增孤立檔案）

---

## Phase 5：Frontend - AgentForm UI Hint

### 5-1 Hint 文字插入

- [x] `frontend/src/app/(main)/agents/_components/AgentForm.tsx`：
  - 於 `<input id="max_tokens" ... />` 之後、`errors.max_tokens` 訊息**之前**插入：
    ```tsx
    <p className="mt-1 text-base text-muted">
      1024 ≈ 750 中文字；長分析 / code review 建議 4096+ 或留空。
    </p>
    ```
  - 文字色採既有 `text-muted` 設計變數（與其他輔助文字一致）
  - 字級沿用既有 `text-base`（與 errors 同字級，視覺一致） —（已由 v1.3.3 commit 449e54e 順手完成；實作字級為 `text-sm` 而非 `text-base`，屬視覺偏好調整，文字色與位置皆合規）
- [x] hint 為**常駐**，不依 `errors` / `exceedsModelLimit` 條件渲染 —（已由 v1.3.3 commit 449e54e 順手完成）

### 5-2 既有警告共存

- [x] 確認 `errors.max_tokens` 與 `exceedsModelLimit` 訊息仍依條件渲染於 hint 之下，三段顯示順序：
  1. hint（常駐）
  2. `errors.max_tokens`（驗證錯誤時）
  3. `exceedsModelLimit`（超過模型上限時）
  —（已由 v1.3.3 commit 449e54e 順手完成；AgentForm.tsx L993-1006 三段順序符合）

### 5-3 i18n / 文案來源

- [x] hint 文字直接寫死於元件（既有 AgentForm 全頁皆 hardcode 中文，未引入 i18n） —（已由 v1.3.3 commit 449e54e 順手完成）
- [x] 不新增翻譯檔，遵循專案既有單語繁中策略 —（已由 v1.3.3 commit 449e54e 順手完成）

---

## Phase 6：驗收

> Runtime 行為驗收統一彙整於 [runtime-acceptance.md](runtime-acceptance.md)。
> 本檔案 Phase 0 ~ 5 的程式碼層 checkbox 即為實作交付清單；smoke / curl / 瀏覽器互動類驗證請見 acceptance 檔案對應章節。

