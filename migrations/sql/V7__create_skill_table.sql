CREATE TABLE IF NOT EXISTS skill (
    pid               BIGSERIAL    PRIMARY KEY,
    skill_uid         UUID         NOT NULL DEFAULT gen_random_uuid(),
    owner_uid         UUID         NOT NULL,
    name              VARCHAR(100) NOT NULL,
    description       TEXT         NOT NULL,
    file_path         VARCHAR(500) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size         BIGINT       NOT NULL,
    visibility        VARCHAR(10)  NOT NULL DEFAULT 'private',
    is_active         BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted        BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_skill_user
        FOREIGN KEY (owner_uid) REFERENCES "user" (user_uid),
    CONSTRAINT chk_skill_visibility
        CHECK (visibility IN ('public', 'private'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_skill_skill_uid
    ON skill (skill_uid);

CREATE INDEX IF NOT EXISTS idx_skill_owner_uid
    ON skill (owner_uid);

CREATE TRIGGER trg_skill_set_updated_at
    BEFORE UPDATE ON skill
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE  skill                    IS 'Skill 資料表';
COMMENT ON COLUMN skill.pid               IS '內部自增主鍵';
COMMENT ON COLUMN skill.skill_uid         IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN skill.owner_uid         IS '擁有者 UID（關聯 user）';
COMMENT ON COLUMN skill.name              IS 'Skill 名稱';
COMMENT ON COLUMN skill.description       IS 'Skill 描述';
COMMENT ON COLUMN skill.file_path         IS '伺服器端檔案儲存路徑';
COMMENT ON COLUMN skill.original_filename IS '原始上傳檔案名稱';
COMMENT ON COLUMN skill.file_size         IS '檔案大小（bytes）';
COMMENT ON COLUMN skill.visibility        IS '可見性（public / private）';
COMMENT ON COLUMN skill.is_active         IS '是否啟用';
COMMENT ON COLUMN skill.is_deleted        IS '是否軟刪除';
COMMENT ON COLUMN skill.created_at        IS '建立時間';
COMMENT ON COLUMN skill.updated_at        IS '更新時間（Trigger 自動維護）';
