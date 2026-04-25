# 可觀察性與成本監控（Observability & Cost Metrics）

> 本文件定義 LLM 呼叫的成本 / 延遲 / 品質監控架構。回答「花了多少 / 省了多少 / 哪裡慢 / 哪些失敗」這類運營問題。
>
> 與 [00-memory-system.md](00-memory-system.md) 互補：主架構講「pipeline 該長怎樣」，本文件講「**怎麼證明它有效**」。
>
> 相關文件：
>
> - [Tasks/v1.3/propose-v1.3.0.md §3-4](../Tasks/v1.3/propose-v1.3.0.md) — 記憶 pipeline 可觀察性（trace 層）
> - [backend/app/clients/openrouter/](../../backend/app/clients/openrouter/) — 目前 LLM 呼叫入口

---

## 1. 目的

定義一套**輕量、單一進入點、可 SQL 查詢**的監控機制，回答以下問題：

- 這個月（/週/日）花了多少錢？
- classifier 幫我省了多少？（counterfactual）
- 哪個 user / session / agent 最燒錢？
- prompt cache 命中率多少？省了多少？
- p50 / p95 延遲多少？哪一步最慢？
- 哪些 model 失敗最多？

**範圍內**：

- LLM 呼叫的 token / 成本 / 延遲記錄
- counterfactual baseline 計算（用來證明優化有效）
- admin SQL 查詢範本

**範圍外**：

- Prometheus / Grafana / OpenTelemetry 等重量級觀測（v2.x 後再評估，見 §7）
- 評估資料集（propose §3-4 層 2，與 metrics 互補但職責不同：metrics 看「花多少」、eval 看「答多好」）

---

## 2. 核心觀念

### 2-1 先量再優化

> 沒 metrics 時所有「省錢」都是憑感覺。

加任何優化（classifier / cache / reranker）**之前**就必須先有 metrics — 否則無法證明它有效，也無法在它出問題時發現。

### 2-2 必須記錄 baseline（counterfactual）

「省了多少」=「如果**沒做這個優化**會花多少」 −「實際花的」。

光記 `actual_cost` 無法回答「classifier 值不值得」。必須**同時**記 `baseline_cost`：假設沒 classifier、全走 expensive 會花多少。

### 2-3 集中進入點（Single Entry Point）

所有 LLM 呼叫**必須**過同一個 wrapper。任何繞過 wrapper 的呼叫 = 漏記 = metrics 失真。

實作上：

- `backend/app/services/llm_metering.py` 是唯一允許呼叫 OpenRouter / embedding API 的位置
- 其他 service / worker 一律呼叫 metering wrapper，不直接呼叫 client
- code review 必檢：`from app.clients.openrouter import` 不應出現在 `llm_metering.py` 以外

### 2-4 記憶生命週期：metrics 與業務資料分離

`llm_call_log` 是**運營資料**，與業務資料生命週期獨立：

- 不跟著 session / user 刪除而連動清除（保留 30 天供事後稽核）
- 對 `user_uid` / `session_uid` 不做 FK cascade
- 30 天前的細節聚合到月表後刪明細

---

## 3. 指標清單

### 3-1 每次 LLM 呼叫（call-level，必記）

| 欄位 | 來源 | 用途 |
| --- | --- | --- |
| `ts` | 系統時間（UTC+8）| 時序查詢 |
| `session_uid` / `user_uid` / `agent_uid` | 從 request context 取 | 維度切片 |
| `purpose` | wrapper 呼叫端傳入 | 區分用途（chat / memory_extract / embedding / classifier / image_describe）|
| `route` | classifier 決策 | `skip` / `cheap` / `expensive` / `null`（非 chat 場景）|
| `model` | 實際呼叫的模型 ID | 成本歸因 |
| `input_tokens` / `output_tokens` | OpenRouter response.usage | 計費基礎 |
| `cache_creation_tokens` / `cache_read_tokens` | Anthropic 回傳 | 算 cache 命中率 |
| `actual_cost_usd` | tokens × 該 model 單價 | 真花了多少 |
| `baseline_cost_usd` | tokens × **expensive model 單價** | 沒 classifier 會花多少 |
| `latency_ms` | call 起訖差 | UX 監控 |
| `rag_hit_count` | retrieval 撈到幾筆 | 證明 RAG 有用 |
| `rag_max_score` | top-1 cosine score | retrieval 品質 |
| `error` | 失敗原因（成功為 null）| 穩定性 |

### 3-2 進階（後續加）

| 欄位 | 用途 | 加入時機 |
| --- | --- | --- |
| `cited_uids[]` | 主 model 回答**真的引用了**哪些 RAG 結果（需要 prompt 加 citation 機制）| 觀察 retrieval 浪費率時加 |
| `query_embedding_cost` | embedding 也要錢，獨立記錄 | embedding 用量大時加 |

### 3-3 Worker / Pipeline（與 LLM 呼叫無關，靠 health endpoint 暴露）

| 指標 | 來源 | 暴露方式 |
| --- | --- | --- |
| `memory_queue_length` | Redis `LLEN chat:memory:queue` | `/api/v1/health` |
| `memory_dlq_length` | Redis `LLEN chat:memory:dlq` | `/api/v1/health` |
| `worker_alive` | heartbeat（worker 每 30 秒寫 Redis key + TTL）| `/api/v1/health` |

> propose §3-4 已規劃此層，本文件不重述。

---

## 4. 「省了多少」怎麼算

### 4-1 Classifier 省的錢

```
saved_by_classifier = sum(baseline_cost_usd) − sum(actual_cost_usd)
```

每次呼叫**必須**記兩個欄位：

- `actual_cost_usd`：實際花的
- `baseline_cost_usd`：假設沒 classifier、全走 expensive 會花的

範例：

| route | input | output | actual | baseline | saved |
| --- | --- | --- | --- | --- | --- |
| skip | 0 | 0 | $0 | $0.001 | $0.001 |
| cheap | 500 | 200 | $0.0008 | $0.012 | $0.0112 |
| expensive | 500 | 800 | $0.013 | $0.013 | $0 |

**重點**：`skip` 也要寫一筆 log（input/output tokens 為 0、actual 為 0、baseline 用「假設走 expensive 的預估值」）— 否則「省的錢」會少算最大宗的部分。

### 4-2 Prompt Cache 省的錢

Anthropic prompt cache：`cache_read` 收 0.1× 單價、`cache_creation` 收 1.25× 單價。

```
without_cache = (cache_read_tokens + cache_creation_tokens + input_tokens) × full_input_price
actual        = cache_read_tokens × 0.1× + cache_creation_tokens × 1.25× + input_tokens × full_input_price
saved_by_cache = without_cache − actual
```

cache 命中率：

```
cache_hit_rate = cache_read_tokens / (cache_read_tokens + input_tokens)
```

**告警閾值**：cache_hit_rate < 50% → system prompt 沒寫好 / cache breakpoint 放錯位置，要檢查。

### 4-3 RAG 是否「省」？

RAG **不省錢，反而多花**（塞了更多 context）。它省的是「回答品質差導致使用者重問 N 次」的成本，這要靠**間接指標**衡量：

| 指標 | 怎麼量 | 加入時機 |
| --- | --- | --- |
| 重問率 | 同 session 內 user 連續訊息語意相似度 > 0.8 的比例 | v1.4 |
| 對話深度 | 平均一個 session 幾輪結束 | v1.4 |
| 引用 vs 撈取比率 | `cited_count / retrieved_count`，低 → top_k 該降 | 加 citation 機制後 |

第一階段不做。

---

## 5. 實作架構

### 5-1 資料表

```sql
CREATE TABLE llm_call_log (
    pid                     BIGSERIAL PRIMARY KEY,
    ts                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_uid             UUID,
    user_uid                UUID,
    agent_uid               UUID,
    purpose                 VARCHAR(40)  NOT NULL,
        -- 'chat' / 'memory_extract' / 'embedding' / 'classifier'
        -- / 'image_describe' / 'skill_factory' / 其他
    route                   VARCHAR(20),
        -- 'skip' / 'cheap' / 'expensive' / NULL（非 chat 場景）
    model                   VARCHAR(100),
    input_tokens            INT     NOT NULL DEFAULT 0,
    output_tokens           INT     NOT NULL DEFAULT 0,
    cache_creation_tokens   INT     NOT NULL DEFAULT 0,
    cache_read_tokens       INT     NOT NULL DEFAULT 0,
    actual_cost_usd         NUMERIC(10, 6) NOT NULL DEFAULT 0,
    baseline_cost_usd       NUMERIC(10, 6) NOT NULL DEFAULT 0,
    latency_ms              INT,
    rag_hit_count           INT,
    rag_max_score           NUMERIC(4, 3),
    error                   TEXT
);

CREATE INDEX idx_llm_call_log_ts      ON llm_call_log (ts DESC);
CREATE INDEX idx_llm_call_log_user    ON llm_call_log (user_uid, ts DESC);
CREATE INDEX idx_llm_call_log_session ON llm_call_log (session_uid, ts DESC);
CREATE INDEX idx_llm_call_log_purpose ON llm_call_log (purpose, ts DESC);
```

**設計決策**：

- 無 `chat_message_uid` 直接欄位（一個 user message 可能對應多次 LLM 呼叫，硬綁反而難查）
- `actual_cost_usd` / `baseline_cost_usd` 用 `NUMERIC(10, 6)` — 6 位小數對應到 $0.000001 精度
- 不建外鍵 cascade（見 §2-4）

### 5-2 Wrapper（單一進入點）

```python
# backend/app/services/llm_metering.py（新增）
async def call_llm_metered(
    *,
    purpose: str,
    route: str | None = None,
    session_uid: str | None = None,
    user_uid: str | None = None,
    agent_uid: str | None = None,
    rag_hit_count: int | None = None,
    rag_max_score: float | None = None,
    **call_kwargs,  # 透傳給 openrouter client
) -> Response:
    start = time.time()
    actual_model = call_kwargs.get("model")
    log_payload = {
        "purpose": purpose, "route": route,
        "session_uid": session_uid, "user_uid": user_uid, "agent_uid": agent_uid,
        "model": actual_model,
        "rag_hit_count": rag_hit_count, "rag_max_score": rag_max_score,
    }
    try:
        resp = await openrouter_client.chat(**call_kwargs)
        usage = resp.usage
        actual = compute_cost(actual_model, usage)
        baseline = compute_cost(EXPENSIVE_MODEL_ID, usage)
        log_payload.update({
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_creation_tokens": getattr(usage, "cache_creation_tokens", 0),
            "cache_read_tokens": getattr(usage, "cache_read_tokens", 0),
            "actual_cost_usd": actual,
            "baseline_cost_usd": baseline,
            "latency_ms": int((time.time() - start) * 1000),
        })
        await metering_repo.log(log_payload)
        return resp
    except Exception as exc:
        log_payload["error"] = str(exc)[:500]
        log_payload["latency_ms"] = int((time.time() - start) * 1000)
        await metering_repo.log(log_payload)
        raise
```

**呼叫端範例**：

```python
# chat_service.py
resp = await call_llm_metered(
    purpose="chat",
    route="expensive",
    session_uid=session_uid,
    user_uid=owner_uid,
    rag_hit_count=len(retrieved),
    rag_max_score=retrieved[0][1] if retrieved else None,
    model="anthropic/claude-sonnet-4-6",
    messages=messages,
)

# memory_worker.py
resp = await call_llm_metered(
    purpose="memory_extract",
    session_uid=session_uid,
    model="anthropic/claude-haiku-4-5",
    messages=llm_messages,
)
```

### 5-3 `skip` 路線也要寫 log

當 classifier 決定 skip：

```python
await metering_repo.log({
    "purpose": "chat",
    "route": "skip",
    "session_uid": session_uid,
    "user_uid": user_uid,
    "model": None,
    "input_tokens": 0,
    "output_tokens": 0,
    "actual_cost_usd": 0,
    "baseline_cost_usd": estimate_baseline_for_skip(user_input),
    "latency_ms": 0,
})
```

`estimate_baseline_for_skip`：用 `len(user_input) / 4` 估 input tokens、output 估 200 tokens、套 expensive 單價。粗估即可，重點是「skip 確實有省錢」這件事被記下。

### 5-4 Model 價格表

```yaml
# backend/app/config/model_prices.yaml
"anthropic/claude-haiku-4-5":
  input: 1.0           # $/M tokens
  output: 5.0
  cache_read: 0.1
  cache_creation: 1.25
"anthropic/claude-sonnet-4-6":
  input: 3.0
  output: 15.0
  cache_read: 0.3
  cache_creation: 3.75
# embedding
"openai/text-embedding-3-small":
  input: 0.02
  output: 0
```

**維運**：每月對一次 OpenRouter 官方價格，或讀 `/api/v1/models` API 動態抓。價格變更需在價格表加註 `# updated: YYYY-MM-DD`。

### 5-5 Admin Endpoint

最小版只需一支：

```
GET /api/v1/admin/metrics/cost
  ?range=today | 7d | 30d | month
  &group_by=route | model | user | session | purpose
```

回傳：

```json
{
    "range": "7d",
    "total_actual_usd": 12.34,
    "total_baseline_usd": 45.67,
    "saved_usd": 33.33,
    "saved_pct": 73.0,
    "breakdown": [
        { "key": "expensive", "actual": 10.0, "baseline": 10.0, "calls": 320 },
        { "key": "cheap",     "actual":  2.3, "baseline": 30.0, "calls": 800 },
        { "key": "skip",      "actual":  0.0, "baseline":  5.7, "calls": 1200 }
    ]
}
```

UI 階段 0 不做，直接 SQL 查；觀察一陣子需求穩定後才畫 admin 頁面。

---

## 6. SQL 查詢範本

### 6-1 今日總花費

```sql
SELECT SUM(actual_cost_usd) AS today_usd
FROM llm_call_log
WHERE ts >= CURRENT_DATE;
```

### 6-2 今日 classifier 省了多少

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

### 6-3 Route 分佈

```sql
SELECT route, COUNT(*) AS calls, SUM(actual_cost_usd) AS cost
FROM llm_call_log
WHERE ts >= CURRENT_DATE AND purpose = 'chat'
GROUP BY route
ORDER BY cost DESC;
```

### 6-4 Top 10 燒錢 user（近 7 天）

```sql
SELECT user_uid, SUM(actual_cost_usd) AS cost, COUNT(*) AS calls
FROM llm_call_log
WHERE ts >= NOW() - INTERVAL '7 days'
  AND user_uid IS NOT NULL
GROUP BY user_uid
ORDER BY cost DESC
LIMIT 10;
```

### 6-5 P50 / P95 延遲（近 1 天 chat）

```sql
SELECT
    percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms)  AS p50_ms,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_ms,
    percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99_ms
FROM llm_call_log
WHERE purpose = 'chat'
  AND ts >= NOW() - INTERVAL '1 day'
  AND error IS NULL;
```

### 6-6 Cache 命中率（近 7 天）

```sql
SELECT
    SUM(cache_read_tokens)::FLOAT
    / NULLIF(SUM(cache_read_tokens + input_tokens), 0)        AS cache_hit_rate
FROM llm_call_log
WHERE ts >= NOW() - INTERVAL '7 days'
  AND model LIKE 'anthropic/%';
```

### 6-7 失敗率（近 1 天，按 model 分）

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

---

## 7. 演進路線

| 階段 | 加什麼 | 觸發條件 |
| --- | --- | --- |
| 0 | `llm_call_log` 表 + wrapper + 7 個 admin SQL | **本架構起點** |
| 1 | Cache 命中率告警（< 50% 寄信 / Slack）| 觀察一週後 |
| 2 | Admin UI 視覺化（圖表）| SQL 已能回答問題、需要非技術人員看 |
| 3 | 月表聚合 + 明細刪除（節省儲存）| `llm_call_log` 超過 1000 萬筆 |
| 4 | Citation 機制 + cited vs retrieved 比率 | 開始懷疑 RAG 浪費 |
| 5 | Prometheus + Grafana | 流量上萬呼叫 / 日、需要告警系統 |
| 6 | OpenTelemetry + 觀測雲 | 多 service 架構出現 |

**新手原則**：階段 0 → 1 → 2 之間至少各跑一個月，讓數據穩定後再進下一階段。

---

## 8. 維運注意

### 8-1 寫入效能

預估流量：每天 1000 chat × 3 次 LLM 呼叫 = 3000 筆 / 天。直接同步寫 PostgreSQL **完全沒問題**。

若未來流量超過 100k 筆 / 天：

- 改用 Redis stream 暫存 → background flush worker 每 5 秒批次寫 PostgreSQL
- 或改用 TimescaleDB hypertable

### 8-2 隱私

`llm_call_log` 不存 prompt / response 原文，**不會**洩漏對話內容。但要注意：

- `error` 欄位可能含 prompt 片段（如 token limit error），記得截斷 + 過濾敏感字串
- admin endpoint 必須加權限驗證（限 admin role）

### 8-3 價格表更新

OpenRouter / Anthropic 偶爾調價。若價格表沒更新：

- `actual_cost_usd` 會偏離真實
- 但**歷史 log 不重算**（保留當時價格的成本），這是審計需要

新價格生效日 = 價格表檔案的 `# updated: YYYY-MM-DD` 那天，往前的 log 不動。

### 8-4 保留期限

- 明細：30 天（足夠查任何「為什麼上週某天爆量」）
- 月表（聚合）：永久保留

明細刪除 cron：

```sql
DELETE FROM llm_call_log WHERE ts < NOW() - INTERVAL '30 days';
```

---

## 9. 與其他文件的關係

| 文件 | 角色 |
| --- | --- |
| 本文件 | 監控 / 成本 / 延遲指標的設計藍圖 |
| [00-memory-system.md](00-memory-system.md) | 記憶系統與 RAG pipeline 主架構 |
| [propose-v1.3.0.md §3-4](../Tasks/v1.3/propose-v1.3.0.md) | Worker pipeline trace（與本文件互補：trace 看「卡在哪」、metrics 看「花多少」）|
| [Design-Base/00-overview.md](../Design-Base/00-overview.md) | 系統技術棧 |

**互補關係**：

- 本文件 = **量化**（花多少 / 省多少 / 延遲）
- propose §3-4 = **追蹤**（哪一步卡 / DLQ 多少）
- 評估資料集（propose §3-4 層 2）= **品質**（答得多好）

三者缺一不可，但分階段做：先 metrics（本文件）→ 再 trace（propose §3-4）→ 最後 eval。

---

## 10. 變更記錄

| 日期 | 版本 | 變更 |
| --- | --- | --- |
| 2026-04-25 | 0.1 | 初版：定義 `llm_call_log` schema、wrapper、7 個 admin SQL、演進路線 |
