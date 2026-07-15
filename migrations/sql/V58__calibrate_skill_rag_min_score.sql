-- ============================================================
-- V58：校準 skill.rag.min_score 預設值 0.5 → 0.35（v1.6 fixed #2）
--
-- 依據：本機以真實 embedding + pgvector 實測（docs/Tasks/v1.6/fixed.md #2），
--   單詞查詢對「名稱完全相同」的 Skill 相似度僅約 0.49，預設 0.5 會把
--   合理命中全數擋掉；自然語句查詢約 0.75。0.35 可涵蓋單詞查詢
--   且不至於撈進無關結果。
--
-- 僅在該鍵仍為出廠值 '0.5' 時更新（保留人工調整值，對齊 V57 的
-- ON CONFLICT DO NOTHING 精神）。
-- ============================================================

UPDATE system_setting
SET value = '0.35'
WHERE key = 'skill.rag.min_score'
  AND value = '0.5';
