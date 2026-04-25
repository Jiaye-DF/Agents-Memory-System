-- ============================================================
-- V47：建立 agentic_skill_suggestion 表（v1.3.6 Agentic Skill 工廠正式版）
--
-- 規範依據：
--   - docs/Tasks/v1.3/propose-v1.3.0.md §5-2（Agentic Skill 工廠升級）
--   - docs/Tasks/v1.3/tasks-v1.3.6.md Phase 0-1
--
-- 設計重點：
--   1. Suggestion 從 Redis 暫存搬到 DB 表，保留 30 天供事後分析
--   2. owner_user_uid / scope_uid / created_skill_uid 皆「不」綁 DB FK
--      —— 跨模組泛型 + 容忍上游資源刪除（連動清除由 service layer 處理，
--         與 propose §3-3 記憶生命週期對齊）
--   3. Partial Unique：同擁有者 + scope + scope_uid + signature 同時間至多一筆 pending
--      （approved / rejected / expired 不限，可保留歷史紀錄）
-- ============================================================

CREATE TABLE IF NOT EXISTS agentic_skill_suggestion (
    pid                            BIGSERIAL     PRIMARY KEY,
    agentic_skill_suggestion_uid   UUID          NOT NULL DEFAULT gen_random_uuid(),
    owner_user_uid                 UUID          NOT NULL,
    scope                          VARCHAR(20)   NOT NULL,
    scope_uid                      UUID          NOT NULL,
    name                           VARCHAR(50)   NOT NULL,
    description                    VARCHAR(200)  NOT NULL,
    system_prompt                  TEXT          NOT NULL,
    confidence                     NUMERIC(4, 3) NOT NULL,
    source_memory_uids             UUID[]        NOT NULL DEFAULT ARRAY[]::UUID[],
    signature                      VARCHAR(64)   NOT NULL,
    status                         VARCHAR(20)   NOT NULL DEFAULT 'pending',
    created_skill_uid              UUID          NULL,
    is_active                      BOOLEAN       NOT NULL DEFAULT TRUE,
    is_deleted                     BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at                     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at                     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_agentic_skill_suggestion_scope
        CHECK (scope IN ('session', 'project', 'user')),
    CONSTRAINT chk_agentic_skill_suggestion_status
        CHECK (status IN ('pending', 'approved', 'rejected', 'expired')),
    CONSTRAINT chk_agentic_skill_suggestion_confidence
        CHECK (confidence >= 0 AND confidence <= 1)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_agentic_skill_suggestion_uid
    ON agentic_skill_suggestion (agentic_skill_suggestion_uid);

-- Partial Unique：同 scope 同 signature 同時間至多一筆 pending（cooldown 防護）
CREATE UNIQUE INDEX IF NOT EXISTS uq_agentic_skill_suggestion_pending
    ON agentic_skill_suggestion (owner_user_uid, scope, scope_uid, signature)
    WHERE is_deleted = FALSE AND status = 'pending';

-- 列表查詢：使用者 + 狀態（list / pending recommender 共用）
CREATE INDEX IF NOT EXISTS idx_agentic_skill_suggestion_owner_status
    ON agentic_skill_suggestion (owner_user_uid, status);

-- scope 索引：給 admin debug / 範圍限定查詢用
CREATE INDEX IF NOT EXISTS idx_agentic_skill_suggestion_scope
    ON agentic_skill_suggestion (owner_user_uid, scope, scope_uid)
    WHERE is_deleted = FALSE;

-- created_at 索引：30 天 expired 掃描用（lazy 標記，無 worker）
CREATE INDEX IF NOT EXISTS idx_agentic_skill_suggestion_created
    ON agentic_skill_suggestion (created_at DESC);

CREATE TRIGGER trg_agentic_skill_suggestion_set_updated_at
    BEFORE UPDATE ON agentic_skill_suggestion
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE  agentic_skill_suggestion                              IS 'Agentic Skill 工廠正式版的 Skill 候選表（v1.3.6；保留 30 天供事後分析）';
COMMENT ON COLUMN agentic_skill_suggestion.pid                          IS '內部自增主鍵';
COMMENT ON COLUMN agentic_skill_suggestion.agentic_skill_suggestion_uid IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN agentic_skill_suggestion.owner_user_uid               IS '所屬使用者 UID（不綁 FK；user 刪除由 service layer 連動）';
COMMENT ON COLUMN agentic_skill_suggestion.scope                        IS 'suggestion 範圍：session / project / user（CHECK 約束）';
COMMENT ON COLUMN agentic_skill_suggestion.scope_uid                    IS '對應 scope 的資源 UID（不綁 FK 以容忍資源刪除；對應記憶刪除時改 status=expired 而非硬刪）';
COMMENT ON COLUMN agentic_skill_suggestion.name                         IS 'Skill 名稱（最多 50 字元）';
COMMENT ON COLUMN agentic_skill_suggestion.description                  IS 'Skill 用途描述（最多 200 字元）';
COMMENT ON COLUMN agentic_skill_suggestion.system_prompt                IS '建議的 Skill system prompt 全文（私有資料；admin debug 不回傳全文）';
COMMENT ON COLUMN agentic_skill_suggestion.confidence                   IS 'LLM 候選信心分數（0.000 ~ 1.000；小於 confidence_floor 不寫入）';
COMMENT ON COLUMN agentic_skill_suggestion.source_memory_uids           IS '本次生成所參考的 memory uid 陣列（chat_memory / project_memory / user_memory 任一）';
COMMENT ON COLUMN agentic_skill_suggestion.signature                    IS 'sha256(sorted(set(topics)))；同 scope_uid + signature 在 cooldown 內不重複生成';
COMMENT ON COLUMN agentic_skill_suggestion.status                       IS '處理狀態：pending（待處理）/ approved / rejected / expired（CHECK 約束）';
COMMENT ON COLUMN agentic_skill_suggestion.created_skill_uid            IS 'status=approved 時填入新建立的 skill_uid（不綁 FK 以容忍 skill 後續刪除）';
COMMENT ON COLUMN agentic_skill_suggestion.is_active                    IS '是否啟用';
COMMENT ON COLUMN agentic_skill_suggestion.is_deleted                   IS '是否軟刪除（user 帳號刪除時連動）';
COMMENT ON COLUMN agentic_skill_suggestion.created_at                   IS '建立時間';
COMMENT ON COLUMN agentic_skill_suggestion.updated_at                   IS '更新時間（Trigger 自動維護）';
