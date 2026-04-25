-- ============================================================
-- V41：chat_session.agent_uid 改 nullable + 標 deprecated
-- 依 docs/Tasks/v1.3/tasks-v1.3.3.md Phase 0-4
--
-- 多 Agent 改用 session_agent 中介表；agent_uid 保留 nullable
-- 以容過渡期（既有讀取路徑、舊 API 仍可運作），未來版本再評估 drop。
-- ============================================================

ALTER TABLE chat_session
    ALTER COLUMN agent_uid DROP NOT NULL;

COMMENT ON COLUMN chat_session.agent_uid IS
    '[DEPRECATED v1.3.3] 單 Agent 時代欄位，多 Agent 改用 session_agent 中介表；保留 nullable 以容過渡期，未來版本再評估 drop';
