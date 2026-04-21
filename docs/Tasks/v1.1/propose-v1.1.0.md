# v1.1 Propose

> 本文件為 v1.1 的構想與討論紀錄。定稿後拆為 `tasks-v1.1.*.md` 規格文件再進行實作。

---

## 0. 前置假設

v1.0 已完成並作為基線：

- Agents / Skills CRUD、公開/私人/刪除、下載 AGENTS.md
- RBAC（admin / member）
- Cursor-based 分頁（`pid` 排序）
- `system_setting` 表與 admin 設定介面

v1.1 於此之上新增對話與記憶層，不改動既有 v1.0 資料表（僅新增）。

---

## 1. 版本目標

1. **平台管理強化**：Skills 編輯能力（整包重上 + 單檔線上編輯）
2. **Agent 對話功能**：支援單一 Session 與 Agent 進行對話
3. **Projects 容器**：類似 ChatGPT Projects，聚合多個 Session
4. **Session 記憶系統**：摘要 + 向量化 + pgvector 檢索
5. **Agentic RAG 檢索**：Session scope，admin 可調

---

## 2. 技術選型

**不引入 agent framework**（LangChain / LlamaIndex / LangGraph 等）。理由：本專案已是分層清晰的 FastAPI + SQLAlchemy 架構，引入框架會與既有 repository / service 層衝突，且 debug 複雜度上升。

| 任務 | 技術 |
| --- | --- |
| LLM 呼叫（streaming） | `httpx` + OpenRouter Chat Completions API（SSE） |
| 訊息 / Session 持久化 | SQLAlchemy + PostgreSQL |
| Embedding | OpenRouter `openai/text-embedding-3-small`（1536 維，共用 `OPENROUTER_API_KEY`） |
| 向量檢索 | pgvector cosine similarity |
| 非同步任務 | Redis queue + 後端 worker（FastAPI lifespan 啟動） |
| 結構化輸出 | Pydantic + OpenRouter `response_format: json_schema` |

若未來確定要做 Tool call / 多 Agent 協作，再評估 `pydantic-ai`；**不先綁架構**。

---

## 3. 核心規則與設定

### 3-1 Agent / chat_session / chat_project 關係

- 每個 Agent 可裝多個 Skills（v1.0 已定）
- **每個 `chat_session` 對應 1 個 Agent**（1:1）
- `chat_session` **可選擇**屬於某個 `chat_project`，或不屬於任何 Project（游離對話）——v1.1.4 起
  - 側欄採 ChatGPT 風格雙區導航：「最近對話」列游離 session、「Projects」列 project 及其 session
  - 使用者可透過 `POST /api/v1/chat/sessions/{uid}/move` 在「某 Project」與「游離」之間搬移

### 3-2 容量上限

| `system_setting` key | 預設 | 最大 | 可調整者 | 備註 |
| --- | --- | --- | --- | --- |
| `chat.max_sessions_per_project` | 3 | 5 | admin | 參考 ChatGPT Projects 觀察，第 4 個 Session 後響應與記憶表現下降 |
| `chat.max_projects_per_user` | 5 | 20 | admin | 防止濫建 |
| `chat.max_orphan_sessions_per_user` | 10 | 30 | admin | 游離對話上限；與 Project 內 Session 分開計算（v1.1.4 新增） |

### 3-3 Agentic RAG 檢索

由 admin 統一配置，member 無感消費檢索結果。

| `system_setting` key | 預設 | 說明 |
| --- | --- | --- |
| `rag.enabled` | `true` | 是否啟用 RAG 注入 |
| `rag.top_k` | `5` | 每次檢索取幾筆 |
| `rag.min_score` | `0.7` | 餘弦相似度門檻 |

### 3-4 記憶抽取設定

| `system_setting` key | 預設 | 說明 |
| --- | --- | --- |
| `memory.extractor_model` | `anthropic/claude-haiku-4-5` | 小模型負責關鍵字 / topic 抽取 |
| `memory.batch_size` | `5` | 每 N 則訊息觸發批次 |
| `memory.idle_seconds` | `60` | idle N 秒觸發批次（與 batch_size 任一條件成立即觸發） |
| `memory.skip_rules` | JSON 物件 | 預篩規則參數，admin 可調（見 §6-3） |

### 3-5 權限

| 操作 | admin | 擁有者 | 他人 |
| --- | --- | --- | --- |
| 讀 `chat_project` / `chat_session` 清單 | ✅ 全部 | ✅ 自己的 | ❌ |
| 讀 `chat_message` 內容 | ❌ | ✅ | ❌ |
| 讀 `chat_memory` | ❌ | ✅ | ❌ |
| 刪除 `chat_project` / `chat_session` | ✅ | ✅ | ❌ |
| 調整 `system_setting` | ✅ | ❌ | ❌ |

> admin 僅能看聚合數據（Project / Session 數、Token 用量），不能看訊息內容，避免隱私爭議。

---

## 4. 資料模型（新增表）

> 命名規則：對話領域的表統一加 `chat_` 前綴，避免與 HTTP session、通知 message 等概念撞名。

### 4-1 `chat_project`

| 欄位 | 型別 | 備註 |
| --- | --- | --- |
| `pid` | `bigserial` PK | cursor 分頁排序 |
| `chat_project_uid` | `uuid` | 對外識別 |
| `owner_user_uid` | `uuid` FK | |
| `name` | `varchar(100)` | |
| `description` | `text` nullable | |
| `created_at` / `updated_at` / `deleted_at` | | 軟刪除 |

### 4-2 `chat_session`

| 欄位 | 型別 | 備註 |
| --- | --- | --- |
| `pid` / `chat_session_uid` | | |
| `chat_project_uid` | `uuid` FK | |
| `agent_uid` | `uuid` FK | 1:1 |
| `title` | `varchar(200)` | 由首則訊息自動生成 |
| `created_at` / `updated_at` / `deleted_at` | | 軟刪除 |

### 4-3 `chat_message`

| 欄位 | 型別 | 備註 |
| --- | --- | --- |
| `pid` / `chat_message_uid` | | |
| `chat_session_uid` | `uuid` FK | |
| `role` | enum (`user` / `assistant` / `system` / `tool`) | |
| `content` | `text` | |
| `token_in` / `token_out` | `int` | 供成本追蹤 |
| `cost_usd` | `numeric(10,6)` | |
| `model` | `varchar(100)` | 當次實際呼叫的 model |
| `created_at` | | 不可編輯、不軟刪除（審計用） |

### 4-4 `chat_memory`

| 欄位 | 型別 | 備註 |
| --- | --- | --- |
| `pid` / `chat_memory_uid` | | |
| `chat_session_uid` | `uuid` FK | |
| `source_chat_message_uids` | `uuid[]` | 回溯來源訊息 |
| `keywords` / `entities` | `text[]` | |
| `topic` | `varchar(200)` | |
| `embedding` | `vector(1536)` | **維度鎖定 1536** |
| `created_at` | | |

### 4-5 成本追蹤

- Session / Project 層級的 token / cost 由 SQL 聚合 `chat_message` 表即席計算，不另存快照
- 若聚合查詢變慢再加 `chat_session_usage_snapshot` 物化表

---

## 5. 對話 Pipeline

### 5-1 單輪流程

```
user 送訊息
  │
  ▼
寫 chat_message (role=user) → PG（同步）
  │
  ▼
組 prompt：
  ├─ system prompt（Agent 設定 + Skills 內容注入）
  ├─ 最近 N 則對話歷史
  └─ RAG 檢索結果（依 §3-3 設定）
  │
  ▼
呼叫 OpenRouter（streaming SSE）
  │
  ▼
寫 chat_message (role=assistant) → PG
  │
  ▼
丟非同步任務：Redis queue → memory worker
```

### 5-2 Context Window 管理

- 組 prompt 前估算 token 數，超過 model 上限的 70% 時：
  1. 丟棄最舊的對話歷史（保留 system + 最近 3 輪）
  2. 若仍超限，用 `chat_memory` 的摘要替代被丟棄的段落
- Agent 切換 model 後，上限依新 model 重算

### 5-3 Streaming 與錯誤處理

- 回覆採 SSE streaming，前端逐字顯示
- LLM 呼叫失敗 → 重試 2 次（指數 backoff）→ 仍失敗回 5xx，**不寫 assistant chat_message**
- Embedding 失敗 → 任務重入 queue，最多 3 次；超過則標 `failed` 存 DLQ，不阻塞使用者

---

## 6. 記憶系統設計

### 6-1 寫入時機分層

| 資料 | 時機 | 通道 |
| --- | --- | --- |
| 對話原文 | 即時同步 | PG（`chat_message` 表） |
| 摘要 / 向量化 | 非同步 batch | Redis queue → worker → pgvector |

### 6-2 摘要 Pipeline

```
對話訊息
   │
   ▼
Rule-based 預篩（無 LLM，控 input token）
   │ pass
   ▼
Small LLM：關鍵字 + topic 抽取（固定 JSON output schema）
   │
   ▼
Embedding：關鍵字串接後向量化
   │
   ▼
pgvector 寫入 chat_memory 表
```

### 6-3 Rule-based 預篩規則

| 規則 | 行為 | 參數（預設） |
| --- | --- | --- |
| 訊息長度過短 | 略過 | `N = 15` 字 |
| 純問候 / 確認語（`hi` / `好` / `收到` / `謝謝`） | 略過 | 白名單比對 |
| 純 emoji / 貼圖 | 略過 | regex |
| 錯誤訊息回聲（`role=tool` 且 `is_error=true`） | 略過 | |
| 超過長度上限 | 頭尾保留、中間截斷 | `M = 2000` tokens |

所有參數透過 `memory.skip_rules`（JSON）由 admin 調整。

### 6-4 固定 Output Schema（控 output token）

```json
{
  "keywords": ["..."],
  "entities": ["..."],
  "topic": "...",
  "is_actionable": true
}
```

### 6-5 RAG 檢索 Prompt 注入

- 檢索結果以 `<memory>` 區塊接在 system prompt 後、對話歷史前
- 每筆記憶格式：`[topic] keywords: …`，**不貼原始訊息內容**（隱私 + token 節流）
- 檢索失敗 → 空區塊、不中斷對話

---

## 7. Skills 編輯

### 7-1 功能範圍

| 能力 | 說明 |
| --- | --- |
| 重新上傳整包 | Skill 詳情頁「重新上傳」按鈕，沿用現有上傳流程覆蓋原 zip |
| 線上編輯單一檔案 | Code viewer 加「編輯」切換為 textarea，儲存後回寫進 zip |
| 使用量提示 | 觸發編輯前呼叫 `GET /skills/{uid}/usage`，Dialog 顯示「N 個 Agent 將套用新內容」 |
| 同步策略 | 不做 cascade（Agents 靠 skill_uid 關聯，內容變更即時生效） |

### 7-2 線上編輯邊界

- **可編輯副檔名白名單**：`.md` / `.txt` / `.json` / `.yaml` / `.yml` / `.py` / `.ts` / `.js` / `.sh`
- **不支援**：新增檔案、刪除檔案、改檔名、二進位檔編輯 → 走「重新上傳整包」
- **並發控制**：樂觀鎖，儲存時比對 `updated_at`，衝突回 409 要求使用者重載
- **版本歷史**：不做版本保留；如需回滾請使用者自行保留本地副本

---

## 8. 驗收指標

- 對話首字延遲 P95 < 2s（streaming 啟動時間）
- 記憶寫入延遲（非同步）P95 < 30s
- RAG 檢索 P95 < 200ms
- Skills 線上編輯儲存成功率 > 99%

---

## 9. 下一步

1. 確認尚未拍板項目（見對話）
2. 拆分 tasks 規格：
   - `tasks-v1.1.1.md`：對話 + Session / Project 基礎（`chat_project` / `chat_session` / `chat_message` 表）
   - `tasks-v1.1.2.md`：記憶系統 + RAG 檢索（`chat_memory` 表、worker、prompt 注入）
   - `tasks-v1.1.3.md`：Skills 編輯（可與 1.1.1 / 1.1.2 並行）
