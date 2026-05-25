-- ============================================================
-- V54：建立 entity_tag 表（泛型中介表：tag ↔ skill / script / agent）
-- 依 docs/Tasks/v1.5/tasks-v1.5.1.md §1-2 / propose-v1.5.1.md §2-3
-- 決策：
--   - 泛型 entity_type + entity_uid，不綁 DB FK（沿用 user_favorite V34 風格）
--   - 軟刪 tag 時由 service 連動軟刪 entity_tag（不靠 DB cascade）
--   - 同 tag 對同 entity 未軟刪僅一筆（Partial Unique）
-- ============================================================

CREATE TABLE IF NOT EXISTS entity_tag (
    pid             BIGSERIAL    PRIMARY KEY,
    entity_tag_uid  UUID         NOT NULL DEFAULT gen_random_uuid(),
    tag_uid         UUID         NOT NULL,
    entity_type     VARCHAR(20)  NOT NULL,
    entity_uid      UUID         NOT NULL,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted      BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_entity_tag_entity_type
        CHECK (entity_type IN ('skill', 'script', 'agent'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_tag_entity_tag_uid
    ON entity_tag (entity_tag_uid);

-- Partial Unique：同 tag 對同 entity 未軟刪僅一筆
-- 重複 PUT 走 idempotent / 復活路徑
CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_tag_assignment_alive
    ON entity_tag (tag_uid, entity_type, entity_uid)
    WHERE is_deleted = FALSE;

-- 「這個 entity 的所有 tag」查詢 / response bulk load 用
CREATE INDEX IF NOT EXISTS idx_entity_tag_entity
    ON entity_tag (entity_type, entity_uid);

-- 「這個 tag 掛在哪些 entity」查詢 / filter intersect / cascade soft-delete 用
CREATE INDEX IF NOT EXISTS idx_entity_tag_tag_uid
    ON entity_tag (tag_uid);

CREATE TRIGGER trg_entity_tag_set_updated_at
    BEFORE UPDATE ON entity_tag
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE  entity_tag                 IS '泛型中介表：tag ↔ (skill / script / agent)，不綁 DB FK 以利跨表';
COMMENT ON COLUMN entity_tag.pid             IS '內部自增主鍵';
COMMENT ON COLUMN entity_tag.entity_tag_uid  IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN entity_tag.tag_uid         IS 'Tag 邏輯外鍵 → tag.tag_uid（不綁 DB FK，由 service 保證一致性）';
COMMENT ON COLUMN entity_tag.entity_type     IS '對應 entity 類型：skill / script / agent';
COMMENT ON COLUMN entity_tag.entity_uid      IS 'Entity UID，對應 skill_uid / script_uid / agent_uid（不綁 FK 以容忍 tombstone）';
COMMENT ON COLUMN entity_tag.is_active       IS '是否啟用';
COMMENT ON COLUMN entity_tag.is_deleted      IS '是否軟刪除（tag 軟刪時由 service 連動）';
COMMENT ON COLUMN entity_tag.created_at      IS '建立時間';
COMMENT ON COLUMN entity_tag.updated_at      IS '更新時間（Trigger 自動維護）';
