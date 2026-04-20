INSERT INTO system_setting (key, value, value_type, description, is_public) VALUES
    ('chat.max_sessions_per_project', '3', 'integer', '每個 Project 可建立的 Session 數量上限', TRUE),
    ('chat.max_projects_per_user', '5', 'integer', '每位使用者可建立的 Project 數量上限', TRUE)
ON CONFLICT DO NOTHING;
