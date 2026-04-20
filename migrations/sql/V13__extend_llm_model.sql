ALTER TABLE llm_model
    ADD COLUMN IF NOT EXISTS is_default        BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS max_output_tokens INTEGER;

CREATE UNIQUE INDEX IF NOT EXISTS uq_llm_model_default
    ON llm_model (is_default) WHERE is_default = TRUE AND is_deleted = FALSE;

COMMENT ON COLUMN llm_model.is_default        IS '是否為系統預設模型（全表唯一）';
COMMENT ON COLUMN llm_model.max_output_tokens IS '單次回覆最大 Token 數（NULL 表示未設定）';

UPDATE llm_model SET is_default = TRUE
 WHERE model_id = 'anthropic/claude-sonnet-4'
   AND is_deleted = FALSE
   AND NOT EXISTS (
       SELECT 1 FROM llm_model WHERE is_default = TRUE AND is_deleted = FALSE
   );

UPDATE llm_model SET max_output_tokens = 8192  WHERE model_id = 'anthropic/claude-sonnet-4' AND max_output_tokens IS NULL;
UPDATE llm_model SET max_output_tokens = 8192  WHERE model_id = 'anthropic/claude-haiku-4'  AND max_output_tokens IS NULL;
UPDATE llm_model SET max_output_tokens = 16384 WHERE model_id = 'openai/gpt-4o'             AND max_output_tokens IS NULL;
UPDATE llm_model SET max_output_tokens = 16384 WHERE model_id = 'openai/gpt-4o-mini'        AND max_output_tokens IS NULL;
UPDATE llm_model SET max_output_tokens = 8192  WHERE model_id = 'google/gemini-2.5-flash'   AND max_output_tokens IS NULL;
