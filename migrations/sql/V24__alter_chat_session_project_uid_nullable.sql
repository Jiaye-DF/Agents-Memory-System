-- 1) chat_project_uid 改為可空（游離 session）
ALTER TABLE chat_session ALTER COLUMN chat_project_uid DROP NOT NULL;

-- 2) 新增 owner_user_uid 欄位以支援游離 session 的擁有權查詢
ALTER TABLE chat_session ADD COLUMN IF NOT EXISTS owner_user_uid UUID;

-- 3) 從 chat_project.owner_user_uid 回填既有 session（v1.1.4 前所有 session 都有 project）
UPDATE chat_session cs
   SET owner_user_uid = cp.owner_user_uid
  FROM chat_project cp
 WHERE cs.chat_project_uid = cp.chat_project_uid
   AND cs.owner_user_uid IS NULL;

-- 4) 設為 NOT NULL + FK + Index
ALTER TABLE chat_session ALTER COLUMN owner_user_uid SET NOT NULL;

ALTER TABLE chat_session
    ADD CONSTRAINT fk_chat_session_owner
    FOREIGN KEY (owner_user_uid) REFERENCES "user" (user_uid);

CREATE INDEX IF NOT EXISTS idx_chat_session_owner_user_uid
    ON chat_session (owner_user_uid);

-- 5) COMMENT
COMMENT ON COLUMN chat_session.chat_project_uid IS '所屬 Project UID（NULL 代表游離對話，不屬於任何 Project）';
COMMENT ON COLUMN chat_session.owner_user_uid   IS 'Session 擁有者 UID（v1.1.4 起獨立於 chat_project，供游離 session 直接查擁有權）';
