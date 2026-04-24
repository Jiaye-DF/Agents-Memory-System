-- ============================================================
-- V33：為 agent / skill 加入社群互動計數欄位（favorite_count / download_count）
-- 依 docs/Tasks/v1.2/tasks-v1.2.1.md §1-1
-- 計數策略：denormalized 欄位 + 寫入時即時 +/- 1；並發依賴 PG row-level lock
-- ============================================================

-- ------------------------------------------------------------
-- agent
-- ------------------------------------------------------------
ALTER TABLE agent
    ADD COLUMN IF NOT EXISTS favorite_count INT NOT NULL DEFAULT 0;
ALTER TABLE agent
    ADD COLUMN IF NOT EXISTS download_count INT NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_agent_favorite_count
    ON agent (favorite_count DESC);
CREATE INDEX IF NOT EXISTS idx_agent_download_count
    ON agent (download_count DESC);

COMMENT ON COLUMN agent.favorite_count IS '被收藏次數（denormalized，收藏 / 取消收藏時原子 +/- 1）';
COMMENT ON COLUMN agent.download_count IS '被下載次數（denormalized；v1.2 Agent 恆為 0，欄位保留供未來 export / import 使用）';

-- ------------------------------------------------------------
-- skill
-- ------------------------------------------------------------
ALTER TABLE skill
    ADD COLUMN IF NOT EXISTS favorite_count INT NOT NULL DEFAULT 0;
ALTER TABLE skill
    ADD COLUMN IF NOT EXISTS download_count INT NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_skill_favorite_count
    ON skill (favorite_count DESC);
CREATE INDEX IF NOT EXISTS idx_skill_download_count
    ON skill (download_count DESC);

COMMENT ON COLUMN skill.favorite_count IS '被收藏次數（denormalized，收藏 / 取消收藏時原子 +/- 1）';
COMMENT ON COLUMN skill.download_count IS '被下載次數（denormalized，下載 zip 回傳前原子 +1；同 user 24h Redis dedup）';
