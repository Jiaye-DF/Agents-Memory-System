CREATE TABLE IF NOT EXISTS chat_attachment (
    pid                 BIGSERIAL     PRIMARY KEY,
    chat_attachment_uid UUID          NOT NULL DEFAULT gen_random_uuid(),
    owner_user_uid      UUID          NOT NULL,
    chat_session_uid    UUID          NOT NULL,
    file_name           VARCHAR(255)  NOT NULL,
    file_type           VARCHAR(100)  NOT NULL,
    file_size           BIGINT        NOT NULL,
    file_path           TEXT          NOT NULL,
    is_active           BOOLEAN       NOT NULL DEFAULT TRUE,
    is_deleted          BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_chat_attachment_user
        FOREIGN KEY (owner_user_uid) REFERENCES "user" (user_uid),
    CONSTRAINT fk_chat_attachment_session
        FOREIGN KEY (chat_session_uid) REFERENCES chat_session (chat_session_uid)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_attachment_chat_attachment_uid
    ON chat_attachment (chat_attachment_uid);

CREATE INDEX IF NOT EXISTS idx_chat_attachment_session_uid
    ON chat_attachment (chat_session_uid);

DROP TRIGGER IF EXISTS trg_chat_attachment_set_updated_at ON chat_attachment;
CREATE TRIGGER trg_chat_attachment_set_updated_at
    BEFORE UPDATE ON chat_attachment
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE  chat_attachment                     IS '對話附件表（圖片 / 文字檔），儲存附件 metadata 與本機檔案路徑';
COMMENT ON COLUMN chat_attachment.pid                 IS '內部自增主鍵';
COMMENT ON COLUMN chat_attachment.chat_attachment_uid IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN chat_attachment.owner_user_uid      IS '上傳者 user_uid';
COMMENT ON COLUMN chat_attachment.chat_session_uid    IS '所屬 Session UID';
COMMENT ON COLUMN chat_attachment.file_name           IS '使用者上傳時的原始檔名';
COMMENT ON COLUMN chat_attachment.file_type           IS 'MIME type（例：image/png、text/markdown）';
COMMENT ON COLUMN chat_attachment.file_size           IS '檔案大小（bytes）';
COMMENT ON COLUMN chat_attachment.file_path           IS '本機儲存路徑（data/attachments/{yyyymm}/{uid}.{ext}）';
COMMENT ON COLUMN chat_attachment.is_active           IS '是否啟用';
COMMENT ON COLUMN chat_attachment.is_deleted          IS '軟刪除標記';
COMMENT ON COLUMN chat_attachment.created_at          IS '建立時間';
COMMENT ON COLUMN chat_attachment.updated_at          IS '更新時間（Trigger 自動維護）';
