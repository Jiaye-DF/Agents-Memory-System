-- ============================================================
-- V39：建立 session_agent 中介表（v1.3.3 多 Agent 對話）
-- 依 docs/Tasks/v1.3/tasks-v1.3.3.md Phase 0-1 / 0-2
--
-- 用途：讓一個 chat_session 可同時掛多個 agent，取代 v1.1 起的
--       chat_session.agent_uid 單一 Agent 設計。
-- 軟刪除：is_deleted=TRUE 標記退出 session（保留歷史審計用）。
-- 角色：role 欄位限 'primary' / 'member'；同 session 僅一個 primary
--       由 partial unique index 保證。
-- ============================================================

CREATE TABLE IF NOT EXISTS session_agent (
    pid                BIGSERIAL    PRIMARY KEY,
    session_agent_uid  UUID         NOT NULL DEFAULT gen_random_uuid(),
    chat_session_uid   UUID         NOT NULL,
    agent_uid          UUID         NOT NULL,
    role               VARCHAR(20)  NOT NULL DEFAULT 'member',
    is_active          BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted         BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_session_agent_session
        FOREIGN KEY (chat_session_uid) REFERENCES chat_session (chat_session_uid)
        ON DELETE CASCADE,
    CONSTRAINT fk_session_agent_agent
        FOREIGN KEY (agent_uid) REFERENCES agent (agent_uid)
        ON DELETE RESTRICT,
    CONSTRAINT chk_session_agent_role
        CHECK (role IN ('primary', 'member'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_session_agent_session_agent_uid
    ON session_agent (session_agent_uid);

-- 同一 session 同一 agent 僅一筆有效紀錄；軟刪後可以重新加入
CREATE UNIQUE INDEX IF NOT EXISTS uq_session_agent_pair
    ON session_agent (chat_session_uid, agent_uid)
    WHERE is_deleted = FALSE;

-- 同一 session 僅允許一個 primary
CREATE UNIQUE INDEX IF NOT EXISTS uq_session_agent_primary
    ON session_agent (chat_session_uid)
    WHERE role = 'primary' AND is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_session_agent_session
    ON session_agent (chat_session_uid)
    WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_session_agent_agent
    ON session_agent (agent_uid)
    WHERE is_deleted = FALSE;

DROP TRIGGER IF EXISTS trg_session_agent_set_updated_at ON session_agent;
CREATE TRIGGER trg_session_agent_set_updated_at
    BEFORE UPDATE ON session_agent
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE  session_agent                    IS 'Session 與 Agent 的中介表（v1.3.3 多 Agent 對話）';
COMMENT ON COLUMN session_agent.pid                IS '內部自增主鍵';
COMMENT ON COLUMN session_agent.session_agent_uid  IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN session_agent.chat_session_uid   IS '所屬 Session UID';
COMMENT ON COLUMN session_agent.agent_uid          IS '掛載的 Agent UID';
COMMENT ON COLUMN session_agent.role               IS '角色：primary（同 session 唯一）或 member';
COMMENT ON COLUMN session_agent.is_active          IS '是否啟用';
COMMENT ON COLUMN session_agent.is_deleted         IS '軟刪除標記（離開 session）';
COMMENT ON COLUMN session_agent.created_at         IS '建立時間';
COMMENT ON COLUMN session_agent.updated_at         IS '更新時間（Trigger 自動維護）';

-- ============================================================
-- 一次性遷移：把 v1.1 既有 chat_session.agent_uid 同步寫入 session_agent
-- 這個 INSERT 僅在本 migration 套用時執行一次；後續寫入由 application 層處理。
-- ON CONFLICT DO NOTHING：避免重跑 migration（理論上不會發生）誤建重複資料。
-- ============================================================

INSERT INTO session_agent (chat_session_uid, agent_uid, role)
SELECT chat_session_uid, agent_uid, 'primary'
  FROM chat_session
 WHERE agent_uid IS NOT NULL
   AND is_deleted = FALSE
ON CONFLICT DO NOTHING;
