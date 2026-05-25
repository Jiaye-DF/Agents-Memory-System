-- ============================================================
-- V53：建立 tag 表（per-user 自由輸入的 tag 池）
-- 依 docs/Tasks/v1.5/tasks-v1.5.1.md §1-1 / propose-v1.5.1.md §2-2
-- 決策：
--   - per-user 隔離（owner_user_uid）
--   - 跨 entity 類型共用（不分 skill / script / agent）
--   - 同擁有者 case-insensitive 唯一（lower(name) 比對）
--   - 軟刪允許同名復活（Partial Unique WHERE is_deleted = FALSE）
-- ============================================================

CREATE TABLE IF NOT EXISTS tag (
    pid             BIGSERIAL    PRIMARY KEY,
    tag_uid         UUID         NOT NULL DEFAULT gen_random_uuid(),
    owner_user_uid  UUID         NOT NULL,
    name            VARCHAR(50)  NOT NULL,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted      BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_tag_owner_user
        FOREIGN KEY (owner_user_uid) REFERENCES "user" (user_uid)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_tag_tag_uid
    ON tag (tag_uid);

-- Partial Unique：同擁有者 case-insensitive 未軟刪僅一筆
-- 軟刪後同名可被復活（find-or-create 模式）
CREATE UNIQUE INDEX IF NOT EXISTS uq_tag_owner_name_alive
    ON tag (owner_user_uid, lower(name))
    WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_tag_owner_user_uid
    ON tag (owner_user_uid);

CREATE TRIGGER trg_tag_set_updated_at
    BEFORE UPDATE ON tag
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE  tag                 IS 'Per-user tag 池（跨 skill / script / agent 共用，自由輸入沉澱）';
COMMENT ON COLUMN tag.pid             IS '內部自增主鍵';
COMMENT ON COLUMN tag.tag_uid         IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN tag.owner_user_uid  IS 'Tag 擁有者 user_uid（per-user 隔離）';
COMMENT ON COLUMN tag.name            IS 'Tag 顯示名稱（同擁有者 case-insensitive 未軟刪時唯一，最長 50 字元）';
COMMENT ON COLUMN tag.is_active       IS '是否啟用';
COMMENT ON COLUMN tag.is_deleted      IS '是否軟刪除（刪除時連動 entity_tag 由 service 軟刪）';
COMMENT ON COLUMN tag.created_at      IS '建立時間';
COMMENT ON COLUMN tag.updated_at      IS '更新時間（Trigger 自動維護）';
