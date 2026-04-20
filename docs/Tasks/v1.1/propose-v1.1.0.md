# 目標

1. 建立 Agents 對話功能 (單一 Sessions)
2. 建立專案對話(Projects)功能 (類似 Chatgpt, 但一個專案最多只能放 5 個 Sessions)
3. 針對未來建構 Agentic RAG 與 Hermes Agents 系統架構規劃

## 規則

1. 每 1 個 Agent 可以裝多個 Skills
2. 每 1 個 Session 對應 1 個 Agent（v1.1 鎖 1:1；多 Agent 對話留 v1.2+）
3. 每 1 個 Project 的 Session 數量上限為**系統設定可調**（沿用 `system_setting` 機制，key：`project.max_sessions`，預設 5）
   - 5 的定義：參考 ChatGPT Projects 行為觀察，通常第 4 個 Session 後響應變慢與記憶衰退
   - admin 可於「系統設定」頁調整

## 注意

1. 每次對話都需要進行寫入 PG DB 內部 (未來需要做 RAG 功能, 需考慮分層檢索設計)
2. 針對每位 User, 可以有小小的記憶系統管理 (針對使用者偏好, 摘要等進行回覆)
3. 針對每個 Sessions 需要有相應的記憶系統 (給 Hermes Agent 來產生摘要 Skills, 可以針對會議結論, 會議摘要, 專案架構設計, 繪製架構圖等功能)
4. 每個 Project 也需要有記憶系統功能 (類似層級式的架構)

=> 這邊需要討論是否會大量消耗 Token 問題, 理想上要最精簡 Token 架構
=> OpenRouter 可以採用分層模型架構, 針對重要資訊再進行大型 LLM 處理即可, 其他可以降規 (甚至可以單純用規則推論)

### 記憶寫入 Pipeline（已討論決策）

**寫入時機分兩階段**
1. **對話原文** → 即時同步寫入 PG（低成本、保證保留）
2. **摘要 / 向量化** → 非同步 job（Redis queue），不阻塞使用者回覆

**摘要 pipeline**
```
對話訊息
  ↓
Rule-based 預篩（無 LLM，控 input token）
  ↓ pass
Small LLM 做關鍵字 + topic 抽取（固定 JSON output schema）
  ↓
Embedding（關鍵字串接後向量化）
  ↓
pgvector 寫入 session 記憶表
```

**Rule-based 預篩規則**（待補完）
- 訊息長度 < N 字 → 略過
- 純問候/確認語（"hi"、"好的"、"收到"、"謝謝"）→ 略過
- 純 emoji / 貼圖 → 略過
- 錯誤訊息回聲 → 略過
- **Input token 硬上限**：超過 M tokens 時頭尾保留中間截斷
- 同 session 連續訊息**批次處理**（每 K 則或 idle > T 秒觸發）以攤銷呼叫成本

**固定 output schema（控 output token）**
```json
{
  "keywords": ["..."],
  "entities": ["..."],
  "topic": "...",
  "is_actionable": true
}
```

### 待拍板小點

- 關鍵字抽取用哪個 model？（建議 `anthropic/claude-haiku-4-5` 或 `deepseek/deepseek-chat` 等 cheap tier；由 admin 於 `system_setting` 指定 key `memory.extractor_model`）
- Embedding 方案？
  - A. OpenRouter embeddings endpoint（統一走 OpenRouter）
  - B. 後端 container 內跑 sentence-transformers（本地、無 per-call 成本，但 image 變大）
  - C. OpenAI `text-embedding-3-small` 直連
- 批次 trigger：**每 5 則 vs idle > 60 秒**，先二擇一還是兩個條件 OR？
- 預篩規則清單是否要可配置（寫進 `system_setting` 的 JSON），或 hardcode 在程式碼？

## 平台管理強化

1. **Skills 編輯**（來自 v1.0 使用者回饋）
   - **重新上傳整包**：Skill 詳情頁提供「重新上傳」按鈕，沿用現有上傳流程覆蓋原 zip
   - **線上編輯單一檔案**：Code viewer 加「編輯」切換成 textarea，儲存後回寫進 zip（限文字檔、不支援新增/刪除/改檔名）
   - **使用量提示**：觸發編輯前呼叫 `GET /skills/{uid}/usage` 取得引用此 Skill 的 Agents 清單，Dialog 顯示「N 個 Agent 將套用新內容」
   - 不做 cascade 同步（Agents 靠 skill_uid 關聯，內容變更即時生效）

## Future

1. 儀錶板需要有 AI 查詢功能 (可以針對關鍵字, 找到相似對應的 Agents, Skills 提供使用者參考)
2. 有 API 模式, 使用者可以透過 API 來界接此系統取得相關資料 (當然需要 API Key 管理)
