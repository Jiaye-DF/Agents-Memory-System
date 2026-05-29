# v1.5.2 任務規格：下載人員紀錄（download_log）

> **狀態：進行中（Phase 1-3 code 實作完成；Phase 4 部署 / 驗收待人工執行）**

## 版本目標

記錄「誰、何時、下載了哪個 Skill / Agent / Script」，供稽核。現況僅有 `download_count` 聚合計數（v1.2.1），無從得知下載者身份；本版新增一張寫入即不可變的稽核表，並在下載流程寫入。查詢直接以 SQL 進行，不做 API / 前端 UI。

- 每次下載都寫一筆，與既有 24h Redis dedup 計數**獨立**
- `username` / `resource_name` 存下載當下快照，資源日後改名 / 軟刪仍可追溯
- `counted` 欄位標記本次是否實際 +1 `download_count`，供與聚合計數對帳

### 範圍內

- Flyway **V55**（`download_log` 表）
- 後端：`download_log` Model / Repository（單筆寫入）
- 後端：`download_service.record_download()` + 三 entity download 流程寫入

### 範圍外

- 查詢 API（`/admin/download-logs` 等）—（決策：直接下 SQL 查即可）
- 前端 UI
- 附帶下載的關聯 Skills 另記為獨立下載事件（決策：Agent 下載只記 Agent 本身一筆，附帶 Skills 維持原本「僅計數」行為）
- 保留期 / 定期清理 job
- 單元測試（純加表 / 加寫入，沿用既有 log repository 自我保護慣例）

---

## 前置現況

- **既有 Flyway 最大版本**：`V54__create_entity_tag_table.sql`，本 task 起算 **V55**
- **稽核表參考實作**（寫入即不可變、無 FK、獨立 DeclarativeBase）：
  - [`models/llm_call_log.py`](../../../backend/app/models/llm_call_log.py) + [V38 migration](../../../migrations/sql/V38__create_llm_call_log.sql)
  - [`repositories/llm_call_log_repository.py`](../../../backend/app/repositories/llm_call_log_repository.py)（`log()` 失敗只 warning 不 raise）
- **既有下載計數**：[`services/download_service.py`](../../../backend/app/services/download_service.py) `try_increment_download`（24h Redis dedup）
- **既有下載流程**：
  - [`services/skill_service.py`](../../../backend/app/services/skill_service.py) `download_skill`
  - [`services/agent_service.py`](../../../backend/app/services/agent_service.py) `download_agent`
  - [`services/script_service.py`](../../../backend/app/services/script_service.py) `download_script`
- **既無**：`download_log` 表、`download_log` Model / Repository

---

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | 記錄粒度 | **每次下載都記一筆**（同人 24h 內重複下載也留紀錄）|
| 2 | 名稱存法 | `username` / `resource_name` 存下載**當下快照**（不查詢時 join）|
| 3 | 查詢介面 | **建表 + 寫入即可**，查詢直接下 SQL，不做 API / 前端 UI |
| 4 | Agent 下載 | 只記 Agent 本身一筆；附帶關聯 Skills 維持原本「僅計數」行為，不另記紀錄 |
| 5 | counted 欄位 | 記錄本次是否實際 +1（TRUE=首次/未去重；FALSE=24h dedup 命中未計），供對帳 |
| 6 | FK / 生命週期 | 不綁 DB FK、無 `is_deleted` / `updated_at`，沿用 `llm_call_log` 風格 |
| 7 | 寫入失敗處理 | repository 吞例外只 log warning，不拖垮下載主流程 |

---

## Phase 0：依賴與設定

無新依賴。純 DB + 既有技術棧。

---

## Phase 1：DB Migration

### 1-1 V55 — 建 `download_log` 表

- [x] 新建 [`migrations/sql/V55__create_download_log.sql`](../../../migrations/sql/V55__create_download_log.sql)
- [x] 表結構：`pid` BIGSERIAL / `ts` TIMESTAMPTZ DEFAULT NOW() / `user_uid` UUID / `username` VARCHAR(50) / `resource_type` VARCHAR(20) / `resource_uid` UUID / `resource_name` VARCHAR(255) / `counted` BOOLEAN DEFAULT TRUE
- [x] 索引：`idx_download_log_ts ON (ts DESC)`
- [x] 索引：`idx_download_log_user ON (user_uid, ts DESC)`
- [x] 索引：`idx_download_log_resource ON (resource_type, resource_uid, ts DESC)`
- [x] 無 DB FK、無 `is_deleted` / `updated_at`（沿用 `llm_call_log` 風格）
- [x] `COMMENT ON TABLE` + 每欄位 `COMMENT ON COLUMN` 中文說明

---

## Phase 2：Model / Repository 層

### 2-1 `app/models/download_log.py`（新建）

- [x] `class DownloadLogBase(DeclarativeBase)`：`pid` / `ts`（獨立 base，無 `updated_at` / `is_deleted` / `is_active`）
- [x] `class DownloadLog(DownloadLogBase)`：`user_uid` / `username` / `resource_type` / `resource_uid` / `resource_name` / `counted`
- [x] 不綁 FK、不繼承 `Base`（仿 `llm_call_log`）

### 2-2 `app/repositories/download_log_repository.py`（新建）

- [x] `async def log(payload, db) -> None`：whitelist 欄位 → `db.add` + `flush`
- [x] 任何 DB 錯誤僅 log warning 不 raise（仿 `llm_call_log_repository.log`）

---

## Phase 3：Service 寫入串接

### 3-1 `download_service.record_download`

- [x] 新增 `async def record_download(resource_type, resource_uid, resource_name, user_uid, counted, db)`
- [x] 查 `user_repository.get_by_uid` 取 `username` 快照（查無 user 退而以 `user_uid` 充當）
- [x] `user_uid` / `resource_uid` 轉 `uuid.UUID` 後寫入

### 3-2 三 entity download 流程串接

- [x] [`skill_service.download_skill`](../../../backend/app/services/skill_service.py)：`counted = try_increment_download(...)` → `record_download("skill", ...)`
- [x] [`script_service.download_script`](../../../backend/app/services/script_service.py)：同上
- [x] [`agent_service.download_agent`](../../../backend/app/services/agent_service.py)：`record_download("agent", ...)` 只記 Agent 一筆；附帶 Skills 維持原本 `try_increment_download` 計數

### 3-3 本機驗證

- [x] `py_compile` 改動的 6 個 Python 檔通過

---

## Phase 4：部署與驗收

### 4-1 部署順序

- [ ] Merge 本 task PR 到 `main`
- [ ] Flyway 跑 V55（純加表，無 outage）
- [ ] Backend 重啟生效

### 4-2 驗收清單（以 SQL 查 `download_log`）

- [ ] 下載任一 Skill / Agent / Script 後，`download_log` 出現對應 row（`username` / `resource_name` 正確）
- [ ] 同人 24h 內重複下載：仍新增 row，且第二筆起 `counted = FALSE`
- [ ] Agent 下載：`download_log` 僅 `resource_type='agent'` 一筆；關聯 Skills 不另記紀錄
- [ ] 常用查詢：

```sql
-- 最近下載：誰、何時、下載了什麼
SELECT ts, username, resource_type, resource_name, counted
FROM download_log ORDER BY ts DESC LIMIT 50;

-- 某資源被哪些人下載
SELECT ts, username, user_uid FROM download_log
WHERE resource_type = 'skill' AND resource_name = 'xxx' ORDER BY ts DESC;

-- 某人下載過哪些東西
SELECT ts, resource_type, resource_name FROM download_log
WHERE username = 'xxx' ORDER BY ts DESC;

-- 各資源下載排行（總事件 vs 實際計數，可與 download_count 對帳）
SELECT resource_type, resource_name,
       COUNT(*) AS total_events,
       COUNT(*) FILTER (WHERE counted) AS counted_events
FROM download_log
GROUP BY resource_type, resource_name ORDER BY total_events DESC;
```

### 4-3 Rollback

- 程式碼層：可（純加功能，往回拔不影響既有資料）
- DB 層：不建議 drop V55，forward fix 即可
