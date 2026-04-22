# v1.1 Extended Propose — UX / 附件 / Agentic Skill PoC

> 本文件為 v1.1 延伸優化的構想與討論紀錄。定稿後拆為 `tasks-v1.1.5.md` ~ `tasks-v1.1.7.md`。
>
> 前置：[propose-v1.1.0.md](propose-v1.1.0.md)
>
> 最終目標：**Agentic RAG + 模型推論**

---

## 0. 前置現況

v1.1.1 ~ v1.1.4 已完成對話、Session / Project、記憶、RAG、Skills 線上編輯、游離 Session。剩餘缺口：

1. 輸入框高度固定、無 Copy 按鈕 — 基礎體驗債
2. 無法上傳圖片 / 檔案 — RAG 素材單一
3. Skills 完全靠人工撰寫 — Agentic 自學能力缺席

前兩項是體驗債，第三項是通往 Agentic RAG 的**關鍵原型**。

---

## 1. 版本 Roadmap

| 子版本 | 主題 | 性質 | 時程估 |
| --- | --- | --- | --- |
| v1.1.5 | UX Pack（輸入框 auto-resize、Copy、截斷 badge） | 純前端 | 1-2 天 |
| v1.1.6 | 附件系統（圖片 + 文字檔） | Infra | 3-5 天 |
| v1.1.7 | Agentic Skill 工廠 PoC | 架構驗證 | 1 週 |

三個子版本**可平行開發**：無 schema / 前端檔案衝突（見 §6）。

---

## 2. 通往 Agentic RAG 的脈絡

```text
v1.1.5 UX Pack         ─ 降低輸入門檻，累積更多有效對話
v1.1.6 附件系統         ─ 對話素材多樣化（圖片 / 檔案 → 記憶層）
v1.1.7 Skill 工廠 PoC   ─ 自學工具，Agentic 第一塊拼圖
v1.2   跨層記憶 + 多 Agent ─ Skill 工廠升級跨 session、Agent 自動帶 Skill
v1.3   公開 API         ─ 對外暴露完整 Agentic 能力
```

v1.1.7 明確為 **PoC**，目的是自行設計一遍 Agentic loop 理解架構，之後再評估引入 Hermes / pydantic-ai 等框架。

---

## 3. v1.1.5 — UX Pack

> **狀態：已完成（commit 6cc0959, 2026-04-22）**

### 範圍內

- **輸入框 auto-resize**：`textarea` 依內容行數 auto-grow（上限 10 行，超出啟動 scroll）
  - 實作點：[sessions/[uid]/page.tsx](../../../frontend/src/app/(main)/sessions/[uid]/page.tsx) 既有 `textareaRef` + `onInput` 同步 `scrollHeight` 到 `style.height`
- **Copy 模型回覆**：每則 assistant message hover 顯示 Copy 按鈕
  - `navigator.clipboard.writeText(message.content)` + 2 秒 ✓ 反饋
- **截斷 badge**：OpenRouter `finish_reason === "length"` 時 UI 標 ⚠「回覆被截斷」
  - 承 [propose-v1.2.0.md §2-5 B](../v1.2/propose-v1.2.0.md)，提前在 v1.1.5 做

### 範圍外

- max_tokens UI hint（§2-5 A）— 等 1.1.6 一起動 AgentForm 再加
- Agent Template 預設值（§2-5 C）— 等 v1.2 多 Agent 一起

### DB 變更

| Migration | 內容 |
| --- | --- |
| V28 | `ALTER TABLE chat_message ADD COLUMN finish_reason VARCHAR(20)` + COMMENT |

### 驗收

- [ ] 輸入框隨文字自動加高，超過 10 行改 scroll
- [ ] Assistant message hover 顯示 Copy，點擊後 ✓ 反饋 2 秒
- [ ] 設 `max_tokens = 100` 對話時 UI 顯示截斷 badge

---

## 4. v1.1.6 — 附件系統

> **狀態：已完成（commit d3e6976, 2026-04-22；見 tasks-v1.1.6.md）**

### 範圍內

- `chat_attachment` 表 + local volume 儲存（未來改 S3 只需改 `file_path` 語意）
- `POST /api/v1/chat/sessions/{uid}/attachments`（multipart/form-data）
- `chat_message` 加 `attachment_uids UUID[] NULL` 關聯訊息附件
- **圖片**：base64 / URL 進 OpenRouter vision model（Claude 3+ / Gemini / GPT-4o）
- **文字檔**（`.md` / `.txt` / `.json` / `.csv`）：讀成 text 拼入 user content，前置 `File: {filename}\n` 標記
- **前端**：📎 按鈕 + 拖放 + 縮圖 / 檔名預覽 + 可移除

### 範圍外

- 語音 / 影片（v1.3+）
- OCR（純圖片無字時不抽）— 等明確需求
- 病毒掃描（暫依副檔名白名單 + 大小上限）

### Schema 摘要

```sql
CREATE TABLE chat_attachment (
    pid                  BIGSERIAL     PRIMARY KEY,
    chat_attachment_uid  UUID          NOT NULL DEFAULT gen_random_uuid(),
    owner_user_uid       UUID          NOT NULL,
    chat_session_uid     UUID          NOT NULL,
    file_name            VARCHAR(255)  NOT NULL,
    file_type            VARCHAR(50)   NOT NULL,
    file_size            BIGINT        NOT NULL,
    file_path            VARCHAR(500)  NOT NULL,
    is_active            BOOLEAN       NOT NULL DEFAULT TRUE,
    is_deleted           BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW()
    -- FK、uq_、idx_、trg_、COMMENT 省略，依 21-database.md 慣例
);
```

`chat_message` 加一欄：`attachment_uids UUID[] NULL`（與 `source_chat_message_uids` 同樣 array、不加 FK）。

### 設定

| system_setting key | 預設 | 最大 |
| --- | --- | --- |
| `chat.max_attachment_size_mb` | 10 | 50 |
| `chat.max_attachments_per_message` | 5 | 10 |
| `chat.attachment_allowed_extensions` | `.png,.jpg,.jpeg,.webp,.pdf,.md,.txt,.json,.csv` | — |

### 跟記憶系統的銜接

- 圖片上傳 → vision model 產 1-2 句**描述**（worker 多一步 preprocess）→ 描述進 `chat_memory.topic / keywords`
- **不**存 raw binary 進 memory（pgvector 不吃圖片、成本爆炸）
- 文字檔 → 當普通 text 餵 extractor，沿用 `memory_prefilter.truncate_for_extraction`

### 驗收

- [ ] 上傳 < 10MB 圖片成功、過大被拒、白名單外副檔名被拒
- [ ] Claude / Gemini vision 能描述上傳的圖片
- [ ] 文字檔內容能被 LLM 引用
- [ ] 圖片對話的 `memory.topic` 是描述文字而非 `[image]`

---

## 5. v1.1.7 — Agentic Skill 工廠 PoC

> **狀態：已完成（commit 98a4d5a, 2026-04-22）** — analyzer / generator / approve / reject 流程、觀察性 Redis stream、admin debug 端點與前端側邊欄均已實作。

### 目標

驗證 Agentic loop 最小閉環：

```text
session chat_memory 累積
  │
  ▼
Pattern Analyzer（掃 memory、算主題聚類）
  │
  ▼
Skill Generator（LLM 生成 name / description / system_prompt）
  │
  ▼
建議清單 → 使用者審核 → 入庫為私人 Skill
```

### PoC 範圍（刻意限縮）

- **Scope：單一 session**（跨 session 等 v1.2 §2-3 `user_memory` 完成再升級）
- **觸發條件**：session memory 數 >= `min_memory_count` **且** 前 3 topic 頻率加總 >= `topic_concentration`
- **不自動入庫**：使用者必須手動 approve，避免未授權 skill 氾濫

### Generator 產出格式

```json
{
  "suggested": true,
  "name": "學術風格改寫助手",
  "description": "根據使用者偏好，將一般文字改寫為學術論文風格",
  "system_prompt": "你是...",
  "confidence": 0.82,
  "source_memory_uids": ["...", "..."]
}
```

### 候選 Skill 暫存（不新增 DB 表）

```text
Redis Key: skill:suggestion:{user_uid}:{session_uid}
Value:    JSON array of suggestions
TTL:      7 days
```

使用者 approve 才寫 `skill` 表（沿用既有 `POST /skills` API，把 `system_prompt` 打包為單檔 `.md` 放進 zip）。

### 設定

| system_setting key | 預設 | 說明 |
| --- | --- | --- |
| `agentic.skill_factory.enabled` | `true` | 總開關 |
| `agentic.skill_factory.min_memory_count` | 10 | 觸發門檻 |
| `agentic.skill_factory.topic_concentration` | 0.3 | 前 3 topic 頻率加總 |
| `agentic.skill_factory.analyzer_model` | `anthropic/claude-haiku-4-5` | 分析模型 |

### 觀察性（學習價值的關鍵）

PoC 的意義在看清每一步，所以每階段**必須 log**（對齊 [propose-v1.2.0.md §2-4](../v1.2/propose-v1.2.0.md) Debug 層 1）：

- Rule 觸發條件是否成立的理由（哪條不符）
- Analyzer 的 memory 輸入 + suggestion 輸出完整 payload
- 使用者 approve / reject 比率（寫 `agentic:skill:log` Redis stream 供事後分析）

### 驗收

- [ ] 累積 10+ 筆主題聚焦的 memory 能觸發 analyzer
- [ ] 產出 >= 1 個合理的 skill suggestion（人工判斷 name / description）
- [ ] 使用者前端審核 + 建立 skill
- [ ] 建立後 skill 能掛到其他 Agent
- [ ] 每階段 log 可追溯 suggestion 來源 memory

---

## 6. 跨子版本衝突檢查

| 動到 | 1.1.5 | 1.1.6 | 1.1.7 |
| --- | --- | --- | --- |
| `chat_message` 表 | ✓（finish_reason，V28） | ✓（attachment_uids，V29） | ✗ |
| `skill` 表 | ✗ | ✗ | ✗（只用現有 API） |
| `chat_memory` | ✗ | ✗（圖片描述進來但 schema 不變） | ✗（只讀） |
| `sessions/[uid]/page.tsx` | ✓（輸入框、Copy） | ✓（附件區） | ✓（建議側欄） |

**需協調**：Flyway 版號（V28 / V29 切開）；前端檔案編輯位置不重疊。

---

## 7. 跟 v1.2 / v1.3 的銜接

| v1.1 延伸 | 對應 v1.2 升級 |
| --- | --- |
| 1.1.6 圖片 + vision | §2-2 Classifier 要能識別「含圖片」→ 強制走 vision model |
| 1.1.7 Skill PoC（session scope） | §2-8 升級跨 session（消費 `user_memory` / `project_memory`） |
| 1.1.7 人工審核 Skill | §2-1 多 Agent 自動推薦適合 Skill |

本 propose 定稿後**同步更新** [propose-v1.2.0.md](../v1.2/propose-v1.2.0.md) 補 §2-8 / §2-2 / §2-1。

v1.3 公開 API 可承接：1.1.6 的上傳 API / quota 基礎、1.1.7 的 Agentic 能力對外暴露。

---

## 8. 下一步

1. 本 propose 定稿
2. 起手 `tasks-v1.1.5.md`（純前端、風險最低、見效快）
3. 1.1.6 / 1.1.7 依需要擇一優先開工（兩者可平行）
4. 每子版本完成後**回填** `tasks-v1.1.X.md` 狀態標題（CLAUDE.md §任務文件回填）
