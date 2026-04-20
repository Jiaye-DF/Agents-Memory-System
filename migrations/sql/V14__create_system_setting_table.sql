CREATE TABLE IF NOT EXISTS system_setting (
    pid                BIGSERIAL    PRIMARY KEY,
    system_setting_uid UUID         NOT NULL DEFAULT gen_random_uuid(),
    key                VARCHAR(100) NOT NULL,
    value              TEXT         NOT NULL,
    value_type         VARCHAR(20)  NOT NULL DEFAULT 'string',
    description        TEXT,
    is_public          BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active          BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted         BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_system_setting_uid
    ON system_setting (system_setting_uid);

CREATE UNIQUE INDEX IF NOT EXISTS uq_system_setting_key
    ON system_setting (key) WHERE is_deleted = FALSE;

DROP TRIGGER IF EXISTS trg_system_setting_updated_at ON system_setting;
CREATE TRIGGER trg_system_setting_updated_at
    BEFORE UPDATE ON system_setting
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE  system_setting                    IS '系統可調設定（key/value）表';
COMMENT ON COLUMN system_setting.pid                IS '內部自增主鍵，不對外暴露';
COMMENT ON COLUMN system_setting.system_setting_uid IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN system_setting.key                IS '設定鍵（如 agent.max_skills）';
COMMENT ON COLUMN system_setting.value              IS '設定值（統一以字串儲存，由服務層按 value_type 解析）';
COMMENT ON COLUMN system_setting.value_type         IS '值型別（string / integer / boolean / json）';
COMMENT ON COLUMN system_setting.description        IS '設定說明';
COMMENT ON COLUMN system_setting.is_public          IS '是否可由 member 讀取（true 出現在 /api/v1/settings/public）';
COMMENT ON COLUMN system_setting.is_active          IS '是否啟用';
COMMENT ON COLUMN system_setting.is_deleted         IS '軟刪除標記';
COMMENT ON COLUMN system_setting.created_at         IS '建立時間';
COMMENT ON COLUMN system_setting.updated_at         IS '更新時間（Trigger 自動維護）';

INSERT INTO system_setting (key, value, value_type, description, is_public) VALUES
    ('agent.max_skills', '10', 'integer', 'Agent 可關聯的 Skills 數量上限', TRUE)
ON CONFLICT DO NOTHING;
