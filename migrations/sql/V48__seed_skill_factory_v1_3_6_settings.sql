-- ============================================================
-- V48：v1.3.6 Skill 工廠正式版 system_setting 種子（補三 scope 閾值與 recommender）
--
-- 規範依據：
--   - docs/Tasks/v1.3/tasks-v1.3.6.md §0-2 / 「初始閾值建議」表
--
-- 設計重點：
--   1. v1.1.7 的 `agentic.skill_factory.min_memory_count` / `topic_concentration` /
--      `cooldown_hours` 等 key 不動；session scope 程式端優先抓 `*.session.*`，
--      未設則 fallback 既有 key 以避免破壞 v1.1.7
--   2. ON CONFLICT DO NOTHING 確保 idempotent（重複套用 migration 不報錯）
-- ============================================================

INSERT INTO system_setting (key, value, value_type, description, is_public) VALUES
    -- session scope（沿用 v1.1.7 PoC 設定值；新 key 與既有 fallback 並存）
    ('agentic.skill_factory.session.min_memory_count', '10', 'integer',
        'session scope 觸發 Skill 候選生成的最小記憶數量', FALSE),
    ('agentic.skill_factory.session.topic_concentration', '0.3', 'string',
        'session scope 前 3 個 topic 頻率加總閾值（0.0 ~ 1.0）', FALSE),

    -- project scope（樣本量加倍 / 主題聚焦門檻提高）
    ('agentic.skill_factory.project.min_memory_count', '20', 'integer',
        'project scope 觸發 Skill 候選生成的最小 project_memory 數量', FALSE),
    ('agentic.skill_factory.project.topic_concentration', '0.4', 'string',
        'project scope 前 3 個 topic 頻率加總閾值（比 session 嚴）', FALSE),

    -- user scope（跨 project 長期偏好需更多樣本）
    ('agentic.skill_factory.user.min_memory_count', '30', 'integer',
        'user scope 觸發 Skill 候選生成的最小 user_memory 數量', FALSE),
    ('agentic.skill_factory.user.topic_concentration', '0.5', 'string',
        'user scope 前 3 個 topic 頻率加總閾值（最嚴）', FALSE),

    -- 全域：confidence 下限（低於此值的 LLM 候選不寫入 DB）
    ('agentic.skill_factory.confidence_floor', '0.6', 'string',
        'LLM 生成候選的 confidence 寫入下限；低於此值不寫入 DB', FALSE),

    -- 全域：suggestion TTL（lazy 標記為 expired）
    ('agentic.skill_factory.suggestion_ttl_days', '30', 'integer',
        'suggestion 自 created_at 起 N 天後 status 標為 expired（lazy 標記）', FALSE),

    -- recommender 主開關與門檻
    ('agentic.recommender.enabled', 'true', 'boolean',
        'Skill 推薦器總開關（false 時不對訊息送推薦事件）', FALSE),
    ('agentic.recommender.min_confidence', '0.75', 'string',
        '進入推薦清單的 confidence 下限（比 confidence_floor 嚴）', FALSE),
    ('agentic.recommender.cosine_threshold', '0.65', 'string',
        '訊息向量 vs 來源記憶向量的 cosine 相似度下限', FALSE),
    ('agentic.recommender.max_per_request', '3', 'integer',
        '單則訊息最多回幾筆推薦（避免抽屜爆量）', FALSE)
ON CONFLICT DO NOTHING;
