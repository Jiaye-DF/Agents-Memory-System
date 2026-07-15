# v1.6.0 任務規格：Skills RAG 語意檢索 + AI 分析

> **狀態：未開始（規格定稿，待實作）**
>
> 前置：[propose-v1.6.0.md](propose-v1.6.0.md)

## 版本目標

在 Skills 管理頁既有關鍵字查詢之外，新增一個獨立的「AI 分析」語意檢索模式：自然語言需求 → 向量檢索最相近的 Skill → LLM 生成推薦理由 → 前端標示「AI 分析」字樣。

- `skill` 表加向量欄位（name + description + 檔案內容）
- 寫入側自動維護 embedding（失敗不擋主流程）+ 既有資料回填
- `POST /api/v1/skills/search` 語意檢索 endpoint
- LLM 生成推薦理由（可由 system_setting 開關）
- 前端「AI 分析」模式與現有關鍵字過濾並存

### 範圍內

- Flyway **V56**（`skill` 加 `embedding`）+ **V57**（seed `skill.rag.*`）
- 後端：`skill` model 加 `embedding`；`skill_embedding_service`；`skill_repository.search_similar`；`skill_service.semantic_search`
- 後端：`llm_metering` 加 `PURPOSE_SKILL_ANALYZE`；OpenRouter client 加 `analyze_skill_matches`
- 後端：`POST /api/v1/skills/search` + schema
- 後端：`scripts/backfill_skill_embedding.py`
- 前端：`skillsApi.ts` 加語意檢索 hook；`skills/page.tsx` 加「AI 分析」模式 + 結果渲染
- 測試：組文字 / cosine 排序 / visibility / analyze 開關

### 範圍外

- Script / Agent 語意檢索（本版僅 Skill）
- dashboard / 公開市集語意檢索入口
- keyword + vector 混合（RRF）融合
- 檔案內容 chunking / 多向量
- embedding 背景 worker / 佇列
- re-ranking / cross-encoder

---

## 前置現況

- **既有 Flyway 最大版本**：`V55__create_download_log.sql`，本 task 起算 **V56**
- **既有 Skill 相關**：
  - Model [`models/skill.py`](../../../backend/app/models/skill.py)（**無** embedding 欄位）
  - Service [`services/skill_service.py`](../../../backend/app/services/skill_service.py)（upload:154 / update:314 / reupload:660 / update_file_content:798 / _skill_to_dict:79 / list_skills:261）
  - Repository [`repositories/skill_repository.py`](../../../backend/app/repositories/skill_repository.py)（`stmt_visible_to_user:22`，**無** search_similar）
  - Router [`api/v1/skills/router.py`](../../../backend/app/api/v1/skills/router.py)
  - Schema [`schemas/skills/schemas.py`](../../../backend/app/schemas/skills/schemas.py)（`SkillResponse`）
- **RAG 範式參考**：
  - [`models/chat_memory.py`](../../../backend/app/models/chat_memory.py)（`Vector(1536)`）
  - [`repositories/chat_memory_repository.py:126`](../../../backend/app/repositories/chat_memory_repository.py)（`search_similar` raw SQL cosine）
  - [`services/rag_service.py`](../../../backend/app/services/rag_service.py)（early-return / 失敗降級）
  - [`services/llm_metering.py`](../../../backend/app/services/llm_metering.py)（`PURPOSE_EMBEDDING`、`_dispatch_non_stream:194`）
  - [V44 migration:38](../../../migrations/sql/V44__create_project_memory_table.sql)（HNSW index 範式）、[V46](../../../migrations/sql/V46__seed_three_layer_rag_settings.sql)（seed 範式）
- **回填 script 參考**：[`scripts/migrate_storage_to_s3.py`](../../../backend/scripts/migrate_storage_to_s3.py)
- **前端**：[`skills/page.tsx`](../../../frontend/src/app/(main)/skills/page.tsx)（純前端 `matchByTextAndAuthor` 過濾）、[`store/skillsApi.ts`](../../../frontend/src/store/skillsApi.ts)
- **既無**：`skill.embedding`、`skill_embedding_service.py`、`skill_repository.search_similar`、`POST /skills/search`、`backfill_skill_embedding.py`、前端語意檢索 hook / UI

---

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | 「AI 分析」層級 | LLM 生成推薦理由（非只加徽章） |
| 2 | embedding 來源 | 名稱 + 描述 + 檔案內容（`.md` / `.txt`，截斷） |
| 3 | 與關鍵字查詢關係 | 新增獨立「AI 分析」模式並存，不取代前端過濾 |
| 4 | embedding 欄位 | 存 `skill` 表內（1:1），NULL 允許 + 檢索過濾 |
| 5 | embedding 更新時機 | upload / reupload / update_file_content / 描述變動，同步 inline |
| 6 | 更新失敗策略 | 只 log warning，不 raise（不擋主流程） |
| 7 | LLM 呼叫路徑 | 必經 `call_llm_metered`（新增 `PURPOSE_SKILL_ANALYZE`），禁止直呼 client |
| 8 | AI 分析呈現 | per-item 理由（每筆一句 `ai_reason`），失敗降級為 null |
| 9 | 檢索可見性 | `owner OR public`，與 `stmt_visible_to_user` 同語意 |
| 10 | 檢索/融合 | 純向量 cosine，本版**不**與 keyword 融合 |
| 11 | 既有資料 | backfill script 一次性回填，可重跑（挑 NULL） |
| 12 | AI 分析模型 | 小模型 `anthropic/claude-haiku-4-5`（system_setting 可調） |

---

## Phase 0：依賴與設定

- [ ] 確認 `.env` / `.env.example`：本版不新增環境變數（所有可調參數走 `system_setting`）
- [ ] 確認 pgvector / HNSW 於現有環境已啟用（V1 已建 extension，chat_memory 已用 HNSW）

---

## Phase 1：DB Migration

### 1-1 V56 — `skill` 加 `embedding`

- [ ] 新建 [`migrations/sql/V56__add_skill_embedding.sql`](../../../migrations/sql/)
- [ ] `ALTER TABLE skill ADD COLUMN embedding VECTOR(1536) NULL`
- [ ] `CREATE INDEX IF NOT EXISTS idx_skill_embedding_hnsw ON skill USING HNSW (embedding vector_cosine_ops)`
- [ ] `COMMENT ON COLUMN skill.embedding IS '語意檢索向量（text-embedding-3-small，1536 維；name+描述+檔案內容；NULL=未回填/生成失敗）'`

### 1-2 V57 — seed `skill.rag.*` system_setting

- [ ] 新建 [`migrations/sql/V57__seed_skill_rag_settings.sql`](../../../migrations/sql/)
- [ ] `INSERT ... ON CONFLICT DO NOTHING`，鍵：
  - [ ] `skill.rag.enabled` = `true` (boolean)
  - [ ] `skill.rag.top_k` = `8` (integer)
  - [ ] `skill.rag.min_score` = `0.5` (string)
  - [ ] `skill.rag.analyze_enabled` = `true` (boolean)
  - [ ] `skill.rag.analyze_top_n` = `5` (integer)
  - [ ] `skill.rag.analyze_model` = `"anthropic/claude-haiku-4-5"` (json)
  - [ ] `skill.rag.embed_content_max_chars` = `8000` (integer)

### 1-3 本機驗證

- [ ] `docker compose -f docker-compose.dev.yml up backend` 啟動，Flyway 自動跑 V56 / V57
- [ ] `\d skill` 可見 `embedding` 欄位；`\di` 可見 HNSW index
- [ ] `SELECT key FROM system_setting WHERE key LIKE 'skill.rag.%'` 七個鍵齊全

---

## Phase 2：Model 層

- [ ] [`models/skill.py`](../../../backend/app/models/skill.py) 加：
  - [ ] `from pgvector.sqlalchemy import Vector`
  - [ ] `embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)`

---

## Phase 3：Repository 層

### 3-1 `skill_repository.search_similar`（新增）

- [ ] [`repositories/skill_repository.py`](../../../backend/app/repositories/skill_repository.py) 加 `async def search_similar(query_embedding, top_k, min_score, user_uid, db) -> list[tuple[Skill, float]]`
- [ ] raw SQL（沿用 [chat_memory_repository:126](../../../backend/app/repositories/chat_memory_repository.py)）：
  - [ ] `WHERE is_deleted = FALSE AND embedding IS NOT NULL`
  - [ ] `AND (owner_user_uid = :user_uid OR visibility = 'public')`
  - [ ] `AND 1 - (embedding <=> CAST(:query AS vector)) >= :min_score`
  - [ ] `ORDER BY embedding <=> CAST(:query AS vector) LIMIT :top_k`
  - [ ] SELECT 需含 `owner` 顯示名所需欄位（或回 Skill 後另 bulk 取 owner；沿用既有 `owner` joined 模式）
- [ ] 回傳 `[(Skill, score)]`，不回傳 embedding 省流量

---

## Phase 4：Embedding 生成服務

### 4-1 `services/skill_embedding_service.py`（新建）

- [ ] `def build_embedding_text(name, description, zip_bytes, max_chars) -> str`
  - [ ] name + description + 解壓取 `.md` / `.txt` 內容（`SKILL.md` / `README.md` 優先，路徑排序）
  - [ ] 串接後截斷至 `max_chars`
  - [ ] 解壓失敗 → 退化為只用 name + description
- [ ] `async def update_embedding(skill, zip_bytes, db) -> None`
  - [ ] 讀 setting `skill.rag.embed_content_max_chars`
  - [ ] `build_embedding_text` → `call_llm_metered(purpose=PURPOSE_EMBEDDING, text=..., user_uid=skill.owner_user_uid)`
  - [ ] `UPDATE skill SET embedding = ...`
  - [ ] 全程 try/except，失敗只 `logger.warning`，**不 raise**

### 4-2 寫入側 hook 掛載

- [ ] [`upload_skill`](../../../backend/app/services/skill_service.py) put_object 成功後呼叫 `update_embedding`（用手上的 zip_content）
- [ ] [`reupload_skill`](../../../backend/app/services/skill_service.py) put_object 成功後呼叫
- [ ] [`update_file_content`](../../../backend/app/services/skill_service.py) 寫入後呼叫（用 new_zip）
- [ ] [`update_skill`](../../../backend/app/services/skill_service.py) 描述變動時 → get_object 拿 zip → 呼叫
- [ ] 確認四處皆為「失敗不影響原有回應」

---

## Phase 5：LLM 分析（AI 推薦理由）

### 5-1 OpenRouter client

- [ ] [`clients/openrouter.py`](../../../backend/app/clients/openrouter.py) 加 `async def analyze_skill_matches(query, skills_payload, model) -> list[dict]`
  - [ ] prompt：對每筆 skill 給一句繁中「為什麼符合需求」，回 JSON（`[{name, reason}]` 或依 index 對應）
  - [ ] 解析失敗 → 回空 list（不 raise）

### 5-2 `llm_metering` 分派

- [ ] [`llm_metering.py`](../../../backend/app/services/llm_metering.py) 加 `PURPOSE_SKILL_ANALYZE = "skill_analyze"`
- [ ] [`_dispatch_non_stream`](../../../backend/app/services/llm_metering.py) 加分支：`purpose == PURPOSE_SKILL_ANALYZE → analyze_skill_matches(query, skills_payload, model)`

---

## Phase 6：Service — 語意檢索組裝

### 6-1 `skill_service.semantic_search`（新增）

- [ ] `async def semantic_search(user_uid, query, top_k, db) -> dict`
- [ ] 讀 settings：`skill.rag.enabled` / `top_k` / `min_score` / `analyze_enabled` / `analyze_top_n` / `analyze_model`
- [ ] `enabled=false` 或 query 空 → 回 `{items: [], analysis: None}`（early-return，不付 embedding 成本）
- [ ] `call_llm_metered(PURPOSE_EMBEDDING, text=query, user_uid=...)` → vector
- [ ] `skill_repository.search_similar(vector, top_k, min_score, user_uid, db)`
- [ ] bulk load `is_favorited` / `tags`（沿用 [list_skills](../../../backend/app/services/skill_service.py) 模式）
- [ ] `_skill_to_dict` 擴充：多接 `score` / `ai_reason` 參數（或包一層 dict）
- [ ] `analyze_enabled and items` → `call_llm_metered(PURPOSE_SKILL_ANALYZE, ...)` 對前 `analyze_top_n` 筆生成理由，回填 `ai_reason`
- [ ] LLM 失敗 → `ai_reason` 全 None，items 照回（降級）

---

## Phase 7：Schema + Router

### 7-1 Schema

- [ ] [`schemas/skills/schemas.py`](../../../backend/app/schemas/skills/schemas.py) 加：
  - [ ] `class SkillSearchRequest`：`query: str`（trim 驗證，非空），`top_k: int | None = None`
  - [ ] `class SkillSearchItem(SkillResponse)`：加 `score: float`、`ai_reason: str | None = None`
  - [ ] `class SkillSearchData`：`items: list[SkillSearchItem]`、`analysis: str | None = None`

### 7-2 Router

- [ ] [`skills/router.py`](../../../backend/app/api/v1/skills/router.py) 加 `POST "/search"`（**註冊於 `GET "/{skill_uid}"` 之前**，避免路由衝突）
  - [ ] `response_model=ApiResponse[SkillSearchData]`
  - [ ] 呼叫 `skill_service.semantic_search(current_user.user_uid, body.query, body.top_k, db)`
- [ ] 確認 `/api/docs` 顯示新 endpoint 與 schema

---

## Phase 8：回填 Script

- [ ] 新建 [`backend/scripts/backfill_skill_embedding.py`](../../../backend/scripts/)（沿用 [migrate_storage_to_s3.py](../../../backend/scripts/migrate_storage_to_s3.py) 範式）
- [ ] 查 `embedding IS NULL AND is_deleted = FALSE` 的 skill
- [ ] 逐筆 get_object → `build_embedding_text` → embed → UPDATE → commit
- [ ] 逐筆 log 進度；失敗跳過續跑，最後印失敗 uid 清單
- [ ] 可重跑（只挑 NULL）

---

## Phase 9：前端

### 9-1 Types + API slice

- [ ] `frontend/src/types` 加 `SkillSearchItem`（Skill + `score` + `ai_reason`）、`SkillSearchResult`
- [ ] [`store/skillsApi.ts`](../../../frontend/src/store/skillsApi.ts) 加 `useSemanticSearchSkillsMutation()`（`POST /skills/search`，body `{query, top_k?}`）

### 9-2 頁面整合

- [ ] [`skills/page.tsx`](../../../frontend/src/app/(main)/skills/page.tsx)：
  - [ ] 加 `searchMode: "keyword" | "ai"` state + 切換 UI（FilterChip 或 toggle 按鈕）
  - [ ] AI 模式：placeholder 改「用一句話描述你要找的 Skill…」，Enter / 按鈕觸發 mutation
  - [ ] AI 模式渲染 `result.items`：沿用 `SkillRow` + 「AI 分析」徽章 + score（`相似度 NN%`）+ `ai_reason` 文字
  - [ ] loading 用 `<PageLoading />`；空結果顯示「找不到語意相近的 Skill」
  - [ ] keyword 模式維持現狀（`filteredSkills`）不受影響

### 9-3 元件

- [ ] `SkillRow`（或新 `SkillSearchRow`）加 `score` / `aiReason` / 徽章 props（不破壞既有呼叫點）

---

## Phase 10：測試

### 10-1 後端單元

- [ ] `tests/services/test_skill_embedding_service.py`：
  - [ ] `build_embedding_text` 正常組合（name+desc+md）
  - [ ] 解壓失敗退化為 name+desc
  - [ ] 超長內容截斷至 max_chars
- [ ] `tests/repositories/test_skill_repository.py`（或既有加）：
  - [ ] `search_similar` cosine 排序正確
  - [ ] visibility 過濾（他人私有不回）
  - [ ] `embedding IS NULL` 不回
- [ ] `tests/services/test_skill_semantic_search.py`：
  - [ ] `enabled=false` / query 空 → 回空且不呼 embedding
  - [ ] `analyze_enabled=false` → items 有值、`ai_reason` 全 None
  - [ ] LLM 失敗降級（items 照回）

### 10-2 手動 smoke

- [ ] 上傳含 `SKILL.md` 的 skill → DB `embedding` 非 NULL
- [ ] 跑 backfill → 既有 skill embedding 補齊
- [ ] `POST /skills/search {query}` 回語意結果 + score + ai_reason
- [ ] 前端切「AI 分析」→ 輸入自然語言 → 顯示徽章 + 理由；切回關鍵字維持現狀
- [ ] 他人私有 skill 不出現在結果

---

## Phase 11：部署與驗收

### 11-1 部署順序

- [ ] Merge 本 task PR 到 `main`
- [ ] Coolify 自動 deploy，Flyway 跑 V56 / V57
- [ ] Backend 重啟生效
- [ ] 執行回填：`python -m scripts.backfill_skill_embedding`
- [ ] 前端重整可見「AI 分析」模式
- [ ] 無 outage（加欄位 NULL + 加 endpoint）

### 11-2 驗收清單

- [ ] Phase 1 ~ 10 所有 checkbox 完成
- [ ] `pytest backend/tests -v` 全綠
- [ ] `\d skill` 有 `embedding` + HNSW index
- [ ] `POST /skills/search` 回 score + ai_reason；analyze 開關生效
- [ ] 私有他人 skill 不洩漏
- [ ] 前端 lint / type check 全綠

### 11-3 Rollback

- 程式碼層：可（新 endpoint / 欄位往回拔，不影響既有資料）
- DB 層：不建議 drop V56 / V57，forward fix 即可
