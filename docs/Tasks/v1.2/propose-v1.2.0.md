# v1.2 Propose

> 本文件為 v1.2 的構想與討論紀錄。定稿後拆為 `tasks-v1.2.*.md` 規格文件再進行實作。
>
> 前置版本：[v1.1 propose](../v1.1/propose-v1.1.0.md)

---

## 0. 前置假設

v1.1 已完成並作為基線：

- Session ↔ Agent 1:1 對話、訊息持久化
- Project / Session / Message / session_memory 資料表
- Session scope 的 Agentic RAG
- `system_setting` 已包含 `rag.scopes` / `rag.top_k` / `rag.min_score`

---

## 1. 版本目標

1. **多 Agent 對話**：放寬 Session:Agent 為 1:N，一個 Session 可同時掛多個 Agent 協作
2. **分層 Model Classifier**：前置 classifier 判斷訊息是否需要送大模型，降低成本
3. **User / Project 層記憶**：跨 Session 記憶聚合與檢索

### 範圍內

- Session ↔ Agent 多對關聯、Agent 切換 / 呼叫策略
- 訊息分類 pipeline（classifier → router → LLM）
- `project_memory` / `user_memory` 表與聚合 worker
- RAG 三層檢索（session / project / user）融合策略

### 範圍外（延後）

- v1.3+：儀表板 AI 查詢、公開 API + API Key 管理

---

## 2. 待討論項目

### 2-1 多 Agent 對話

- **觸發方式**：使用者 @mention 指定 Agent？還是 LLM 自動 routing？
- **順序**：多 Agent 回應是串行（A → B）還是並行（同時跑取 best）？
- **對話歷史歸屬**：一則 assistant 訊息綁一個 Agent，前端顯示誰說的
- **Schema 變更**：`session_agent` 中介表（session_uid, agent_uid, role），取代 v1.1 的 `session.agent_uid`

### 2-2 分層 Model Classifier

- **Classifier 模型**：極小模型（e.g. local DistilBERT / 規則引擎）先判斷「是否需要 LLM 回覆」
- **三層分流**：
  1. 無需回覆（系統訊息、純表情） → 不呼叫 LLM
  2. 簡單問答 → cheap LLM（haiku / deepseek）
  3. 複雜推理 → 主 LLM
- **設定 key**：`classifier.enabled` / `classifier.model` / `classifier.thresholds`
- **量測指標**：classifier 誤判率、整體成本下降百分比

### 2-3 User / Project 層記憶

- **Project 記憶**：定期從該 Project 下所有 Session 的 `session_memory` 做二次聚合（同主題合併）
- **User 記憶**：跨 Project 的長期偏好（e.g. 使用者常用語言、偏好回覆風格）
- **寫入時機**：Session 結束 / idle N 小時 / 手動觸發
- **Schema**：`project_memory`、`user_memory` 結構類似 `session_memory` 但多一個 `source_session_uids[]`
- **檢索融合**：三層 top_k 合併後重新排序（RRF？加權求和？）

---

## 3. 下一步

等 v1.1 實作完、觀察一段時間再啟動 propose 細化。
