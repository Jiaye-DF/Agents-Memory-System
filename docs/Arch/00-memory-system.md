# 記憶系統架構（Memory System Architecture）

> 本文件為記憶系統的設計框架與演進藍圖。記錄「為什麼這樣設計」與「該往哪裡走」，補足 [Design-Base](../Design-Base/) 偏實作規範、Tasks 偏單版本實作清單的缺口。
>
> 相關文件：
>
> - [Design-Base/00-overview.md](../Design-Base/00-overview.md) — 系統總覽、技術棧
> - [Tasks/v1.3/propose-v1.3.0.md](../Tasks/v1.3/propose-v1.3.0.md) — v1.3 三層記憶 / SSE / Skill 工廠規劃
> - [backend/app/workers/memory_worker.py](../../backend/app/workers/memory_worker.py) — 目前的抽取 pipeline 實作
> - [backend/app/repositories/chat_memory_repository.py](../../backend/app/repositories/chat_memory_repository.py) — 目前的 vector 檢索實作

---

## 1. 目的

定義記憶系統的**完整架構藍圖**與**演進順序**，回答三個問題：

1. 哪些資料適合走 RAG（向量檢索）、哪些不適合
2. 完整 pipeline 應該長什麼形狀（終極形態）
3. 從目前狀態到終極形態，該按什麼順序加元件

本文件**不**列實作細節 — 細節由各版本 `tasks-vX.Y.Z.md` 承接。

---

## 2. 核心觀念：RAG 的適用邊界

### 2-1 RAG 是什麼

`RAG = Retrieval-Augmented Generation` — 在 LLM 生成前，先從某個庫撈出相關資料塞進 prompt。三步：

- **Retrieval**：用某種方式找出相關內容（向量、關鍵字、SQL 都算）
- **Augmented**：把撈到的塞進 prompt
- **Generation**：LLM 根據 prompt 生成

**重點**：RAG 不等於 vector search。vector 只是其中一種 retrieval 方式。

### 2-2 適用判斷準則

> **RAG 解決的是「語意模糊」+「資料量大到塞不進 prompt」的問題。任一邊不成立，就用更簡單的工具。**

| 資料類型 | 用 RAG？ | 用什麼 | 理由 |
| --- | --- | --- | --- |
| `chat_memory`（session 對話片段） | ✅ | 向量檢索 | 量大、語意模糊（「之前提過的那個 bug」） |
| `project_memory`（跨 session 主題聚合） | ✅ | 向量 + scope filter | 跨 session 找相關討論，仍是語意匹配 |
| `user_memory`（長期偏好） | ⚠️ 半適合 | 通常**全部**塞 prompt | 數量小（< 50 筆），不需 retrieval |
| Skill / 規範文件 | ✅ | 向量 + 關鍵字混合 | 多份 md，需找與任務相關的規範 |
| `chat_message`（聊天訊息原文） | ❌ | 直接 SQL `ORDER BY created_at DESC LIMIT N` | 已有時序、scope，SQL 比 vector 快 100 倍 |
| Agent / Session 列表 | ❌ | SQL | 結構化資料、精確查詢 |

**新手陷阱**：學會 vector search 後容易「什麼都想 vector」。判斷依據永遠是「**語意模糊嗎？資料塞得下嗎？**」，兩者都成立才需要 RAG。

---

## 3. 終極架構（目標形狀）

```text
User Input
    │
    ▼
┌─────────────────────────┐
│ [1] 路由分類器           │
│   skip / cheap / expensive
└─┬───────────────┬───────┘
  │ skip          │ cheap         │ expensive
  ▼               ▼               ▼
固定字串       haiku 直接答    ┌──────────────────┐
                              │ [2] embedding     │
                              └────────┬─────────┘
                                       ▼
                              ┌──────────────────┐
                              │ [3] 三層 vector   │
                              │   search          │
                              │   ├─ session      │
                              │   ├─ project      │
                              │   └─ user         │
                              │   各撈 top 20~50  │
                              └────────┬─────────┘
                                       ▼
                              ┌──────────────────┐
                              │ [4] RRF 融合      │
                              │   合併三層結果    │
                              └────────┬─────────┘
                                       ▼
                              ┌──────────────────┐
                              │ [5] Reranker      │
                              │   挑 top 3~5      │
                              └────────┬─────────┘
                                       ▼
                              ┌──────────────────┐
                              │ [6] 塞進 Prompt   │
                              └────────┬─────────┘
                                       ▼
                              ┌──────────────────┐
                              │ [7] 主 model      │
                              │   串流回答        │
                              └──────────────────┘
```

### 設計原則

1. **單一主 LLM 呼叫**：整條 pipeline 只有 [7] 是主 model 推理。其他元件（classifier / embedding / reranker）成本低 1~3 個量級。
2. **不在 retrieval 後再用 LLM 摘要**：摘要 = 壓縮 = 失真。除非真的塞不下 context，否則不加。判斷門檻：`total_retrieved_tokens > context_budget * 0.5`。
3. **不加意圖推斷器**：embedding 本身就是「意圖的數學表達」，不需要先用 LLM 翻譯一次。
4. **每加一個元件前，先驗證痛點存在**：不要憑想像加複雜度。

---

## 4. 元件職責總覽

| 元件 | 職責 | 解決的問題 | 成本量級 |
| --- | --- | --- | --- |
| [1] 路由分類器 | 決定**走哪條路**（skip / cheap / expensive） | 省金錢（避免無謂呼叫貴 model） | 極低（規則 / 小 model） |
| [2] embedding | 把語意變成 1536 維**座標** | 讓「相似 = 距離近」可計算 | 極低 |
| [3] vector search | 找**鄰居**（cosine 相似度） | 從大量資料快速縮小範圍 | 極低（pgvector） |
| [4] RRF 融合 | 把多層 / 多源結果**合併排序** | 跨層 RAG 的尺度不一致問題 | 0（純算術） |
| [5] reranker | 從候選裡**精挑** top N | 提升精準度（vector 撈的順序不一定對） | 低（cross-encoder ~50ms） |
| [6] Prompt 組裝 | 把 retrieval 結果 + 對話歷史 + system prompt **拼起來** | — | 0 |
| [7] 主 model | **生成**最終答案 | 推理、措辭、創造 | 高（主要成本所在） |

**關鍵觀念**：每個元件做一件事、不重疊。如果發現兩個元件做類似的事，通常代表其中一個是冗餘的（例：意圖推斷器 vs embedding）。

### 命名澄清

| 容易混淆的名稱 | 在做什麼 | 推薦用法 |
| --- | --- | --- |
| 意圖推斷器（Intent Classifier） | 推斷使用者「**想做什麼**」（道謝 / 查詢 / code review...） | ❌ 不採用 — 與 embedding 重疊，且 output 是標籤，下游還要 if/else 才能變動作 |
| **路由分類器（Routing Classifier）** | 決定「該走哪條路」（skip / cheap / expensive） | ✅ propose §4-2 採用 — output 直接是動作 |
| 語意分類器 | 詞義模糊 — 容易被當成意圖推斷器 | 不建議使用此名稱 |

判斷標準：**分類器的 output 應該是「動作」，不是「標籤」。**

---

## 5. 三層記憶設計

### 5-1 層次定義

| 層 | scope | 寫入時機 | 預期數量 | 生命週期 |
| --- | --- | --- | --- | --- |
| `chat_memory` | session | 對話進行中（worker 即時抽取） | 數十 ~ 數百 / session | session 刪除即清 |
| `project_memory` | project | 二次聚合 worker（idle / 手動觸發） | 數十 ~ 數百 / project | project 刪除即清 |
| `user_memory` | user | 跨 project 聚合 worker | < 100 / user | user 停用 / 刪除才清 |

### 5-2 生命週期硬規範

> 詳見 [propose-v1.3.0.md §3-3](../Tasks/v1.3/propose-v1.3.0.md)

| 刪除動作 | 連動清除 | **不**連動 |
| --- | --- | --- |
| Session 刪除 | `chat_memory`（session scope） | `project_memory`、`user_memory` |
| Project 刪除 | Project 內 sessions 的 `chat_memory`、`project_memory` | `user_memory` |
| User 停用 / 刪除 | 全部三層 | — |

**不可違反**：`project_memory` / `user_memory` 不建立指向 session 的 FK cascade。違反會導致跨層聚合被 session 刪除誤抹。

### 5-3 為何要分三層

- **不分層**：所有記憶混在一張表，scope 用欄位過濾 — 實作最簡單
- **分三層的理由**：
  1. 生命週期不同（見 §5-2）
  2. 寫入頻率不同（chat 即時、project 定期、user 偶爾）
  3. 抽取邏輯不同（chat 是片段、project 是聚合、user 是長期偏好）
  4. 檢索策略可獨立調（每層各自的 top_k / min_score）

---

## 6. Threshold 機制

vector search 兩個正交門檻，**必須**同時用：

### 6-1 min_score（相似度下限）

「**低於這個分數的，當作不相關，直接丟掉**」

- 範圍：0 ~ 1（cosine similarity，越高越相似）
- 建議起點：0.6 ~ 0.75
- 太低 → 撈到雜訊污染 prompt
- 太高 → 撈不到任何東西，等於沒用 RAG

### 6-2 top_k（數量上限）

「**最多只取 N 筆**」

- 建議起點：5 ~ 20
- 太少 → 漏掉相關內容
- 太多 → 佔 prompt 空間、稀釋訊號

### 6-3 兩者協同

SQL 同時套用：

```sql
WHERE 1 - (embedding <=> :query) >= :min_score
ORDER BY embedding <=> :query
LIMIT :top_k
```

行為：

- 100 筆都 >= min_score → 取 top_k 筆
- 3 筆 >= min_score → 取 3 筆（不湊滿 top_k）
- 0 筆 >= min_score → 不塞 RAG 結果，純靠 model 自己答

**心法**：寧可不撈，也不要撈錯。撈錯比撈不到更糟，因為 LLM 會被誤導。

---

## 7. 演進路線（實作順序）

不要一次到位。每加一個元件前，**先確認痛點實際存在**。

| 階段 | 加什麼 | 觸發條件 | 對應版本 |
| --- | --- | --- | --- |
| 0 | 最小可行 RAG（embedding → vector search → prompt → 主 model） | — | ✅ v1.1 已完成 |
| 1 | Threshold 調校 + 觀察 | 看 retrieval 撈出來的東西合不合理 | 持續進行 |
| 2 | 三層記憶 + RRF 融合 | 單層 RAG 不足以涵蓋跨 session 場景 | v1.3.5 |
| 3 | 路由分類器 | 觀察到「N% 訊息根本不該打貴 model」 | v1.3.4 |
| 4 | Reranker | 觀察到 vector 撈出的排序不夠準 | v1.4+ |
| 5 | Hybrid search（vector + BM25） | 純語意匹配漏掉精確關鍵字場景 | v1.4+ |
| 6 | Query rewriting | 使用者輸入太短 / 太模糊 | 撞牆才加 |

**新手原則**：

- 一次只動一個變數（工程通則）
- 加元件前先收集數據驗證痛點
- 能用 SQL 解決就不用 vector，能用 vector 就不用 LLM，能用 1 次 LLM 就不用 2 次

---

## 8. 開源方案借鑑（不整合，借設計）

整包整合的成本通常高於收益。建議「**借設計，不借程式碼**」：

| 來源 | 借什麼 | 借到哪裡 |
| --- | --- | --- |
| [mem0](https://github.com/mem0ai/mem0) | 衝突合併 prompt（add / update / delete / noop 四向決策） | v1.3.5 user_memory 抽取（避免重複堆積） |
| [Zep / Graphiti](https://github.com/getzep/zep) | temporal validity（記憶的時間衰減 / 失效） | 未來 user_memory 演化 |
| [Cognee](https://github.com/topoteretes/cognee) | pipeline trace 切點 | propose §3-4 可觀察性 |
| [Elasticsearch RRF](https://www.elastic.co/guide/en/elasticsearch/reference/current/rrf.html) | RRF 公式 `score = Σ 1/(k + rank)`，k=60 | propose §3-2 三層融合 |
| [bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) | 開源 reranker，中文好、本地可跑 | 階段 4 reranker 接入 |
| [ragas](https://github.com/explodinggradients/ragas) | context_precision / context_recall 指標 | propose §3-4 層 2 評估 |

**不採用整合的理由**：

- 多數框架預設 OpenAI，與本專案 OpenRouter 體系需 wrapper
- chat_service / memory_worker / Skill 工廠耦合度已成形，整合會搶 ownership
- 守住 schema 與 Design-Base 一致性比拿到「免費」功能更重要

---

## 9. 與其他文件的關係

| 文件 | 角色 |
| --- | --- |
| 本文件（`docs/Arch/00-memory-system.md`） | **設計藍圖** — 為什麼這樣設計、該往哪裡走 |
| [`docs/Design-Base/*`](../Design-Base/) | **實作規範** — 程式碼風格、資料庫設計、API 規範 |
| [`docs/Tasks/v*/propose-*.md`](../Tasks/) | **單版本構想** — 該版本要做什麼、為什麼 |
| [`docs/Tasks/v*/tasks-*.md`](../Tasks/) | **單版本實作清單** — 該版本實際拆成的工作項 |

**優先順序**（衝突時）：

`Design-Base`（實作規範） > **本文件**（架構藍圖） > `propose`（單版本構想） > `tasks`（單版本清單）

理由：實作規範是底線，架構藍圖是長期方向，單版本文件可隨版本調整。

---

## 10. 變更記錄

| 日期 | 版本 | 變更 |
| --- | --- | --- |
| 2026-04-25 | 0.1 | 初版：定義終極架構 + 演進路線 + RAG 適用邊界 |
