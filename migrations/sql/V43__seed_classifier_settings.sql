-- ============================================================
-- V43：seed 路由分類器（Routing Classifier）的 system_setting keys
-- 依 docs/Tasks/v1.3/tasks-v1.3.4.md Phase 0-1
--
-- 演進路徑（規則 → model）：
--   1. 規則引擎（v1.3.4 本版）— 零成本、可解釋
--   2. 規則撐不住時：local DistilBERT 二分類器 / 三分類器
--   3. 量大穩定後：雲端極小 model（haiku 級判斷）
-- classifier.model 欄位即為未來切換點，當前固定 "rule-based"。
--
-- 沿用 V14 system_setting INSERT pattern；以 uq_system_setting_key
-- partial index 為依據，重跑時 ON CONFLICT DO NOTHING 保留人工調整值。
-- ============================================================

INSERT INTO system_setting (key, value, value_type, description, is_public) VALUES
    (
        'classifier.enabled',
        'true',
        'boolean',
        '路由分類器開關（false 時全部走 expensive；multimodal 強制路由不受此影響）',
        FALSE
    ),
    (
        'classifier.model',
        '"rule-based"',
        'json',
        '分類器模型 ID；本版固定 rule-based。演進路徑：rule-based → local DistilBERT → 雲端極小 model',
        FALSE
    ),
    (
        'classifier.cheap_model',
        '"anthropic/claude-haiku-4-5"',
        'json',
        'cheap 路線使用的 model ID（不走 Agent 設定，刻意統一以利 metrics 比較）',
        FALSE
    ),
    (
        'classifier.skip_response_template',
        '"收到，繼續～"',
        'json',
        'skip 路線回固定字串模板（不呼叫 LLM）',
        FALSE
    ),
    (
        'classifier.thresholds',
        '{"min_length": 3, "greeting_whitelist": ["hi", "hello", "嗨", "你好", "好", "好的", "收到", "謝謝", "ok", "thanks", "thx"], "cheap_max_length": 60, "cheap_max_history_turns": 4, "skip_response_template_fallback": "收到。"}',
        'json',
        '規則引擎閾值（JSON）：min_length / greeting_whitelist / cheap_max_length / cheap_max_history_turns / skip_response_template_fallback',
        FALSE
    )
ON CONFLICT DO NOTHING;
