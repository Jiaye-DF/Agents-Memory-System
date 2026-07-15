# v1.6.3 任務規格：AI 搜尋稽核紀錄 + UI 調整

> **狀態：進行中（Phase 1-5 code 完成、pytest 55 綠 / tsc 全綠 / 本機 V61 跑通；剩部署後實測稽核寫入）**
>
> 前置：[propose-v1.6.3.md](propose-v1.6.3.md)

## 版本目標

記錄使用者的 AI 查詢行為（query / RAG 結果 / 分數，JSONB 精簡）供稽核分析；UI 隱藏無解讀價值的相似度分數；搜尋模式改單一切換按鈕（「關鍵字查詢」⇄「AI 查詢」）。API 契約不變。

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | 稽核表範式 | 完全比照 V55 download_log：無 FK、寫入不可變、獨立 base、username 快照 |
| 2 | results 形態 | JSONB `[{"uid","name","score"}]` 依分數降序（精簡） |
| 3 | 0 命中 | 也記（內容缺口訊號）；early-return（disabled / 空 query / embedding 失敗）不記 |
| 4 | 失敗策略 | 稽核寫入任何失敗只 warning，絕不影響搜尋回應 |
| 5 | 分數去向 | UI 移除；API response 保留 `score`；稽核表 + `llm_call_log.rag_*` 可查 |
| 6 | 模式切換 | 單一按鈕：預設「關鍵字查詢」（muted），點擊→「AI 查詢」（primary），再點切回 |

## Phase 1：DB Migration

- [x] `migrations/sql/V61__create_skill_search_log.sql`：表 + `idx_skill_search_log_ts (ts DESC)` + `idx_skill_search_log_user (user_uid, ts DESC)` + COMMENT（欄位見 propose §2）

## Phase 2：Model + Repository

- [x] `app/models/skill_search_log.py`：`SkillSearchLog`（獨立 base，比照 download_log.py）；`__init__.py` export
- [x] `app/repositories/skill_search_log_repository.py`：`log(payload, db)`（allowed_fields 過濾 + 吞例外，比照 download_log_repository）

## Phase 3：Service 寫入

- [x] `skill_service.semantic_search`：檢索完成後呼叫 `_record_search_log(...)`（helper 整段 try/except）：username 快照（user_repository，查無以 user_uid 充當）、query trim 截 500、results 依分數降序
- [x] AI 分析 metered 呼叫補 `rag_hit_count=len(items)`、`rag_max_score=最高分`

## Phase 4：前端

- [x] `SearchModeBar`：select → 單一切換按鈕（「關鍵字查詢」⇄「AI 查詢」，aria-pressed；showModeSelect 沿用）
- [x] 兩頁 `SkillRow`：`score` prop → `isAiResult: boolean`（徽章條件），移除「相似度 NN%」

## Phase 5：測試與驗證

- [x] `test_skill_semantic_search.py` 加：檢索成功時稽核 log 一筆（含 0 命中）、early-return 不記、稽核失敗不影響回傳
- [x] `pytest` 全綠；`tsc --noEmit` 全綠；本機 flyway V61 跑通
