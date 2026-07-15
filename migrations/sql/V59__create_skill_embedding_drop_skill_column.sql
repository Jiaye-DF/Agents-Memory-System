-- ============================================================
-- V59：建立 skill_embedding 表 + 移除 skill.embedding 欄位（v1.6.2）
--
-- 規範依據：
--   - docs/Tasks/v1.6/propose-v1.6.2.md §2（資料模型）
--   - docs/Tasks/v1.6/tasks-v1.6.2.md Phase 1
--
-- 設計重點（勿違反）：
--   1. 1:N 多向量：一個 Skill 對應 name / description / content 三條向量，
--      檢索按 Skill 取最高分，解決單向量語意稀釋問題
--   2. **不建** (skill_uid, source_type) 唯一索引——為未來 content chunking
--      （多條 content row）預留；替換一致性由 service 層同 transaction
--      delete + insert 保證
--   3. skill 為軟刪體系：skill 軟刪時 rows 保留不連動，
--      檢索經 join skill.is_deleted = FALSE 自然過濾
-- ============================================================

CREATE TABLE IF NOT EXISTS skill_embedding (
    pid                 BIGSERIAL    PRIMARY KEY,
    skill_embedding_uid UUID         NOT NULL DEFAULT gen_random_uuid(),
    skill_uid           UUID         NOT NULL,
    source_type         VARCHAR(20)  NOT NULL,
    embedding           VECTOR(1536) NOT NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_skill_embedding_skill FOREIGN KEY (skill_uid)
        REFERENCES skill (skill_uid),
    CONSTRAINT chk_skill_embedding_source_type
        CHECK (source_type IN ('name', 'description', 'content'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_skill_embedding_skill_embedding_uid
    ON skill_embedding (skill_embedding_uid);

CREATE INDEX IF NOT EXISTS idx_skill_embedding_skill_uid
    ON skill_embedding (skill_uid);

CREATE INDEX IF NOT EXISTS idx_skill_embedding_vec_hnsw
    ON skill_embedding USING HNSW (embedding vector_cosine_ops);

-- 欄位上的舊 HNSW 向量索引（idx_skill_embedding_hnsw）隨欄位刪除自動移除
ALTER TABLE skill DROP COLUMN IF EXISTS embedding;

COMMENT ON TABLE  skill_embedding                     IS 'Skill 多向量表（1:N；name / description / content 各自獨立 embedding，檢索按 Skill 取最高分；skill 軟刪不連動，join 自然過濾）';
COMMENT ON COLUMN skill_embedding.pid                 IS '內部自增主鍵';
COMMENT ON COLUMN skill_embedding.skill_embedding_uid IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN skill_embedding.skill_uid           IS '所屬 Skill UID（FK 至 skill；skill 軟刪時 rows 保留，檢索經 join 過濾）';
COMMENT ON COLUMN skill_embedding.source_type         IS '向量來源段（name / description / content；不設唯一約束，為 content chunking 預留）';
COMMENT ON COLUMN skill_embedding.embedding           IS '向量（text-embedding-3-small，1536 維）';
COMMENT ON COLUMN skill_embedding.created_at          IS '建立時間（重建時整批 delete + insert，即最近重建時間）';
