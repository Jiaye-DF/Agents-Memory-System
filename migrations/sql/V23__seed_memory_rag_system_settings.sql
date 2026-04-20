INSERT INTO system_setting (key, value, value_type, description, is_public) VALUES
    ('memory.extractor_model', 'anthropic/claude-haiku-4-5', 'string', '記憶摘要使用的 LLM model（OpenRouter id）', FALSE),
    ('memory.batch_size', '5', 'integer', '記憶批次大小（每 N 則訊息觸發一次摘要）', FALSE),
    ('memory.idle_seconds', '60', 'integer', '記憶批次 idle 閾值（秒，超過則立即處理 buffer）', FALSE),
    ('memory.skip_rules', '{"min_length": 15, "greeting_whitelist": ["hi", "hello", "好", "好的", "收到", "謝謝", "ok"], "max_tokens": 2000}', 'json', '記憶預篩規則（JSON：min_length / greeting_whitelist / max_tokens）', FALSE),
    ('rag.enabled', 'true', 'boolean', '是否啟用 RAG 檢索注入 system prompt', FALSE),
    ('rag.top_k', '5', 'integer', 'RAG 檢索 top-k 數量', FALSE),
    ('rag.min_score', '0.7', 'string', 'RAG cosine similarity 最小分數（0.0 ~ 1.0）', FALSE)
ON CONFLICT DO NOTHING;
