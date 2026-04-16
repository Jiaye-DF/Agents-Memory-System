CREATE TABLE IF NOT EXISTS "user" (
    pid              BIGSERIAL    PRIMARY KEY,
    user_uid         UUID         NOT NULL DEFAULT gen_random_uuid(),
    username         VARCHAR(50)  NOT NULL,
    account          VARCHAR(100) NOT NULL,
    hashed_password  VARCHAR(200) NOT NULL,
    role_uid         UUID         NOT NULL,
    login_fail_count INTEGER      NOT NULL DEFAULT 0,
    locked_until     TIMESTAMPTZ,
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted       BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_user_user_role
        FOREIGN KEY (role_uid) REFERENCES user_role (user_role_uid)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_user_uid
    ON "user" (user_uid);

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_account
    ON "user" (account) WHERE is_deleted = FALSE;

CREATE TRIGGER trg_user_set_updated_at
    BEFORE UPDATE ON "user"
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE  "user"                    IS '使用者資料表';
COMMENT ON COLUMN "user".pid                IS '內部自增主鍵';
COMMENT ON COLUMN "user".user_uid           IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN "user".username           IS '使用者名稱';
COMMENT ON COLUMN "user".account            IS '登入帳號';
COMMENT ON COLUMN "user".hashed_password    IS '密碼雜湊（bcrypt）';
COMMENT ON COLUMN "user".role_uid           IS '所屬角色 UID（關聯 user_role）';
COMMENT ON COLUMN "user".login_fail_count   IS '連續登入失敗次數';
COMMENT ON COLUMN "user".locked_until       IS '帳號鎖定到期時間（NULL 表示未鎖定）';
COMMENT ON COLUMN "user".is_active          IS '是否啟用';
COMMENT ON COLUMN "user".is_deleted         IS '是否軟刪除';
COMMENT ON COLUMN "user".created_at         IS '建立時間';
COMMENT ON COLUMN "user".updated_at         IS '更新時間（Trigger 自動維護）';
