-- ============================================================
-- V56：skill 表加 embedding 向量欄位（v1.6.0）
--
-- 規範依據：
--   - docs/Tasks/v1.6/propose-v1.6.0.md §2（資料模型）
--   - docs/Tasks/v1.6/tasks-v1.6.0.md Phase 1
--
-- 設計重點（勿違反）：
--   1. embedding 允許 NULL（propose §2-2）
--      —— 既有資料尚未回填、或上傳當下生成失敗時為 NULL；
--         檢索時以 WHERE embedding IS NOT NULL 排除，不可改 NOT NULL
--   2. 沿用 chat_memory / project_memory 的 HNSW cosine 索引 pattern（V22 / V44）
--   3. 向量存 skill 表內（1:1 同生命週期，soft-delete 自然連動），不另拆表
-- ============================================================

ALTER TABLE skill
    ADD COLUMN IF NOT EXISTS embedding VECTOR(1536) NULL;

CREATE INDEX IF NOT EXISTS idx_skill_embedding_hnsw
    ON skill USING HNSW (embedding vector_cosine_ops);

COMMENT ON COLUMN skill.embedding IS '語意檢索向量（text-embedding-3-small，1536 維；name+描述+檔案內容；NULL=未回填/生成失敗）';
