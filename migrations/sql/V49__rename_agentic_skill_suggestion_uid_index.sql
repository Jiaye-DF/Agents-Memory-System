-- ============================================================
-- 修正 V47 的 agentic_skill_suggestion uid 唯一索引命名，對齊
-- 21-database.md §命名慣例（`uq_{表}_{表}_uid`，禁止簡寫為 `uq_{表}_uid`），
-- 延續 V15 / V26 的索引重命名修正。
--
-- V47 建立時誤寫為 `uq_agentic_skill_suggestion_uid`（屬規範禁止的簡寫格式），
-- 與 V35 (uq_script_script_uid)、V44 (uq_project_memory_project_memory_uid)、
-- V45 (uq_user_memory_user_memory_uid) 不一致；本 migration 統一改名。
-- ============================================================

ALTER INDEX IF EXISTS uq_agentic_skill_suggestion_uid
    RENAME TO uq_agentic_skill_suggestion_agentic_skill_suggestion_uid;
