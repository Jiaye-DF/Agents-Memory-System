-- ============================================================
-- 修正 V17 / V18 / V19 / V20 / V22 的唯一索引命名，對齊
-- 21-database.md §命名慣例（uq_{表}_{欄位}，禁止簡寫），
-- 延續 V15 已完成的 V9 / V12 / V14 索引重命名。
-- ============================================================

-- ------------------------------------------------------------
-- agent_template（V17）
-- ------------------------------------------------------------
ALTER INDEX IF EXISTS uq_agent_template_uid
    RENAME TO uq_agent_template_agent_template_uid;

-- ------------------------------------------------------------
-- chat_project（V18）
-- ------------------------------------------------------------
ALTER INDEX IF EXISTS uq_chat_project_uid
    RENAME TO uq_chat_project_chat_project_uid;

-- ------------------------------------------------------------
-- chat_session（V19）
-- ------------------------------------------------------------
ALTER INDEX IF EXISTS uq_chat_session_uid
    RENAME TO uq_chat_session_chat_session_uid;

-- ------------------------------------------------------------
-- chat_message（V20）
-- ------------------------------------------------------------
ALTER INDEX IF EXISTS uq_chat_message_uid
    RENAME TO uq_chat_message_chat_message_uid;

-- ------------------------------------------------------------
-- chat_memory（V22）
-- ------------------------------------------------------------
ALTER INDEX IF EXISTS uq_chat_memory_uid
    RENAME TO uq_chat_memory_chat_memory_uid;
