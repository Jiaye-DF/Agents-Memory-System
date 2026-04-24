-- ============================================================
-- V37：script 加 visibility 欄位（對齊 agent / skill 的 v1.1 既有設計）
-- 依 docs/Tasks/v1.2/tasks-v1.2.5.md §0-1 / fixed.md §4
-- DEFAULT 'private'：既有 row 套用後自動帶 private，不做 data migration
-- CHECK：'public' / 'private' 兩值限制，與 V5 agent / V7 skill 一致
-- ============================================================

ALTER TABLE script
    ADD COLUMN visibility VARCHAR(10) NOT NULL DEFAULT 'private';

ALTER TABLE script
    ADD CONSTRAINT chk_script_visibility
    CHECK (visibility IN ('public', 'private'));

COMMENT ON COLUMN script.visibility IS '可見性：public（公開）或 private（私人）';
