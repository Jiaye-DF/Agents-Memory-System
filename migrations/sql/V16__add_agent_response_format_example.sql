ALTER TABLE agent ADD COLUMN IF NOT EXISTS response_format_example TEXT;
COMMENT ON COLUMN agent.response_format_example IS '當 response_format=json 時，使用者提供的範例結構，附加到 system prompt 指引 LLM 輸出格式';
