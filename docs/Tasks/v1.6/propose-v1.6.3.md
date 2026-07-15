# v1.6.3 Propose — AI 搜尋稽核紀錄 + UI 調整（隱藏分數、模式按鈕化）

> 本文件為 v1.6.3 的構想與討論紀錄。定稿後於 [tasks-v1.6.3.md](tasks-v1.6.3.md) 進行實作。
>
> 前置版本：[propose-v1.6.2.md](propose-v1.6.2.md)

---

## 1. 版本目標

1. **`skill_search_log` 稽核表**：記錄使用者用 AI 模式查了什麼、RAG 回傳了哪些結果與相似度（JSONB 精簡快照），供管理者 SQL 分析使用行為與內容缺口
2. **UI 隱藏相似度分數**：原始 cosine 分數（實測多落在 0.5~0.6）對使用者無解讀價值，移出 UI、轉入稽核紀錄
3. **搜尋模式切換按鈕化**：SearchModeBar 左側原生 select 改為**單一切換按鈕**——預設「關鍵字查詢」，點一下變「AI 查詢」，再點切回

### 範圍內

- **V61**：`skill_search_log`（完全比照 [V55 download_log](../../../migrations/sql/V55__create_download_log.sql) 稽核表範式：無 FK、寫入即不可變、快照欄位）
- Model / Repository：`SkillSearchLog`（獨立 base）+ `skill_search_log_repository.log()`（失敗吞掉只 warning）
- `semantic_search` 寫入稽核（含 0 命中；early-return 路徑不記）＋ 順手把 `rag_hit_count` / `rag_max_score` 帶進 AI 分析的 metered 呼叫（`llm_call_log` 既有欄位）
- 前端：兩頁移除「相似度 NN%」（徽章與理由保留，徽章改綁 `isAiResult`）；SearchModeBar select → 單一切換按鈕（「關鍵字查詢」⇄「AI 查詢」）
- API 契約不變（response 仍含 `score`，僅 UI 不顯示）

### 範圍外

- 稽核紀錄的 Admin 檢視頁（先以 SQL 查詢；有需要再開版）
- 保留期限 / 清理排程

---

## 2. `skill_search_log`（V61）

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `pid` | BIGSERIAL PK | |
| `ts` | TIMESTAMPTZ DEFAULT NOW() | 查詢時間 |
| `user_uid` | UUID NOT NULL | 查詢者（不綁 FK） |
| `username` | VARCHAR(50) NOT NULL | 查詢當下快照 |
| `query` | VARCHAR(500) NOT NULL | 搜尋字串（trim 後） |
| `scope` | VARCHAR(10) NOT NULL | visible / public |
| `hit_count` | INTEGER NOT NULL | 命中數（0 也記＝內容缺口訊號） |
| `results` | JSONB NOT NULL DEFAULT '[]' | `[{"uid","name","score"}]` 精簡快照，依分數降序 |

- 索引：`idx_skill_search_log_ts (ts DESC)`、`idx_skill_search_log_user (user_uid, ts DESC)`
- 寫入點：`semantic_search` 檢索完成後（分析理由生成前）；整段 try/except，失敗絕不影響搜尋回應
- 常用查詢範例：
  ```sql
  -- 誰查了什麼
  SELECT ts, username, query, hit_count FROM skill_search_log ORDER BY ts DESC LIMIT 50;
  -- 0 命中的查詢（內容缺口）
  SELECT query, COUNT(*) FROM skill_search_log WHERE hit_count = 0 GROUP BY query ORDER BY 2 DESC;
  -- 分數分佈
  SELECT (r->>'score')::numeric AS score FROM skill_search_log, jsonb_array_elements(results) r;
  ```

## 3. UI 調整

- `SkillRow`（兩頁）：`score` prop 移除 → `isAiResult?: boolean`（徽章condition），「相似度 NN%」span 刪除
- `SearchModeBar`：左側 `<select>` → **單一切換按鈕**：keyword 模式顯示「關鍵字查詢」（muted 樣式），點擊切至 ai 模式顯示「AI 查詢」（primary 樣式），再點切回；`aria-pressed` 標注狀態；容器版型與分隔線不變；`showModeSelect` 語意沿用（隱藏時鎖 keyword）

## 4. 部署

V61 純加表，無 outage；部署即生效，無 backfill 需求。

## 5. 驗收

- [ ] AI 模式搜尋一次 → `skill_search_log` 多一筆（含 username 快照、results JSONB 依分數降序）；0 命中也記
- [ ] `llm_call_log` 的 skill_analyze 列帶 `rag_hit_count` / `rag_max_score`
- [ ] UI 不再顯示相似度；徽章與理由正常；模式切換為單一按鈕（「關鍵字查詢」⇄「AI 查詢」）
- [ ] 搜尋主流程不受稽核寫入失敗影響；`pytest` / `tsc` 全綠
