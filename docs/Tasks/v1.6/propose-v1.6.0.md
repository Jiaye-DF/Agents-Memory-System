# v1.6.0 Propose — Skills RAG 語意檢索 + AI 分析

> 本文件為 v1.6.0 的構想與討論紀錄。定稿後於 [tasks-v1.6.0.md](tasks-v1.6.0.md) 進行實作。
>
> 前置版本：[propose-v1.5.1.md](../v1.5/propose-v1.5.1.md)（Tag 分類，與本版無資料相依，可並存）

---

## 0. 前置假設

- 專案已具備完整三層 RAG 基礎設施（v1.1 ~ v1.3.5）：
  - pgvector extension（[V1](../../../migrations/sql/V1__create_extension_pgvector.sql)）、`VECTOR(1536)` + HNSW cosine index 範式（[V22](../../../migrations/sql/V22__create_chat_memory_table.sql) / [V44](../../../migrations/sql/V44__create_project_memory_table.sql)）
  - embedding 產生統一走 [`llm_metering.call_llm_metered(purpose=PURPOSE_EMBEDDING)`](../../../backend/app/services/llm_metering.py)（`text-embedding-3-small`，1536 維）
  - cosine 檢索範式 [`chat_memory_repository.search_similar`](../../../backend/app/repositories/chat_memory_repository.py)（`1 - (embedding <=> query)` 為 score）
- **LLM 呼叫集中進入點硬規範**（docs/Arch/01-observability-and-metrics.md §2-3）：除 `llm_metering` 外禁止任何模組直接呼叫 OpenRouter client。本版新增的「AI 分析」LLM 呼叫**必須**走 `call_llm_metered`，新增一個 `purpose` 與 dispatch 分支。
- 既有 Skills 查詢（[`skills/page.tsx`](../../../frontend/src/app/(main)/skills/page.tsx)）為**純前端過濾**（`matchByTextAndAuthor` 對已載入的 ≤50 筆做名稱/描述比對），後端**無**搜尋 endpoint、`skill` 表**無** embedding 欄位。
- `skill` 內容以 ZIP 存於 S3（`storage_key`，v1.5.0 定型），既有 [`get_file_content`](../../../backend/app/services/skill_service.py) 已能解壓讀取單檔文字。

---

## 1. 版本目標

在既有 Skills 管理頁的關鍵字查詢之外，**新增一個獨立的「AI 分析」語意檢索模式**：使用者輸入自然語言需求 → 後端以向量檢索找出語意最相近的 Skill → 再由 LLM 生成「為什麼這個 Skill 符合你的需求」的推薦理由，並在結果標示「AI 分析」字樣。

1. **`skill` 表加向量欄位**，內容 = 名稱 + 描述 + 檔案內容（`.md` / `.txt`）
2. **寫入側自動維護 embedding**：upload / reupload / 描述更新後同步重算（失敗不擋主流程）
3. **既有資料回填** embedding（backfill script）
4. **新增語意檢索 endpoint** `POST /api/v1/skills/search`
5. **LLM 生成推薦理由**（可由 system_setting 開關；關閉時只回向量結果）
6. **前端加「AI 分析」模式切換**，與現有關鍵字過濾並存，結果標示「AI 分析」徽章 + 理由文字

### 範圍內

- 後端：
  - `skill` 表加 `embedding VECTOR(1536) NULL` + HNSW index（**V56**）
  - seed 語意檢索 / AI 分析相關 `system_setting`（**V57**）
  - `skill` model 加 `embedding` 欄位
  - `skill_embedding_service`：組文字（name + description + 檔案內容）→ embedding
  - `skill_service`：upload / reupload / update 後 hook 更新 embedding
  - `skill_repository.search_similar`：cosine + visibility 過濾
  - `skill_service.semantic_search`：query embedding → 檢索 → （選配）AI 分析
  - `llm_metering` 新增 `PURPOSE_SKILL_ANALYZE` + dispatch 分支；OpenRouter client 加 `analyze_skill_matches`
  - `POST /api/v1/skills/search` endpoint + Swagger schema
  - `backend/scripts/backfill_skill_embedding.py` 回填既有資料
- 前端：
  - `skillsApi.ts` 加 `useSemanticSearchSkillsMutation`（或 lazy query）
  - [`skills/page.tsx`](../../../frontend/src/app/(main)/skills/page.tsx) 加「AI 分析」模式切換 + 結果渲染（score / 理由 / 徽章）
- 測試：embedding 組文字、search_similar cosine 排序 / visibility、semantic_search 開關 AI 分析

### 範圍外（延後）

- Script / Agent 的語意檢索（本版僅 Skill；範式定型後 v1.6.x 再複製）
- 公開市集 / dashboard 的語意檢索入口（本版僅 `/skills` 管理頁）
- 混合檢索（keyword + vector 的 RRF 融合）—— 本版關鍵字與語意為**互斥兩模式**，不融合
- 檔案內容分塊（chunking）與多向量 —— 本版一個 skill 一個向量（name+desc+截斷內容）
- embedding 重算的背景 worker / 佇列 —— 本版走同步 inline（失敗 log，不阻塞）
- Re-ranking 模型 / cross-encoder

---

## 2. 資料模型

### 2-1 為什麼在 `skill` 表加欄位（而非獨立向量表）

| 方案 | 評估 |
| --- | --- |
| 獨立 `skill_embedding` 表（1:1） | 多一張表 + join；skill 與其向量本質 1:1、同生命週期，拆表無益 |
| 獨立多向量表（1:N，chunking） | 為未來 chunking 保留彈性，但本版一個 skill 一向量，過度設計 |
| **`skill` 表加 `embedding` 欄位** ✅ | 1:1 同生命週期，soft-delete 自然連動，checkbox 過濾最簡單 |

### 2-2 `embedding` 欄位（V56）

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `embedding` | `VECTOR(1536)` **NULL** | 允許 NULL：既有資料尚未回填、或生成失敗時為 NULL；檢索時 `WHERE embedding IS NOT NULL` 排除 |

- 索引：`idx_skill_embedding_hnsw ON skill USING HNSW (embedding vector_cosine_ops)`（沿用 [V44:38](../../../migrations/sql/V44__create_project_memory_table.sql) 範式）
- **為什麼 NULL 而非 NOT NULL**：`chat_memory` 的 embedding 是 NOT NULL，因為它由 worker 產生時必有向量；但 `skill` 是既有既存資料 + 使用者上傳當下同步生成可能失敗，強制 NOT NULL 會讓上傳失敗或 migration 卡住。故用 NULL + 檢索過濾。

### 2-3 `system_setting` seed（V57）

沿用 [V46](../../../migrations/sql/V46__seed_three_layer_rag_settings.sql) 的 `INSERT ... ON CONFLICT DO NOTHING` 範式：

| key | 預設 | value_type | 說明 |
| --- | --- | --- | --- |
| `skill.rag.enabled` | `true` | boolean | 語意檢索總開關；關閉時 endpoint 回空 |
| `skill.rag.top_k` | `8` | integer | 向量檢索回傳筆數上限 |
| `skill.rag.min_score` | `0.5` | string | 最低 cosine 相似度（跨語意較鬆，低於記憶層的 0.6~0.7） |
| `skill.rag.analyze_enabled` | `true` | boolean | 是否呼叫 LLM 生成推薦理由；關閉時只回向量結果 |
| `skill.rag.analyze_top_n` | `5` | integer | 丟給 LLM 生成理由的前 N 筆（控制成本） |
| `skill.rag.analyze_model` | `"anthropic/claude-haiku-4-5"` | json | AI 分析使用的小模型 ID（對齊 [`memory.aggregation_extractor_model`](../../../migrations/sql/V46__seed_three_layer_rag_settings.sql)） |
| `skill.rag.embed_content_max_chars` | `8000` | integer | 組 embedding 文字時，檔案內容截斷上限（避免超長文本） |

---

## 3. Embedding 生成策略

### 3-1 組文字來源（決策：名稱＋描述＋檔案內容）

`skill_embedding_service.build_embedding_text(skill, zip_bytes) -> str`：

```
{name}

{description}

{檔案內容}
```

- 檔案內容：解壓 ZIP，取副檔名 `.md` / `.txt` 的檔案（依路徑排序，`SKILL.md` / `README.md` 優先），串接後截斷至 `skill.rag.embed_content_max_chars`
- 只取文字類檔案，跳過二進位；解壓失敗 → 退化為只用 name + description（不擋）
- 與既有 [`EDITABLE_EXTENSIONS`](../../../backend/app/services/skill_service.py) 精神一致，但這裡只需 `.md` / `.txt`（可讀性最高的說明文字）

### 3-2 寫入側 hook（同步 inline）

在既有流程尾端呼叫 `skill_embedding_service.update_embedding(skill, zip_bytes, db)`：

| 觸發點 | 位置 | 備註 |
| --- | --- | --- |
| 上傳 | [`upload_skill`](../../../backend/app/services/skill_service.py) put_object 後 | zip_content 在手，直接用 |
| 重新上傳 | [`reupload_skill`](../../../backend/app/services/skill_service.py) put_object 後 | 內容變了必重算 |
| 線上編輯檔案 | [`update_file_content`](../../../backend/app/services/skill_service.py) 後 | 內容變了必重算 |
| 改描述 | [`update_skill`](../../../backend/app/services/skill_service.py) 描述變動時 | 需 get_object 拿 zip 重組文字 |

- **失敗策略**：embedding 更新包在 try/except，失敗只 `logger.warning`，**不 raise**（對齊 [rag_service](../../../backend/app/services/rag_service.py) 與 [skill_recommender_service](../../../backend/app/services/skill_recommender_service.py) 的「記憶/推薦失敗不擋主流程」原則）。失敗時該 skill 的 `embedding` 維持舊值或 NULL。
- **為什麼同步而非背景 worker**：Skill 上傳頻率低（非高頻對話），同步一次 embedding（~數百 ms）可接受，避免引入佇列複雜度（範圍外）。

### 3-3 既有資料回填

`backend/scripts/backfill_skill_embedding.py`（沿用 [`migrate_storage_to_s3.py`](../../../backend/scripts/migrate_storage_to_s3.py) 的獨立 script 範式）：

- 查 `embedding IS NULL AND is_deleted = FALSE` 的 skill
- 逐筆 get_object → build_embedding_text → embed → UPDATE
- 逐筆 commit + log 進度；失敗跳過續跑（記錄失敗 uid）
- 可重跑（idempotent：只挑 NULL）

---

## 4. 檢索設計

### 4-1 `skill_repository.search_similar`

沿用 [`chat_memory_repository.search_similar`](../../../backend/app/repositories/chat_memory_repository.py) 的 raw SQL + `mappings()` 範式：

```sql
SELECT skill_uid, owner_user_uid, name, description, ...,
       1 - (embedding <=> CAST(:query AS vector)) AS score
FROM skill
WHERE is_deleted = FALSE
  AND embedding IS NOT NULL
  AND (owner_user_uid = :user_uid OR visibility = 'public')   -- 對齊 stmt_visible_to_user
  AND 1 - (embedding <=> CAST(:query AS vector)) >= :min_score
ORDER BY embedding <=> CAST(:query AS vector)
LIMIT :top_k
```

- **可見性**：與既有 [`stmt_visible_to_user`](../../../backend/app/repositories/skill_repository.py) 同語意（自己的 or public），避免語意檢索洩漏他人私有 skill
- 回傳 `list[tuple[Skill, float]]`（同 chat_memory 範式，不回傳 embedding 省流量）

### 4-2 `skill_service.semantic_search`

```
semantic_search(user_uid, query, db) -> dict:
  if not skill.rag.enabled: return {items: [], analysis: None}
  vector = call_llm_metered(PURPOSE_EMBEDDING, text=query, user_uid=...)
  rows = skill_repository.search_similar(vector, top_k, min_score, user_uid, db)
  items = [_skill_to_dict(s, score=score) for s, score in rows]  # 含 score + tags + is_favorited（bulk load）
  if skill.rag.analyze_enabled and items:
      analysis = _analyze(query, rows[:analyze_top_n])   # LLM
      回填每筆 ai_reason（或整體 analysis 段落）
  return {items, analysis}
```

- query 空字串 → 回空（不付 embedding 成本），對齊 rag_service 的 early-return
- bulk load `is_favorited` / `tags` 沿用既有 [`list_skills`](../../../backend/app/services/skill_service.py) 模式

---

## 5. AI 分析（LLM 推薦理由）

### 5-1 集中進入點（硬規範）

**不可**在 service 直接呼叫 OpenRouter client。作法：

1. OpenRouter client 加 `async def analyze_skill_matches(query, skills_payload, model) -> AnalyzeResult`
   - `skills_payload`：`[{name, description, score}, ...]`（前 N 筆）
   - prompt：要求對每筆給一句「為什麼符合需求」的繁中理由，回 JSON
2. [`llm_metering.py`](../../../backend/app/services/llm_metering.py) 加：
   - `PURPOSE_SKILL_ANALYZE = "skill_analyze"` 常數
   - [`_dispatch_non_stream`](../../../backend/app/services/llm_metering.py) 新分支：`purpose == PURPOSE_SKILL_ANALYZE → analyze_skill_matches(...)`
3. `skill_service` 呼叫 `call_llm_metered(purpose=PURPOSE_SKILL_ANALYZE, ...)`

### 5-2 回傳結構

兩種呈現，本版採 **per-item 理由**（每筆 skill 一句），前端好逐列顯示：

```json
{
  "items": [
    {"skill_uid": "...", "name": "...", "score": 0.82, "ai_reason": "此 Skill 專門處理 PDF 表格抽取，符合你要從報表擷取數據的需求。", "...其餘 skill 欄位": "..."}
  ],
  "analysis": null
}
```

- `analyze_enabled = false` 或 LLM 失敗 → `ai_reason` 為 `null`，`items` 仍回（純向量結果），前端只顯示 score，不顯示理由
- LLM 失敗只 log warning，不讓整個搜尋 500（降級為無理由）

### 5-3 成本控制

- 每次 AI 分析搜尋 = 1 次 query embedding + 1 次 LLM 分析（僅前 `analyze_top_n` 筆）
- 因此設計為**獨立模式**：預設走關鍵字前端過濾，使用者主動切「AI 分析」才觸發後端 + LLM

---

## 6. API 設計

### 6-1 `POST /api/v1/skills/search`（新增）

| 項目 | 內容 |
| --- | --- |
| Method / Path | `POST /api/v1/skills/search` |
| Body | `{ "query": "從報表 PDF 抽數據", "top_k": 8 }`（`top_k` 選配，未給用 setting 預設） |
| 權限 | 登入使用者；檢索範圍限「自己的 or public」 |
| Response | `ApiResponse[SkillSearchData]` |

```python
class SkillSearchItem(SkillResponse):     # 繼承既有 SkillResponse
    score: float
    ai_reason: str | None = None

class SkillSearchData(BaseModel):
    items: list[SkillSearchItem]
    analysis: str | None = None           # 保留整體分析段落（本版多為 None）
```

- 放在 [`skills/router.py`](../../../backend/app/api/v1/skills/router.py)，`POST ""` 之後、`GET "/{skill_uid}"` **之前**註冊（避免 `/search` 被 `/{skill_uid}` 吃掉路由）
- `/api/docs` 自動同步 schema

---

## 7. 前端設計

### 7-1 「AI 分析」模式切換

[`skills/page.tsx`](../../../frontend/src/app/(main)/skills/page.tsx) 現有搜尋列（`Input` + FilterChip）旁加一顆切換：

- **關鍵字模式（預設）**：維持現狀，前端過濾 `filteredSkills`
- **AI 分析模式**：搜尋框 placeholder 改「用一句話描述你要找的 Skill…」，送出（Enter / 按鈕）才呼叫 `POST /skills/search`
- 切換以本地 state `searchMode: "keyword" | "ai"`，不動既有 keyword 路徑

### 7-2 結果渲染

- AI 分析模式下，列表改渲染 `searchResult.items`：
  - 沿用 `SkillRow` 視覺，額外：
    - **「AI 分析」徽章**（近似既有 `@作者` chip 樣式，色系用 primary）
    - score 顯示（如 `相似度 82%`）
    - `ai_reason` 存在時，在描述下方顯示一段淺色理由文字
  - loading 時 `<PageLoading />`；無結果顯示「找不到語意相近的 Skill」

### 7-3 API slice

`store/skillsApi.ts` 加：

```ts
useSemanticSearchSkillsMutation()   // POST /skills/search, body {query, top_k?}
```

- 用 mutation（非 query）因為是使用者主動觸發、帶 body、不需快取 key 化

---

## 8. Migration / 部署

### 8-1 Migration 順序

| 版本 | 內容 |
| --- | --- |
| **V56** | `ALTER TABLE skill ADD COLUMN embedding VECTOR(1536) NULL` + HNSW index + COMMENT |
| **V57** | seed `skill.rag.*` system_setting（`ON CONFLICT DO NOTHING`） |

### 8-2 部署順序

1. Merge PR → Coolify deploy，Flyway 跑 V56 / V57
2. Backend 重啟生效（新 endpoint 上線；此時既有 skill 的 embedding 皆 NULL → 語意檢索回空/少）
3. **執行回填**：`python -m scripts.backfill_skill_embedding`（一次性，逐筆補向量）
4. 前端重整可見「AI 分析」模式

- **無 outage**：加欄位（NULL）+ 加 endpoint，既有查詢與資料不動
- 回填前語意檢索可用但結果稀疏，屬預期（漸進生效）

### 8-3 Rollback

- 程式碼層：可（新 endpoint / 欄位往回拔，不影響既有資料）
- DB 層：不建議 drop V56/V57，forward fix 即可

---

## 9. 風險與決策

| # | 風險 / 議題 | 應對 |
| --- | --- | --- |
| 1 | LLM 分析成本隨搜尋次數上升 | 獨立模式（預設關鍵字）；`analyze_top_n=5` 限筆；`analyze_enabled` 可全關 |
| 2 | 上傳同步 embedding 拖慢上傳回應 | 失敗不擋、僅 log；Skill 上傳低頻，數百 ms 可接受；如成瓶頸再改背景（範圍外） |
| 3 | 既有資料回填期間結果稀疏 | 部署後跑一次 backfill script；文件明列步驟 3 |
| 4 | `/search` 路由被 `/{skill_uid}` 吃掉 | router 註冊順序：`/search` 早於 `/{skill_uid}` |
| 5 | 私有 skill 經語意檢索洩漏 | search_similar 內建 `owner OR public` 過濾，與 stmt_visible_to_user 同語意 |
| 6 | embedding 維度 / 模型與記憶層不一致 | 一律走 `call_llm_metered(PURPOSE_EMBEDDING)`，同 `text-embedding-3-small` 1536 維 |
| 7 | 描述更新需 get_object 才能重組文字（多一次 S3 讀） | 僅描述變動時觸發；低頻可接受 |
| 8 | LLM 回傳非合法 JSON | client 內解析失敗 → 回無理由結果，service 降級（items 照回） |

---

## 10. 驗收標準

- [ ] V56 / V57 跑通，`\d skill` 可見 `embedding` 欄位與 HNSW index
- [ ] 上傳一個新 Skill → DB 該筆 `embedding` 非 NULL
- [ ] 執行 backfill script → 既有 Skill 的 `embedding` 補齊
- [ ] `POST /api/v1/skills/search {query}` 回傳語意相近清單，含 score
- [ ] `analyze_enabled=true` 時每筆帶 `ai_reason`；設 false 時 `ai_reason` 為 null 但 items 照回
- [ ] 私有他人 Skill 不出現在我的語意檢索結果
- [ ] 前端「AI 分析」模式：輸入自然語言 → 顯示結果 + 「AI 分析」徽章 + 理由文字；關鍵字模式維持現狀
- [ ] `/api/docs` 可見 `POST /skills/search` 與 schema
- [ ] `pytest backend/tests -v` 全綠；前端 lint / type check 全綠
