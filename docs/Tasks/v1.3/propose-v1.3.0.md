# v1.3 Propose

> 本文件為 v1.3+ 的構想與討論紀錄。定稿後拆為 `tasks-v1.3.*.md` 規格文件再進行實作。
>
> 前置版本：[v1.1 propose](../v1.1/propose-v1.1.0.md)、[v1.2 propose](../v1.2/propose-v1.2.0.md)

---

## 0. 前置假設

v1.2 已完成並作為基線：

- 多 Agent 對話
- 分層 Model Classifier
- User / Project 層記憶與三層 RAG 檢索

---

## 1. 版本目標

1. **儀表板 AI 查詢**：以自然語言查詢「相似 Agents / Skills」、使用統計
2. **公開 API 模式 + API Key 管理**：提供外部系統以 API Key 呼叫 Agent 對話

### 範圍內

- 儀表板 AI 查詢入口（chat box → 關鍵字萃取 → 向量檢索 Agents / Skills）
- API Key CRUD、scope 限制、rate limit
- 對外公開的對話 API（對應 v1.1 對話 pipeline）

---

## 2. 待討論項目

### 2-1 儀表板 AI 查詢

- **查詢對象**：Agents / Skills / 使用統計（誰在用哪個 Agent、哪個 Skill 熱門）
- **實作方向**：
  - Agents / Skills 本身也做 embedding（name + description）
  - 使用者輸入自然語言 → 向量檢索 → 回傳列表
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

等 v1.2 實作完、觀察一段時間再啟動 propose 細化。
