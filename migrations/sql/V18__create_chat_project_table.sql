CREATE TABLE IF NOT EXISTS chat_project (
    pid              BIGSERIAL    PRIMARY KEY,
    chat_project_uid UUID         NOT NULL DEFAULT gen_random_uuid(),
    owner_user_uid   UUID         NOT NULL,
    name             VARCHAR(100) NOT NULL,
    description      TEXT,
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted       BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_chat_project_user FOREIGN KEY (owner_user_uid) REFERENCES "user" (user_uid)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_project_uid
    ON chat_project (chat_project_uid);

CREATE INDEX IF NOT EXISTS idx_chat_project_owner_user_uid
    ON chat_project (owner_user_uid);

DROP TRIGGER IF EXISTS trg_chat_project_set_updated_at ON chat_project;
CREATE TRIGGER trg_chat_project_set_updated_at
    BEFORE UPDATE ON chat_project
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE  chat_project                  IS '對話 Project 容器表';
COMMENT ON COLUMN chat_project.pid              IS '內部自增主鍵';
COMMENT ON COLUMN chat_project.chat_project_uid IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN chat_project.owner_user_uid   IS '擁有者 user_uid';
COMMENT ON COLUMN chat_project.name             IS 'Project 名稱（1-100 字元）';
COMMENT ON COLUMN chat_project.description      IS 'Project 描述';
COMMENT ON COLUMN chat_project.is_active        IS '是否啟用';
COMMENT ON COLUMN chat_project.is_deleted       IS '軟刪除標記';
COMMENT ON COLUMN chat_project.created_at       IS '建立時間';
COMMENT ON COLUMN chat_project.updated_at       IS '更新時間（Trigger 自動維護）';
