-- v1.3.0 Phase 0：建立 llm_call_log（運營資料表，30 天保留、無業務 FK cascade）
-- 設計依據：docs/Arch/01-observability-and-metrics.md §5-1
-- 此表為「寫入即不可變」之運營審計表，與業務資料生命週期獨立：
--   * 不掛 FK：session_uid / user_uid / agent_uid 為 UUID 但不綁外鍵，業務軟刪不連動
--   * 無 updated_at / is_deleted：log 一旦寫入即不修改、不軟刪
--   * 對外不提供 *_uid 欄位（pid 即唯一鍵；本表為內部運營資料，不對外暴露）

CREATE TABLE IF NOT EXISTS llm_call_log (
    pid                     BIGSERIAL      PRIMARY KEY,
    ts                      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    session_uid             UUID,
    user_uid                UUID,
    agent_uid               UUID,
    purpose                 VARCHAR(40)    NOT NULL,
    route                   VARCHAR(20),
    model                   VARCHAR(100),
    input_tokens            INT            NOT NULL DEFAULT 0,
    output_tokens           INT            NOT NULL DEFAULT 0,
    cache_creation_tokens   INT            NOT NULL DEFAULT 0,
    cache_read_tokens       INT            NOT NULL DEFAULT 0,
    actual_cost_usd         NUMERIC(10, 6) NOT NULL DEFAULT 0,
    baseline_cost_usd       NUMERIC(10, 6) NOT NULL DEFAULT 0,
    latency_ms              INT,
    rag_hit_count           INT,
    rag_max_score           NUMERIC(4, 3),
    error                   TEXT
);

-- 索引：時序、user / session / purpose 切片
CREATE INDEX IF NOT EXISTS idx_llm_call_log_ts
    ON llm_call_log (ts DESC);
CREATE INDEX IF NOT EXISTS idx_llm_call_log_user
    ON llm_call_log (user_uid, ts DESC);
CREATE INDEX IF NOT EXISTS idx_llm_call_log_session
    ON llm_call_log (session_uid, ts DESC);
CREATE INDEX IF NOT EXISTS idx_llm_call_log_purpose
    ON llm_call_log (purpose, ts DESC);

COMMENT ON TABLE  llm_call_log                       IS 'LLM 呼叫運營日誌（成本 / 延遲 / 失敗率，審計用、30 天保留、無業務 FK）';
COMMENT ON COLUMN llm_call_log.pid                   IS '內部自增主鍵';
COMMENT ON COLUMN llm_call_log.ts                    IS '呼叫時間（TIMESTAMPTZ，存 UTC+8 wall-clock）';
COMMENT ON COLUMN llm_call_log.session_uid           IS '所屬 chat session UID（不綁 FK，session 軟刪不連動）';
COMMENT ON COLUMN llm_call_log.user_uid              IS '發起呼叫的使用者 UID（不綁 FK）';
COMMENT ON COLUMN llm_call_log.agent_uid             IS '呼叫使用的 Agent UID（不綁 FK，可為 NULL）';
COMMENT ON COLUMN llm_call_log.purpose               IS '呼叫用途（chat / memory_extract / embedding / classifier / image_describe / skill_factory 等）';
COMMENT ON COLUMN llm_call_log.route                 IS 'classifier 路由結果（skip / cheap / expensive，非 chat 場景為 NULL）';
COMMENT ON COLUMN llm_call_log.model                 IS '實際呼叫的 model id（skip 路線為 NULL）';
COMMENT ON COLUMN llm_call_log.input_tokens          IS '輸入 token 數';
COMMENT ON COLUMN llm_call_log.output_tokens         IS '輸出 token 數';
COMMENT ON COLUMN llm_call_log.cache_creation_tokens IS 'Anthropic prompt cache 建立 token 數（其他供應商為 0）';
COMMENT ON COLUMN llm_call_log.cache_read_tokens     IS 'Anthropic prompt cache 命中 token 數（其他供應商為 0）';
COMMENT ON COLUMN llm_call_log.actual_cost_usd       IS '實際花費（美元，精度 0.000001）';
COMMENT ON COLUMN llm_call_log.baseline_cost_usd     IS 'counterfactual baseline 成本（假設全走 EXPENSIVE_MODEL_ID 會花的錢）';
COMMENT ON COLUMN llm_call_log.latency_ms            IS '本次呼叫起訖延遲（毫秒）';
COMMENT ON COLUMN llm_call_log.rag_hit_count         IS 'RAG 撈到的記憶筆數（非 chat 場景為 NULL）';
COMMENT ON COLUMN llm_call_log.rag_max_score         IS 'RAG top-1 cosine score（非 chat 場景為 NULL）';
COMMENT ON COLUMN llm_call_log.error                 IS '錯誤訊息（成功為 NULL；最多 500 字元，不存 prompt / response 原文）';
