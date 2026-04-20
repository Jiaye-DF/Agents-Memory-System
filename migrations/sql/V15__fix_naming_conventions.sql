-- ============================================================
-- 修正 V9 / V12 / V14 的索引與 Trigger 命名，對齊
-- 21-database.md §命名慣例（uq_{表}_{欄位}、trg_{表}_{動作}），
-- 並同步 V11 的 llm_model.provider 註解與 seed 以符合
-- tasks-v1.0.1.md §已確認決策 #1（provider 統一為 OpenRouter）。
-- ============================================================

-- ------------------------------------------------------------
-- llm_model
-- ------------------------------------------------------------
ALTER INDEX IF EXISTS uq_llm_model_uid
    RENAME TO uq_llm_model_llm_model_uid;

ALTER TRIGGER trg_llm_model_updated_at
    ON llm_model
    RENAME TO trg_llm_model_set_updated_at;

UPDATE llm_model
   SET provider = 'OpenRouter'
 WHERE provider IN ('OpenAI', 'Anthropic', 'Google')
   AND is_deleted = FALSE;

COMMENT ON COLUMN llm_model.provider
    IS '模型提供商（統一為 OpenRouter，對應 tasks-v1.0.1.md §已確認決策 #1）';

-- ------------------------------------------------------------
-- agent_language
-- ------------------------------------------------------------
ALTER INDEX IF EXISTS uq_agent_language_uid
    RENAME TO uq_agent_language_agent_language_uid;

ALTER TRIGGER trg_agent_language_updated_at
    ON agent_language
    RENAME TO trg_agent_language_set_updated_at;

-- ------------------------------------------------------------
-- system_setting
-- ------------------------------------------------------------
ALTER INDEX IF EXISTS uq_system_setting_uid
    RENAME TO uq_system_setting_system_setting_uid;

ALTER TRIGGER trg_system_setting_updated_at
    ON system_setting
    RENAME TO trg_system_setting_set_updated_at;
