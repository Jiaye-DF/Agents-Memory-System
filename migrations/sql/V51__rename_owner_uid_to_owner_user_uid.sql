-- ============================================================
-- agent / skill 兩張表 owner_uid → owner_user_uid
-- 對應 task spec：docs/Tasks/v1.3/tasks-v1.3.7.md §0-1
--
-- 統一 owner 欄位命名：v1.0 兩張短形式（agent / skill 用 owner_uid）
-- 對齊 v1.1+ 七張表的長形式（owner_user_uid），消除散落的命名分歧。
--
-- PostgreSQL 行為：
--   - ALTER TABLE ... RENAME COLUMN 會自動更新所有內部 metadata，
--     含 FK constraint（fk_agent_user / fk_skill_user）對欄位的引用，
--     **不**需重建 FK。
--   - Index 對欄位的引用會自動更新，但 index 自身名稱不變，
--     需手動 ALTER INDEX RENAME。
--   - Column comment 不會自動跟隨 RENAME，需手動 COMMENT ON。
-- ============================================================

-- ------------------------------------------------------------
-- agent
-- ------------------------------------------------------------
ALTER TABLE agent
    RENAME COLUMN owner_uid TO owner_user_uid;

ALTER INDEX IF EXISTS idx_agent_owner_uid
    RENAME TO idx_agent_owner_user_uid;

COMMENT ON COLUMN agent.owner_user_uid
    IS '擁有者 UID（關聯 user.user_uid）';

-- ------------------------------------------------------------
-- skill
-- ------------------------------------------------------------
ALTER TABLE skill
    RENAME COLUMN owner_uid TO owner_user_uid;

ALTER INDEX IF EXISTS idx_skill_owner_uid
    RENAME TO idx_skill_owner_user_uid;

COMMENT ON COLUMN skill.owner_user_uid
    IS '擁有者 UID（關聯 user.user_uid）';
