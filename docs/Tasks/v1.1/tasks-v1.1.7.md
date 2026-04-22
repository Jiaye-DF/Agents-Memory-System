# v1.1.7 任務規格：Agentic Skill 工廠 PoC

> **狀態：已完成（commit 98a4d5a, 2026-04-22）** — 後端 analyzer / generator / approve-reject 流程、前端側邊欄與觀察性 log 皆實作完畢；依賴 Redis 執行環境與對話累積才能完整驗收。
>
> 前置：[propose-v1.1-extended.md §5](propose-v1.1-extended.md)。
> 最終目標：驗證 Agentic loop 最小閉環 — 系統從 chat_memory 自學 Skill，使用者審核後入庫供 Agent 掛載。

## 版本目標

第一塊 Agentic 拼圖：讓系統自動掃 session chat_memory，識別主題聚焦的使用模式，LLM 產出 skill 候選（name / description / system_prompt）供使用者審核。

### 範圍內

- `skill_factory` worker：analyzer（rule + LLM）觸發條件判斷
- `skill_factory` worker：generator 呼叫 LLM 產出 skill suggestion（JSON schema）
- Redis 暫存 suggestion（`skill:suggestion:{user_uid}:{session_uid}`，TTL 7 天）
- `GET /api/v1/chat/sessions/{uid}/skill-suggestions` 查詢候選
- `POST /api/v1/chat/sessions/{uid}/skill-suggestions/{idx}/approve` → 呼叫既有 `POST /skills` 建立 skill
- `POST /api/v1/chat/sessions/{uid}/skill-suggestions/{idx}/reject` → 標記拒絕（供事後分析）
- 前端 session 頁面加「建議 Skill」側邊欄（開關可收起）
- 每階段 log 完整（Rule 判斷 / LLM 輸入 / 輸出 / 使用者決策）

### 範圍外

- 跨 session pattern（→ v1.2 §2-8 正式版，依賴 user_memory / project_memory）
- Skill 自動掛載到 Agent（→ v1.2 §2-1）
- Skill 自動上線（無審核流程）— **禁止**
- 候選 Skill 版本管理
- 前端 admin 查看全系統 Skill 建議數據（留 v1.2+）

---

## 前置現況

- [memory_worker.py](../../../backend/app/workers/memory_worker.py) 已示範 background task 模式（lifespan 啟動、Redis queue 消費）
- [chat_memory_repository](../../../backend/app/repositories/chat_memory_repository.py) `list_by_session` 可取單 session 所有 memory
- [skill_service](../../../backend/app/services/skill_service.py) 既有 `POST /skills` 上傳打包 zip 流程，本版沿用
- OpenRouter client 已支援 structured output（見 `extract_memory` 實作）

---

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | Scope | **僅單一 session**（跨 session 等 v1.2 §2-3 `user_memory`） |
| 2 | 觸發時機 | memory_worker 寫完新 memory → 發事件到 `skill_factory_queue`，skill_factory worker 獨立消費（不阻塞 memory pipeline） |
| 3 | 觸發條件 | memory 數 >= `min_memory_count`（預設 10）且前 3 topic 頻率加總 >= `topic_concentration`（預設 0.3） |
| 4 | 分析模型 | `anthropic/claude-haiku-4-5`（便宜、適合批次分析，可由 `agentic.skill_factory.analyzer_model` 覆寫） |
| 5 | 候選儲存 | Redis（`skill:suggestion:{user_uid}:{session_uid}`，TTL 7 天），不新增 DB 表 |
| 6 | 重複觸發防護 | 同 session 相同 memory signature（topic 集合 hash）在 24h 內**不**重複生成 |
| 7 | Skill 入庫方式 | 沿用 `POST /skills` API，把 `system_prompt` 打包為 `prompt.md` 放進單檔 zip |
| 8 | Skill ownership | 建立後 `owner = user_uid` 私人 skill（不公開，避免 PoC 污染其他使用者） |
| 9 | 使用者拒絕後 | 標記 rejected 暫留在 Redis；**不**永久黑名單（每次新 memory 進來仍可能重生，但 signature hash 會去重） |
| 10 | Log 保留 | `agentic:skill:log` Redis stream，保 30 天，事後觀察 approve/reject 訊號 |

---

## Phase 0：Seed

- [x] **V32**：`seed_agentic_skill_factory_settings.sql`
  - `agentic.skill_factory.enabled` = `true`
  - `agentic.skill_factory.min_memory_count` = `10`
  - `agentic.skill_factory.topic_concentration` = `0.3`
  - `agentic.skill_factory.analyzer_model` = `anthropic/claude-haiku-4-5`
  - `agentic.skill_factory.cooldown_hours` = `24`（同 signature 防重複觸發）

---

## Phase 1：Backend — Analyzer + Generator

### 1-1 OpenRouter Client

- [x] `clients/openrouter/client.py` 新增 `generate_skill_suggestion(memories_payload, model) -> dict`：
  - 固定 JSON schema：`{ name, description, system_prompt, confidence, source_memory_uids }`
  - 對齊 `extract_memory` 的 structured output 模式（structured output + post-parse 截斷防禦，見 [fixed.md #3](fixed.md)）
  - `confidence` 0-1 float，`name` <= 50 字元、`description` <= 200 字元

### 1-2 Skill Factory Service

- [x] `app/services/skill_factory_service.py`（新檔）：
  - `analyze_session(session_uid, user_uid, db) -> list[dict] | None`
    - 取 `chat_memory_repository.list_by_session(session_uid)`
    - Rule 檢查：memory 數量 / 主題聚焦度
    - signature = `sha256(sorted(set(topics)))`；查 Redis `skill:signature:{user_uid}:{session_uid}` 是否在 cooldown
    - 組 payload 丟 `generate_skill_suggestion`
    - 結果存 Redis `skill:suggestion:{user_uid}:{session_uid}`（JSON list）+ signature + cooldown 戳記
    - 寫 `agentic:skill:log`（type=generated）
  - `list_suggestions(user_uid, session_uid) -> list[dict]` — 從 Redis 讀
  - `approve_suggestion(user_uid, session_uid, idx, db) -> Skill`
    - 驗證 idx 存在 + 未被 approved/rejected
    - 打包 suggestion.system_prompt 為 `prompt.md`，放進單檔 zip
    - 呼叫 `skill_service.upload_skill` 產生 skill
    - 在 Redis 標記 idx 狀態 = approved、記 created_skill_uid
    - 寫 `agentic:skill:log`（type=approved）
  - `reject_suggestion(user_uid, session_uid, idx, db) -> None`
    - 標記狀態 = rejected
    - 寫 log

### 1-3 Skill Factory Worker

- [x] `app/workers/skill_factory_worker.py`（新檔）：
  - 主迴圈消費 Redis queue `skill_factory_queue`，內容 `{ user_uid, session_uid }`
  - 呼叫 `analyze_session`；失敗記 log 不阻塞
  - Cooldown / enabled=false 時跳過
- [x] `memory_worker.py`：寫完 chat_memory 後，額外 `lpush skill_factory_queue`（一行幾 byte，影響極小）
- [x] `main.py::lifespan`：啟動 skill_factory_worker（仿 memory_worker 模式）

### 1-4 API Router

- [x] `app/api/v1/chat/router.py` 新增：
  - `GET /chat/sessions/{uid}/skill-suggestions` → 回 Redis 候選清單（含 idx + status）
  - `POST /chat/sessions/{uid}/skill-suggestions/{idx}/approve` → 回建立的 Skill 資訊
  - `POST /chat/sessions/{uid}/skill-suggestions/{idx}/reject`
- [x] 所有端點驗證 session 擁有者

### 1-5 Schema

- [x] `app/schemas/chat/skill_suggestion_schemas.py`（新檔）：
  - `SkillSuggestionItem { idx; name; description; system_prompt; confidence; source_memory_uids; status; created_skill_uid | None }`
  - `SkillSuggestionListData`

---

## Phase 2：Frontend

### 2-1 型別

- [x] `types/chat.ts::SkillSuggestion`

### 2-2 RTK Query

- [x] `store/chatApi.ts`：
  - `listSkillSuggestions` query（providesTags `SkillSuggestions-{sessionUid}`）
  - `approveSkillSuggestion` mutation（invalidates `SkillSuggestions-{sessionUid}` + `Skills`）
  - `rejectSkillSuggestion` mutation（invalidates `SkillSuggestions-{sessionUid}`）

### 2-3 Session 頁面側邊欄

- [x] [sessions/[uid]/page.tsx](../../../frontend/src/app/(main)/sessions/[uid]/page.tsx) 新增「建議 Skill」側邊欄：
  - 位置：與「記憶」抽屜**並列**或下方獨立抽屜（不重疊）
  - 頂部切換按鈕（類似「記憶」按鈕風格），預設收起
  - 內容：每項 suggestion 顯示 name + description + confidence 徽章 + 來源 memory 摘要
  - 按鈕：✅「建立」→ approve；❌「拒絕」→ reject
  - approve 成功後顯示 Dialog：「已建立 skill。要立即掛到目前 Agent 嗎？」→ Yes 則自動呼叫 `updateAgent` 將該 skill_uid 加入
- [x] 空狀態：「對話累積一段時間後會出現建議的 Skills。現有 N 則記憶（達到 M 則且主題聚焦即可觸發）」

### 2-4 視覺

- [x] Confidence 徽章：0.8+ 綠、0.6-0.8 黃、< 0.6 灰
- [x] 所有元素 `hover:cursor-pointer`、`rounded-xl`（11-ui-ux 規範）
- [x] **禁止**顯示任何 uid（suggestion idx 也不顯示，內部使用）— 遵循 [10-frontend.md § 識別碼顯示](../../Design-Base/10-frontend.md)

---

## Phase 3：觀察性（PoC 關鍵）

這是 PoC 的**主要學習產物**，不是附屬功能。

- [x] worker log 使用 `logger.info`（非 debug），格式化：
  - `skill_factory: analyze session_uid=X memory_count=Y topic_concentration=Z decision={triggered|skipped:reason}`
  - `skill_factory: llm_input memories={...} model=X`
  - `skill_factory: llm_output suggestions={...}`
- [x] `agentic:skill:log` Redis stream 結構：
  - `{ ts, user_uid, session_uid, type: "generated|approved|rejected", signature, suggestion_snapshot, source_memory_uids }`
  - TTL 30 天（以 XADD MAXLEN~10000 近似，足以覆蓋 PoC 規模的 30 天事件量）
- [x] 預留**簡易查詢 API**：`GET /api/v1/admin/debug/skill-factory/recent?limit=50` 讀 stream，方便開發者觀察（admin-only）

---

## Phase 4：文件

- [x] [propose-v1.1-extended.md §5](propose-v1.1-extended.md) 實作完回填狀態標題
- [x] [propose-v1.2.0.md §2-8](../v1.2/propose-v1.2.0.md) 加一行「承接 v1.1.7 commit xxx 的 PoC，approve/reject 訊號可用於 threshold 調校」
- [ ] `docs/Tasks/v1.1/fixed.md`：驗收期 bug 記錄 —（無驗收 bug 可紀錄，留空待驗收期填入）

---

## 驗收

- [ ] 在 session 累積 10+ 筆主題聚焦的 memory（例如同一個技術學習 session）
- [ ] 等待 memory_worker 寫完後最多 1 分鐘內，Redis `skill:suggestion:...` 出現候選
- [ ] 前端側邊欄顯示至少 1 個合理的 suggestion（人工判斷 name + description + system_prompt 有關聯）
- [ ] 點「建立」後 `/skills` 出現新的私人 skill；點「拒絕」後該項 status = rejected
- [ ] 建立後提示「掛到 Agent」流程可用，掛載後該 Agent 下次對話生效
- [ ] **admin 不能**看其他使用者的 suggestion 清單（403）
- [ ] 關閉 `agentic.skill_factory.enabled` 後新 memory 不再觸發 analyzer
- [ ] 同 signature 在 24h 內**不**重複產 suggestion
- [ ] `agentic:skill:log` Redis stream 有對應的 generated / approved / rejected 三類紀錄
- [ ] `GET /admin/debug/skill-factory/recent` 能回最近 50 筆事件
