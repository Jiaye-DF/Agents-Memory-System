-- 一次性 dev DB 校正：把既有 agent_language / agent_template 的 sort_order
-- 從 10/20/30/40/50 改為 1/2/3/4/5，與重編後的 V12 / V17 seed 對齊。
--
-- 使用方式：
--   docker compose -f docker-compose.dev.yml exec -T postgres \
--     psql -U $POSTGRES_USER -d $POSTGRES_DB \
--     < migrations/scripts/dev_renumber_sort_order.sql
--
-- 注意：
--   1. 本檔不在 migrations/sql/ 下，Flyway 不會自動套用
--   2. 套用前請先執行 flyway repair 對齊 V12 / V17 checksum
--   3. 僅依 code / template_key 比對既有列；新增列不會影響

BEGIN;

-- agent_language
UPDATE agent_language SET sort_order = 1 WHERE code = 'zh-TW';
UPDATE agent_language SET sort_order = 2 WHERE code = 'en';
UPDATE agent_language SET sort_order = 3 WHERE code = 'ja';
UPDATE agent_language SET sort_order = 4 WHERE code = 'zh-CN';
UPDATE agent_language SET sort_order = 5 WHERE code = 'ko';

-- agent_template
UPDATE agent_template SET sort_order = 1 WHERE template_key = 'python-dev';
UPDATE agent_template SET sort_order = 2 WHERE template_key = 'code-reviewer';
UPDATE agent_template SET sort_order = 3 WHERE template_key = 'zh-writer';
UPDATE agent_template SET sort_order = 4 WHERE template_key = 'zh-en-translator';

-- 驗證
SELECT 'agent_language' AS tbl, code, sort_order FROM agent_language ORDER BY sort_order;
SELECT 'agent_template' AS tbl, template_key, sort_order FROM agent_template ORDER BY sort_order;

COMMIT;
