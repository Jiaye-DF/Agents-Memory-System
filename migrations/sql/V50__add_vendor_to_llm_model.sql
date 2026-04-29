-- ============================================================
-- 為 llm_model 新增 vendor 欄位（廠商：anthropic / openai / google ...）。
--
-- 與既有 provider 欄位的語意分工：
--   - provider：接入通道 / gateway（目前統一 'OpenRouter'，未來可能新增
--     anthropic_native / bedrock / vertex 等）。
--   - vendor  ：模型廠商（從 model_id 第一段 split_part(model_id, '/', 1)
--     衍生），對應前後端管理頁顯示的「供應商」chip。
--
-- 此前管理頁的 vendor 顯示由 service / 前端 runtime 從 model_id 即時
-- 推導，導致每次 render 都要重算；改為持久化欄位後可直接讀取。
-- ============================================================

ALTER TABLE llm_model
    ADD COLUMN IF NOT EXISTS vendor VARCHAR(50);

UPDATE llm_model
   SET vendor = split_part(model_id, '/', 1)
 WHERE vendor IS NULL;

ALTER TABLE llm_model
    ALTER COLUMN vendor SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_llm_model_vendor ON llm_model(vendor);

COMMENT ON COLUMN llm_model.vendor
    IS '模型廠商（anthropic / openai / google ...），由 model_id vendor 段衍生並持久化';

-- ------------------------------------------------------------
-- 規範化 provider：a5ec97f 後新建的資料把 vendor 值寫進 provider，導致
-- 此欄位混雜（'OpenRouter' / 'anthropic' / 'openai' ...）。vendor 欄
-- 上線後 provider 還原為單純的 gateway 語意，目前統一為 'OpenRouter'。
-- ------------------------------------------------------------
UPDATE llm_model
   SET provider = 'OpenRouter'
 WHERE provider != 'OpenRouter';
