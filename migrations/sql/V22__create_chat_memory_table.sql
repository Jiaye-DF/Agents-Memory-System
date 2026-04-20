CREATE TABLE IF NOT EXISTS chat_memory (
    pid                      BIGSERIAL        PRIMARY KEY,
    chat_memory_uid          UUID             NOT NULL DEFAULT gen_random_uuid(),
    chat_session_uid         UUID             NOT NULL,
    source_chat_message_uids UUID[]           NOT NULL,
    keywords                 TEXT[]           NOT NULL DEFAULT '{}',
    entities                 TEXT[]           NOT NULL DEFAULT '{}',
    topic                    VARCHAR(200)     NULL,
    embedding                VECTOR(1536)     NOT NULL,
    created_at               TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_chat_memory_session FOREIGN KEY (chat_session_uid) REFERENCES chat_session (chat_session_uid)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_memory_uid
    ON chat_memory (chat_memory_uid);

CREATE INDEX IF NOT EXISTS idx_chat_memory_session_uid
    ON chat_memory (chat_session_uid);

CREATE INDEX IF NOT EXISTS idx_chat_memory_embedding_hnsw
    ON chat_memory USING HNSW (embedding vector_cosine_ops);

COMMENT ON TABLE  chat_memory                          IS '對話記憶表（Session 層，隨 Session 軟刪而 hard delete）';
COMMENT ON COLUMN chat_memory.pid                      IS '內部自增主鍵';
COMMENT ON COLUMN chat_memory.chat_memory_uid          IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN chat_memory.chat_session_uid         IS '所屬 Session UID';
COMMENT ON COLUMN chat_memory.source_chat_message_uids IS '來源訊息 UID 陣列（批次摘要）';
COMMENT ON COLUMN chat_memory.keywords                 IS '關鍵字列表（小模型抽取）';
COMMENT ON COLUMN chat_memory.entities                 IS '實體列表（人名 / 地點 / 概念）';
COMMENT ON COLUMN chat_memory.topic                    IS '主題描述（摘要標題）';
COMMENT ON COLUMN chat_memory.embedding                IS '向量（text-embedding-3-small，1536 維）';
COMMENT ON COLUMN chat_memory.created_at               IS '建立時間';
