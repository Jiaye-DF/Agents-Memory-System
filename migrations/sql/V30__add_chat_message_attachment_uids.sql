ALTER TABLE chat_message
    ADD COLUMN IF NOT EXISTS attachment_uids UUID[] NULL;

COMMENT ON COLUMN chat_message.attachment_uids
    IS '訊息攜帶的附件 UID 陣列（對應 chat_attachment.chat_attachment_uid），無附件時為 NULL';
