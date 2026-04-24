-- ============================================================
-- V36：Seed 儀錶板排行榜設定
-- 依 docs/Tasks/v1.2/tasks-v1.2.4.md §1-1 / propose-v1.2.0.md §2-4
-- 沿用 V31 / V32 / V35 的 `INSERT ... ON CONFLICT DO NOTHING` seed 風格。
-- ============================================================

INSERT INTO system_setting (key, value, value_type, description, is_public) VALUES
    ('dashboard.ranking_size', '10', 'integer',
     '儀錶板首頁排行榜 top N 數量（每類資源各自撈 N 條後合併重排截 N）', FALSE)
ON CONFLICT DO NOTHING;
