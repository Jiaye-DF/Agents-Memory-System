-- ============================================================
-- V45：建立 user_memory 表（v1.3.5）
--
-- 規範依據：
--   - docs/Tasks/v1.3/propose-v1.3.0.md §3-1 / §3-3（跨層生命週期硬規範）
--   - docs/Arch/00-memory-system.md §5 / §6
--   - docs/Tasks/v1.3/tasks-v1.3.5.md Phase 0-2
--
-- 設計重點（勿違反）：
--   1. 對 chat_session **不**建立 FK cascade（propose §3-3）
--   2. 對 chat_project **不**連動：user_memory 是跨 project 的長期偏好，
--      project 刪除不應抹掉跨 project 累積的偏好（propose §3-3）
--   3. 對 user 建立 FK：user 停用 / 刪除由 service 層手動 hard delete 連動
--   4. 採 MemoryBase（無 updated_at / is_deleted / is_active）
-- ============================================================

CREATE TABLE IF NOT EXISTS user_memory (
    pid                      BIGSERIAL        PRIMARY KEY,
    user_memory_uid          UUID             NOT NULL DEFAULT gen_random_uuid(),
    owner_user_uid           UUID             NOT NULL,
    source_session_uids      UUID[]           NOT NULL,
    source_project_uids      UUID[]           NOT NULL DEFAULT '{}',
    keywords                 TEXT[]           NOT NULL DEFAULT '{}',
    entities                 TEXT[]           NOT NULL DEFAULT '{}',
    topic                    VARCHAR(200)     NULL,
    embedding                VECTOR(1536)     NOT NULL,
    created_at               TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_user_memory_user FOREIGN KEY (owner_user_uid)
        REFERENCES "user" (user_uid)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_memory_user_memory_uid
    ON user_memory (user_memory_uid);

CREATE INDEX IF NOT EXISTS idx_user_memory_owner_user_uid
    ON user_memory (owner_user_uid);

CREATE INDEX IF NOT EXISTS idx_user_memory_embedding_hnsw
    ON user_memory USING HNSW (embedding vector_cosine_ops);

COMMENT ON TABLE  user_memory                          IS 'User 層記憶表（跨 project 的長期偏好，審計用 / 快照；隨 user 停用 / 刪除由 service 層 hard delete 連動）';
COMMENT ON COLUMN user_memory.pid                      IS '內部自增主鍵';
COMMENT ON COLUMN user_memory.user_memory_uid          IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN user_memory.owner_user_uid           IS '所屬 user UID（FK 至 user；user 停用 / 刪除時連動清除）';
COMMENT ON COLUMN user_memory.source_session_uids      IS '聚合來源 session UID 陣列（不建 FK cascade，session 刪除不連動，propose §3-3 硬規範）';
COMMENT ON COLUMN user_memory.source_project_uids      IS '追溯來源 project UID 陣列（不連動 project 刪除，propose §3-3 硬規範）';
COMMENT ON COLUMN user_memory.keywords                 IS '長期偏好關鍵字（語言 / 風格 / 領域 / 慣用工具等）';
COMMENT ON COLUMN user_memory.entities                 IS '長期偏好實體列表';
COMMENT ON COLUMN user_memory.topic                    IS '偏好主題摘要';
COMMENT ON COLUMN user_memory.embedding                IS '向量（text-embedding-3-small，1536 維）';
COMMENT ON COLUMN user_memory.created_at               IS '建立時間（聚合寫入時間）';
