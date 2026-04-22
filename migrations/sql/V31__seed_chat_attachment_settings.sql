INSERT INTO system_setting (key, value, value_type, description, is_public) VALUES
    ('chat.max_attachment_size_mb', '10', 'integer', '單一附件檔案大小上限（MB），admin 可調，最大 50', TRUE),
    ('chat.max_attachments_per_message', '5', 'integer', '單則訊息可攜帶的附件數量上限，admin 可調，最大 10', TRUE),
    ('chat.attachment_allowed_extensions', '.png,.jpg,.jpeg,.webp,.pdf,.md,.txt,.json,.csv', 'string', '允許上傳的附件副檔名白名單（逗號分隔，含點）', TRUE),
    ('memory.image_describe_model', 'anthropic/claude-haiku-4-5', 'string', '記憶抽取圖片描述所使用的 vision model id（OpenRouter）', TRUE)
ON CONFLICT DO NOTHING;
