CREATE TABLE IF NOT EXISTS user_role (
    pid            BIGSERIAL    PRIMARY KEY,
    user_role_uid  UUID         NOT NULL DEFAULT gen_random_uuid(),
    name           VARCHAR(50)  NOT NULL,
    description    VARCHAR(200),
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted     BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_role_user_role_uid
    ON user_role (user_role_uid);

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_role_name
    ON user_role (name) WHERE is_deleted = FALSE;

CREATE TRIGGER trg_user_role_set_updated_at
    BEFORE UPDATE ON user_role
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE  user_role                   IS '使用者角色定義表';
COMMENT ON COLUMN user_role.pid               IS '內部自增主鍵';
COMMENT ON COLUMN user_role.user_role_uid     IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN user_role.name              IS '角色名稱（如 admin、member）';
COMMENT ON COLUMN user_role.description       IS '角色說明';
COMMENT ON COLUMN user_role.is_active         IS '是否啟用';
COMMENT ON COLUMN user_role.is_deleted        IS '是否軟刪除';
COMMENT ON COLUMN user_role.created_at        IS '建立時間';
COMMENT ON COLUMN user_role.updated_at        IS '更新時間（Trigger 自動維護）';

INSERT INTO user_role (name, description) VALUES
    ('admin',  '系統管理員，可管理所有使用者與系統設定'),
    ('member', '一般成員，僅可操作自身資源');
