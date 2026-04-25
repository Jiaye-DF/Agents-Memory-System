# v1.3.4 任務規格：分層 Model Classifier（路由分類器）

> **狀態：進行中（程式碼完成：commit 843610e, 2026-04-25；runtime smoke / 使用者實測資料待累積）** — 規則引擎 / V43 seed / chat_service 三路分流 / skip log 全部就位；Phase 6 中需「使用者實測累積資料」的條目（連續 100 則 skip / cost endpoint 三組 breakdown / cheap 命中率觀察 / saved_pct 觀察）保留 `[ ]` 待後續資料累積後評估。
>
> 前置：[propose-v1.3.0.md §4-2](propose-v1.3.0.md)、[docs/Arch/00-memory-system.md §4](../../Arch/00-memory-system.md)（路由分類器 vs 意圖推斷器的區別）、[docs/Arch/01-observability-and-metrics.md §4-1 / §5-3](../../Arch/01-observability-and-metrics.md)、[tasks-v1.3.0.md](tasks-v1.3.0.md)（metrics 必須先就位）、[tasks-v1.3.3.md](tasks-v1.3.3.md)（session_agent schema、多 Agent 路由整合點）
>
> 後續依賴：（無）

## 版本目標

於 chat 進入點前置一道**路由分類器（Routing Classifier）**，依訊息內容把每一次對話分流到三條路：

1. **skip** — 純打招呼 / 純表情 / 系統訊息，**不**呼叫任何 LLM，回固定字串
2. **cheap** — 簡單問答，走 cheap model（haiku / deepseek 級，從 `system_setting` 讀）
3. **expensive** — 複雜推理，走主 LLM（從該訊息對應的 Agent 設定讀）

並承接 v1.1.6 附件機制：訊息含**圖片附件**時**強制**走 vision model（跳過 classifier 文字分流），避免圖片被誤判為「無需回覆」。

### 命名與職責邊界（不可混淆）

> 重點對齊 [docs/Arch/00-memory-system.md §4](../../Arch/00-memory-system.md)

| 名稱 | 在做什麼 | 本版採用？ |
| --- | --- | --- |
| 意圖推斷器（Intent Classifier） | 推斷使用者「想做什麼」，output 是**標籤** | ❌ 不採用（與 embedding 重疊、output 還要 if/else 才能變動作） |
| **路由分類器（Routing Classifier）** | 決定「該走哪條路」，output 直接是**動作** | ✅ 本版採用 |
| 語意分類器 | 詞義模糊 | ❌ 不使用此名稱 |

實作 PR / commit / log 訊息一律用「路由分類器 / Routing Classifier / classifier」措辭，**禁用**「意圖推斷器 / Intent Classifier」字眼避免下游誤解。

### 範圍內

- **Classifier 模型選型拍板**：本版採**規則引擎（rule-based）**起跳；不接 local DistilBERT、不接雲端 haiku 級判斷器（演進路徑見「已確認決策」#1）
- 規則引擎延伸自 v1.1 既有 [memory_prefilter](../../../backend/app/services/memory_prefilter.py) 的 `DEFAULT_SKIP_RULES`（greeting whitelist / min_length / max_tokens / 純 emoji 偵測），擴展為三層輸出
- Multimodal 強制路由：訊息含圖片附件 → 直接走 expensive vision model（跳過分流）
- System Settings：`classifier.enabled` / `classifier.thresholds` / `classifier.skip_response_template` / `classifier.cheap_model` / `classifier.model`（後者占位給未來 model 路徑）
- `chat_service.send_message` 整合：分類 → 三條路徑分發 → metrics 寫入
- `skip` 路線**必寫**一筆 `llm_call_log`（`actual_cost=0` / `baseline_cost` 用 expensive model 估算 input/output token 成本），否則「省了多少」會少算最大宗
- `cheap` / `expensive` / vision 路線寫入 `llm_call_log` 時 `route` 欄位帶入分類結果（v1.3.0 metrics schema 已有此欄位）
- Admin endpoint 擴：`GET /api/v1/admin/metrics/cost?group_by=route` 已可由 v1.3.0 SQL 直接 group，本版不另開新端點，僅在驗收檢查 `route` 分佈寫入正確

### 範圍外

- 訊息分類用 LLM rerank（規則引擎不需 LLM；§2 跨類別硬規範語言要求亦不適用，因為**沒有 LLM 呼叫**）
- 自動誤判率告警（→ follow-up，待累積使用者「重問率」訊號後評估）
- Classifier 推薦 model 自動切換（→ v1.4+，先靠 `system_setting` 手動調）
- Local DistilBERT / 雲端 haiku 級判斷器（→ 規則引擎撐不住時再升級，**本版不做**）
- skip / cheap 路線的 token 用量 baseline 自動回饋調校 cheap model 邊界（→ follow-up）

---

## 前置現況

- v1.1：`memory_prefilter.should_skip` 已具備 greeting whitelist / min_length / 純 emoji 偵測能力（給 memory_worker 用），可直接擴展給 chat 入口共用
- v1.1.6：附件系統已就位，`chat_service.send_message` 內已會載入 `loaded_attachments`、辨識 `image_attachments` 並判斷 `model_supports_vision(model)`，本版即在此判斷之前插入 classifier
- v1.3.0（前置）：`llm_call_log` 表 + `llm_metering.py` wrapper + `route` 欄位定義已就位；本版只負責「正確帶入 route 值」與「寫 skip 路線 log」
- v1.3.3（前置）：`session_agent` 中介表上線後，多 Agent session 的「該訊息對應到哪個 Agent」由 v1.3.3 決定；classifier 拿到的「expensive model」即是 v1.3.3 路由完的 Agent.model
- 預設 `DEFAULT_SKIP_RULES`（[memory_worker.py L33-37](../../../backend/app/workers/memory_worker.py)）：

```python
DEFAULT_SKIP_RULES = {
    "min_length": 15,
    "greeting_whitelist": ["hi", "hello", "好", "好的", "收到", "謝謝", "ok"],
    "max_tokens": 2000,
}
```

本版在此基礎上擴展 cheap / expensive 邊界判斷規則。

---

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | Classifier 模型選型 | **規則引擎（rule-based）** — 零成本、零 latency、可解釋；演進路徑：規則撐不住 → local DistilBERT → 雲端 haiku 級判斷器（本版**僅**做規則引擎） |
| 2 | 規則來源 | 擴展 v1.1 `memory_prefilter` 的判斷邏輯，**不**重寫；新增的三層判斷封裝於新模組 `app/services/classifier_service.py`，原 `memory_prefilter` 不動以避免影響 memory_worker |
| 3 | skip 路線回應 | 固定字串模板（`classifier.skip_response_template`，預設「收到，繼續～」），不呼叫 LLM、不串流（直接一次性 SSE `event: delta` + `event: done`） |
| 4 | cheap 模型來源 | `system_setting.classifier.cheap_model`（預設 `anthropic/claude-haiku-4-5`），**不**走 Agent 設定 — cheap 路徑刻意統一以利 metrics 比較 |
| 5 | expensive 模型來源 | Agent.model（v1.3.3 多 Agent 路由完的結果），與既有 chat 行為一致 |
| 6 | Multimodal 強制路由 | 訊息含**任一**圖片附件 → 強制 expensive + vision model；classifier 完全跳過。文字 / PDF 附件**不**觸發強制路由 |
| 7 | classifier.enabled = false 時 | 全部走 expensive（與 v1.3.4 上線前行為一致），**仍**寫 `route='expensive'` 進 log（不寫 NULL，方便事後切換比較） |
| 8 | skip log 必寫 | `actual_cost_usd=0`、`baseline_cost_usd=estimate_baseline_for_skip(content)`（用 `len(content)/4` 估 input、output 估 200 tokens、套 expensive model 單價），無此筆則 §4-1「classifier 省的錢」會嚴重少算 |
| 9 | cheap 與 expensive 的判斷邏輯 | 規則引擎難以精準分辨；本版採**保守策略**：未命中 skip 即進 expensive，cheap 暫時只命中**極短純問答 + 無 RAG hit** 的少數情境（避免規則誤判把複雜問題丟給 cheap model 答錯） |
| 10 | 規則閾值由 system_setting 控制 | 全部閾值（min_length / max_tokens / cheap_max_length / cheap_max_history / greeting_whitelist）以 JSON 存於 `classifier.thresholds`，可線上調整不需重啟 |
| 11 | 誤判率指標 | 本版**只記** `route` 欄位 + 重問率原始資料（同 session 連續 user 訊息），自動誤判率告警 → follow-up |
| 12 | classifier 自身的成本 | 規則引擎**零成本**，因此 `purpose='classifier'` 的 log **不寫**（vs 未來 model 路徑時才會有 classifier 自身呼叫） |
| 13 | session_agent 整合點 | classifier 在「v1.3.3 多 Agent 路由完、決定本則訊息對應的 Agent」**之後**執行；classifier 看得到該 Agent.model，作為 expensive 路徑的呼叫對象 |

---

## Phase 0：Migration / Seed

> 本版**不新增表**；`llm_call_log` 已在 v1.3.0 建立、`route` 欄位已存在。僅 seed system_setting。
>
> Migration 版本對應：v1.3.0 = V38（llm_call_log）、v1.3.3 = V39–V42（multi-agent schema）、本 task = V43。

### 0-1 V43：seed classifier system settings

- [x] `migrations/sql/V43__seed_classifier_settings.sql`
  - `INSERT INTO system_setting (key, value, description) VALUES`：
    - `('classifier.enabled', 'true', '路由分類器開關（false 時全部走 expensive）')`
    - `('classifier.model', '"rule-based"', '分類器模型 ID；本版固定 rule-based，未來改 model 路徑時調整')`
    - `('classifier.cheap_model', '"anthropic/claude-haiku-4-5"', 'cheap 路線使用的 model ID')`
    - `('classifier.skip_response_template', '"收到，繼續～"', 'skip 路線回固定字串模板')`
    - `('classifier.thresholds', '<JSON>', '規則引擎閾值（JSON）')` — JSON 內容：
      ```json
      {
        "min_length": 3,
        "greeting_whitelist": ["hi", "hello", "嗨", "你好", "好", "好的", "收到", "謝謝", "ok", "thanks", "thx"],
        "cheap_max_length": 60,
        "cheap_max_history_turns": 4,
        "skip_response_template_fallback": "收到。"
      }
      ```
  - `ON CONFLICT (key) DO NOTHING` — 已存在則不覆蓋（保留人工調整值）
  - 全部欄位 `COMMENT ON COLUMN`（沿用 v14 system_setting 表既有 COMMENT pattern）

> `min_length=3` 比 memory_prefilter 的 `15` 小：因為 chat 入口的 skip 標準「不需要 LLM 回覆」嚴於「不抽進記憶」，誤把使用者真實問題分到 skip 比誤抽記憶代價高。

---

## Phase 1：Backend — Classifier Service（規則引擎）

### 1-1 新增 `app/services/classifier_service.py`

- [x] 模組頂層常數：
  - `RouteDecision = Literal["skip", "cheap", "expensive"]`
  - 預設 fallback 規則（與 V43 seed 同步，作為 `system_setting` 抓不到時的硬 fallback）
- [x] `async def classify(content: str, *, attachments: list[dict] | None, history_turns: int, db: AsyncSession) -> dict`
  - 回傳：`{"route": RouteDecision, "reason": str, "matched_rule": str}`
  - `reason` 給 metrics / debug log 用（e.g. `"greeting_whitelist:hi"`、`"length<min_length"`）
  - **multimodal 強制路由**：`attachments` 含 `kind=='image'` → 直接回 `{"route": "expensive", "reason": "multimodal_force", "matched_rule": "image_attachment"}`，不進規則判斷
  - 讀 `classifier.enabled`：false → 直接回 expensive（`reason="classifier_disabled"`）
  - 讀 `classifier.thresholds` JSON
- [x] 規則順序（短路判斷，命中即回）：
  1. **multimodal**：見上（已在進入規則前處理）
  2. **skip 條件**：
     - `len(content.strip()) < min_length` → skip
     - 純 emoji（沿用 `memory_prefilter._EMOJI_PATTERN` 邏輯，去除 emoji 後為空）→ skip
     - `content.strip().lower()` 命中 `greeting_whitelist` → skip
  3. **cheap 條件**（保守）：
     - `len(content) <= cheap_max_length` **且** `history_turns <= cheap_max_history_turns` **且** 不含問號以外的多句結構（簡單啟發式：`. ? !` 標點少於 2 個）→ cheap
  4. **預設**：expensive
  —（已改為：skip 子條件順序由「min_length → emoji → greeting」改為「greeting → emoji → min_length」，使「hi」/「好」等短於 `min_length=3` 的 whitelist 條目仍能命中 `matched_rule='greeting_whitelist:<word>'`，對齊 §6 驗收要求）
- [x] **不**直接 import `memory_prefilter` 內部函式 — 把共用的 emoji pattern 抽到 `app/core/text_utils.py` 或在 classifier_service 內重宣告（避免兩模組互相耦合）
  > **WHY**：memory_prefilter 服務 memory_worker（背景批次抽取），classifier_service 服務 chat 入口（同步請求），生命週期 / 設定來源不同，不互相依賴
- [x] `def estimate_baseline_for_skip(content: str, expensive_model: str) -> Decimal`
  - `input_tokens = max(len(content) // 4, 1)`
  - `output_tokens = 200`（估算）
  - 套 `expensive_model` 的 input/output 單價（讀 v1.3.0 `model_prices.yaml` / `compute_cost`）回 `actual_cost_usd` 的同型別 `Decimal`
- [x] 單元測試 `tests/services/test_classifier_service.py`：
  - 各規則命中 / 未命中組合（greeting / 純 emoji / 短訊息 / 長問題 / 含圖片 / classifier disabled）
  - `estimate_baseline_for_skip` 對空字串 / 純 emoji 不會除以零
  - 整個 classify() 在 db 抓不到 system_setting 時 fallback 行為正確

### 1-2 規則引擎演進路徑（task 內明示）

- [x] 模組頂部加註解說明（繁中）：
  ```
  # 演進路徑（規則 → model）：
  # 1. 規則引擎（v1.3.4 本版）— 零成本、可解釋
  # 2. 規則撐不住時：local DistilBERT 二分類器 / 三分類器（待定）
  # 3. 量大穩定後：雲端極小 model（haiku 級判斷）
  # classifier.model 欄位即為未來切換點，當前固定 "rule-based"。
  ```
- [x] 在 `system_setting` 描述中亦明示此演進路徑（V43 seed `classifier.model` 的 description）

---

## Phase 2：Backend — Multimodal 強制路由

### 2-1 整合判斷點

- [x] `chat_service.send_message` 內已先載入 `loaded_attachments`（v1.1.6 既有），把「`image_attachments` 是否非空」當作 multimodal 訊號，**先於** classifier_service 呼叫前判斷
- [x] classifier_service.classify 接收 `attachments` 參數，若有 image → 直接回 `expensive` + `matched_rule="image_attachment"`
- [x] 不論 `classifier.enabled` 為何，multimodal 強制路由**永遠生效**（避免關閉 classifier 後反而又把圖片當文字處理）

### 2-2 vision model 解析（沿用 v1.1.6）

- [x] expensive 路線取 model 後仍走既有 `model_supports_vision(model)` 判斷：
  - 支援 → 走 multimodal 拼接
  - 不支援 → 既有 graceful degradation（「圖片附件已略過」）— 這層由 v1.1.6 處理，本版不動

### 2-3 邊界用例

- [x] **純圖片無文字**：classifier 進入點看到 `content.strip() == ""` 但 `image_attachments` 非空 → 走 multimodal expensive（**不**進 skip 規則）
- [x] **圖片 + greeting**（"hi" + 一張圖）：multimodal 優先 → expensive
- [x] **僅 PDF / text 附件 + greeting**：不觸發強制路由 → 跑 classifier 規則（PDF / text 走文字路徑判斷）

---

## Phase 3：Backend — System Settings 整合

### 3-1 system_setting_service 補 helper

- [x] `system_setting_service.get_classifier_config(db) -> dict`：
  - 一次撈齊 `classifier.enabled` / `classifier.cheap_model` / `classifier.skip_response_template` / `classifier.thresholds` / `classifier.model`
  - 內建 fallback（與 V43 seed 同值），抓不到 / 解析失敗時 log warning + 回 fallback
  —（已改為：helper 落在 `classifier_service.get_classifier_config(db)` 而非 `system_setting_service`，因實際使用方為 chat_service / classifier_service，且 fallback 常數（DEFAULT_THRESHOLDS / DEFAULT_CHEAP_MODEL 等）也在 classifier_service；system_setting_service 維持泛型 get/get_bool/get_json 介面不擴張）
- [x] 既有 `get_setting` / `get_setting_with_default` 不動 — 新 helper 只是聚合

### 3-2 admin settings UI（最小改動）

- [x] 確認 admin `/admin/settings` 頁面（v1.2 既有）能列出新 keys 並可編輯（既有 settings UI 走泛型 key/value，**理論上**不需改 code；驗收項目逐一確認 UI 顯示） —（既有泛型 settings UI 走 `/api/v1/admin/settings` 與 SystemSetting 表，5 個 classifier.* keys 由 V43 seed 帶入後即可被列出 / 編輯；UI 視覺驗收交由使用者執行）
- [x] `classifier.thresholds` 在 UI 上會以多行 JSON 編輯，提醒在 PR 描述中說明調整時的 JSON schema —（V43 seed 內 description 已敘明 thresholds 五個鍵：min_length / greeting_whitelist / cheap_max_length / cheap_max_history_turns / skip_response_template_fallback）

---

## Phase 4：Backend — chat_service 整合 classifier

### 4-1 整合點

- [x] `app/services/chat_service.py::send_message`：
  - **位置**：在「驗證 session / 取 agent / 載入附件」之後，「組 messages / RAG 檢索 / 呼叫 stream_chat_completion」之前插入
  - 傳入 classifier_service.classify 的參數：
    - `content`：使用者本則訊息
    - `attachments=loaded_attachments`
    - `history_turns`：可由 `chat_message_repository.count_by_session` 估算（避免額外 query 全部 history）
    - `db`
  - 拿到 `decision`：
    - `route == "skip"` → 走 §4-2 skip 分支
    - `route == "cheap"` → 用 `classifier.cheap_model` 取代 agent.model，繼續既有 RAG + stream 流程
    - `route == "expensive"` → 維持既有 agent.model 流程（含 v1.1.6 multimodal）
- [x] 把 `decision["route"]` 透過 v1.3.0 wrapper `call_llm_metered(... route=decision["route"], ...)` 傳入；wrapper 內寫 `llm_call_log.route`

### 4-2 skip 路線實作

- [x] **不呼叫 LLM**；直接 yield SSE：
  - `event: delta\ndata: {"content": skip_response_template}\n\n`
  - `event: done\ndata: {"finish_reason": "stop", "truncated": false}\n\n`
  —（已改為：done event 不傳 `truncated` 欄位，沿用既有 expensive 路線 done payload 結構並追加 `route`；finish_reason='stop' 已能表達非截斷狀態。`chat_message.finish_reason='stop'` 寫入維持，前端顯示行為一致）
- [x] 仍寫 `chat_message`（assistant role、`content=skip_response_template`、`finish_reason="stop"`、`truncated=false`），維持與 cheap / expensive 路線資料一致（前端時序顯示不破）
- [x] **必寫** `llm_call_log`（見 §5）

### 4-3 cheap 路線實作

- [x] 不改 RAG 檢索 / system prompt 組裝（與 expensive 共用，避免兩條路差異過大難以調 prompt）
- [x] 僅替換 `model` 參數：呼叫 `call_llm_metered` 時 `model=cheap_model`
- [x] **WHY 不獨立 prompt**：規則引擎只能保守判斷簡單問題，prompt 結構保持一致才能在事後 metrics 上對照「同 prompt 不同 model 的答題效果」

### 4-4 expensive 路線

- [x] 維持既有行為，只新增 `route="expensive"` 傳入 metering wrapper
- [x] multimodal 強制路由命中時亦走此路徑（route 標記 `expensive`，wrapper 不另外標 `multimodal`，靠 `model` 欄位即可區分）

### 4-5 history_turns 計算

- [x] 使用既有 `chat_message_repository.count_by_session`（若無則新增）回「該 session 已有的對話輪數」
- [x] 為求效能，可改抓 `len(history) // 2`（既有 §721 已撈 last N）— 二擇一視效能 / 順序而定，task 中標註「兩擇一即可，以不重複 query 為原則」 —（採 `count_by_session(...) // 2`：classifier 在 history fetch 之前執行，避免改寫 §721 撈 history 順序，僅多一次 COUNT(*)）

---

## Phase 5：Backend — Skip 路線 Metrics Log

### 5-1 在 `llm_metering` 補 skip 專用接口

- [x] `llm_metering.py` 新增：
  ```python
  async def log_skip_call(
      *,
      session_uid: str,
      user_uid: str,
      agent_uid: str | None,
      content: str,
      expensive_model: str,
      db: AsyncSession,
  ) -> None
  ```
  —（已由 v1.3.0 預備：實際介面為 `log_skip_call(*, session_uid, user_uid, agent_uid=None, user_input)`；不收 `content` / `expensive_model` / `db` 三參數，內部走 `llm_pricing.estimate_baseline_for_skip(user_input)` 並使用 `EXPENSIVE_MODEL_ID` 設定，DB session 由 wrapper 自管。本版本沿用此介面，不擴張）
- [x] 內部組裝（對齊 [Arch §5-3](../../Arch/01-observability-and-metrics.md)）：
  - `purpose="chat"`
  - `route="skip"`
  - `model=None`
  - `input_tokens=0` / `output_tokens=0` / `cache_*=0`
  - `actual_cost_usd=Decimal("0")`
  - `baseline_cost_usd=classifier_service.estimate_baseline_for_skip(content, expensive_model)`
    —（已改為：`baseline_cost_usd = llm_pricing.estimate_baseline_for_skip(user_input)`，與 classifier_service 內 `estimate_baseline_for_skip` 共用同一份 llm_pricing 計算邏輯，輸出值等價）
  - `latency_ms=0`
  - `rag_hit_count=None` / `rag_max_score=None`
  - `error=None`

### 5-2 chat_service 串接

- [x] skip 路線在 yield 完 SSE 後（最後一個 `event: done` 之前），呼叫 `llm_metering.log_skip_call(...)`
- [x] 失敗（DB 寫入錯）時 log warning 但**不**讓 SSE 失敗 — metrics 是運營資料，不能擋使用者體驗

### 5-3 cheap / expensive 路線 metrics

- [x] cheap：`call_llm_metered(... route="cheap", model=cheap_model, ...)` — wrapper 自動算 actual / baseline
- [x] expensive：`call_llm_metered(... route="expensive", model=agent.model, ...)`
- [x] 兩者 baseline 計算規則沿用 v1.3.0：以 `EXPENSIVE_MODEL_ID`（v1.3.0 設定的「假設都用這個 model」） × usage 的單價計

### 5-4 誤判率 follow-up 標記

- [x] task 文件 + chat_service / classifier_service 模組頂部加 TODO 註解（繁中）：
  ```
  # TODO(follow-up)：誤判率指標
  # 訊號：同 session 連續 user 訊息語意相似度 > 0.8 或 < 5 秒內重發 → 視為「使用者重問」
  # 觀察基準：route='skip' / 'cheap' 後立即被使用者重問的比率
  # 達成條件：v1.3.0 metrics 累積 7+ 天資料、且 chat 量級足夠統計顯著
  ```
  —（已落於 `app/services/classifier_service.py` 模組頂部；chat_service 不重複，避免兩處 TODO 散落造成同步成本）

---

## Phase 6：驗收

> Runtime 行為驗收統一彙整於 [runtime-acceptance.md](runtime-acceptance.md)。
> 本檔案 Phase 0 ~ 5 的程式碼層 checkbox 即為實作交付清單；smoke / curl / 瀏覽器互動類驗證請見 acceptance 檔案對應章節。

