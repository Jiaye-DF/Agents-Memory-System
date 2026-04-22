# v1.1.5 任務規格：UX Pack（輸入框、Copy、截斷 badge）

> **狀態：已完成（commit 待補, 2026-04-22）**
>
> 前置：[propose-v1.1-extended.md §3](propose-v1.1-extended.md)
>
> 最終目標：降低輸入門檻 + 讓使用者看到 LLM 截斷現象。

## 版本目標

改善 v1.1 累積的三個基礎體驗缺口：

1. 對話輸入框 textarea 固定高度，長訊息難打
2. 使用者無法快速 copy assistant 回覆
3. LLM 被 `max_tokens` 截斷時 UI 完全無提示（見 [propose-v1.2.0.md §2-5](../v1.2/propose-v1.2.0.md)）

### 範圍內

- 輸入框 auto-resize：隨內容行數自動增高（上限 10 行），超出啟動內部 scroll
- 每則 assistant message 加 Copy 按鈕，hover 顯示、點擊後 2 秒 ✓ 反饋
- OpenRouter `finish_reason === "length"` 時，assistant message 顯示 ⚠「回覆被截斷」badge
- `chat_message` 資料表新增 `finish_reason VARCHAR(20) NULL` 欄位（V28 migration）
- `chat_service.send_message` 從 OpenRouter chunk 抽 `finish_reason` 寫入 DB
- 後端回應 `ChatMessageResponse` 加 `finish_reason` 欄位

### 範圍外

- `max_tokens` UI hint（propose-v1.2.0.md §2-5 A）— 等 v1.1.6 一起動 AgentForm 再加
- Agent Template 預設 `max_tokens` 分類（§2-5 C）— v1.2 多 Agent 一起
- Copy 按鈕的「複製為 markdown / 純文字」選項 — 先只做純文字複製
- 訊息編輯 / 刪除 / 重新生成 — 超出本版範圍

---

## 前置現況

- [chat_service.py:697](../../../backend/app/services/chat_service.py#L697) 組 completion 時傳 `max_tokens=agent.max_tokens`，provider 截斷時不可見
- [chat_service.py:595-599](../../../backend/app/services/chat_service.py#L595-L599) `_extract_usage` 已從 chunk 抽 usage；同樣模式可抽 `finish_reason`
- [sessions/[uid]/page.tsx](../../../frontend/src/app/(main)/sessions/[uid]/page.tsx) 有既有 `textareaRef`、訊息列表 render 位置
- `backend/app/schemas/chat/schemas.py::ChatMessageResponse` 目前無 `finish_reason` 欄位

---

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | `finish_reason` 欄位型別 | `VARCHAR(20) NULL`，足以容納 `stop` / `length` / `tool_calls` / `content_filter` 等 OpenRouter 可能值 |
| 2 | 歷史訊息無此欄位 | NULL 不顯示 badge（前端以「不為 null 且 === 'length'」判斷）|
| 3 | Copy 範圍 | 僅複製 `message.content` 純文字，不含 metadata |
| 4 | auto-resize 行數上限 | 10 行，對應 `max-h-[250px]` 左右（line-height 依現有字型）|
| 5 | 截斷 badge 位置 | 訊息末尾（metadata 區：tokens / cost 同一行前後）|

---

## Phase 0：Migration

- [x] **V28**：`add_chat_message_finish_reason.sql`
  - `ALTER TABLE chat_message ADD COLUMN IF NOT EXISTS finish_reason VARCHAR(20) NULL;`
  - `COMMENT ON COLUMN chat_message.finish_reason IS 'OpenRouter finish_reason（stop / length / tool_calls 等；NULL 代表歷史訊息或非 assistant 角色）';`

---

## Phase 1：Backend

### 1-1 Model

- [x] `app/models/chat_message.py`：新增 `finish_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)`

### 1-2 Schema

- [x] `app/schemas/chat/schemas.py::ChatMessageResponse`：新增 `finish_reason: str | None = None`

### 1-3 Service

- [x] `chat_service._message_to_dict`：output 多一個 `"finish_reason": message.finish_reason`
- [x] `chat_service.send_message`：
  - 新增 helper `_extract_finish_reason(chunk) -> str | None`（參考 `_extract_usage` 寫法，從 `chunk["choices"][0].get("finish_reason")` 抽）
  - streaming loop 內更新 `finish_reason` 變數（取最後一個非 None 值）
  - 寫 assistant message 時把 `finish_reason` 帶入 `chat_message_repository.create` 的 payload
  - `done` SSE event payload 同步帶上 `finish_reason`

### 1-4 Repository

- [x] `chat_message_repository.create`：支援 `finish_reason` 欄位寫入（若用 `**data` 傳入，通常自動支援，確認即可）—（既有 `ChatMessage(**message_data)` 自動吃新欄位，無需改碼）

---

## Phase 2：Frontend

### 2-1 型別

- [x] `types/chat.ts::ChatMessage`：新增 `finish_reason: string | null`

### 2-2 輸入框 auto-resize

- [x] [sessions/[uid]/page.tsx](../../../frontend/src/app/(main)/sessions/[uid]/page.tsx) 的 textarea：
  - 加 `onInput` handler：`el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, MAX_PX) + 'px'`—（實作用 `onChange` 內呼叫 `resizeTextarea()`，效果等同）
  - `MAX_PX` 設常數（10 行約 240px，依實際 line-height 確定）
  - 送出訊息後重置高度為 auto（避免保持最後的大高度）
  - 確保觸控 / 手機 virtual keyboard 下表現正常（實測）—（CSS `max-h-60` + `overflow-y-auto` + JS 同步高度，使用者實測驗收）

### 2-3 Copy 按鈕

- [x] 每則 assistant message 區塊 hover 顯示 Copy 按鈕：
  - 位置：訊息右上或底部，跟既有 metadata 區對齊—（採右上 absolute 位置，與訊息區共用 `group` hover）
  - 樣式：`hover:cursor-pointer`、`rounded-xl`（11-ui-ux 規範）
  - onClick：`navigator.clipboard.writeText(message.content)` → setCopiedUid 狀態 → 2 秒後清除
  - 複製中顯示 ✓ + 「已複製」；使用者 keyboard focus 也能觸發（無障礙）—（`focus:opacity-100` 已支援）
- [x] User message 不加 Copy（避免混淆使用者自己的輸入）

### 2-4 截斷 badge

- [x] 判斷：`message.role === 'assistant' && message.finish_reason === 'length'`
- [x] 位置：訊息 metadata 區（`model`、`tokens`、`cost` 旁）
- [x] 樣式：紅或橘背景 + ⚠ + 「回覆被截斷」文字，`hover` tooltip「LLM 達到 max_tokens 上限。建議在 Agent 設定提高 max_tokens 或清空此欄位」
- [x] 使用 CSS variable 色彩（`--color-warning-bg` / `--color-warning`），**禁止**寫死 hex（11-ui-ux 規範）—（使用 Tailwind `bg-warning-bg text-warning`，透過既有 `@theme inline` 對應 CSS variable）

---

## Phase 3：文件

- [x] `propose-v1.1-extended.md §3`：實作完回填狀態標題 `> **狀態：已完成（commit xxx, YYYY-MM-DD）**`
- [ ] `docs/Tasks/v1.1/fixed.md`：若驗收期間發現 bug，記錄問題 + 修法—（驗收後視實際情況補）

---

## 驗收

- [ ] 輸入框：打 1 行 = 基本高度；打 5 行 = 對應增高；打 20 行 = 10 行高度 + 內部 scroll
- [ ] 送出訊息後輸入框恢復初始高度
- [ ] Assistant message hover 顯示 Copy 按鈕，點擊後瀏覽器剪貼簿有該則訊息的 content，UI 顯示 ✓ 兩秒
- [ ] User message **不**出現 Copy 按鈕
- [ ] 設 agent `max_tokens = 100` 發起長對話：assistant message 尾端出現 ⚠「回覆被截斷」badge
- [ ] 歷史訊息（無 `finish_reason`）或 `finish_reason === 'stop'` 時，**不**顯示 badge
- [ ] 重新整理頁面後 badge 仍正確顯示（代表 DB 有持久化 finish_reason）
- [ ] DB 直接查 `SELECT finish_reason FROM chat_message WHERE role = 'assistant' LIMIT 10` 可見新欄位寫入
