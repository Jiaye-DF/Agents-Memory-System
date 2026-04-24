-- ============================================================
-- V34：建立 user_favorite 表（泛型跨資源收藏）
-- 依 docs/Tasks/v1.2/tasks-v1.2.1.md §1-2 / propose-v1.2.0.md §2-1
-- 決策：
--   - resource_type + resource_uid 泛型，不綁 DB FK（容忍資源被刪除 → tombstone）
--   - Partial Unique：同 (owner_user_uid, resource_type, resource_uid) 未軟刪時只能一筆
--   - script 於 v1.2.3 才建表，但 CHECK 提前包含，避免 v1.2.3 再改 constraint
-- ============================================================

CREATE TABLE IF NOT EXISTS user_favorite (
    pid               BIGSERIAL    PRIMARY KEY,
    user_favorite_uid UUID         NOT NULL DEFAULT gen_random_uuid(),
    owner_user_uid    UUID         NOT NULL,
    resource_type     VARCHAR(20)  NOT NULL,
    resource_uid      UUID         NOT NULL,
    is_active         BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted        BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_user_favorite_resource_type
        CHECK (resource_type IN ('agent', 'skill', 'script'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_favorite_user_favorite_uid
    ON user_favorite (user_favorite_uid);

-- Partial Unique：同擁有者對同資源未軟刪僅能一筆（重複 POST 走 idempotent 路徑 / 復活）
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_favorite_owner_resource_alive
    ON user_favorite (owner_user_uid, resource_type, resource_uid)
    WHERE is_deleted = FALSE;

-- 「我的收藏」按類型列表查詢用
CREATE INDEX IF NOT EXISTS idx_user_favorite_owner_type
    ON user_favorite (owner_user_uid, resource_type);

CREATE TRIGGER trg_user_favorite_set_updated_at
    BEFORE UPDATE ON user_favorite
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE  user_favorite                    IS '使用者收藏表（泛型：agent / skill / script，不綁 DB FK）';
COMMENT ON COLUMN user_favorite.pid                IS '內部自增主鍵';
COMMENT ON COLUMN user_favorite.user_favorite_uid  IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN user_favorite.owner_user_uid     IS '收藏者 user_uid（不綁 FK 以利跨模組解耦）';
COMMENT ON COLUMN user_favorite.resource_type      IS '資源類型：agent / skill / script';
COMMENT ON COLUMN user_favorite.resource_uid       IS '資源 UID，對應 agent_uid / skill_uid / script_uid（不綁 FK 以容忍來源被刪除 → tombstone）';
COMMENT ON COLUMN user_favorite.is_active          IS '是否啟用';
COMMENT ON COLUMN user_favorite.is_deleted         IS '是否軟刪除（取消收藏即設為 TRUE；重新收藏則復活）';
COMMENT ON COLUMN user_favorite.created_at         IS '建立時間';
COMMENT ON COLUMN user_favorite.updated_at         IS '更新時間（Trigger 自動維護）';
