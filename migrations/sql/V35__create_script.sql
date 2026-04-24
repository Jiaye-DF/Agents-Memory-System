-- ============================================================
-- V35：建立 script 表（腳本資源管理）
-- 依 docs/Tasks/v1.2/tasks-v1.2.3.md §A-1 / propose-v1.2.0.md §2-3
-- 與 Skill 結構平行：zip 打包儲存、favorite_count / download_count 跟 V33 對齊
-- 注意：resource_type 'script' 已於 V34 的 CHECK 提前加入，此處無需再動
-- ============================================================

CREATE TABLE IF NOT EXISTS script (
    pid              BIGSERIAL     PRIMARY KEY,
    script_uid       UUID          NOT NULL DEFAULT gen_random_uuid(),
    owner_user_uid   UUID          NOT NULL,
    name             VARCHAR(255)  NOT NULL,
    description      TEXT,
    file_name        VARCHAR(255)  NOT NULL,
    file_path        VARCHAR(500)  NOT NULL,
    file_size        BIGINT        NOT NULL,
    favorite_count   INT           NOT NULL DEFAULT 0,
    download_count   INT           NOT NULL DEFAULT 0,
    is_active        BOOLEAN       NOT NULL DEFAULT TRUE,
    is_deleted       BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_script_owner_user
        FOREIGN KEY (owner_user_uid) REFERENCES "user" (user_uid)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_script_script_uid
    ON script (script_uid);

-- Partial Unique：同擁有者未軟刪時 name 不可重複（可容忍軟刪歷史同名）
CREATE UNIQUE INDEX IF NOT EXISTS uq_script_owner_name_alive
    ON script (owner_user_uid, name)
    WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_script_owner_user_uid
    ON script (owner_user_uid);

CREATE INDEX IF NOT EXISTS idx_script_favorite_count
    ON script (favorite_count DESC);

CREATE INDEX IF NOT EXISTS idx_script_download_count
    ON script (download_count DESC);

CREATE TRIGGER trg_script_set_updated_at
    BEFORE UPDATE ON script
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE  script                 IS 'Script（腳本資源）資料表';
COMMENT ON COLUMN script.pid             IS '內部自增主鍵';
COMMENT ON COLUMN script.script_uid      IS '對外唯一識別碼（UUID）';
COMMENT ON COLUMN script.owner_user_uid  IS '擁有者 user_uid（關聯 user）';
COMMENT ON COLUMN script.name            IS 'Script 名稱（同擁有者未軟刪時唯一）';
COMMENT ON COLUMN script.description     IS 'Script 描述（可為空）';
COMMENT ON COLUMN script.file_name       IS '原始檔名 / 資料夾名（顯示用）';
COMMENT ON COLUMN script.file_path       IS '伺服器儲存的 zip 檔路徑';
COMMENT ON COLUMN script.file_size       IS 'zip 檔大小（bytes）';
COMMENT ON COLUMN script.favorite_count  IS '被收藏次數（denormalized，收藏 / 取消收藏時原子 +/- 1）';
COMMENT ON COLUMN script.download_count  IS '被下載次數（denormalized，下載 zip 回傳前原子 +1；同 user 24h Redis dedup）';
COMMENT ON COLUMN script.is_active       IS '是否啟用';
COMMENT ON COLUMN script.is_deleted      IS '是否軟刪除';
COMMENT ON COLUMN script.created_at      IS '建立時間';
COMMENT ON COLUMN script.updated_at      IS '更新時間（Trigger 自動維護）';

-- ------------------------------------------------------------
-- Seed system_setting：Script 上傳限制（v1.2.3 §A-2）
-- ------------------------------------------------------------
INSERT INTO system_setting (key, value, value_type, description, is_public) VALUES
    ('script.max_total_size_mb', '50', 'integer',
     'Script 單次上傳總大小上限（MB，最大 200）', FALSE),
    ('script.max_files_per_upload', '200', 'integer',
     'Script 單次上傳檔案數量上限（最大 1000）', FALSE),
    ('script.allowed_extensions', '.py,.sh,.js,.ts,.json,.yaml,.yml,.md,.txt,.csv', 'string',
     'Script 上傳允許的副檔名白名單（逗號分隔）', FALSE)
ON CONFLICT DO NOTHING;
