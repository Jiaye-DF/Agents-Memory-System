CREATE TABLE IF NOT EXISTS agent_language (
    pid                BIGSERIAL    PRIMARY KEY,
    agent_language_uid UUID         NOT NULL DEFAULT gen_random_uuid(),
    code               VARCHAR(20)  NOT NULL,
    name               VARCHAR(50)  NOT NULL,
    sort_order         INTEGER      NOT NULL DEFAULT 0,
    is_default         BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active          BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted         BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_language_uid
    ON agent_language (agent_language_uid);

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_language_code
    ON agent_language (code) WHERE is_deleted = FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_language_default
    ON agent_language (is_default) WHERE is_default = TRUE AND is_deleted = FALSE;

DROP TRIGGER IF EXISTS trg_agent_language_updated_at ON agent_language;
CREATE TRIGGER trg_agent_language_updated_at
    BEFORE UPDATE ON agent_language
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE  agent_language                    IS 'Agent 語言偏好選項表';
COMMENT ON COLUMN agent_language.pid                IS '內部自增主鍵，不對外暴露';
COMMENT ON COLUMN agent_language.agent_language_uid IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN agent_language.code               IS '語系碼（如 zh-TW、en），儲存於 agent.language';
COMMENT ON COLUMN agent_language.name               IS '顯示名稱（如 繁體中文）';
COMMENT ON COLUMN agent_language.sort_order         IS '下拉選單排序，數字越小越前面';
COMMENT ON COLUMN agent_language.is_default         IS '是否為預設語言（全表唯一）';
COMMENT ON COLUMN agent_language.is_active          IS '是否啟用，停用後不出現在 member 端清單';
COMMENT ON COLUMN agent_language.is_deleted         IS '軟刪除標記';
COMMENT ON COLUMN agent_language.created_at         IS '建立時間';
COMMENT ON COLUMN agent_language.updated_at         IS '更新時間（Trigger 自動維護）';

INSERT INTO agent_language (code, name, sort_order, is_default) VALUES
    ('zh-TW', '繁體中文', 10, TRUE),
    ('en',    'English',  20, FALSE),
    ('ja',    '日本語',   30, FALSE),
    ('zh-CN', '简体中文', 40, FALSE),
    ('ko',    '한국어',   50, FALSE)
ON CONFLICT DO NOTHING;
