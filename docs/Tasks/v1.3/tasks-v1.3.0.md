# v1.3.0 任務規格：基礎設施 — 成本 metrics（`llm_call_log` + 集中 wrapper）

> 前置：[propose-v1.3.0.md §3-4](propose-v1.3.0.md)、[docs/Arch/01-observability-and-metrics.md](../../Arch/01-observability-and-metrics.md)
> 後續依賴：v1.3.1 / v1.3.4 / v1.3.5 / v1.3.6 皆需此版完成才能驗證成本影響

## 版本目標

建立 LLM 呼叫成本 / 延遲 / 失敗率的單一進入點觀測機制，作為 v1.3 後續 task 的成本驗證底座：

- 新表 `llm_call_log`（30 天保留、無業務 FK cascade，詳見 [docs/Arch/01-observability-and-metrics.md §5-1](../../Arch/01-observability-and-metrics.md)）
- 新 service `llm_metering.call_llm_metered` 作為唯一允許呼叫 OpenRouter / embedding 的進入點（詳見 [§5-2](../../Arch/01-observability-and-metrics.md)）
- 既有所有 LLM 呼叫遷移到 metered wrapper：`chat_service.stream_chat_completion`、`memory_worker.extract_memory` / `embed` / `describe_image`、`skill_factory_service.generate_skill_suggestion`
- `skip` 路線寫入 baseline log（counterfactual 估算，詳見 [§5-3](../../Arch/01-observability-and-metrics.md)）
- 模型價格表 `backend/app/config/model_prices.yaml`（詳見 [§5-4](../../Arch/01-observability-and-metrics.md)）
- Admin endpoint `GET /api/v1/admin/metrics/cost`（詳見 [§5-5](../../Arch/01-observability-and-metrics.md)）
- 7 個 admin SQL 範本作為 reference（詳見 [§6](../../Arch/01-observability-and-metrics.md)）

### 範圍內

- DB Migration：V38 建立 `llm_call_log` 表 + 索引
- 後端：`llm_metering` service、`llm_call_log_repository`、`model_prices.yaml` + loader、cost 計算工具
- 既有 LLM 呼叫端遷移到 metered wrapper
- `skip` 路線 baseline 估算（雖然 v1.3.0 還沒 classifier，但機制先建好供 v1.3.4 直接套用）
- Admin endpoint：`GET /api/v1/admin/metrics/cost?range=&group_by=`
- 7 個 admin SQL 範本以 markdown reference 區塊保留於 task 檔尾

### 範圍外

- Admin UI 視覺化（指向 [docs/Arch/01-observability-and-metrics.md §7 階段 2](../../Arch/01-observability-and-metrics.md)）
- Cache 命中率告警 / Slack 通知（指向 §7 階段 1）
- 月表聚合 cron + 明細刪除（指向 §7 階段 3）
- Prometheus / Grafana / OpenTelemetry（指向 §7 階段 5、6）
- Citation 機制與 cited vs retrieved 比率（指向 §7 階段 4）
- 評估資料集 / LLM-as-judge（屬 propose §3-4 層 2，由 v1.3.1+ 承接）

---

## 前置現況

- 既有 LLM 呼叫者（無 metering）：
  - [`backend/app/services/chat_service.py`](../../../backend/app/services/chat_service.py) 內 `stream_chat_completion`（chat 主對話 SSE 串流）
  - [`backend/app/workers/memory_worker.py`](../../../backend/app/workers/memory_worker.py) 內 `extract_memory` / `embed` / `describe_image`
  - [`backend/app/services/skill_factory_service.py`](../../../backend/app/services/skill_factory_service.py) 內 `generate_skill_suggestion`
- 既有 OpenRouter wrapper：[`backend/app/clients/openrouter/client.py`](../../../backend/app/clients/openrouter/client.py)（內含 chat / embed / extract_memory / describe_image / generate_skill_suggestion）
- 既有 admin router：[`backend/app/api/v1/admin/router.py`](../../../backend/app/api/v1/admin/router.py)（已具 `require_role("admin")` pattern）
- 既有 migration 最大版本 = V37（`migrations/sql/V37__add_script_visibility.sql`），本 task 起算 **V38**
- 既有 repositories `__init__.py` 無 barrel export，repository 模組為各檔直接 import
- 既有 `backend/app/config/` 目錄**不存在**，本 task 需新建

---

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | 寫入策略 | 同步寫 PostgreSQL；流量 < 100k 筆 / 天無需 Redis stream 緩衝（詳見 [§8-1](../../Arch/01-observability-and-metrics.md)） |
| 2 | `chat_message_uid` 欄位 | **不加**（一次 user message 可能對應多次 LLM 呼叫，硬綁反而難查，詳見 [§5-1 設計決策](../../Arch/01-observability-and-metrics.md)） |
| 3 | `actual_cost_usd` / `baseline_cost_usd` 精度 | `NUMERIC(10, 6)`（對應到 $0.000001） |
| 4 | FK cascade | **不建** — `session_uid` / `user_uid` / `agent_uid` 為 UUID 但不綁外鍵（詳見 [§2-4](../../Arch/01-observability-and-metrics.md)） |
| 5 | `EXPENSIVE_MODEL_ID` baseline 用模型 | `anthropic/claude-sonnet-4-6`（與既有 chat 預設模型對齊，未來 classifier 開啟時這就是「沒 classifier 會用的模型」） |
| 6 | `skip` baseline 估算法 | `len(user_input) / 4` 估 input tokens、output 估 200 tokens、套 EXPENSIVE_MODEL_ID 單價（詳見 [§5-3](../../Arch/01-observability-and-metrics.md)） |
| 7 | 集中進入點 lint 規則 | code review 必檢；不引入 import-linter 等工具，靠規範與 PR review 把關（詳見 [§2-3](../../Arch/01-observability-and-metrics.md)） |
| 8 | `error` 欄位敏感資訊 | 截斷至 500 字元、不存 prompt / response 原文（詳見 [§8-2](../../Arch/01-observability-and-metrics.md)） |
| 9 | 價格表更新方式 | 手動維護 `model_prices.yaml`，每次調整加 `# updated: YYYY-MM-DD` 註解；歷史 log 不重算（詳見 [§8-3](../../Arch/01-observability-and-metrics.md)） |
| 10 | 保留期限 | 30 天明細；月表聚合本版**不做**（詳見 [§8-4](../../Arch/01-observability-and-metrics.md)） |
| 11 | 時間欄位時區 | `ts TIMESTAMPTZ DEFAULT NOW()`，與既有 `chat_memory` / `chat_message` 一致；查詢面以 UTC+8 呈現由 service 層處理 |
| 12 | embedding 呼叫的 baseline | embedding 無 cheap / expensive 區別，`baseline_cost_usd = actual_cost_usd`（不算「省」） |

---

## Phase 0：Migration

### 0-1 V38：建立 `llm_call_log`

- [ ] `migrations/sql/V38__create_llm_call_log.sql`（schema 對齊 [docs/Arch/01-observability-and-metrics.md §5-1](../../Arch/01-observability-and-metrics.md)）
  - `pid BIGSERIAL PRIMARY KEY`
  - `ts TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  - `session_uid UUID`、`user_uid UUID`、`agent_uid UUID`（不建 FK）
  - `purpose VARCHAR(40) NOT NULL`、`route VARCHAR(20)`、`model VARCHAR(100)`
  - `input_tokens INT NOT NULL DEFAULT 0`、`output_tokens INT NOT NULL DEFAULT 0`
  - `cache_creation_tokens INT NOT NULL DEFAULT 0`、`cache_read_tokens INT NOT NULL DEFAULT 0`
  - `actual_cost_usd NUMERIC(10, 6) NOT NULL DEFAULT 0`、`baseline_cost_usd NUMERIC(10, 6) NOT NULL DEFAULT 0`
  - `latency_ms INT`、`rag_hit_count INT`、`rag_max_score NUMERIC(4, 3)`、`error TEXT`
  - 索引：`idx_llm_call_log_ts` / `idx_llm_call_log_user` / `idx_llm_call_log_session` / `idx_llm_call_log_purpose`
  - `COMMENT ON TABLE` + 全部欄位 `COMMENT ON COLUMN`（繁體中文，明示用途）

---

## Phase 1：Backend — 價格表與 Wrapper

### 1-1 模型價格表

- [ ] 新建 `backend/app/config/__init__.py`（空檔即可，使資料夾為 package）
- [ ] `backend/app/config/model_prices.yaml`：對齊 [docs/Arch/01-observability-and-metrics.md §5-4](../../Arch/01-observability-and-metrics.md) 範例
  - 至少含：`anthropic/claude-haiku-4-5`、`anthropic/claude-sonnet-4-6`、`openai/text-embedding-3-small`
  - 每個 model 欄位：`input` / `output` / `cache_read` / `cache_creation`（單位 `$/M tokens`）
  - 檔頭註解：`# 來源：OpenRouter 官方價格；更新時於對應 model 加 # updated: YYYY-MM-DD`
- [ ] `backend/app/services/llm_pricing.py`（新增）
  - 模組載入時讀取 `model_prices.yaml` 為 dict（lazy + cache，不走每次呼叫 IO）
  - `compute_cost(model: str, usage: dict) -> Decimal`：input / output / cache_creation / cache_read 分項計算
  - `compute_baseline_cost(usage: dict, expensive_model: str) -> Decimal`：用 `EXPENSIVE_MODEL_ID` 重算
  - `estimate_baseline_for_skip(user_input: str) -> Decimal`：對齊 [§5-3](../../Arch/01-observability-and-metrics.md) 演算法
  - 模型不在價格表時：log warning 並回 `Decimal("0")`（不擋呼叫）
- [ ] 常數 `EXPENSIVE_MODEL_ID = "anthropic/claude-sonnet-4-6"` 定於 `llm_pricing.py`，由 settings 環境變數 `LLM_BASELINE_EXPENSIVE_MODEL` 覆寫
- [ ] `.env.example` / `.env` 補 `LLM_BASELINE_EXPENSIVE_MODEL`（預設 `anthropic/claude-sonnet-4-6`）

### 1-2 `llm_metering` service（**單一進入點**）

- [ ] `backend/app/services/llm_metering.py`：對齊 [docs/Arch/01-observability-and-metrics.md §5-2](../../Arch/01-observability-and-metrics.md) wrapper schema
  - `async def call_llm_metered(*, purpose, route, session_uid, user_uid, agent_uid, rag_hit_count, rag_max_score, **call_kwargs) -> Response`
  - 內部依 `purpose` 分派到對應 OpenRouter client 函式（`stream_chat_completion` / `extract_memory` / `embed` / `describe_image` / `generate_skill_suggestion`）
  - 統一計算 `latency_ms = int((time.time() - start) * 1000)`
  - 從 response.usage 抽 `input_tokens` / `output_tokens` / `cache_creation_tokens` / `cache_read_tokens`（後二者於 OpenRouter 回應中可能不存在，缺則 0）
  - 計 `actual_cost_usd` 與 `baseline_cost_usd`，後者統一以 `EXPENSIVE_MODEL_ID` 計算（embedding 例外，依決策 #12 直接 = actual）
  - 失敗 / 異常仍寫一筆 log（`error` 欄填截斷後的 exception message，500 字元上限），再 raise 原例外
- [ ] `async def log_skip_call(*, session_uid, user_uid, agent_uid, user_input: str)`：
  - 為 v1.3.4 classifier 預留，呼叫 `estimate_baseline_for_skip` 並寫一筆 `route='skip'`、tokens 全 0、actual=0、baseline=估算值 的 log
  - v1.3.0 不會被任何 caller 呼叫，但介面先定好
- [ ] streaming 路線（chat）特殊處理：
  - `stream_chat_completion` 是 `AsyncIterator`，wrapper 需收完整段、合併最後一個 chunk 的 usage 後再寫 log
  - 為避免破壞前端 SSE 體驗，wrapper 採「pass-through async generator」模式：邊 yield chunk 給呼叫端、邊累積 usage / latency；於 generator 結束（or 例外）時寫 log
  - 提供 `call_llm_metered_stream(...) -> AsyncIterator[dict]` 變體 API
- [ ] **集中進入點原則**：模組頂部 docstring 註明「除本檔外，禁止其他模組 `from app.clients.openrouter import` 任何 LLM 呼叫函式」

### 1-3 Repository

- [ ] `backend/app/models/llm_call_log.py`：`LlmCallLog` 對應 V38 schema（不繼承 `Base` mixin，因為無 `is_active` / `is_deleted` / `updated_at`）
- [ ] `backend/app/repositories/llm_call_log_repository.py`
  - `async def log(payload: dict, db: AsyncSession) -> None`：單筆寫入；缺漏欄位走 DB DEFAULT
  - `async def aggregate_cost(range_key: str, group_by: str, db: AsyncSession) -> dict`：給 admin endpoint 用
    - `range_key`：`today` / `7d` / `30d` / `month`（月為當月起算）
    - `group_by`：`route` / `model` / `user` / `session` / `purpose`
    - 回 `{ total_actual, total_baseline, saved, saved_pct, breakdown: [...] }`，對齊 [§5-5](../../Arch/01-observability-and-metrics.md) response 格式
  - SQL 用 `SUM(actual_cost_usd)` / `SUM(baseline_cost_usd)` + `GROUP BY` 動態組
  - 寫入失敗（DB down 等）：log error 但**不**raise，避免 metrics 壞掉拖垮主流程

---

## Phase 2：Backend — Schema

### 2-1 Admin metrics schema

- [ ] `backend/app/schemas/admin/metrics_schemas.py`（新增）
  - `CostBreakdownItem`：`{ key: str, actual: Decimal, baseline: Decimal, calls: int }`
  - `CostMetricsResponse`：`{ range: str, total_actual_usd: Decimal, total_baseline_usd: Decimal, saved_usd: Decimal, saved_pct: float, breakdown: list[CostBreakdownItem] }`
  - `range` 用 `Literal["today", "7d", "30d", "month"]`
  - `group_by` 用 `Literal["route", "model", "user", "session", "purpose"]`

---

## Phase 3：既有 LLM 呼叫遷移到 metered wrapper

> 原則：原本 `from app.clients.openrouter import xxx` 的呼叫，全部改走 `from app.services.llm_metering import call_llm_metered`（或其 stream 變體）。OpenRouter client 函式仍保留，但只允許 `llm_metering.py` 內部使用。

### 3-1 `chat_service.py`：對話主流程

- [ ] [`backend/app/services/chat_service.py`](../../../backend/app/services/chat_service.py) L818 `stream_chat_completion(...)` 改走 `call_llm_metered_stream`
  - 傳入 `purpose="chat"`、`route="expensive"`（v1.3.4 classifier 上線後改由 caller 動態傳入）
  - `session_uid` / `user_uid` / `agent_uid` 從現有 context 取
  - `rag_hit_count` / `rag_max_score`：由 chat_service 既有的 retrieval 段落取（若 retrieval 命中 list 為空則 0 / null）
- [ ] 移除 `from app.clients.openrouter import stream_chat_completion`（保留 client 內函式定義即可）

### 3-2 `memory_worker.py`：記憶抽取 + embedding + 圖片描述

- [ ] [`backend/app/workers/memory_worker.py`](../../../backend/app/workers/memory_worker.py) L216 `extract_memory(...)` 改走 `call_llm_metered`
  - `purpose="memory_extract"`、`route=None`、`session_uid`、`user_uid=session.owner_user_uid`
- [ ] L224 `openrouter_embed(embed_input)` 改走 `call_llm_metered`
  - `purpose="embedding"`、`route=None`、`session_uid`、`user_uid`
  - embedding 的 baseline = actual（決策 #12）
- [ ] L147 `describe_image(...)` 改走 `call_llm_metered`
  - `purpose="image_describe"`、`route=None`
  - `session_uid` 從外層 `_process_batch` 透傳；`user_uid` 同樣透傳
- [ ] 移除 `from app.clients.openrouter import describe_image, embed as openrouter_embed, extract_memory`

### 3-3 `skill_factory_service.py`：Skill 候選生成

- [ ] [`backend/app/services/skill_factory_service.py`](../../../backend/app/services/skill_factory_service.py) L269 `generate_skill_suggestion(...)` 改走 `call_llm_metered`
  - `purpose="skill_factory"`、`route=None`、`user_uid`、`session_uid`（若可取）
- [ ] 移除 `from app.clients.openrouter import generate_skill_suggestion`

### 3-4 集中進入點驗證

- [ ] grep 確認除 `backend/app/services/llm_metering.py` 外，**無**其他檔案 `from app.clients.openrouter import (stream_chat_completion|extract_memory|embed|describe_image|generate_skill_suggestion)`
- [ ] `backend/app/clients/openrouter/__init__.py` 對外暴露的函式 docstring 加註：「**內部 API**，外部請呼叫 `app.services.llm_metering.call_llm_metered`」

---

## Phase 4：Admin Endpoint

### 4-1 Cost endpoint

- [ ] [`backend/app/api/v1/admin/router.py`](../../../backend/app/api/v1/admin/router.py) 新增 endpoint
  - `GET /api/v1/admin/metrics/cost`
  - Query：`range: Literal["today","7d","30d","month"] = "today"`、`group_by: Literal["route","model","user","session","purpose"] = "route"`
  - 掛 `require_role("admin")`
  - response_model 用 `ApiResponse[CostMetricsResponse]`
  - service 層放 `backend/app/services/admin_metrics_service.py`（或併入既有 admin_service）
- [ ] Swagger `/api/docs` 顯示 endpoint 與 response schema 完整

### 4-2 路由註冊

- [ ] 確認 admin router 已於 [`backend/app/api/v1/router.py`](../../../backend/app/api/v1/router.py) 掛載；新 endpoint 自動繼承

---

## Phase 5：驗收

### Migration

- [ ] V38 套用後 `llm_call_log` 表存在、欄位 / 索引 / COMMENT 齊全
- [ ] Flyway V37 → V38 順序套用無 out-of-order

### 價格表 / 計算

- [ ] `llm_pricing.compute_cost("anthropic/claude-haiku-4-5", {...})` 對單純 input/output 場景產出與 [§5-4](../../Arch/01-observability-and-metrics.md) 表格一致的成本（手算對照）
- [ ] `compute_cost` 對 cache_read_tokens 套 0.1× 單價、cache_creation_tokens 套 1.25×（依 [§4-2](../../Arch/01-observability-and-metrics.md)）
- [ ] 模型不在價格表時 `compute_cost` 回 `Decimal("0")` 並 log warning，不 raise
- [ ] `estimate_baseline_for_skip("hello")` 產出 > 0 的 Decimal（粗估即可，不做精確驗證）

### Wrapper 行為

- [ ] 成功 chat 呼叫後 `llm_call_log` 多一筆，欄位齊全（`actual_cost_usd > 0`、`baseline_cost_usd > 0`、`latency_ms > 0`、`error IS NULL`）
- [ ] OpenRouter 端 4xx / 5xx 失敗時仍寫一筆 log（`error` 非 null，截斷 ≤ 500 字元），且原例外正常上拋
- [ ] streaming chat 寫 log 的時機是 generator 結束之後（usage 已收齊），前端 SSE 體驗不受影響
- [ ] embedding 呼叫的 `baseline_cost_usd == actual_cost_usd`（決策 #12）

### 既有呼叫遷移

- [ ] `chat_service` 主對話可正常串流（end-to-end smoke），且 log 寫入 `purpose='chat'` 一筆
- [ ] `memory_worker` 處理一輪批次後，`llm_call_log` 含 `purpose='memory_extract'` + `purpose='embedding'`（若有圖片附件再加 `purpose='image_describe'`）
- [ ] `skill_factory_worker` 觸發後 log 含 `purpose='skill_factory'`
- [ ] grep 驗證集中進入點：除 `llm_metering.py` 外無其他模組直接 import OpenRouter LLM 呼叫函式

### Admin endpoint

- [ ] `GET /api/v1/admin/metrics/cost?range=today&group_by=route` 200 回傳，response shape 對齊 [§5-5](../../Arch/01-observability-and-metrics.md)
- [ ] 非 admin 呼叫 → 403
- [ ] `range` / `group_by` 給超出 enum 值 → 422
- [ ] 全部五種 `group_by` 都能跑通（route / model / user / session / purpose）
- [ ] 全部四種 `range` 都能跑通（today / 7d / 30d / month）
- [ ] 空資料時回 `{ total_actual_usd: 0, total_baseline_usd: 0, saved_usd: 0, saved_pct: 0, breakdown: [] }`（不 raise）
- [ ] Swagger `/api/docs` 顯示新 endpoint 與 schema

### 規範

- [ ] 所有新增程式碼註解 / docstring 為**繁體中文**
- [ ] `llm_call_log` 欄位 COMMENT 為繁體中文
- [ ] `model_prices.yaml` 註解為繁體中文
- [ ] API 文件路徑維持 `/api/docs`，**未**新增 `/swagger` / `/openapi` 等

---

## 附錄 A：Admin SQL 範本（reference）

> 以下 7 個 query 對應 [docs/Arch/01-observability-and-metrics.md §6](../../Arch/01-observability-and-metrics.md)，本 task 不寫成 endpoint，僅作為 admin 直接連 PostgreSQL 查詢時的常用範本。未來 §7 階段 2 做 admin UI 時可作為頁面卡片的資料來源依據。

### A-1 今日總花費

```sql
SELECT SUM(actual_cost_usd) AS today_usd
FROM llm_call_log
WHERE ts >= CURRENT_DATE;
```

### A-2 今日 classifier 省了多少

```sql
SELECT
    SUM(actual_cost_usd)                          AS spent,
    SUM(baseline_cost_usd)                        AS baseline,
    SUM(baseline_cost_usd - actual_cost_usd)      AS saved,
    ROUND(
        100.0 * SUM(baseline_cost_usd - actual_cost_usd)
              / NULLIF(SUM(baseline_cost_usd), 0),
        2
    )                                              AS saved_pct
FROM llm_call_log
WHERE ts >= CURRENT_DATE;
```

### A-3 Route 分佈

```sql
SELECT route, COUNT(*) AS calls, SUM(actual_cost_usd) AS cost
FROM llm_call_log
WHERE ts >= CURRENT_DATE AND purpose = 'chat'
GROUP BY route
ORDER BY cost DESC;
```

### A-4 Top 10 燒錢 user（近 7 天）

```sql
SELECT user_uid, SUM(actual_cost_usd) AS cost, COUNT(*) AS calls
FROM llm_call_log
WHERE ts >= NOW() - INTERVAL '7 days'
  AND user_uid IS NOT NULL
GROUP BY user_uid
ORDER BY cost DESC
LIMIT 10;
```

### A-5 P50 / P95 / P99 延遲（近 1 天 chat）

```sql
SELECT
    percentile_cont(0.5)  WITHIN GROUP (ORDER BY latency_ms) AS p50_ms,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_ms,
    percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99_ms
FROM llm_call_log
WHERE purpose = 'chat'
  AND ts >= NOW() - INTERVAL '1 day'
  AND error IS NULL;
```

### A-6 Cache 命中率（近 7 天，僅 Anthropic）

```sql
SELECT
    SUM(cache_read_tokens)::FLOAT
    / NULLIF(SUM(cache_read_tokens + input_tokens), 0)        AS cache_hit_rate
FROM llm_call_log
WHERE ts >= NOW() - INTERVAL '7 days'
  AND model LIKE 'anthropic/%';
```

### A-7 失敗率（近 1 天，按 model 分）

```sql
SELECT
    model,
    COUNT(*) FILTER (WHERE error IS NOT NULL) AS failures,
    COUNT(*)                                  AS total,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE error IS NOT NULL) / COUNT(*),
        2
    )                                          AS failure_rate_pct
FROM llm_call_log
WHERE ts >= NOW() - INTERVAL '1 day'
GROUP BY model
ORDER BY failure_rate_pct DESC;
```
