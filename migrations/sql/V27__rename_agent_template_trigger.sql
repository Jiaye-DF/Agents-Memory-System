-- ============================================================
-- 修正 V17 的 Trigger 命名，對齊 21-database.md §命名慣例
-- （trg_{表}_set_updated_at，不可省略 set_ 中綴）。
-- V15 曾統一修正 V9 / V12 / V14 的同類命名；V17 於 V15 之後
-- 新增，未套用修正 → 本檔補齊。
-- ============================================================

ALTER TRIGGER trg_agent_template_updated_at
    ON agent_template
    RENAME TO trg_agent_template_set_updated_at;
