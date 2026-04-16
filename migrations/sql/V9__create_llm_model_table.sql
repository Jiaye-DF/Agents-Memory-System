CREATE TABLE IF NOT EXISTS llm_model (
    pid BIGSERIAL PRIMARY KEY,
    llm_model_uid UUID NOT NULL DEFAULT gen_random_uuid(),
    provider VARCHAR(50) NOT NULL,
    model_id VARCHAR(100) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_llm_model_uid ON llm_model(llm_model_uid);
CREATE UNIQUE INDEX IF NOT EXISTS uq_llm_model_model_id ON llm_model(model_id);
CREATE INDEX IF NOT EXISTS idx_llm_model_provider ON llm_model(provider);

CREATE TRIGGER trg_llm_model_updated_at
    BEFORE UPDATE ON llm_model
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

INSERT INTO llm_model (provider, model_id, display_name) VALUES
    ('OpenAI', 'openai/gpt-4o', 'GPT-4o'),
    ('OpenAI', 'openai/gpt-4o-mini', 'GPT-4o Mini'),
    ('Anthropic', 'anthropic/claude-sonnet-4', 'Claude Sonnet 4'),
    ('Anthropic', 'anthropic/claude-haiku-4', 'Claude Haiku 4'),
    ('Google', 'google/gemini-2.5-flash', 'Gemini 2.5 Flash')
ON CONFLICT DO NOTHING;
