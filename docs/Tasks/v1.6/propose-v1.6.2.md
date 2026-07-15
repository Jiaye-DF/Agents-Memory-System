# v1.6.2 Propose — Skill 向量儲存架構重設計（多向量 1:N）

> 本文件為 v1.6.2 的構想與討論紀錄。定稿後於 [tasks-v1.6.2.md](tasks-v1.6.2.md) 進行實作。
>
> 前置版本：[propose-v1.6.0.md](propose-v1.6.0.md) / [propose-v1.6.1.md](propose-v1.6.1.md)

---

## 0. 動機（fixed.md #2 的實測教訓）

v1.6.0 把「名稱＋描述＋檔案內容（≤8000 字元）」串接壓成**一條**向量。實測（[fixed.md #2](fixed.md)）證明這會稀釋語意：

| 查詢 | 對「Coolify Deploy 上傳部署文件」的 cosine |
| --- | --- |
| 「Coolify」（單詞） | **0.4930**（名稱完全同名仍過不了 0.5） |
| 「幫我把服務部署到 Coolify」 | 0.7496 |

內容塞得越多，任何單一關鍵詞在向量中占比越稀。**根本解法：名稱 / 描述 / 檔案內容各自獨立 embedding，檢索取該 Skill 的最高分**——單詞查詢會直接命中名稱向量。

---

## 1. 版本目標

1. 新增 **`skill_embedding` 表（1:N）**：一個 Skill 三條向量（`name` / `description` / `content`）
2. **移除 `skill.embedding` 欄位**（架構重設計，不保留棄用欄位）
3. 檢索改為「對所有向量比對 → 每個 Skill 取最高分」
4. backfill 重寫；寫入側 hook 調整（名稱變動也觸發重算）
5. API 契約不變（`POST /skills/search` 的 request / response 不動），前端零改動

### 範圍內

- **V59**：`CREATE TABLE skill_embedding` + `ALTER TABLE skill DROP COLUMN embedding`
- Model：新 `SkillEmbedding`；`Skill` 移除 `embedding`
- `skill_embedding_service` 重寫：三段文字 → 三次 embed → delete + insert 全量替換
- `skill_repository.search_similar` 重寫：兩層 SQL（內層 HNSW 取近鄰、外層 join skill 過濾 + 按 skill 取 MAX 分）
- 寫入 hook：`update_skill` 改為「名稱**或**描述變動」都觸發（原本只看描述）
- `backfill_skill_embedding.py` 重寫（改查「無任何 embedding row」的 skill）
- 測試更新 + **門檻校準實驗**（真 embedding 正負例實測，決定 `skill.rag.min_score` 是否隨版調整）

### 範圍外（延後）

- content 分塊 chunking（本 schema 已預留：多條 `source_type='content'` row 即可，v1.6.x+）
- Script / Agent 語意檢索
- 前端任何改動

---

## 2. 資料模型

### 2-1 `skill_embedding` 表（V59）

沿用 [V44 project_memory](../../../migrations/sql/V44__create_project_memory_table.sql) 的 MemoryBase 風格（審計 / 衍生資料，無 updated_at / is_deleted）：

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `pid` | BIGSERIAL PK | |
| `skill_embedding_uid` | UUID DEFAULT gen_random_uuid() | 對外識別 |
| `skill_uid` | UUID NOT NULL FK → `skill.skill_uid` | 所屬 Skill；skill 為軟刪體系，rows 保留、檢索經 join 自然過濾 |
| `source_type` | VARCHAR(20) CHECK IN ('name','description','content') | 向量來源段 |
| `embedding` | VECTOR(1536) NOT NULL | text-embedding-3-small |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | |

- 索引：`uq_skill_embedding_skill_embedding_uid`、`idx_skill_embedding_skill_uid`、`idx_skill_embedding_vec_hnsw (HNSW vector_cosine_ops)`
- **不建** `(skill_uid, source_type)` 唯一索引——為未來 chunking（多條 content row）預留；替換一致性由 service 層「同 transaction delete + insert」保證
- 同一 migration 內 `ALTER TABLE skill DROP COLUMN IF EXISTS embedding`（欄位上的 HNSW index 隨欄位自動刪除）

### 2-2 向量內容切分

| source_type | 文字來源 | 備註 |
| --- | --- | --- |
| `name` | `skill.name` | 單詞查詢的主要命中目標 |
| `description` | `skill.description` | |
| `content` | ZIP 內 `.md`/`.txt`（SKILL.md → README.md → 路徑序），截 `skill.rag.embed_content_max_chars` | 無可用內容時**不建此 row**（該 skill 只有 2 條向量） |

### 2-3 生命週期

- 寫入 / 重傳 / 線上編輯 / 名稱或描述更新 → service 同 transaction **delete 該 skill 全部 rows + 重建**（三次 embed，成本低、語意簡單）
- Skill 軟刪 → rows 保留（檢索 join `skill.is_deleted = FALSE` 自然過濾）；復活即恢復可檢索
- 失敗策略不變：embedding 重建失敗只 log warning 不擋主流程（此時舊 rows 已刪 → 該 skill 暫時不可語意檢索，待下次寫入或 backfill 補；接受此取捨，換取「無 stale 向量」）

---

## 3. 檢索設計

### 3-1 兩層 SQL（HNSW 友善）

```sql
-- 內層：純向量近鄰（走 HNSW），多取候選（top_k * 6，涵蓋同 skill 多 row 與可見性過濾損耗）
-- 外層：join skill 過濾（is_deleted / 可見性）+ 按 skill 取最高分 + 門檻 + top_k
SELECT t.skill_uid, MAX(t.score) AS score
FROM (
    SELECT se.skill_uid,
           1 - (se.embedding <=> CAST(:q AS vector)) AS score
    FROM skill_embedding se
    ORDER BY se.embedding <=> CAST(:q AS vector)
    LIMIT :candidate_k          -- top_k * 6
) t
JOIN skill s ON s.skill_uid = t.skill_uid
WHERE s.is_deleted = FALSE
  AND {visibility_clause}       -- scope 邏輯沿用 v1.6.1（visible / public）
GROUP BY t.skill_uid
HAVING MAX(t.score) >= :min_score
ORDER BY score DESC
LIMIT :top_k
```

- 兩段式 hydrate 沿用（uid + score → ORM 撈 Skill 保 owner joined-load）
- `search_similar` 簽名不變（呼叫端零改動）

### 3-2 門檻校準（實測驅動，不再拍腦袋）

實作完成後在本機以真 embedding 跑校準實驗（正例：單詞 / 自然語句對相關 Skill；負例：無關查詢），記錄分數分佈後決定：

- 名稱向量命中預估 0.7+，`min_score` 有條件回調（候選 0.45）
- 若調整 → 併入 V59 尾端 conditional UPDATE（僅動仍為 `'0.35'` 出廠值的環境）；實測不支持則不動
- 實驗數據記入 tasks doc 回填

---

## 4. 部署與風險

### 4-1 部署順序（⚠️ 有一步必做）

1. Merge → deploy，Flyway 跑 V59（**舊向量隨欄位刪除即消失**）
2. **立即重跑 backfill**：`python -m scripts.backfill_skill_embedding`（此刻起語意檢索才有資料）
3. V59 到 backfill 完成之間，語意檢索回空——測試環境可接受；正式環境上線時須排在同一維護窗

### 4-2 風險

| # | 風險 | 應對 |
| --- | --- | --- |
| 1 | DROP COLUMN 不可逆 | 向量為衍生資料（可由 backfill 全量重建），非唯一真相來源，可安全刪 |
| 2 | 寫入成本 ×3 | embedding 單價極低、Skill 寫入低頻，可忽略 |
| 3 | 重建失敗致該 skill 暫無向量 | log warning + backfill 可補（§2-3 取捨已明示） |
| 4 | 候選數 top_k*6 不夠（極端多 row 時） | 目前一 skill 最多 3 row，6 倍充裕；chunking 時代再調 |

---

## 5. 驗收標準

- [ ] V59 跑通：`\d skill_embedding` 存在、`skill` 表無 `embedding` 欄位
- [ ] 上傳 skill → `skill_embedding` 出現 2~3 rows（name / description / content）
- [ ] backfill 重跑 → 既有 skill 全數有 rows
- [ ] 單詞查名稱（如「Coolify」）→ 命中且分數顯著高於 v1.6.0 的 0.49（預期 0.7+）
- [ ] 自然語句查詢 → 維持或優於 0.75
- [ ] 無關查詢不因門檻回調而混入
- [ ] scope=visible / public 行為與 v1.6.1 一致；API 契約不變、前端零改動
- [ ] `pytest backend/tests -v` 全綠
