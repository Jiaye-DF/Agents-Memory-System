CREATE TABLE IF NOT EXISTS chat_session (
    pid              BIGSERIAL    PRIMARY KEY,
    chat_session_uid UUID         NOT NULL DEFAULT gen_random_uuid(),
    chat_project_uid UUID         NOT NULL,
    agent_uid        UUID         NOT NULL,
    title            VARCHAR(200) NOT NULL DEFAULT '未命名對話',
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted       BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_chat_session_project FOREIGN KEY (chat_project_uid) REFERENCES chat_project (chat_project_uid),
    CONSTRAINT fk_chat_session_agent FOREIGN KEY (agent_uid) REFERENCES agent (agent_uid)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_session_uid
    ON chat_session (chat_session_uid);

CREATE INDEX IF NOT EXISTS idx_chat_session_project_uid
    ON chat_session (chat_project_uid);

CREATE INDEX IF NOT EXISTS idx_chat_session_agent_uid
    ON chat_session (agent_uid);

DROP TRIGGER IF EXISTS trg_chat_session_set_updated_at ON chat_session;
CREATE TRIGGER trg_chat_session_set_updated_at
    BEFORE UPDATE ON chat_session
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE  chat_session                  IS '對話 Session 表（1 session 對 1 agent）';
COMMENT ON COLUMN chat_session.pid              IS '內部自增主鍵';
COMMENT ON COLUMN chat_session.chat_session_uid IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN chat_session.chat_project_uid IS '所屬 Project UID';
COMMENT ON COLUMN chat_session.agent_uid        IS '綁定的 Agent UID（建立後不可變更）';
COMMENT ON COLUMN chat_session.title            IS 'Session 標題，首則訊息自動帶入前 30 字';
COMMENT ON COLUMN chat_session.is_active        IS '是否啟用';
COMMENT ON COLUMN chat_session.is_deleted       IS '軟刪除標記';
COMMENT ON COLUMN chat_session.created_at       IS '建立時間';
COMMENT ON COLUMN chat_session.updated_at       IS '更新時間（Trigger 自動維護）';
