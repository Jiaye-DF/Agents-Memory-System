-- ============================================================
-- user_role 表
-- ============================================================
COMMENT ON TABLE user_role IS '使用者角色定義表';
COMMENT ON COLUMN user_role.pid IS '內部自增主鍵，不對外暴露';
COMMENT ON COLUMN user_role.user_role_uid IS '角色的外部唯一識別碼（UUID）';
COMMENT ON COLUMN user_role.name IS '角色名稱，如 admin、member';
COMMENT ON COLUMN user_role.description IS '角色說明文字';
COMMENT ON COLUMN user_role.is_active IS '是否啟用，停用後無法被指派';
COMMENT ON COLUMN user_role.is_deleted IS '軟刪除標記，true 表示已刪除';
COMMENT ON COLUMN user_role.created_at IS '建立時間（UTC）';
COMMENT ON COLUMN user_role.updated_at IS '最後更新時間（UTC），由 Trigger 自動維護';

-- ============================================================
-- user 表
-- ============================================================
COMMENT ON TABLE "user" IS '使用者帳號表';
COMMENT ON COLUMN "user".pid IS '內部自增主鍵，不對外暴露';
COMMENT ON COLUMN "user".user_uid IS '使用者的外部唯一識別碼（UUID）';
COMMENT ON COLUMN "user".username IS '使用者顯示名稱，2-50 字元';
COMMENT ON COLUMN "user".account IS '登入帳號，≥8 字元，含字母與數字，全站唯一';
COMMENT ON COLUMN "user".hashed_password IS 'bcrypt 雜湊後的密碼，禁止明文儲存';
COMMENT ON COLUMN "user".role_uid IS '對應 user_role.user_role_uid 的外鍵';
COMMENT ON COLUMN "user".login_fail_count IS '連續登入失敗次數，成功登入後歸零';
COMMENT ON COLUMN "user".locked_until IS '帳號鎖定到期時間，NULL 表示未鎖定';
COMMENT ON COLUMN "user".is_active IS '是否啟用，停用後無法登入';
COMMENT ON COLUMN "user".is_deleted IS '軟刪除標記';
COMMENT ON COLUMN "user".created_at IS '建立時間（UTC）';
COMMENT ON COLUMN "user".updated_at IS '最後更新時間（UTC）';

-- ============================================================
-- agent 表
-- ============================================================
COMMENT ON TABLE agent IS 'AI Agent 設定表';
COMMENT ON COLUMN agent.pid IS '內部自增主鍵，不對外暴露';
COMMENT ON COLUMN agent.agent_uid IS 'Agent 的外部唯一識別碼（UUID）';
COMMENT ON COLUMN agent.owner_uid IS '擁有者，對應 user.user_uid';
COMMENT ON COLUMN agent.name IS 'Agent 名稱，最長 100 字元';
COMMENT ON COLUMN agent.description IS 'Agent 描述說明';
COMMENT ON COLUMN agent.language IS '語言偏好，如「繁體中文」';
COMMENT ON COLUMN agent.style IS '回答風格，如「專業」、「友善」';
COMMENT ON COLUMN agent.identity IS 'Agent 身分設定';
COMMENT ON COLUMN agent.role_prompt IS '角色系統提示詞（System Prompt）';
COMMENT ON COLUMN agent.model IS '使用的 LLM 模型 ID，對應 llm_model.model_id';
COMMENT ON COLUMN agent.temperature IS '生成溫度，0=確定性高，2=隨機性高';
COMMENT ON COLUMN agent.max_tokens IS '單次回覆最大 Token 數';
COMMENT ON COLUMN agent.greeting IS 'Agent 開場白，對話開始時的第一句話';
COMMENT ON COLUMN agent.response_format IS '回覆格式：markdown / plain_text / json';
COMMENT ON COLUMN agent.visibility IS '可見性：public（公開）或 private（私人）';
COMMENT ON COLUMN agent.is_active IS '是否啟用';
COMMENT ON COLUMN agent.is_deleted IS '軟刪除標記';
COMMENT ON COLUMN agent.created_at IS '建立時間（UTC）';
COMMENT ON COLUMN agent.updated_at IS '最後更新時間（UTC）';

-- ============================================================
-- agent_skill 表
-- ============================================================
COMMENT ON TABLE agent_skill IS 'Agent 與 Skill 的多對多關聯表';
COMMENT ON COLUMN agent_skill.agent_uid IS '對應 agent.agent_uid';
COMMENT ON COLUMN agent_skill.skill_uid IS '對應 skill.skill_uid';

-- ============================================================
-- skill 表
-- ============================================================
COMMENT ON TABLE skill IS 'Skills 模組表';
COMMENT ON COLUMN skill.pid IS '內部自增主鍵，不對外暴露';
COMMENT ON COLUMN skill.skill_uid IS 'Skill 的外部唯一識別碼（UUID）';
COMMENT ON COLUMN skill.owner_uid IS '擁有者，對應 user.user_uid';
COMMENT ON COLUMN skill.name IS 'Skill 名稱，最長 100 字元';
COMMENT ON COLUMN skill.description IS 'Skill 功能描述（必填）';
COMMENT ON COLUMN skill.file_path IS '伺服器端檔案儲存路徑';
COMMENT ON COLUMN skill.original_filename IS '使用者上傳時的原始檔名';
COMMENT ON COLUMN skill.file_size IS '檔案大小（位元組）';
COMMENT ON COLUMN skill.visibility IS '可見性：public（公開）或 private（私人）';
COMMENT ON COLUMN skill.is_active IS '是否啟用';
COMMENT ON COLUMN skill.is_deleted IS '軟刪除標記';
COMMENT ON COLUMN skill.created_at IS '建立時間（UTC）';
COMMENT ON COLUMN skill.updated_at IS '最後更新時間（UTC）';

-- ============================================================
-- llm_model 表
-- ============================================================
COMMENT ON TABLE llm_model IS 'LLM 模型清單，供 Agent 選用';
COMMENT ON COLUMN llm_model.pid IS '內部自增主鍵，不對外暴露';
COMMENT ON COLUMN llm_model.llm_model_uid IS '模型的外部唯一識別碼（UUID）';
COMMENT ON COLUMN llm_model.provider IS '模型提供商，如 OpenAI、Anthropic、Google';
COMMENT ON COLUMN llm_model.model_id IS '模型完整 ID，如 openai/gpt-4o，全站唯一';
COMMENT ON COLUMN llm_model.display_name IS '模型顯示名稱，供前端下拉選單使用';
COMMENT ON COLUMN llm_model.is_active IS '是否啟用，停用後不出現在選單中';
COMMENT ON COLUMN llm_model.is_deleted IS '軟刪除標記';
COMMENT ON COLUMN llm_model.created_at IS '建立時間（UTC）';
COMMENT ON COLUMN llm_model.updated_at IS '最後更新時間（UTC）';
