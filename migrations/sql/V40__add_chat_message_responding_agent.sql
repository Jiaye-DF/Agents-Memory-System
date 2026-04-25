-- ============================================================
-- V40：chat_message 加 responding_agent_uid（v1.3.3 多 Agent 對話）
-- 依 docs/Tasks/v1.3/tasks-v1.3.3.md Phase 0-3
--
-- 一則 assistant 訊息綁定一個 Agent；user 訊息為 NULL。
-- 不在 DB 層加 FK：與 chat_message 既有 pattern 一致（不使用 Python 層 FK）。
-- ============================================================

ALTER TABLE chat_message
    ADD COLUMN IF NOT EXISTS responding_agent_uid UUID NULL;

CREATE INDEX IF NOT EXISTS idx_chat_message_responding_agent
    ON chat_message (responding_agent_uid)
    WHERE responding_agent_uid IS NOT NULL;

COMMENT ON COLUMN chat_message.responding_agent_uid
    IS '生成此訊息的 Agent UID（assistant 訊息用，user 訊息為 NULL）';

-- ============================================================
-- 一次性回填：既有 assistant 訊息以當時 chat_session.agent_uid 視為來源
-- 多 Agent 上線前，session 只可能掛一個 agent，這個對應是準確的。
-- ============================================================

UPDATE chat_message AS cm
   SET responding_agent_uid = cs.agent_uid
  FROM chat_session AS cs
 WHERE cm.chat_session_uid = cs.chat_session_uid
   AND cm.role = 'assistant'
   AND cm.responding_agent_uid IS NULL
   AND cs.agent_uid IS NOT NULL;
