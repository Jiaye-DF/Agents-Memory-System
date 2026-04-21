# v1.1 修正記錄

> 驗收 v1.1.4 游離 Session 功能時陸續發現的 bug 與修正。

---

## 1. ChatMessage / ChatMemory 跨 DeclarativeBase 的 FK 解析失敗

**問題**：送第一則訊息時，SQLAlchemy 於 `flush()` 的 `_sorted_tables` 步驟拋錯：

```text
sqlalchemy.exc.NoReferencedTableError: Foreign key associated with
column 'chat_message.chat_session_uid' could not find table 'chat_session'
```

根因：`ChatMessage` 繼承自 `MessageBase(DeclarativeBase)`、`ChatMemory` 繼承自 `MemoryBase(DeclarativeBase)`，兩者與 `ChatSession`（繼承 `Base`）**分屬不同 metadata**。Python 層的 `ForeignKey("chat_session.chat_session_uid")` 只在同一 metadata 中查表名，跨 base 找不到 → flush 時整個對話 API 炸。

這個 bug 從 v1.1.1 實作起就存在，但只有真的 insert chat_message 時才觸發；送訊息前的 CRUD 都走 `Base` 內部 FK，才沒被發現。

**修正**：移除 Python 層 `ForeignKey` 標記（本來就沒有 ORM `relationship()` 使用它），資料完整性由 DB migration 的 `FOREIGN KEY` constraint 保證。

**影響檔案**：

- `backend/app/models/chat_message.py`
- `backend/app/models/chat_memory.py`

---

## 2. OPENROUTER_API_KEY 未傳入 backend container

**問題**：對話失敗、錯誤訊息「OPENROUTER_API_KEY 未設定，無法呼叫對話 API」。`.env` 有設值但 container 看不到。

根因：`docker-compose.dev.yml` 的 `backend.environment` 沒列 `OPENROUTER_API_KEY`。Docker Compose 只會把 `.env` 展開到 `${VAR}` 被 reference 的地方 — 沒 reference 就不會進 container。

**修正**：在 `backend.environment` 補上 `OPENROUTER_API_KEY`、`OPENROUTER_HTTP_REFERER`、`OPENROUTER_APP_TITLE`、`SKILLS_MAX_FILE_SIZE`、`SKILLS_UPLOAD_DIR` 共 5 個 keys。配合 `docker compose up -d backend`（非 `restart`）讓 compose 重建 container 套用。

**影響檔案**：

- `docker-compose.dev.yml`

---

## 3. Anthropic structured output 不支援 maxItems / maxLength

**問題**：記憶 worker 呼叫 `extract_memory` 時收到 400：

```text
output_config.format.schema: For 'array' type, property 'maxItems' is not supported
```

使用預設 extractor model `anthropic/claude-haiku-4-5` 經 OpenRouter 轉發到 Anthropic 時，Anthropic 的 structured output 規範不收 JSON schema 的 `maxItems` / `maxLength` 約束，批次 3 次重試後丟 DLQ。

**修正**：

1. `MEMORY_EXTRACT_JSON_SCHEMA` 移除 `maxItems` 與 `maxLength`，只保留型別宣告（對所有供應商通用）
2. `extract_memory()` 內在 `json.loads()` 後、`model_validate()` 前做強制截斷：`keywords[:20]`、`entities[:20]`、`topic[:200]`
3. Prompt 指示保留「最多 20 個 / 200 字」，第一道仍靠模型自覺遵守

三層防禦：Prompt → ~~Schema~~（被 Anthropic 拒）→ Post-parse 截斷。

**影響檔案**：

- `backend/app/clients/openrouter/client.py`

---

## 4. useListAgentsQuery limit=100 超過後端上限

**問題**：新對話 / 對話列表、Agent 選單下拉永遠空白。後端 log 出現連續 422：

```text
GET /api/v1/agents?limit=100 HTTP/1.1" 422 Unprocessable Content
query -> limit: Input should be less than or equal to 50
```

前端多處 `useListAgentsQuery({ limit: 100 })`，但 `/api/v1/agents` 端點 `Query(20, ge=1, le=50)`，422 後 RTK Query `baseApi` 把 error 吞掉 → `agents = []` → 下拉永遠空的。此 bug 自 v1.1.1 埋著，之前因單一 agent 狀況沒暴露。

同時掃到 `useListProjectsQuery({ limit: 100 })` 也有同問題（後端上限同樣 50）。

**修正**：三處 `limit: 100` 全部改為 `limit: 50`（對齊後端上限）。

**影響檔案**：

- `frontend/src/app/(main)/sessions/new/page.tsx`
- `frontend/src/app/(main)/projects/[uid]/page.tsx`
- `frontend/src/app/(main)/sessions/[uid]/page.tsx`

---

## 5. Next.js Turbopack routing cache 失效造成 /agents/[uid]/edit 404

**問題**：`/agents/:uid/edit` 回 404，但 `page.tsx` 明確存在於正確路徑。同一個 `AgentForm` 被 `/agents/new` 使用就能正常載入（200），單獨 `/edit` 掛。

根因：多輪檔案 edit + docker restart 累積，Turbopack 的 `.next` routing manifest 沒正確更新巢狀動態路由 `[uid]/edit/page.tsx`。

**修正**：清掉 container 內的 `.next` cache，重啟 container 強制重建。

```bash
docker compose -f docker-compose.dev.yml exec -T frontend rm -rf .next
docker compose -f docker-compose.dev.yml restart frontend
```

此為 Turbopack 已知 cache invalidation 行為，非程式碼 bug。

**影響檔案**：無程式碼改動。

---

## 6. updateSession mutation 沒刷側欄「最近對話」

**問題**：點對話標題 inline 改名後，主畫面 title 變了，但側欄「最近對話」清單仍顯示舊名。

根因：`updateSession` mutation 只 `invalidatesTags: ["ChatSessions"]`，但側欄 `useListOrphanChatSessionsQuery` 的 tag 是 `OrphanChatSessions`，不會被刷。

**修正**：`invalidatesTags` 加入 `"OrphanChatSessions"`，改完名瞬間兩邊同步。

**影響檔案**：

- `frontend/src/store/chatApi.ts`

---

## 處理狀態

| # | 項目 | 狀態 | Commit（待 commit-all） |
| --- | --- | --- | --- |
| 1 | ChatMessage / ChatMemory FK | ✅ 已修 | — |
| 2 | OPENROUTER_API_KEY passthrough | ✅ 已修 | — |
| 3 | Anthropic schema maxItems | ✅ 已修 | — |
| 4 | useListAgentsQuery limit=100 | ✅ 已修 | — |
| 5 | Turbopack 404 | ✅ 清 cache 解決 | — |
| 6 | updateSession tag invalidation | ✅ 已修 | — |

---

## 殘留清理項

- DLQ（`chat:memory:dlq`）有 1 筆失敗批次（Issue #3 被擋下的那次），fix 部署後不會自動重試。清除方式：
  ```bash
  docker compose -f docker-compose.dev.yml exec -T redis redis-cli DEL chat:memory:dlq
  ```
