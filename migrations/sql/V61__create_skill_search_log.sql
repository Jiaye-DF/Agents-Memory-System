-- v1.6.3：建立 skill_search_log（AI 查詢稽核表，寫入即不可變、無業務 FK）
-- 需求：記錄「誰、何時、用 AI 查詢搜了什麼、RAG 回傳哪些結果與相似度」，
--       供稽核使用行為與內容缺口（hit_count = 0 的查詢）分析。
-- 設計同 download_log（V55）/ llm_call_log：
--   * 不掛 FK：user_uid 為 UUID 但不綁外鍵，業務軟刪不連動
--   * 無 updated_at / is_deleted：log 一旦寫入即不修改、不軟刪
--   * username 存查詢當下快照
--   * results 以 JSONB 精簡存 [{"uid","name","score"}]（依分數降序），
--     分數自 v1.6.3 起不再於 UI 顯示，僅入稽核

CREATE TABLE IF NOT EXISTS skill_search_log (
    pid        BIGSERIAL    PRIMARY KEY,
    ts         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    user_uid   UUID         NOT NULL,
    username   VARCHAR(50)  NOT NULL,
    query      VARCHAR(500) NOT NULL,
    scope      VARCHAR(10)  NOT NULL,
    hit_count  INTEGER      NOT NULL,
    results    JSONB        NOT NULL DEFAULT '[]'
);

-- 索引：時序、依查詢者切片
CREATE INDEX IF NOT EXISTS idx_skill_search_log_ts
    ON skill_search_log (ts DESC);
CREATE INDEX IF NOT EXISTS idx_skill_search_log_user
    ON skill_search_log (user_uid, ts DESC);

COMMENT ON TABLE  skill_search_log           IS 'AI 查詢稽核紀錄（誰於何時搜了什麼、RAG 結果與相似度快照；寫入即不可變、無業務 FK）';
COMMENT ON COLUMN skill_search_log.pid       IS '內部自增主鍵';
COMMENT ON COLUMN skill_search_log.ts        IS '查詢時間';
COMMENT ON COLUMN skill_search_log.user_uid  IS '查詢者 UID（不綁 FK，user 軟刪不連動）';
COMMENT ON COLUMN skill_search_log.username  IS '查詢者名稱快照（查詢當下的 user.username）';
COMMENT ON COLUMN skill_search_log.query     IS '搜尋字串（trim 後，截 500 字元）';
COMMENT ON COLUMN skill_search_log.scope     IS '檢索範圍（visible / public）';
COMMENT ON COLUMN skill_search_log.hit_count IS '命中數（0 也記錄＝內容缺口訊號）';
COMMENT ON COLUMN skill_search_log.results   IS 'RAG 結果精簡快照：[{"uid","name","score"}]，依 score 降序';
