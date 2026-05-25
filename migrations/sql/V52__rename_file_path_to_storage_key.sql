ALTER TABLE skill RENAME COLUMN file_path TO storage_key;
ALTER TABLE script RENAME COLUMN file_path TO storage_key;
ALTER TABLE chat_attachment RENAME COLUMN file_path TO storage_key;

COMMENT ON COLUMN skill.storage_key IS 'S3 object key, 格式: skills/{skill_uid}/{filename}.zip';
COMMENT ON COLUMN script.storage_key IS 'S3 object key, 格式: scripts/{script_uid}/{filename}.zip';
COMMENT ON COLUMN chat_attachment.storage_key IS 'S3 object key, 格式: attachments/{chat_attachment_uid}/{filename}';
