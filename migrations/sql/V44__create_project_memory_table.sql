-- ============================================================
-- V44：建立 project_memory 表（v1.3.5）
--
-- 規範依據：
--   - docs/Tasks/v1.3/propose-v1.3.0.md §3-1 / §3-3（跨層生命週期硬規範）
--   - docs/Arch/00-memory-system.md §5 / §6
--   - docs/Tasks/v1.3/tasks-v1.3.5.md Phase 0-1
--
-- 設計重點（勿違反）：
--   1. 對 chat_session **不**建立 FK cascade（propose §3-3）
--      —— 跨層記憶必須獨立生命週期，session 刪除不能誤抹 project_memory
--   2. 對 chat_project 建立 FK：project 刪除由 service 層手動 hard delete
--   3. 沿用 chat_memory 的 HNSW 向量索引 pattern（V22）
--   4. 採 MemoryBase（無 updated_at / is_deleted / is_active），審計表性質
-- ============================================================

CREATE TABLE IF NOT EXISTS project_memory (
    pid                      BIGSERIAL        PRIMARY KEY,
    project_memory_uid       UUID             NOT NULL DEFAULT gen_random_uuid(),
    chat_project_uid         UUID             NOT NULL,
    source_session_uids      UUID[]           NOT NULL,
    source_chat_message_uids UUID[]           NOT NULL DEFAULT '{}',
    keywords                 TEXT[]           NOT NULL DEFAULT '{}',
    entities                 TEXT[]           NOT NULL DEFAULT '{}',
    topic                    VARCHAR(200)     NULL,
    embedding                VECTOR(1536)     NOT NULL,
    created_at               TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_project_memory_project FOREIGN KEY (chat_project_uid)
        REFERENCES chat_project (chat_project_uid)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_project_memory_project_memory_uid
    ON project_memory (project_memory_uid);

CREATE INDEX IF NOT EXISTS idx_project_memory_chat_project_uid
    ON project_memory (chat_project_uid);

CREATE INDEX IF NOT EXISTS idx_project_memory_embedding_hnsw
    ON project_memory USING HNSW (embedding vector_cosine_ops);

COMMENT ON TABLE  project_memory                          IS 'Project 層記憶表（同 project 下所有 session 的二次聚合，審計用 / 快照；隨 project 刪除由 service 層 hard delete 連動）';
COMMENT ON COLUMN project_memory.pid                      IS '內部自增主鍵';
COMMENT ON COLUMN project_memory.project_memory_uid       IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN project_memory.chat_project_uid         IS '所屬 Project UID（FK 至 chat_project；project 刪除時由 service 層連動清除）';
COMMENT ON COLUMN project_memory.source_session_uids      IS '聚合來源 session UID 陣列（不建 FK cascade，session 刪除不連動，propose §3-3 硬規範）';
COMMENT ON COLUMN project_memory.source_chat_message_uids IS '可追溯的來源訊息 UID 陣列（可空）';
COMMENT ON COLUMN project_memory.keywords                 IS '聚合後關鍵字列表（小模型二次抽取）';
COMMENT ON COLUMN project_memory.entities                 IS '聚合後實體列表';
COMMENT ON COLUMN project_memory.topic                    IS '主題摘要（同主題合併後重生成）';
COMMENT ON COLUMN project_memory.embedding                IS '向量（text-embedding-3-small，1536 維）';
COMMENT ON COLUMN project_memory.created_at               IS '建立時間（聚合寫入時間）';
