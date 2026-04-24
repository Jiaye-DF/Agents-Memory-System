# v1.4 Propose

> 本文件為 v1.4+ 的構想與討論紀錄。定稿後拆為 `tasks-v1.4.*.md` 規格文件再進行實作。
>
> 前置版本：[v1.1 propose](../v1.1/propose-v1.1.0.md)、[v1.2 propose](../v1.2/propose-v1.2.0.md)、[v1.3 propose](../v1.3/propose-v1.3.0.md)
>
> 註：本文內容原屬「v1.3 propose」，因 v1.2 重規劃（收藏 / 下載 / 腳本管理 / 儀錶板排行），整體版本順序後移一格 — 原 v1.2 → 新 v1.3、原 v1.3 → 新 v1.4。

---

## 0. 前置假設

v1.3 已完成並作為基線：

- 多 Agent 對話、Session ↔ Agent 1:N
- 分層 Model Classifier
- User / Project 層記憶與三層 RAG 檢索
- Agentic Skill 工廠正式版（跨層記憶、Skill 自動推薦）
- 記憶 / LLM 可觀察性與 SSE `memory_updated` 事件推播

同時 v1.2（收藏 / 下載 / 腳本管理 / 儀錶板排行）亦已完成，本版會直接消費：

- Agents / Skills / Scripts 的 `favorite_count` / `download_count` 已累積一定樣本
- 儀錶板首頁已有「熱度 / 收藏」排行 filter（規則式）

---

## 1. 版本目標

1. **儀表板 AI 查詢**：以自然語言查詢「相似 Agents / Skills / Scripts」、使用統計，補充 v1.2 規則式排行無法涵蓋的模糊意圖
2. **公開 API 模式 + API Key 管理**：提供外部系統以 API Key 呼叫 Agent 對話

### 範圍內

- 儀表板 AI 查詢入口（chat box → 關鍵字萃取 → 向量檢索 Agents / Skills / Scripts）
- API Key CRUD、scope 限制、rate limit
- 對外公開的對話 API（對應 v1.1 對話 pipeline）

---

## 2. 待討論項目

### 2-1 儀表板 AI 查詢

- **查詢對象**：Agents / Skills / Scripts / 使用統計（誰在用哪個 Agent、哪個 Skill 熱門）
- **實作方向**：
  - Agents / Skills / Scripts 本身也做 embedding（name + description）
  - 使用者輸入自然語言 → 向量檢索 → 回傳列表
  - 與 v1.2 排行 filter 並存：排行 = 量化指標（熱度 / 收藏）、AI 查詢 = 語意意圖
- **權限**：admin 看全平台、member 只看自己擁有或公開的

### 2-2 公開 API + API Key 管理

- **Key 結構**：`owner_user_uid` / `name` / `scopes`（e.g. `chat:read` / `chat:write`）/ `last_used_at` / `expires_at`
- **Rate Limit**：每 Key 每分鐘 / 每日配額，由 admin 在 `system_setting` 設預設值
- **對外 API**：
  - `POST /public/v1/sessions/{uid}/messages`：送訊息
  - `GET  /public/v1/sessions/{uid}/messages`：查歷史
- **計費維度**：延用 v1.1 的 `message.cost_usd` 聚合，按 API Key 分組

### 2-3 安全與審計

- API Key 僅在建立時顯示一次
- 儲存 hash（argon2 / bcrypt），驗證時比對
- Audit log：記錄每次呼叫的 key_uid / endpoint / status / latency

---

## 3. 下一步

等 v1.3 實作完、觀察一段時間再啟動 propose 細化。
