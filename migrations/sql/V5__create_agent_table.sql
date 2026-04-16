CREATE TABLE IF NOT EXISTS agent (
    pid          BIGSERIAL    PRIMARY KEY,
    agent_uid    UUID         NOT NULL DEFAULT gen_random_uuid(),
    owner_uid    UUID         NOT NULL,
    name         VARCHAR(100) NOT NULL,
    description  TEXT,
    language     VARCHAR(50),
    style        VARCHAR(50),
    identity     VARCHAR(200),
    role_prompt  TEXT,
    visibility   VARCHAR(10)  NOT NULL DEFAULT 'private',
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted   BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_agent_user FOREIGN KEY (owner_uid) REFERENCES "user" (user_uid),
    CONSTRAINT chk_agent_visibility CHECK (visibility IN ('public', 'private'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_agent_uid ON agent (agent_uid);
CREATE INDEX IF NOT EXISTS idx_agent_owner_uid ON agent (owner_uid);

CREATE TRIGGER trg_agent_set_updated_at
    BEFORE UPDATE ON agent
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE  agent                IS 'Agent 定義表';
COMMENT ON COLUMN agent.pid            IS '內部自增主鍵';
COMMENT ON COLUMN agent.agent_uid      IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN agent.owner_uid      IS '擁有者 UUID（關聯 user 表）';
COMMENT ON COLUMN agent.name           IS 'Agent 名稱';
COMMENT ON COLUMN agent.description    IS 'Agent 描述';
COMMENT ON COLUMN agent.language       IS '語言偏好';
COMMENT ON COLUMN agent.style          IS '風格';
COMMENT ON COLUMN agent.identity       IS '身分';
COMMENT ON COLUMN agent.role_prompt    IS '角色設定';
COMMENT ON COLUMN agent.visibility     IS '可見性（public / private）';
COMMENT ON COLUMN agent.is_active      IS '是否啟用';
COMMENT ON COLUMN agent.is_deleted     IS '是否軟刪除';
COMMENT ON COLUMN agent.created_at     IS '建立時間';
COMMENT ON COLUMN agent.updated_at     IS '更新時間（Trigger 自動維護）';
