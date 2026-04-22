# v1.1.6 任務規格：附件系統（圖片 + 文字檔）

> **狀態：已完成（commit pending, 2026-04-22）**
>
> 前置：[propose-v1.1-extended.md §4](propose-v1.1-extended.md)、[tasks-v1.1.5.md](tasks-v1.1.5.md)（V28 已取走）
>
> 最終目標：讓對話能攜帶圖片與文字檔，對話素材多樣化後進入記憶層，為 multimodal RAG 奠基。

## 版本目標

讓使用者可在對話中上傳圖片（進 OpenRouter vision model）與文字檔（內容拼入 user message content）。附件描述進入記憶層，不存原始 binary。

### 範圍內

- 新增 `chat_attachment` 資料表 + local volume 儲存
- 新增 `POST /api/v1/chat/sessions/{uid}/attachments`（multipart/form-data，單次可傳多檔）
- 新增 `GET /api/v1/chat/attachments/{uid}`（下載 / 預覽）
- `chat_message` 新增 `attachment_uids UUID[] NULL` 欄位
- `send_message` 支援 `attachment_uids` 參數：
  - 圖片 → 以 base64 或 URL 塞 OpenRouter `messages[].content` 的 multimodal 格式
  - 文字檔 → 讀內容拼入 user content，前置 `File: {filename}\n` 標記
- 前端輸入區加 📎 按鈕 + 拖放 + 縮圖 / 檔名預覽 + 移除
- memory_worker 前處理：圖片 → vision model 產 1-2 句描述，描述（非 binary）進 chat_memory

### 範圍外

- 語音 / 影片（v1.3+）
- OCR（純圖片無字時不抽，等需求明確）
- 病毒掃描（暫依副檔名白名單 + 大小上限）
- S3 / 雲端儲存（先 local volume，改 S3 只需改 `file_path` 語意）
- 附件列表頁 / 管理後台

---

## 前置現況

- v1.1.3 Skills 已有檔案上傳實作（zip 進 `data/skills/`），可參考檔案命名 / 儲存模式
- [openrouter/client.py](../../../backend/app/clients/openrouter/client.py) 目前僅支援 text completion，**需擴充**支援 multimodal `content` 陣列
- `OPENROUTER_API_KEY` 與 http referer 已就緒
- OpenRouter 的 vision model：Claude 3+ / Gemini / GPT-4o（使用者選擇的 model 若不支援 vision，後端要 graceful fallback）

---

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | 附件儲存位置 | `data/attachments/{yyyymm}/{uid}.{ext}`，gitignore 已排除 `data/` |
| 2 | 檔案白名單 | `.png .jpg .jpeg .webp .pdf .md .txt .json .csv`（圖片 + 常見文字格式）|
| 3 | `pdf` 處理 | v1.1.6 **暫不處理 pdf 內文**（只能當附件下載），OCR / PDF text extraction 留 v1.2+ |
| 4 | 單檔上限 | `chat.max_attachment_size_mb = 10`，admin 可調最大 50 |
| 5 | 每訊息上限 | `chat.max_attachments_per_message = 5`，admin 可調最大 10 |
| 6 | 圖片傳 LLM | base64 data URL（OpenRouter 跨 provider 最通用），大於 5MB 先 resize（未壓縮的高解析度圖會爆）|
| 7 | 文字檔讀入 | UTF-8 解碼，失敗 fallback 到 latin-1 + 警告訊息（不 crash）|
| 8 | 附件權限 | 上傳者 + session owner 可讀，其他人 403；session 軟刪後附件仍可透過 admin 取回（scope 本版不做，僅保留 FK 設計）|
| 9 | memory 描述 | 圖片附件 → vision 產 1-2 句描述；文字檔 → 內容當普通 text 餵 extractor |
| 10 | LLM 不支援 vision 時 | 後端改用 text-only prompt + 附加「(圖片附件已略過，該 model 不支援 vision)」訊息，**不**報錯 |

---

## Phase 0：Migration

- [x] **V29**：`create_chat_attachment_table.sql`
  - 建表（含 pid / chat_attachment_uid / owner_user_uid / chat_session_uid / file_name / file_type / file_size / file_path / is_active / is_deleted / created_at / updated_at）
  - FK：owner_user_uid → user.user_uid、chat_session_uid → chat_session.chat_session_uid
  - Unique index：`uq_chat_attachment_chat_attachment_uid`（對齊 21-database.md § 命名慣例）
  - 一般 index：`idx_chat_attachment_session_uid`
  - Trigger：`trg_chat_attachment_set_updated_at`
  - 完整 COMMENT ON TABLE / COLUMN
- [x] **V30**：`add_chat_message_attachment_uids.sql`
  - `ALTER TABLE chat_message ADD COLUMN IF NOT EXISTS attachment_uids UUID[] NULL;`
  - COMMENT
- [x] **V31**：`seed_chat_attachment_settings.sql`
  - Insert `chat.max_attachment_size_mb` = '10'
  - Insert `chat.max_attachments_per_message` = '5'
  - Insert `chat.attachment_allowed_extensions` = `.png,.jpg,.jpeg,.webp,.pdf,.md,.txt,.json,.csv`
  - 另含 `memory.image_describe_model`（Phase 2-2 合併入 V31，見 _決策：seed 合併_）

---

## Phase 1：Backend — 儲存層 + API

### 1-1 Model

- [x] `app/models/chat_attachment.py`：新 model 繼承既有 `Base`
- [x] `app/models/chat_message.py`：新增 `attachment_uids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(Uuid), nullable=True)`

### 1-2 Schema

- [x] `app/schemas/chat/attachment_schemas.py`（新檔）：
  - `ChatAttachmentResponse`（含 uid / file_name / file_type / file_size / created_at）
  - `ChatAttachmentListData`
- [x] `app/schemas/chat/schemas.py::ChatMessageResponse`：新增 `attachment_uids: list[str] | None = None`、`attachments: list[ChatAttachmentResponse] | None = None`（遵循 20-backend.md § 關聯資源回應規範 — 多對多關聯回 `{uid, name}`）
- [x] `ChatMessageCreateRequest`：新增 `attachment_uids: list[str] | None = None`

### 1-3 Repository

- [x] `app/repositories/chat_attachment_repository.py`（新檔）：
  - `create(data, db)`
  - `get_by_uid(uid, db)`
  - `list_by_session(session_uid, db)`
  - `list_by_uids(uids, db)`（批次，給 `ChatMessageResponse.attachments` 填充）
  - `soft_delete(attachment, db)`

### 1-4 Service

- [x] `app/services/chat_attachment_service.py`（新檔）：
  - `upload_attachments(user_uid, session_uid, files: list[UploadFile], db) -> list[ChatAttachmentResponse]`
    - 驗證：session 擁有者、檔案大小、副檔名白名單、單訊息數量上限（累計本次 + 已有）
    - 儲存到 `data/attachments/{yyyymm}/{uid}.{ext}`，寫 DB
  - `get_attachment_content(attachment_uid, user_uid, db) -> (file_bytes, file_type, file_name)`
    - 驗證使用者是該 session 擁有者
  - `load_for_prompt(attachment_uids, db) -> list[dict]`
    - 回每個 attachment 的 `{uid, file_type, file_name, content_b64_or_text}`，給 chat_service 組 prompt

### 1-5 API Router

- [x] `app/api/v1/chat/router.py` 新增兩個 endpoint：
  - `POST /chat/sessions/{uid}/attachments`（multipart/form-data、`files: list[UploadFile]`）
  - `GET /chat/attachments/{uid}` 回 StreamingResponse（按 [propose-v1.2.0.md § 統一回應格式豁免端點](../Design-Base/20-backend.md#統一回應格式) 下載豁免）
- [x] `send_message` endpoint 支援 `attachment_uids` 欄位

### 1-6 OpenRouter Client 擴充

- [x] `clients/openrouter/client.py`：
  - `stream_chat_completion` 的 `messages` 型別放寬支援 multimodal content 陣列（OpenRouter 規範：`content: [{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}]`）
  - 新增 helper 將圖片轉 base64 data URL
  - 若選用的 model 不支援 vision（靠 `llm_model.capabilities` 或硬編清單），後端降級為 text-only + 在 prompt 加「(圖片附件已略過)」

### 1-7 Chat Service 整合

- [x] `chat_service.send_message`：
  - 收到 `attachment_uids` → 先 `chat_attachment_service.load_for_prompt`
  - 組 user message 時，若有圖片附件 → 用 multimodal content 陣列
  - 若有文字檔 → 內容前置 `File: {filename}\n` 拼入 text
  - 寫 chat_message 時把 `attachment_uids` 帶入 DB

---

## Phase 2：Backend — Memory Worker 圖片描述

### 2-1 vision 描述

- [x] `clients/openrouter/client.py` 新增 `describe_image(image_b64, model) -> str`（1-2 句描述，用 vision model）
- [x] `workers/memory_worker.py`：
  - 處理 user message 時，若有 attachment_uids 含圖片 → 先呼叫 `describe_image` 取得描述
  - 描述與原始 text 拼接後進 prefilter → extractor（沿用既有 pipeline）
  - 失敗（vision API 錯、附件已刪）時 fallback 到純文字 + log warning

### 2-2 Setting

- [x] `system_setting` 新增 `memory.image_describe_model` = `anthropic/claude-haiku-4-5`（默認，admin 可改）

---

## Phase 3：Frontend

### 3-1 型別

- [x] `types/chat.ts`：
  - `ChatAttachment { chat_attachment_uid; file_name; file_type; file_size; created_at }`
  - `ChatMessage.attachment_uids: string[] | null`
  - `ChatMessage.attachments: ChatAttachment[] | null`
- [x] `types/index.ts` re-export

### 3-2 RTK Query

- [x] `store/chatApi.ts`：
  - `uploadAttachments` mutation（multipart）
  - `sendMessage` 接受 `attachment_uids`

### 3-3 Session 頁面

- [x] [sessions/[uid]/page.tsx](../../../frontend/src/app/(main)/sessions/[uid]/page.tsx) 輸入區改造：
  - 📎 按鈕（左下角或 Send 按鈕旁，`hover:cursor-pointer rounded-xl`）
  - 選檔 / 拖放 → 呼叫 `uploadAttachments`
  - 上傳中顯示 spinner，成功後進 `pendingAttachments` state
  - Chip 預覽區（縮圖 for 圖片 / 📄 + 檔名 for 文字檔 / 可 ✕ 移除）
  - 送出訊息時帶 `attachment_uids = pendingAttachments.map(a => a.chat_attachment_uid)`，送出後清空
- [x] 訊息列表 render 時若有 `message.attachments` → 下方顯示 chips（圖片可點開 lightbox 或新分頁）

### 3-4 錯誤處理

- [x] 超大檔 / 白名單外 / 超出數量 → `useDialog` 顯示 Error Dialog（11-ui-ux 規範）

---

## Phase 4：文件 / Seed

- [x] [propose-v1.1-extended.md §4](propose-v1.1-extended.md) 實作完回填狀態標題
- [ ] `docs/Tasks/v1.1/fixed.md`：驗收期 bug 記錄（驗收期新增）

---

## 驗收

- [ ] 上傳 `.png` < 10MB 成功，預覽縮圖；上傳 > 10MB 被拒；`.exe` 被拒
- [ ] 圖片送給 Claude 3.5 / Gemini：LLM 能描述圖片內容
- [ ] 文字檔 `.md` 送給 LLM：LLM 能引用檔案內容回答
- [ ] 超過 `max_attachments_per_message` 時送出被拒
- [ ] 記憶層：對含圖片的對話 `SELECT topic, keywords FROM chat_memory` 看到的是**圖片描述文字**（例：「一張藍天白雲的風景照」），不是 `[image]` 字面值
- [ ] Model 不支援 vision 時，LLM 仍能回覆（附件被略過，prompt 標註）不崩潰
- [ ] 附件 download endpoint 只有 session owner 可取（別人 403）
- [ ] Session 軟刪後附件記錄仍在（不物理刪），但不影響上傳使用者後續對話
