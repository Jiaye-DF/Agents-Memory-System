-- v1.5.x：建立 download_log（下載人員紀錄表，寫入即不可變、無業務 FK）
-- 需求：記錄「誰、何時、下載了哪個 Skill / Agent / Script」，供稽核以 SQL 查詢。
-- 與 download_count 聚合計數獨立：
--   * download_count 受 24h Redis dedup 影響（同人 24h 內只計 1 次）
--   * download_log 每次下載都寫一筆（不去重），counted 欄位標記本次是否實際 +1
-- 設計同 llm_call_log（docs/Arch/01-observability-and-metrics.md §5-1）：
--   * 不掛 FK：user_uid / resource_uid 為 UUID 但不綁外鍵，業務軟刪不連動
--   * 無 updated_at / is_deleted：log 一旦寫入即不修改、不軟刪
--   * username / resource_name 存下載當下快照，資源日後改名 / 軟刪仍可追溯

CREATE TABLE IF NOT EXISTS download_log (
    pid            BIGSERIAL    PRIMARY KEY,
    ts             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    user_uid       UUID         NOT NULL,
    username       VARCHAR(50)  NOT NULL,
    resource_type  VARCHAR(20)  NOT NULL,
    resource_uid   UUID         NOT NULL,
    resource_name  VARCHAR(255) NOT NULL,
    counted        BOOLEAN      NOT NULL DEFAULT TRUE
);

-- 索引：時序、依下載者切片、依資源切片
CREATE INDEX IF NOT EXISTS idx_download_log_ts
    ON download_log (ts DESC);
CREATE INDEX IF NOT EXISTS idx_download_log_user
    ON download_log (user_uid, ts DESC);
CREATE INDEX IF NOT EXISTS idx_download_log_resource
    ON download_log (resource_type, resource_uid, ts DESC);

COMMENT ON TABLE  download_log               IS '下載人員紀錄（誰於何時下載哪個資源，稽核用、寫入即不可變、無業務 FK）';
COMMENT ON COLUMN download_log.pid           IS '內部自增主鍵';
COMMENT ON COLUMN download_log.ts            IS '下載時間（TIMESTAMPTZ，存 UTC+8 wall-clock）';
COMMENT ON COLUMN download_log.user_uid      IS '下載者 UID（不綁 FK，user 軟刪不連動）';
COMMENT ON COLUMN download_log.username      IS '下載者名稱快照（下載當下的 user.username）';
COMMENT ON COLUMN download_log.resource_type IS '資源類型（skill / agent / script）';
COMMENT ON COLUMN download_log.resource_uid  IS '被下載資源 UID（不綁 FK，資源軟刪不連動）';
COMMENT ON COLUMN download_log.resource_name IS '被下載資源名稱快照（下載當下的資源名稱）';
COMMENT ON COLUMN download_log.counted       IS '本次是否實際 +1 download_count（TRUE=首次/未去重；FALSE=24h dedup 命中未計）';
