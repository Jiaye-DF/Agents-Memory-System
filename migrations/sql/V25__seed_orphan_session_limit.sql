INSERT INTO system_setting (key, value, value_type, description, is_public) VALUES
    ('chat.max_orphan_sessions_per_user', '10', 'integer', '每位使用者可建立的游離 Session（不屬於任何 Project）上限；硬上限 30', TRUE)
ON CONFLICT DO NOTHING;
