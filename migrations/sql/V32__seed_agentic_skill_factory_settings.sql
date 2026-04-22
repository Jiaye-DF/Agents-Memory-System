-- v1.1.7 Agentic Skill 工廠 PoC 系統設定
INSERT INTO system_setting (key, value, value_type, description, is_public) VALUES
    ('agentic.skill_factory.enabled', 'true', 'boolean', 'Agentic Skill 工廠總開關（關閉後不再產生候選 Skill）', FALSE),
    ('agentic.skill_factory.min_memory_count', '10', 'integer', '單一 session 觸發 Skill 候選生成的最小記憶數量', FALSE),
    ('agentic.skill_factory.topic_concentration', '0.3', 'string', '前 3 個 topic 頻率加總閾值（0.0~1.0）', FALSE),
    ('agentic.skill_factory.analyzer_model', 'anthropic/claude-haiku-4-5', 'string', 'Skill 工廠 analyzer/generator 使用的 LLM 模型（OpenRouter id）', FALSE),
    ('agentic.skill_factory.cooldown_hours', '24', 'integer', '同 signature（topic 集合雜湊）冷卻小時數，避免重複觸發', FALSE)
ON CONFLICT DO NOTHING;
