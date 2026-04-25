-- ============================================================
-- V46：seed 三層 RAG / 跨層聚合的 system_setting keys（v1.3.5）
--
-- 規範依據：
--   - docs/Tasks/v1.3/propose-v1.3.0.md §3-1 / §3-2
--   - docs/Tasks/v1.3/tasks-v1.3.5.md Phase 0-3
--
-- 沿用 V14 / V43 的 INSERT pattern；以 uq_system_setting_key
-- partial index 為依據，重跑時 ON CONFLICT DO NOTHING 保留人工調整值。
-- ============================================================

INSERT INTO system_setting (key, value, value_type, description, is_public) VALUES
    -- ---------- 三層 RAG 檢索參數 ----------
    (
        'rag.session.top_k',
        '10',
        'integer',
        '三層 RAG（session 層）檢索 top_k；融合前各層獨立取',
        FALSE
    ),
    (
        'rag.session.min_score',
        '0.7',
        'string',
        '三層 RAG（session 層）最低相似度（cosine score）；沿用 v1.1 預設 0.7',
        FALSE
    ),
    (
        'rag.project.top_k',
        '5',
        'integer',
        '三層 RAG（project 層）檢索 top_k',
        FALSE
    ),
    (
        'rag.project.min_score',
        '0.65',
        'string',
        '三層 RAG（project 層）最低相似度；跨層越廣允許越鬆',
        FALSE
    ),
    (
        'rag.user.top_k',
        '5',
        'integer',
        '三層 RAG（user 層）檢索 top_k',
        FALSE
    ),
    (
        'rag.user.min_score',
        '0.6',
        'string',
        '三層 RAG（user 層）最低相似度；跨層越廣允許越鬆',
        FALSE
    ),
    -- ---------- RRF 融合參數 ----------
    (
        'rag.fusion.k',
        '60',
        'integer',
        'RRF 融合常數 k（Elasticsearch 慣例 k=60；score = Σ 1/(k + rank)）',
        FALSE
    ),
    (
        'rag.fusion.final_top_k',
        '8',
        'integer',
        'RRF 融合後最終塞 prompt 的記憶筆數上限',
        FALSE
    ),
    -- ---------- Project 聚合 worker 觸發參數 ----------
    (
        'memory.project.aggregate_idle_hours',
        '6',
        'integer',
        'Project 二次聚合的 idle 時間閾值（小時）；距上次聚合 ≥ N 小時才觸發',
        FALSE
    ),
    (
        'memory.project.min_chat_memory_count',
        '5',
        'integer',
        '一個 project 累積 chat_memory 達 N 筆才聚合（避免空跑）',
        FALSE
    ),
    -- ---------- User 聚合 worker 觸發參數 ----------
    (
        'memory.user.aggregate_idle_hours',
        '24',
        'integer',
        'User 長期偏好聚合的 idle 時間閾值（小時）',
        FALSE
    ),
    (
        'memory.user.min_session_count',
        '5',
        'integer',
        'User 長期偏好聚合：同主題出現 ≥ N 筆才生 user_memory（N 預設 5）',
        FALSE
    ),
    (
        'memory.user.topic_concentration_pct',
        '60',
        'integer',
        'User 長期偏好聚合：同主題占比 ≥ M%（M 預設 60）',
        FALSE
    ),
    -- ---------- 聚合用 LLM model（共用） ----------
    (
        'memory.aggregation_extractor_model',
        '"anthropic/claude-haiku-4-5"',
        'json',
        'project_memory_worker / user_memory_worker 二次聚合使用的小模型 ID',
        FALSE
    )
ON CONFLICT DO NOTHING;
