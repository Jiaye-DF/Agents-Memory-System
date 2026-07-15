-- ============================================================
-- V57：seed Skill 語意檢索（skill.rag.*）的 system_setting keys（v1.6.0）
--
-- 規範依據：
--   - docs/Tasks/v1.6/propose-v1.6.0.md §2-3
--   - docs/Tasks/v1.6/tasks-v1.6.0.md Phase 1
--
-- 沿用 V46 的 INSERT pattern；以 uq_system_setting_key
-- partial index 為依據，重跑時 ON CONFLICT DO NOTHING 保留人工調整值。
-- ============================================================

INSERT INTO system_setting (key, value, value_type, description, is_public) VALUES
    -- ---------- 語意檢索參數 ----------
    (
        'skill.rag.enabled',
        'true',
        'boolean',
        'Skill 語意檢索總開關；關閉時 search endpoint 回空',
        FALSE
    ),
    (
        'skill.rag.top_k',
        '8',
        'integer',
        'Skill 語意檢索向量回傳筆數上限',
        FALSE
    ),
    (
        'skill.rag.min_score',
        '0.5',
        'string',
        'Skill 語意檢索最低相似度（cosine score）；跨語意較鬆，低於記憶層的 0.6~0.7',
        FALSE
    ),
    -- ---------- AI 分析（推薦理由）參數 ----------
    (
        'skill.rag.analyze_enabled',
        'true',
        'boolean',
        '是否呼叫 LLM 生成推薦理由（AI 分析）；關閉時只回向量結果',
        FALSE
    ),
    (
        'skill.rag.analyze_top_n',
        '5',
        'integer',
        'AI 分析丟給 LLM 生成理由的前 N 筆（控制成本）',
        FALSE
    ),
    (
        'skill.rag.analyze_model',
        '"anthropic/claude-haiku-4-5"',
        'json',
        'AI 分析使用的小模型 ID（對齊 memory.aggregation_extractor_model）',
        FALSE
    ),
    -- ---------- Embedding 組文字參數 ----------
    (
        'skill.rag.embed_content_max_chars',
        '8000',
        'integer',
        '組 embedding 文字時，檔案內容截斷上限（避免超長文本）',
        FALSE
    )
ON CONFLICT DO NOTHING;
