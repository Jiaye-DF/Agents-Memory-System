ALTER TABLE chat_message
    ADD COLUMN IF NOT EXISTS finish_reason VARCHAR(20) NULL;

COMMENT ON COLUMN chat_message.finish_reason IS 'OpenRouter finish_reason（stop / length / tool_calls 等；NULL 代表歷史訊息或非 assistant 角色）';
