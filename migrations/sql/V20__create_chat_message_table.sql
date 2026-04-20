CREATE TABLE IF NOT EXISTS chat_message (
    pid              BIGSERIAL     PRIMARY KEY,
    chat_message_uid UUID          NOT NULL DEFAULT gen_random_uuid(),
    chat_session_uid UUID          NOT NULL,
    role             VARCHAR(20)   NOT NULL,
    content          TEXT          NOT NULL,
    token_in         INTEGER,
    token_out        INTEGER,
    cost_usd         NUMERIC(10,6),
    model            VARCHAR(100),
    is_active        BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_chat_message_session FOREIGN KEY (chat_session_uid) REFERENCES chat_session (chat_session_uid),
    CONSTRAINT chk_chat_message_role CHECK (role IN ('user', 'assistant', 'system', 'tool'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_message_uid
    ON chat_message (chat_message_uid);

CREATE INDEX IF NOT EXISTS idx_chat_message_session_uid_created_at
    ON chat_message (chat_session_uid, created_at);

COMMENT ON TABLE  chat_message                  IS '對話訊息表（不可編輯、不軟刪除，審計用）';
COMMENT ON COLUMN chat_message.pid              IS '內部自增主鍵';
COMMENT ON COLUMN chat_message.chat_message_uid IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN chat_message.chat_session_uid IS '所屬 Session UID';
COMMENT ON COLUMN chat_message.role             IS '角色（user / assistant / system / tool）';
COMMENT ON COLUMN chat_message.content          IS '訊息內容';
COMMENT ON COLUMN chat_message.token_in         IS '輸入 token 數（assistant 訊息才有值）';
COMMENT ON COLUMN chat_message.token_out        IS '輸出 token 數（assistant 訊息才有值）';
COMMENT ON COLUMN chat_message.cost_usd         IS '本次請求成本（美元，assistant 訊息才有值）';
COMMENT ON COLUMN chat_message.model            IS '實際呼叫的 model id（user / system 訊息為 NULL）';
COMMENT ON COLUMN chat_message.is_active        IS '是否啟用（保留欄位，目前固定 TRUE）';
COMMENT ON COLUMN chat_message.created_at       IS '建立時間';
