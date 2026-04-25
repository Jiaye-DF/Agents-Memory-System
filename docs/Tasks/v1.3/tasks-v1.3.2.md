# v1.3.2 任務規格：記憶 UI 即時性（SSE 擴充 `memory_updated` 事件）

> 前置：[propose-v1.3.0.md §3-5](propose-v1.3.0.md)、[tasks-v1.3.1.md](tasks-v1.3.1.md)（worker log 基礎）
> 後續依賴：（無，這版獨立）

## 版本目標

讓使用者送出訊息後不需手動重整即可看到 memory_worker 寫入的 `chat_memory`。確定方案：**SSE 擴充 `memory_updated` 事件、新增獨立 `/events` endpoint**，與既有 `POST /messages` 的訊息 SSE 分開、不引入 WebSocket。

- memory_worker 寫完 `chat_memory` 後 publish Redis pub/sub channel `chat:session:{uid}:memory`（payload 含 `memory_uid`）
- 新增 `GET /api/v1/chat/sessions/{uid}/events` SSE endpoint：訂閱該 channel 並推送 `event: memory_updated` 給前端
- 連線生命週期跟著前端 session 頁面 mount / unmount
- SSE auth 走 query string `?token=xxx`，handler 自行驗證
- 前端封裝 hook `useSessionEvents(sessionUid)`：EventSource + polling 30s fallback
- 收到 `memory_updated` → invalidate `{ type: "ChatMessages", id: "memories-${sessionUid}" }` tag，觸發既有 `useListMemoriesQuery` refetch

### 範圍內

- Backend：memory_worker 寫入後 publish；新 `/events` SSE handler；query string token 驗證
- Backend：事件型別欄位設計（`memory_updated` / `memory_failed` / `session_archived`）統一定義
- Backend：DLQ 進入時可選擇 publish `memory_failed`（預設僅實作 `memory_updated`，`memory_failed` 同步落地但前端不顯示 UI badge）
- Frontend：`useSessionEvents` hook + EventSource / polling fallback
- Frontend：Session 頁面 mount 時呼叫 hook、unmount 時自動 cleanup
- Frontend：收到 `memory_updated` → `dispatch(chatApi.util.invalidateTags([{type: "ChatMessages", id: "memories-${sessionUid}"}]))`

### 範圍外

- WebSocket（已決策不採用，見 propose §3-5）
- 多分頁同 session SSE 連線數上限處理（瀏覽器單一 domain 通常 6 條，僅監控、不主動降級）
- `memory_failed` 對應的 UI badge / 提示樣式（payload / publish 落地，UI 顯示**延後**至後續版本）
- `session_archived` 事件的觸發來源（本版只在型別定義中保留欄位，**不**實作觸發邏輯）
- 多 session 共用單一 SSE 連線（每頁 / 每 session 一條，與既有 `POST /messages` SSE 風格一致）

---

## 前置現況

- **既有 SSE pattern**：`backend/app/services/chat_service.py:657-921` 的 `send_message` 為 generator，由 `backend/app/api/v1/chat/router.py:311-327` 的 `POST /sessions/{uid}/messages` 包成 `StreamingResponse(media_type="text/event-stream")`；event 字串格式 `event: <name>\ndata: <json>\n\n`
- **Memory queue**：`backend/app/workers/memory_worker.py:225-240` 在 `chat_memory_repository.create` 後僅有 log，無事件發送
- **DLQ**：`memory_worker.py:279-297` 已實作；payload 含 `session_uid` / `message_uids` / `error` / `ts`
- **既有 RTK Query tag**：`frontend/src/store/chatApi.ts:243-246` `useListMemoriesQuery` 提供 `{ type: "ChatMessages", id: "memories-${sessionUid}" }`，invalidate 後會自動 refetch
- **Auth**：既有 API 走 `Depends(get_current_user)` 解析 `Authorization: Bearer` header；EventSource 不支援自訂 header，本版需另開 query string token 驗證路徑

---

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | 通道形態 | SSE（不引入 WebSocket） |
| 2 | endpoint 切分 | 新增獨立 `GET /api/v1/chat/sessions/{uid}/events`，**不**併入 `POST /messages` 的訊息 SSE |
| 3 | 事件傳遞媒介 | Redis pub/sub channel `chat:session:{uid}:memory`（與既有 list queue 分流） |
| 4 | publish 時機 | memory_worker `chat_memory_repository.create` 成功後，於 commit 前 publish；publish 失敗僅 warning，不影響主流程 |
| 5 | payload 結構 | `{ "event": "memory_updated", "memory_uid": "<uuid>", "ts": <unix> }`（單一 memory_uid，多筆同 session 也分開 publish） |
| 6 | SSE auth | query string `?token=<access_token>`，handler 自行 decode JWT 並驗證 session 擁有者 |
| 7 | 連線生命週期 | 前端頁面 mount → 建立 EventSource；unmount → 關閉 |
| 8 | Backup 策略 | EventSource `onerror` 時 fallback 到 polling 30s；重連成功後恢復 SSE 並停止 polling |
| 9 | 事件型別擴充空間 | 同一個 `/events` endpoint 設計可承載 `memory_updated` / `memory_failed` / `session_archived`，未來不另開 endpoint |
| 10 | `memory_failed` 落地範圍 | DLQ 進入時 publish `memory_failed`（payload 含 `message_uids`、`error`），但前端**不**顯示 UI badge（延後） |
| 11 | `session_archived` | 僅保留型別欄位定義，**不**實作觸發 |
| 12 | 多分頁 SSE 連線數 | 不主動處理；監控若實際撞到瀏覽器 6 條上限，再評估降級為 polling |
| 13 | 心跳 / keep-alive | handler 每 15 秒送 SSE comment（`: ping\n\n`）防止反向代理閒置斷線 |
| 14 | session 不存在 / 非擁有者 | 回 404（不洩漏存在性差異）、不開連線 |

---

## Phase 1：Backend - Redis Pub/Sub 整合

### 1-1 事件型別與 channel 命名

- [x] 新增 `backend/app/services/session_event_service.py`（或併入既有 `chat_service.py` 同層 service，視專案模組組織）：
  - 常數：`MEMORY_CHANNEL_FMT = "chat:session:{session_uid}:memory"`
  - 事件型別字串集中：`EVENT_MEMORY_UPDATED = "memory_updated"`、`EVENT_MEMORY_FAILED = "memory_failed"`、`EVENT_SESSION_ARCHIVED = "session_archived"`（後者僅常數，無觸發）
  - 函式 `async def publish_memory_updated(session_uid: str, memory_uid: str) -> None`：包 try / except，失敗只 log warning
  - 函式 `async def publish_memory_failed(session_uid: str, message_uids: list[str], error: str) -> None`：同上
  - payload schema 統一：`{"event": <name>, "memory_uid": ..., "ts": <unix_seconds>}`（`memory_failed` 改 `message_uids`）

### 1-2 memory_worker 寫完後 publish

- [x] `backend/app/workers/memory_worker.py:225-240` `chat_memory_repository.create(...)` 成功後：
  - 取回新建 row 的 `chat_memory_uid`（若 `create` 未回傳，補回傳）
  - 呼叫 `session_event_service.publish_memory_updated(session_uid, str(memory_uid))`
  - publish 失敗：log warning，**不** raise（不影響主流程、不退入 DLQ）
- [x] `backend/app/workers/memory_worker.py:279-297` DLQ 進入時：
  - 呼叫 `session_event_service.publish_memory_failed(session_uid, message_uids, str(last_err))`
  - 失敗一樣只 log warning

### 1-3 Repository 層回傳 uid 補強（若需）

- [x] 確認 `backend/app/repositories/chat_memory_repository.py` 的 `create()` 是否回傳 model 物件 / uid；若僅回 None，補成回 model（使 worker 取得 `chat_memory_uid`） —（已確認既有實作已 `await db.refresh(memory)` 並回傳 model，無需補強）
- [x] worker 端使用 `str(created.chat_memory_uid)` 作為 publish payload

---

## Phase 2：Backend - SSE Endpoint

### 2-1 Query string token 驗證

- [x] 新增 `backend/app/api/deps.py` 的輔助函式 `get_current_user_from_query(token: str) -> TokenPayload`（或同層獨立函式）：
  - 沿用既有 JWT decode 邏輯（與 `get_current_user` 共用底層 decoder）
  - 失敗 raise `AppError`（401 / `invalid_token`）
- [x] 不修改既有 `get_current_user`（避免影響其他 endpoint）

### 2-2 `/events` SSE handler

- [x] `backend/app/api/v1/chat/router.py` 新增：
  - `GET /sessions/{chat_session_uid}/events`
  - Query：`token: str = Query(...)`（必填）
  - 不掛 `Depends(get_current_user)`（header 路徑）；改在 handler 內走 `get_current_user_from_query(token)` 解析
  - 驗證 session 擁有者：呼叫 `chat_service._ensure_session_owner` 等價邏輯；非擁有者回 404 —（已改為對外公開的 `chat_service.ensure_session_owner_for_events`，內部仍委派 `_ensure_session_owner`）
  - 回 `StreamingResponse(generator(), media_type="text/event-stream")`
  - 加 `headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}`（避免 nginx / 反向代理 buffer）

### 2-3 SSE generator：訂閱 Redis pub/sub

- [x] `chat_service.subscribe_session_events(session_uid: str) -> AsyncIterator[str]`：
  - 取 `redis = get_redis()`
  - `pubsub = redis.pubsub()`、`await pubsub.subscribe(MEMORY_CHANNEL_FMT.format(session_uid=session_uid))`
  - 開場先 yield 一次 `event: ready\ndata: {}\n\n`（讓前端能確認連線建立）
  - main loop：`await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)`
    - 收到訊息：解析 payload → yield `event: <event_name>\ndata: <json>\n\n`
    - timeout 收到 None：yield SSE comment `: ping\n\n`（keep-alive，瀏覽器忽略）
  - finally：`await pubsub.unsubscribe(...)` + `await pubsub.close()`（必須清理，避免 redis 連線洩漏）
  - 對 `asyncio.CancelledError` 捕捉後 re-raise，確保斷線時 cleanup 執行

### 2-4 Session 不存在 / 非擁有者

- [x] 在 SSE 連線**建立前**驗證並回 404；不要先回 200 再 yield error event（避免前端 EventSource 進入重連循環）

### 2-5 Swagger / OpenAPI

- [x] handler 補 `summary="訂閱 Session 級別非同步事件（SSE）"`、`description` 列出可能的 event names 與 payload 範例
- [x] 回應 schema 文件化以註解形式（FastAPI 對 SSE 無內建 response_model 表示）；`/api/docs` 應顯示此端點

---

## Phase 3：Frontend - useSessionEvents Hook

### 3-1 Hook 介面與型別

- [x] 新增 `frontend/src/hooks/useSessionEvents.ts`：
  - 簽名：`useSessionEvents(sessionUid: string | null | undefined): void`（無回傳；side-effect hook）
  - `sessionUid` 為空時：直接 return（避免空頁載入時建連）
- [x] 事件型別常數：與後端對齊
  ```ts
  export type SessionEventName = "memory_updated" | "memory_failed" | "session_archived" | "ready";
  ```

### 3-2 EventSource 建立與 token 取得

- [x] hook 內 `useEffect`：
  - 從既有 token 來源（與 RTK Query baseQuery 同一處）取 access token；若無 token，return（不建連） —（已改為 token 缺漏時直接 fallback 到 polling，避免使用者剛登入頁面切過來時錯失連線）
  - URL：`${API_BASE_URL}/api/v1/chat/sessions/${sessionUid}/events?token=${encodeURIComponent(token)}`（`NEXT_PUBLIC_API_URL` 已含 `/api/v1` 前綴，故 URL 拼接時不再重覆）
  - `const es = new EventSource(url);`
  - `es.addEventListener("memory_updated", handler)`：parse `event.data` → `dispatch(chatApi.util.invalidateTags([{type: "ChatMessages", id: \`memories-${sessionUid}\`}]))`
  - `es.addEventListener("memory_failed", handler)`：parse → 本版**僅 log**（`console.warn`），不顯示 UI；保留事件 listener 給後續 UI badge 接入
  - `es.addEventListener("ready", () => { /* 連線建立成功，停掉 polling fallback */ })`
  - cleanup：`es.close()`

### 3-3 Polling fallback

- [x] hook 內維護 state：`const [pollingActive, setPollingActive] = useState(false);` —（已改為以 `useRef` 持有 polling timer，避免每次切換都觸發 re-render）
- [x] `es.onerror`：
  - `setPollingActive(true)`
  - `es.close()`
  - 排程 5 秒後重新嘗試建立 EventSource（exponential backoff，可選；首版 5s 固定）
- [x] polling 邏輯：`pollingActive === true` 時，`setInterval` 每 30 秒 `dispatch(chatApi.util.invalidateTags([{type: "ChatMessages", id: \`memories-${sessionUid}\`}]))`
- [x] EventSource 重連成功（收到 `ready` 或任意 event）：`setPollingActive(false)` 並 `clearInterval`
- [x] cleanup：unmount 時關閉 EventSource、清掉 polling timer、清掉重連 timer

### 3-4 重連與例外保護

- [x] 同一 session 重複建連保護：`useEffect` deps 為 `[sessionUid]`，避免 token 變動觸發爆量重連
- [x] 連續錯誤：保留錯誤計數，超過閾值（如 5 次連續失敗）退化為僅 polling（不再重試 SSE），避免無謂連線風暴
- [x] hook 自身**不**處理「多分頁同 session SSE 連線數」議題（範圍外，於監控階段觀察）

---

## Phase 4：Frontend - Session 頁面整合

### 4-1 Session 頁面 mount hook

- [x] `frontend/src/app/(main)/sessions/[uid]/page.tsx`：
  - 在現有 `useListMemoriesQuery({ sessionUid })` 旁，呼叫 `useSessionEvents(sessionUid)` —（已改為 `useSessionEvents(session ? sessionUid : null)`，先確保 session 載入成功 / 擁有權通過再建連，避免 404 觸發 SSE 重連風暴）
  - 驗證：mount 時建連、unmount 時關閉（透過瀏覽器 DevTools Network → EventStream 觀察）

### 4-2 抽屜 / 記憶面板互動確認

- [x] 既有「打開抽屜時 refetch」與「手動 🔄 refetch」行為**不**移除（fail-safe，使用者仍可主動觸發）
- [x] SSE invalidate 與既有手動 refetch 共存，RTK Query 內建 dedup 不會重複請求

### 4-3 既有 `POST /messages` SSE 不動

- [x] 確認既有訊息 SSE 行為與本版互不影響（兩條獨立 EventSource / fetch stream）
- [x] 既有 `useSendMessageMutation` 流程不變

---

## Phase 5：驗收

### Backend

- [ ] memory_worker 寫入 `chat_memory` 後，Redis `PUBLISH chat:session:{uid}:memory` 收得到 payload（用 `redis-cli SUBSCRIBE` 手動驗證）
- [ ] payload 為 JSON：`{"event": "memory_updated", "memory_uid": "<uuid>", "ts": <unix>}`
- [ ] memory_worker DLQ 進入時，publish `{"event": "memory_failed", "message_uids": [...], "error": "...", "ts": ...}`
- [ ] publish 失敗（如 Redis 暫時離線）僅 log warning，主流程仍完成 commit
- [ ] `GET /api/v1/chat/sessions/{uid}/events?token=<valid>` 回 200、`Content-Type: text/event-stream`
- [ ] 開啟連線後 15 秒內若無事件，可收到 `: ping\n\n` keep-alive
- [ ] 非擁有者 / 不存在 session 回 404
- [ ] token 失效 / 缺漏回 401
- [ ] `/api/docs` 顯示 `/sessions/{uid}/events` endpoint 與描述

### Frontend

- [ ] 進入 session 頁面後，DevTools Network 出現 EventStream 連線、狀態為 pending（持續開啟）
- [ ] 送出訊息 → 等待 memory_worker 寫入（< 60s）→ 抽屜 / 記憶面板**自動**出現新項目，無需手動 🔄
- [ ] 離開 session 頁面，EventStream 連線立刻關閉
- [ ] 模擬 SSE 斷線（手動 kill backend）：30s 內自動 polling 觸發 refetch；backend 恢復後重連並停掉 polling

### 整合 / 邊界

- [ ] 同一 session 多次寫入 `chat_memory`，每次都收到對應的 `memory_updated`、UI 累計顯示
- [ ] `memory_failed` 事件可從前端 console 確認接收（UI badge 不在本版）
- [ ] 既有「打開抽屜時 refetch」「手動 🔄」行為不變
- [ ] 既有 `POST /messages` 訊息 SSE 不受影響
- [ ] CLAUDE.md：時區仍為 Asia/Taipei；payload 中 `ts` 以 unix seconds 傳遞，前端如需顯示則於 UI 層轉 Asia/Taipei
