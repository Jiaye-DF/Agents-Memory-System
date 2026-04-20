# v1.1 Propose

> 本文件為 v1.1 的構想與討論紀錄。定稿後拆為 `tasks-v1.1.*.md` 規格文件再進行實作。
>
> 延後項目另見：[v1.2 propose](../v1.2/propose-v1.2.0.md)、[v1.3 propose](../v1.3/propose-v1.3.0.md)

---

## 0. 前置假設

v1.0 已完成並作為基線：

- Agents / Skills CRUD、公開/私人/刪除、下載 AGENTS.md
- RBAC（admin / member）
- Cursor-based 分頁（`pid` 排序）
- `system_setting` 表與 admin 設定介面

v1.1 在此基礎上加入對話與記憶層，不改動既有 v1.0 資料表（僅新增）。

---

## 1. 版本目標

1. **Agent 對話功能**：支援單一 Session 與 Agent 進行對話
2. **Projects 容器**：類似 ChatGPT Projects，一個 Project 聚合多個 Session
3. **Session 記憶系統**：摘要 + 向量化 + pgvector 檢索
4. **Agentic RAG 檢索**：v1.1 僅 Session scope，其餘 scope 預留
5. **平台管理強化**：Skills 編輯能力（整包重上 + 單檔線上編輯）

### 範圍內

- Session ↔ Agent 對話（含歷史訊息持久化至 PG）
- Project 管理（CRUD、容量限制）
- Session 記憶寫入 Pipeline（rule-based 預篩 → small LLM 抽取 → embedding → pgvector）
- Agentic RAG 檢索（v1.1 僅 Session scope）
- Skills 編輯功能（整包重上、單檔線上編輯）

### 範圍外（見其他版本 propose）

- v1.2：多 Agent 對話、分層 Model Classifier、User / Project 層記憶跨層檢索
- v1.3+：儀表板 AI 查詢、公開 API + API Key 管理

---

## 2. 核心規則與已決策項

### 2-1 Agent / Session / Project 關係

- 每個 Agent 可裝多個 Skills（v1.0 已定）
- **每個 Session 對應 1 個 Agent**（v1.1 鎖 1:1，v1.2 再放寬）
- 每個 Project 的 Session 數量上限由 `system_setting` 控制
- Session 必須屬於某個 Project；不支援「無 Project 的游離 Session」（簡化模型）

### 2-2 容量上限

| 設定 key | 預設 | 最大 | 可調整者 | 備註 |
| --- | --- | --- | --- | --- |
| `project.max_sessions` | 3 | 5 | admin | 參考 ChatGPT Projects 觀察，第 4 個 Session 後響應與記憶表現下降 |
| `user.max_projects` | 5 | 20 | admin | 防止 member 濫建 |

### 2-3 Agentic RAG 檢索範圍

由 admin 統一配置，member 無感消費檢索結果。

| 設定 key | 預設 | 說明 |
| --- | --- | --- |
| `rag.scopes` | `["session"]` | JSON 陣列；v1.1 僅 `"session"` 生效，`"project"` / `"user"` 為 v1.2+ 預留，設了也不會檢索 |
| `rag.top_k` | 5 | 每層取幾筆 |
| `rag.min_score` | 0.7 | 餘弦相似度門檻 |

### 2-4 權限

| 操作 | admin | member（擁有者） | member（他人） |
| --- | --- | --- | --- |
| 讀 Project / Session 清單 | ✅ | ✅ | ❌ |
| 讀 Session 訊息內容 | ❌（預設拒絕） | ✅ | ❌ |
| 讀 Session 記憶 | ❌（預設拒絕） | ✅ | ❌ |
| 刪除 Project / Session | ✅ | ✅ | ❌ |
| 調整 `system_setting` | ✅ | ❌ | ❌ |

> admin 僅能看「誰在用多少」的聚合數據，不能看訊息內容，避免隱私爭議。

---

## 3. 資料模型（新增表摘要）

### 3-1 `project`

| 欄位 | 型別 | 備註 |
| --- | --- | --- |
| `pid` | bigserial PK | cursor 分頁排序依據 |
| `uid` | uuid | 對外識別 |
| `owner_user_uid` | uuid FK | |
| `name` | varchar | |
| `description` | text nullable | |
| `created_at` / `updated_at` / `deleted_at` | | 軟刪除 |

### 3-2 `session`

| 欄位 | 型別 | 備註 |
| --- | --- | --- |
| `pid` / `uid` | | |
| `project_uid` | uuid FK | |
| `agent_uid` | uuid FK | v1.1 鎖 1:1 |
| `title` | varchar | 由首則訊息自動生成 |
| `created_at` / `updated_at` / `deleted_at` | | 軟刪除 |

### 3-3 `message`

| 欄位 | 型別 | 備註 |
| --- | --- | --- |
| `pid` / `uid` | | |
| `session_uid` | uuid FK | |
| `role` | enum (`user` / `assistant` / `system` / `tool`) | |
| `content` | text | |
| `token_in` / `token_out` | int | 由後端記錄，供成本追蹤 |
| `cost_usd` | numeric(10,6) | |
| `model` | varchar | 記當次實際呼叫的 model |
| `created_at` | | 不可編輯、不軟刪除（審計用） |

### 3-4 `session_memory`

| 欄位 | 型別 | 備註 |
| --- | --- | --- |
| `pid` / `uid` | | |
| `session_uid` | uuid FK | |
| `source_message_uids` | uuid[] | 回溯來源訊息 |
| `keywords` / `entities` | text[] | |
| `topic` | varchar | |
| `embedding` | `vector(1536)` | **維度鎖定 1536**（見 5-2） |
| `created_at` | | |

### 3-5 成本追蹤

- Session / Project 層級的 token / cost 由 SQL 聚合 `message` 表即席計算，不另存快照。
- 若聚合查詢變慢再加 `session_usage_snapshot` 物化表。

---

## 4. 對話 Pipeline

### 4-1 單輪流程

```
user 送訊息
  │
  ▼
寫 message (role=user) → PG（同步）
  │
  ▼
組 prompt：
  ├─ system prompt（Agent 設定 + Skills）
  ├─ 最近 N 則對話歷史
  └─ RAG 檢索結果（依 2-3 scope）
  │
  ▼
呼叫 LLM（streaming）
  │
  ▼
寫 message (role=assistant) → PG
  │
  ▼
丟非同步任務：Redis queue → memory worker
```

### 4-2 Context window 管理

- 組 prompt 前估算 token 數，超過 model 上限的 70% 時：
  1. 丟棄最舊的對話歷史（保留 system + 最近 3 輪）
  2. 若仍超限，用 session_memory 的摘要替代被丟棄的段落
- Agent 切換 model 後，上限依新 model 重算。

### 4-3 Streaming 與錯誤處理

- 回覆採 SSE streaming，前端逐字顯示。
- LLM 失敗 → 重試 2 次（指數 backoff） → 仍失敗回 5xx，**不寫 assistant message**。
- Embedding 失敗 → 任務重入 queue，最多 3 次；超過則標 `failed` 存 DLQ，不阻塞使用者。

---

## 5. 記憶系統設計

### 5-1 寫入時機分層

| 資料 | 時機 | 通道 |
| --- | --- | --- |
| 對話原文 | 即時同步 | PG（`message` 表） |
| 摘要 / 向量化 | 非同步 batch | Redis queue → worker → pgvector |

不阻塞使用者回覆，降低單次對話的 Token 與延遲成本。

### 5-2 摘要 Pipeline

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
pgvector 寫入 session_memory 表
```

### 5-3 Rule-based 預篩規則

| 規則 | 行為 | 參數（預設） |
| --- | --- | --- |
| 訊息長度 < N 字 | 略過 | N = 15 |
| 純問候 / 確認語（`hi` / `好` / `收到` / `謝謝`） | 略過 | 白名單比對 |
| 純 emoji / 貼圖 | 略過 | regex |
| 錯誤訊息回聲（`role=tool` 且 `is_error=true`） | 略過 | |
| 超過 M tokens | 頭尾保留、中間截斷 | M = 2000 |
| 同 session 批次 trigger | 每 K 則 OR idle > T 秒 | K = 5，T = 60s |

### 5-4 固定 Output Schema（控 output token）

```json
{
  "keywords": ["..."],
  "entities": ["..."],
  "topic": "...",
  "is_actionable": true
}
```

### 5-5 RAG 檢索 Prompt 注入

- 檢索結果以 `<memory>` 區塊接在 system prompt 後、對話歷史前。
- 每筆記憶格式：`[topic] keywords: …`，**不貼原始訊息內容**（隱私 + token 節流）。
- 檢索失敗 → 空區塊、不中斷對話。

---

## 6. 平台管理強化

### 6-1 Skills 編輯（來自 v1.0 使用者回饋）

| 能力 | 說明 |
| --- | --- |
| 重新上傳整包 | Skill 詳情頁「重新上傳」按鈕，沿用現有上傳流程覆蓋原 zip |
| 線上編輯單一檔案 | Code viewer 加「編輯」切換為 textarea，儲存後回寫進 zip |
| 使用量提示 | 觸發編輯前呼叫 `GET /skills/{uid}/usage`，Dialog 顯示「N 個 Agent 將套用新內容」 |
| 同步策略 | 不做 cascade（Agents 靠 skill_uid 關聯，內容變更即時生效） |

### 6-2 線上編輯邊界

- **可編輯副檔名白名單**：`.md` / `.txt` / `.json` / `.yaml` / `.yml` / `.py` / `.ts` / `.js` / `.sh`
- **不支援**：新增檔案、刪除檔案、改檔名、二進位檔編輯 → 要這些請走「重新上傳整包」
- **並發控制**：樂觀鎖，儲存時帶 `updated_at` 比對，衝突回 409 要求使用者重載
- **版本歷史**：v1.1 不做版本保留；若需回滾請使用者自行保留本地副本

---

## 7. 待拍板事項（附建議預設）

### 7-1 記憶抽取 Model

- **建議預設**：`anthropic/claude-haiku-4-5`
- 設定 key：`memory.extractor_model`
- 理由：cheap tier、JSON output 穩定；可由 admin 在 system_setting 改。

### 7-2 Embedding 方案

| 方案 | 維度 | 優點 | 缺點 |
| --- | --- | --- | --- |
| A. OpenRouter embeddings | 依模型 | 金鑰管理單一 | 每次呼叫付費、部分模型品質不穩 |
| **B. OpenAI `text-embedding-3-small`（建議）** | **1536** | 中英文品質佳、成本低（$0.02/M token） | 多一套金鑰 |
| C. 後端 container 跑 sentence-transformers | 768 / 1024 | 本地無 per-call 成本 | image 變大、吃 RAM、中文品質差異大 |

**建議 B**。`session_memory.embedding` 鎖 `vector(1536)`，日後若換方案需 migration 重建索引。

### 7-3 批次 Trigger 條件

- **建議**：OR 條件（每 5 則 OR idle 60 秒），避免冷 session 記憶延遲過長。

### 7-4 預篩規則是否可配置

- **建議 B**：存 `system_setting` JSON，admin 可調。
- 理由：與 2-3 RAG 設定風格一致；規則多為數字參數，複雜度可控。

---

## 8. 驗收指標（tasks 階段細化）

- 對話首字延遲 P95 < 2s（streaming 啟動時間）
- 記憶寫入延遲（非同步）P95 < 30s
- RAG 檢索 P95 < 200ms
- Skills 線上編輯儲存成功率 > 99%

---

## 9. 下一步

1. 使用者確認「待拍板事項」後，propose 定稿
2. 拆分成 tasks 規格（依賴順序）：
   - `tasks-v1.1.1.md`：對話與 Session / Project 基礎（含 message / project / session 表）
   - `tasks-v1.1.2.md`：記憶系統與 RAG 檢索（依賴 1.1.1）
   - `tasks-v1.1.3.md`：Skills 編輯（可與 1.1.1 / 1.1.2 並行）
