# v1.6.2 任務規格：Skill 向量儲存架構重設計（多向量 1:N）

> **狀態：未開始（規格定稿，待實作）**
>
> 前置：[propose-v1.6.2.md](propose-v1.6.2.md)

## 版本目標

`skill.embedding` 單向量 → `skill_embedding` 表（1:N，name / description / content 三向量），檢索按 Skill 取最高分，解決單詞查詢被長文稀釋的問題（實測 0.49 → 預期 0.7+）。API 契約不變、前端零改動。

### 範圍內

- **V59**：建 `skill_embedding` 表 + `ALTER TABLE skill DROP COLUMN embedding`（＋校準實驗後的條件式 min_score UPDATE，若實測支持）
- Model：新 `SkillEmbedding`；`Skill` 移除 `embedding` 欄位
- 新 `skill_embedding_repository`：`replace_for_skill` / `list_by_skill` / 檢索內層查詢
- `skill_embedding_service` 重寫：三段文字 → 三次 embed → 同 transaction delete + insert
- `skill_repository.search_similar` 重寫：兩層 SQL（HNSW 內層 + join 過濾外層 + per-skill MAX）
- `skill_service` hook 調整：`update_skill` 名稱**或**描述變動皆觸發
- `scripts/backfill_skill_embedding.py` 重寫（既有 skills 檔案全量 embedding）
- 測試更新 + 門檻校準實驗（真 embedding 正負例）

### 範圍外

- content chunking（schema 已預留）、Script / Agent 檢索、前端改動

---

## 前置現況

- v1.6.1 已完成（commit `6753df3` 前後）：[`search_similar`](../../../backend/app/repositories/skill_repository.py)（單向量 + scope）、[`skill_embedding_service`](../../../backend/app/services/skill_embedding_service.py)（單向量 build+update）、[`backfill_skill_embedding.py`](../../../backend/scripts/backfill_skill_embedding.py)（查 `embedding IS NULL`）
- **既有 Flyway 最大版本**：`V58__calibrate_skill_rag_min_score.sql`，本 task 起算 **V59**
- 1:N 向量表範式：[`models/chat_memory.py`](../../../backend/app/models/chat_memory.py)（MemoryBase）、[V44](../../../migrations/sql/V44__create_project_memory_table.sql)（FK + HNSW + COMMENT）
- 引用 `Skill.embedding` 的檔案（DROP 後全部要改）：`skill_repository.search_similar`、`skill_embedding_service.update_embedding`、`scripts/backfill_skill_embedding.py`、`tests/repositories/test_skill_repository.py`、`tests/services/test_skill_embedding_service.py`

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | 儲存 | 新表 `skill_embedding` 1:N；`skill.embedding` **移除**（架構重設計，不留棄用欄位） |
| 2 | 向量切分 | name / description / content 三條；content 無可用文字時不建 row |
| 3 | 檢索語意 | query 對全部向量比對，per-skill 取 MAX，門檻作用在 MAX 上 |
| 4 | SQL 形態 | 兩層：內層純 HNSW 近鄰 LIMIT top_k*6，外層 join skill 過濾 + GROUP BY MAX |
| 5 | 替換一致性 | service 同 transaction delete + insert；不建 (skill_uid, source_type) 唯一索引（chunking 預留） |
| 6 | 軟刪連動 | rows 保留，join `skill.is_deleted = FALSE` 自然過濾 |
| 7 | update hook | 名稱或描述任一變動 → 全量重建三向量 |
| 8 | 門檻 | 校準實驗後定；僅以 conditional UPDATE 動仍為 '0.35' 出廠值的環境 |
| 9 | API 契約 | `POST /skills/search` request/response 完全不變 |

---

## Phase 1：DB Migration（V59）

- [ ] 新建 `migrations/sql/V59__create_skill_embedding_drop_skill_column.sql`
- [ ] `CREATE TABLE skill_embedding`：pid / skill_embedding_uid / skill_uid（FK → skill.skill_uid）/ source_type CHECK('name','description','content') / embedding VECTOR(1536) NOT NULL / created_at
- [ ] 索引：`uq_skill_embedding_skill_embedding_uid`、`idx_skill_embedding_skill_uid`、`idx_skill_embedding_vec_hnsw`（HNSW vector_cosine_ops）
- [ ] `ALTER TABLE skill DROP COLUMN IF EXISTS embedding`
- [ ] 檔頭繁中註解（規範依據 propose §2）+ 全欄位 COMMENT
- [ ] （校準後若支持）尾端 conditional UPDATE `skill.rag.min_score` `'0.35'` → 實測值

## Phase 2：Model 層

- [ ] 新建 `app/models/skill_embedding.py`：`SkillEmbedding(MemoryBase 風格)`（比照 chat_memory 的獨立 base 或現有慣例，實作者依 codebase 判斷）
- [ ] `app/models/skill.py` 移除 `embedding` 欄位與 `Vector` import
- [ ] `app/models/__init__.py` export

## Phase 3：Repository 層

- [ ] 新建 `app/repositories/skill_embedding_repository.py`：
  - [ ] `replace_for_skill(skill_uid, rows: list[tuple[source_type, vector]], db)`（delete + bulk insert，同 transaction）
  - [ ] `hard_delete_by_skill(skill_uid, db)`
- [ ] `skill_repository.search_similar` 重寫為兩層 SQL（propose §3-1；scope 條款沿用 v1.6.1）；簽名不變；兩段式 hydrate 保 owner

## Phase 4：Embedding Service 重寫

- [ ] `build_embedding_texts(name, description, zip_bytes, max_chars) -> dict[str, str]`（回 `{'name':…,'description':…,'content':…}`；content 空則無該鍵；ZIP 解壓邏輯沿用現版）
- [ ] `update_embedding(skill, zip_bytes, db)`：逐段 `call_llm_metered(PURPOSE_EMBEDDING)` → `replace_for_skill`；全程 try/except 只 warning
- [ ] `skill_service.update_skill` hook 條件改為 `data.name is not None or data.description is not None`
- [ ] 其餘三處 hook（upload / reupload / update_file_content）呼叫點不變（介面相同）

## Phase 5：Backfill 重寫（既有 skills 檔案全量 embedding）

- [ ] `scripts/backfill_skill_embedding.py`：目標改為「`NOT EXISTS (SELECT 1 FROM skill_embedding WHERE skill_uid = s.skill_uid)` 且未軟刪」的 skill
- [ ] 逐筆 get_object → `update_embedding`（內含三次 embed）→ commit；成敗判定改查該 skill 的 rows 數 > 0
- [ ] `--dry-run` / `--limit` / 進度 log / 失敗續跑 / exit code 慣例沿用現版
- [ ] docstring 註明：v1.6.2 部署後**必須**立即執行（舊向量已隨欄位刪除）

## Phase 6：測試更新

- [ ] `test_skill_embedding_service.py`：改測 `build_embedding_texts` 三段切分（content 空不出鍵、截斷、退化）與 `update_embedding` 呼叫三次 embed + replace
- [ ] `test_skill_repository.py`：改驗兩層 SQL 條款（內層 LIMIT candidate_k、外層 GROUP BY / HAVING / scope 條款）與保序
- [ ] `test_skill_semantic_search.py`：介面未變，確認全綠（mock 簽名如有 scope 之外變動同步）

## Phase 7：門檻校準實驗（真 embedding + 真 pgvector）

- [ ] 本機 flyway 跑 V59 後，以校準腳本實測並記錄：
  - [ ] 正例：單詞對同名 skill（預期 0.7+）、自然語句（預期 ≥0.75）
  - [ ] 負例：無關單詞 / 無關語句對該 skill 的最高分（決定門檻下限）
- [ ] 依數據決定 `skill.rag.min_score` 是否回調（候選 0.45）→ 支持則補進 V59 尾端 conditional UPDATE
- [ ] 實測數據回填本節

## Phase 8：驗證與部署

- [ ] `pytest backend/tests -v` 全綠；本機 flyway V59 跑通
- [ ] 部署順序（⚠️）：deploy（V59 刪舊向量）→ **立即** `python -m scripts.backfill_skill_embedding` → 驗證搜尋
- [ ] 手動 smoke：單詞「Coolify」命中且分數 0.7+；無關查詢不混入；`/skills` 與 dashboard 兩處行為一致
