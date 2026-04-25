# v1.3 Propose

> 本文件為 v1.3 的構想與討論紀錄。定稿後拆為 `tasks-v1.3.*.md` 規格文件再進行實作。
>
> 前置版本：[v1.1 propose](../v1.1/propose-v1.1.0.md)、[v1.1 extended](../v1.1/propose-v1.1-extended.md)、[v1.2 propose](../v1.2/propose-v1.2.0.md)

---

## 0. 前置假設

v1.1 + v1.1 延伸 + v1.2 皆已上線作為 v1.3 基線。各版本範圍與規格詳見對應 propose / tasks 文件，本檔不重述。

---

## 1. 版本目標

1. **多 Agent 對話**：放寬 Session:Agent 為 1:N，一個 Session 可同時掛多個 Agent 協作
2. **分層 Model Classifier**：前置 classifier 判斷訊息是否需要送大模型，降低成本
3. **User / Project 層記憶**：跨 Session 記憶聚合與檢索
4. **記憶 / LLM 輸出的可觀察性**：pipeline 可追蹤、截斷可偵測、UI 即時性可保證
5. **Agentic Skill 工廠正式版**：承接 v1.1.7 PoC（session scope）→ 升級跨 session 消費 `user_memory` / `project_memory`

### 範圍內

- Session ↔ Agent 多對關聯、Agent 切換 / 呼叫策略
- 訊息分類 pipeline（classifier → router → LLM）
- `project_memory` / `user_memory` 表與聚合 worker
- RAG 三層檢索（session / project / user）融合策略
- 記憶系統可觀察性：worker log 分級、admin debug endpoint
- Skills 載入機制強化：一個 Skill 支援多 md 拼接
- 記憶 UI 即時性：既有 SSE channel 擴充 `memory_updated` 事件（不引入 WebSocket）

### 範圍外（延後）

- v1.4+：儀表板 AI 查詢、公開 API + API Key 管理
- **WebSocket**：多人協作需求出現後再評估（v1.1 單人 session 場景不划算）

---

## 2. 跨類別硬規範

### 2-1 LLM 輸出語言：記憶 / Skill 相關 prompt 一律要求繁體中文輸出

任何將輸出寫入「記憶系統」或「Skill 草稿」的 LLM 呼叫，system prompt 必須明確指示輸出為**繁體中文**，不得依使用者輸入語言自動切換。理由：跨層記憶聚合、後續檢索、Skill 推薦等下游消費端都假設語言一致；若某 session 用英文對話導致 `topic` / `keywords` 變英文，跨層 RAG 的相似度匹配會失準。

#### 涵蓋範圍

| Prompt | 位置 | 現況 | 處理 |
| --- | --- | --- | --- |
| 圖片描述 | [openrouter/client.py:573](../../../backend/app/clients/openrouter/client.py#L573) | ✅ 已寫 | 維持 |
| Skill 候選 name / description | [openrouter/client.py:122-123](../../../backend/app/clients/openrouter/client.py#L122-L123) | ✅ 已寫 | 維持 |
| Skill 候選 system_prompt | [openrouter/client.py:124](../../../backend/app/clients/openrouter/client.py#L124) | ⚠️ 漏寫 | v1.2 fixed.md 補修 |
| Memory extract topic / keywords / entities | [openrouter/client.py:78-86](../../../backend/app/clients/openrouter/client.py#L78-L86) `MEMORY_EXTRACT_SYSTEM_PROMPT` | ⚠️ 漏寫 | v1.2 fixed.md 補修 |
| Project / User 記憶聚合 | v1.3 新增（§3-1） | — | 設計時內建 |
| Skill 工廠正式版 analyzer | v1.3 新增（§5-2） | — | 設計時內建 |
| Classifier 若有 LLM rerank | v1.3 新增（§4-2） | — | 若有則內建 |

#### 例外

- 對使用者直接顯示的 assistant 回覆 — **不**強制（依使用者語言為準）
- 機器對機器的 ISO / 時間 / UUID 字串 — 不適用

---

## 3. 記憶系統設計

> 本章「為什麼這樣設計」的長期藍圖見 [docs/Arch/00-memory-system.md](../../Arch/00-memory-system.md) — 終極架構、RAG 適用邊界、元件職責、演進路線。本章只描述 **v1.3 這版要實作的具體變更**。

### 3-1 User / Project 層記憶

- **Project 記憶**：定期從該 Project 下所有 Session 的 `session_memory` 做二次聚合（同主題合併）
- **User 記憶**：跨 Project 的長期偏好（e.g. 使用者常用語言、偏好回覆風格）
- **寫入時機**：Session 結束 / idle N 小時 / 手動觸發
- **Schema**：`project_memory`、`user_memory` 結構類似 `session_memory` 但多一個 `source_session_uids[]`

### 3-2 三層 RAG 檢索融合

- 三層 top_k 合併後採 **RRF（Reciprocal Rank Fusion, k=60）** 融合排序：`score = Σ 1/(k + rank)`
- 採 RRF 而非加權求和的理由：跨層分數尺度不一致（不同層 embedding 分佈差異），RRF 只看排名不看分數，免調權重
- 各層 top_k 建議：session 撈 top 10、project 撈 top 5、user 撈 top 5（融合後再取 top 5~10 塞 prompt）
- 詳細設計與未來 reranker 接入位置見 [docs/Arch/00-memory-system.md §3](../../Arch/00-memory-system.md)

### 3-3 記憶生命週期（關鍵設計，勿違反）

v1.1 現況：Session 刪除時 `chat_memory` 連動硬刪（見 [chat_service.py:542-554](../../../backend/app/services/chat_service.py#L542-L554)）。這在 session scope RAG 成立，但 v1.3 跨層記憶必須獨立生命週期：

| 刪除動作 | 連動清除 | **不**連動 |
| --- | --- | --- |
| Session 刪除 | `chat_memory`（session scope） | `project_memory`、`user_memory` |
| Project 刪除 | Project 內 sessions 的 `chat_memory`、`project_memory` | `user_memory` |
| User 停用 / 刪除 | 全部三層 | — |

若 session 刪除誤清掉 `project_memory`，跨 session 聚合會被意外抹除 → 無法做跨層 RAG。Schema 設計必須確保這點：`project_memory` / `user_memory` **不**建立指向 session 的 FK cascade。

### 3-4 記憶 pipeline 可觀察性（Memory Debug）

v1.1 的 memory pipeline 是黑盒子 — UI 只看得到最終 `chat_memory` 表，中間四個階段（prefilter / buffer / extract / embedding）全部靜默。需分**四個**層次處理，**不能混**：

| 層次 | 回答的問題 | v1.3 實作 |
| --- | --- | --- |
| **0. 成本 metrics** | 花了多少？省了多少？哪個 model 慢？ | `llm_call_log` 表 + `llm_metering.py` wrapper + 7 個 admin SQL；詳見 [docs/Arch/01-observability-and-metrics.md](../../Arch/01-observability-and-metrics.md) |
| **1. 可觀察性** | 卡在哪一步？ | worker log 升 info、admin endpoint `GET /admin/debug/memory/sessions/{uid}` 回全程 trace、Redis queue / DLQ 長度塞進 `/health` |
| **2. 品質評估** | 抽取品質夠好嗎？變好變差？ | `backend/app/evals/memory/` + 10-20 組 eval set + LLM-as-judge CLI（裁判用不同家 model 避免偏差） |
| **3. 檢索診斷** | 為什麼這次 RAG 沒命中？ | `chat_memory_hit` Redis stream（TTL 7 天）紀錄每次檢索 top-K 分數；admin UI retrieve test 頁面 |

投資順序：**層 0（半天）→ 層 1（2 小時）→ 層 2（1 天）→ 層 3（2 天）**。

層 0 是其他 task 的**前置依賴** — 沒有 metrics，後續加 classifier / RAG 改善都無法證明效果。

### 3-5 記憶 UI 即時性（確定：SSE，不引入 WebSocket）

v1.1 現況：memory_worker 非同步寫入（幾秒 ~ 60 秒延遲），前端只在打開抽屜時 / 手動 🔄 才 refetch。使用者容易誤以為「沒記憶」。

#### 方案評估

| 方案 | 即時性 | 成本 | 部署 | 結論 |
| --- | --- | --- | --- | --- |
| WebSocket | 真即時 | 高 | 高（長連線、反向代理、token refresh） | ❌ 太重，單人 session 不值得 |
| **SSE 擴充 `memory_updated` 事件** | 真即時 | 中（SSE 基礎已有） | 低 | ✅ **v1.3 確認採用** |
| Polling 30s | ~30s 延遲 | 低 | 無 | 僅作 SSE 連線斷開時的 backup |
| 手動 refetch | 使用者主動 | 已完成 | 無 | 既有實作，不退場 |

#### 通道選擇：獨立 endpoint，生命週期跟頁面綁

新增 `GET /api/v1/chat/sessions/{uid}/events` SSE endpoint 專做事件推播，不走既有 `POST /messages` 的訊息 SSE。理由：訊息 SSE 只在請求期間建立、閒置即斷；若依賴它，使用者送完訊息後靜置等 worker 寫完，事件會送不到。獨立 endpoint 的連線由前端頁面掛載 / 卸載控制。

#### 流程

1. memory_worker 寫完 `chat_memory` 後，發 Redis pub/sub（channel `chat:session:{uid}:memory`）
2. `GET /chat/sessions/{uid}/events` SSE handler：驗證 session 擁有者 → 訂閱該 channel → 收到訊息後推 `event: memory_updated\ndata: {"memory_uid": "..."}\n\n`
3. 前端 session 頁面 mount 時建立 EventSource，收到 `memory_updated` 時 `dispatch(chatApi.util.invalidateTags([{type: "ChatMessages", id: "memories-${sessionUid}" }]))`
4. 前端頁面 unmount 時關閉 EventSource

#### 事件類型擴充空間

同一個 `/events` endpoint 可統一承載所有 session 級別的非同步事件，未來擴充不用再開新 endpoint：

| event 名稱 | 觸發時機 | 前端處理 |
| --- | --- | --- |
| `memory_updated` | memory_worker 寫完 | invalidate 記憶 query |
| `memory_failed` | memory_worker 超過重試進 DLQ | UI 顯示 ⚠ badge |
| `session_archived`（未來） | session 被他處操作 | 提示使用者重整 |

#### Backup 策略

SSE 連線斷開時（網路抖動、反向代理超時）前端自動 fallback 到 polling 30s，直到 SSE 重連成功。以 hook `useSessionEvents` 封裝 EventSource + polling fallback，對頁面透明。

#### 陷阱提醒

- SSE 無法傳 HTTP header 以外的 auth，需要以 cookie / query string 傳 access token。建議 query string `?token=xxx`，後端 SSE handler 自行驗證。
- 瀏覽器對單一 domain SSE 連線有上限（通常 6 條），多分頁開多 session 可能撞到。短期不處理，監控若發生再降級為 polling。

---

## 4. Agent 與對話流程

### 4-1 多 Agent 對話

- **觸發方式**：使用者 @mention 指定 Agent？還是 LLM 自動 routing？
- **順序**：多 Agent 回應是串行（A → B）還是並行（同時跑取 best）？
- **對話歷史歸屬**：一則 assistant 訊息綁一個 Agent，前端顯示誰說的
- **Schema 變更**：`session_agent` 中介表（session_uid, agent_uid, role），取代 v1.1 的 `session.agent_uid`
- **Agent Template 預設值**：新增 template 類型（general / long-analysis / summary），各自預填合理 `max_tokens`（2048 / 8192 / 2048）
- **Skill 自動推薦**：由 §5-2 Skill 工廠提供候選 Skills，依訊息意圖自動套用到合適 Agent（承 v1.1.7 PoC 人工審核 → 本版改自動推薦 + 使用者隨時關閉）

### 4-2 分層 Model Classifier

- **Classifier 模型**：極小模型（e.g. local DistilBERT / 規則引擎）先判斷「是否需要 LLM 回覆」
- **三層分流**：
  1. 無需回覆（系統訊息、純表情） → 不呼叫 LLM
  2. 簡單問答 → cheap LLM（haiku / deepseek）
  3. 複雜推理 → 主 LLM
- **Multimodal 強制路由**（承 v1.1.6）：訊息含圖片附件時**必走** vision model（跳過 classifier 的文字分流），避免圖片被誤判為「無需回覆」
- **設定 key**：`classifier.enabled` / `classifier.model` / `classifier.thresholds`
- **量測指標**：classifier 誤判率、整體成本下降百分比

### 4-3 LLM 輸出截斷偵測（已落地，僅留 UI hint 待補）

v1.2 期間已完成：後端 [chat_service.py](../../../backend/app/services/chat_service.py) 串流時讀取 `finish_reason`、寫入 message metadata `truncated`，前端 session 頁面已顯示截斷 badge。

剩餘待做：AgentForm 的 `max_tokens` 欄位旁加 hint「1024 ≈ 750 中文字；長分析 / code review 建議 4096+ 或留空」（15 分鐘，併入 §4-1 多 Agent task 一起做）。

---

## 5. Skill 系統

### 5-1 Skills / 規範載入強化（多 md 拼接）

v1.1 現況：`_skill_prompt_text` ([chat_service.py:152-184](../../../backend/app/services/chat_service.py#L152-L184)) **一個 Skill zip 只讀一份 md**（README / `{skill_name}.md` / 第一個 .md）。把 Design-Base 整包 `docs/Design-Base/*` 打包成一個 Skill 時，reviewer 只會拿到其中一份規範。

v1.3 改動：

- `_skill_prompt_text` 支援讀取 zip 內**所有** md，按檔名排序拼接，每份前加 `### {filename}` 標題分隔
- 單個 md 超過 N 字（預設 8000）時發警告 log，避免 prompt 爆炸
- 規範 / 文件類 Skills 建議命名（無強制）：`design-base-frontend`（含 10+11）、`design-base-backend`（含 20+21）、`design-base-auth`（含 30+40）

### 5-2 Agentic Skill 工廠正式版（承接 v1.1.7 PoC）

> 承接 v1.1.7 PoC：Redis `agentic:skill:log` stream 累積的 approve/reject 訊號可用於本版 threshold（`min_memory_count` / `topic_concentration` / confidence 下限）的實測調校。

v1.1.7 PoC 以**單一 session** chat_memory 為樣本、人工審核入庫。本版升級兩個面向：

#### 升級 A：消費跨層記憶

- Analyzer 的輸入從 `chat_memory`（session scope）擴大為 `project_memory`（§3-1）與 `user_memory`（§3-1）
- 三層樣本數遞增，可識別「跨 session 重複的使用習慣 / 領域偏好」（例：使用者在 5 個 session 都要求「用學術風格改寫」→ 跨 session pattern 足夠 strong 才生 Skill，避免 PoC 階段的 false positive）
- 新增觸發條件：`user_memory` 有 >= N 筆 + 同主題占比 >= M%（比 session scope 嚴）

#### 升級 B：Skill 自動推薦給 Agent

- v1.1.7 是「生 Skill → 使用者手動掛到某 Agent」
- 本版加 recommender：訊息送達某 Agent 時，若該使用者有未掛載的高 confidence Skill 符合意圖，**提示使用者**（非自動掛，避免權限膨脹）
- 使用者一鍵掛載後，Skill 加入該 Agent 的 skill_uids

#### Schema 影響

- 新增 `agentic_skill_suggestion` 表（取代 v1.1.7 的 Redis 暫存），保留 30 天供事後分析：

```sql
CREATE TABLE agentic_skill_suggestion (
    pid, agentic_skill_suggestion_uid,
    owner_user_uid, scope VARCHAR(20),          -- 'session' / 'project' / 'user'
    scope_uid UUID,                             -- 對應 scope 的資源 UID
    name, description, system_prompt,
    confidence NUMERIC(4, 3),
    source_memory_uids UUID[],
    status VARCHAR(20) DEFAULT 'pending',       -- pending / approved / rejected / expired
    created_skill_uid UUID,                     -- 若 approved，連到產生的 skill
    is_active, is_deleted, created_at, updated_at
);
```

#### 前置依賴

- §3-1 `user_memory` / `project_memory` 實作完成
- v1.1.7 PoC 累積足夠的「使用者會 approve 哪些建議」訊號，用於調校 threshold

#### 非目標

- 不做「Skill 自動入庫」— 審核流程保留（v1.1.7 人工審核 + v1.3 增推薦提示，但不跳過 approve）
- 不做跨使用者共享 Skill（v1.4 公開 API 再談）

---

## 6. 下一步

### 拆分 task 建議

| Task 檔 | 主題 | 前後相依 |
| --- | --- | --- |
| `tasks-v1.3.0.md` | **基礎設施：成本 metrics**（§3-4 層 0）— `llm_call_log` 表 + `llm_metering.py` wrapper + 既有 LLM 呼叫遷移 + admin SQL | **無依賴，必須最先做**；其他 task 的成本驗證都靠它 |
| `tasks-v1.3.1.md` | 記憶 pipeline 可觀察性（§3-4 層 1）+ Skill 多 md 拼接（§5-1）+ §4-3 UI hint | 依賴 v1.3.0（trace 與 metrics 共用 admin endpoint 規範） |
| `tasks-v1.3.2.md` | 記憶 UI 即時性 SSE（§3-5） | 依賴 v1.3.1 的 worker log 基礎 |
| `tasks-v1.3.3.md` | 多 Agent 對話（§4-1） | §5-2 Skill 推薦入口建議由此整合 |
| `tasks-v1.3.4.md` | 分層 Model Classifier（§4-2） | 依賴 v1.3.0 metrics（沒 metrics 無法驗證 classifier 是否真省錢）；依賴 v1.3.3 的 session_agent schema；multimodal 路由依賴 v1.1.6 附件系統 |
| `tasks-v1.3.5.md` | User / Project 記憶（§3-1 + §3-2 + §3-3） | 依賴 v1.3.1 可觀察性、§3-3 生命週期設計 |
| `tasks-v1.3.6.md` | Agentic Skill 工廠正式版（§5-2） | 依賴 v1.3.5 跨層記憶 + v1.1.7 PoC 實測數據 |

> §2 跨類別硬規範（LLM 輸出語言）適用所有 task，特別是 v1.3.5 / v1.3.6 涉及新增 LLM 呼叫者必須遵守。

**v1.3.0 是 v1.3 系列的根基** — 所有後續 task 的「省了多少 / 慢在哪 / 錯多少」都靠它回答。半天工作量，先做完再開展其他。
