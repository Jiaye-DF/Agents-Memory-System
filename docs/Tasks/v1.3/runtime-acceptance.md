# v1.3 Runtime 驗收清單

> 本檔案彙整 v1.3 系列（v1.3.0 ~ v1.3.6）所有「**程式碼層已交付、需 runtime 驗證**」的項目，按執行順序組織為可逐項勾選的清單。
>
> 程式碼層的 checkbox 已在各 `tasks-v1.3.X.md` 的 Phase 內全部 `[x]`；本檔處理的是「需要 docker / 瀏覽器 / curl 才能驗的行為」。
>
> 建議使用方式：
>
> 1. 先跑 §1「快速健康檢查」確認環境活著
> 2. 從 §2 開始按章節順序勾選
> 3. 每完成一項把 `[ ]` 改 `[x]`，遇到失敗在後方加 `—（失敗原因 / commit yyy 修）`
>
> 完成全部後可在頂部加狀態行：`> **狀態：smoke 全綠（YYYY-MM-DD）**`

---

## 1. 快速健康檢查（5 分鐘）

> AI 已掃描通過 (2026-04-26)

確認 `/dev-up` 後所有服務正常。

- [x] `docker compose -f docker-compose.dev.yml ps` 五個 container 全 `Up` / `Healthy`（flyway 應為 `Exited (0)`）
- [x] `curl -sSf -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/docs` → 200
- [x] `curl -sSf -o /dev/null -w "%{http_code}\n" http://localhost:3000` → 200
- [x] `psql ... -c "SELECT version FROM flyway_schema_history ORDER BY installed_rank DESC LIMIT 1;"` → 48
- [x] `/api/docs` 顯示以下新 endpoint group：
  - `GET /api/v1/admin/metrics/cost`（v1.3.0）
  - `GET /api/v1/admin/debug/memory/sessions/{uid}`（v1.3.1）
  - `GET /api/v1/chat/sessions/{uid}/events`（v1.3.2）
  - `POST/DELETE/PATCH /api/v1/chat/sessions/{uid}/agents/...`（v1.3.3）
  - `POST /api/v1/admin/users/{user_uid}/disable`（v1.3.5）
  - `POST /api/v1/admin/memory/aggregate/{project|user}/{uid}`（v1.3.5）
  - `GET /api/v1/admin/debug/memory/retrieve`（v1.3.5）
  - `GET /api/v1/agents/{uid}/skill-suggestions`（v1.3.6 接 v1.3.3 stub）
  - `POST /api/v1/agents/{uid}/skill-suggestions/{sid}/{accept|reject}`（v1.3.6）

---

## 2. DB Schema 與 Migration（v1.3.0 ~ v1.3.6）

> AI 已掃描通過 (2026-04-26) — 11 支 migration 全套用、表結構與 FK 規範正確

確認 V38–V48 共 11 支 migration 都套用、表結構與 FK 正確。

```bash
docker compose -f docker-compose.dev.yml exec postgres \
  psql -U agents_admin -d agents_memory
```

- [x] V38 `\d llm_call_log` — 欄位 / 索引 / COMMENT 齊全
- [x] V39 `\d session_agent` — partial unique index `uq_session_agent_primary` 存在；同 session 寫兩筆 `primary` → DB 擋
- [x] V40 `\d chat_message` — `responding_agent_uid UUID NULL` 存在；既有 assistant 訊息已自動回填
- [x] V41 `\d chat_session` — `agent_uid` 為 nullable，COMMENT 含 `[DEPRECATED v1.3.3]`
- [x] V42 `SELECT key FROM agent_template WHERE key IN ('general','long-analysis','summary');` → 3 列；max_tokens 為 2048 / 8192 / 2048
- [x] V43 `SELECT key FROM system_setting WHERE key LIKE 'classifier.%';` → 5 列（enabled / model / cheap_model / skip_response_template / thresholds）
- [x] V44 `\d project_memory` — **沒有**指向 `chat_session` 的 FK；HNSW index 建立成功
- [x] V45 `\d user_memory` — **沒有**指向 `chat_session` / `chat_project` 的 FK；HNSW index 建立成功
- [x] V46 `SELECT key FROM system_setting WHERE key LIKE 'rag.%' OR key LIKE 'memory.%';` → 三層 RAG + aggregation 設定全列
- [x] V47 `\d agentic_skill_suggestion` — `scope` CHECK 約束 / partial unique 由 signature 防重複 / status 四值 CHECK
- [x] V48 `SELECT key FROM system_setting WHERE key LIKE 'agentic.%';` → 三 scope 閾值 + recommender 開關全列

---

## 3. v1.3.0 — 成本 metrics

> 證明 LLM 呼叫都過 wrapper、`llm_call_log` 寫入正確、admin endpoint 可查。

### 3-1 核心鏈路寫 log

- [ ] 發一則 chat 訊息 → `SELECT purpose, route, model, input_tokens, output_tokens, actual_cost_usd FROM llm_call_log WHERE purpose='chat' ORDER BY ts DESC LIMIT 1;` → 一筆完整資料
- [ ] 等 ~60s（memory_worker idle 觸發）→ `... WHERE purpose IN ('memory_extract','embedding') ORDER BY ts DESC LIMIT 5;` → 多筆
- [ ] 累積 ≥ 10 筆同主題記憶觸發 skill_factory → `... WHERE purpose='skill_factory';` → 至少一筆

### 3-2 集中進入點守則

- [x] `git grep -n "from app.clients.openrouter import" backend/app/ | grep -vE "llm_metering.py|model_supports_vision|fetch_model_ids"` → **空**（所有 LLM 呼叫都過 wrapper）—（AI 驗 2026-04-26：唯一命中為 `backend/app/clients/openrouter/__init__.py:12` docstring，非實際 import，視為空）

### 3-3 Admin metrics endpoint

- [ ] `GET /api/v1/admin/metrics/cost?range=today&group_by=route` → 200，回 `{ total_actual_usd, total_baseline_usd, saved_usd, saved_pct, breakdown }`
- [ ] `GET /api/v1/admin/metrics/cost?range=7d&group_by=user` → 200
- [ ] `GET /api/v1/admin/metrics/cost?range=invalid&group_by=route` → 422（Literal 驗證）
- [ ] 無 admin token → 403

### 3-4 Known gap（不阻擋上線）

- [ ] 觀察 `extract_memory` / `describe_image` / `generate_skill_suggestion` 三個 client 的 `actual_cost_usd` 為 0（client 不回 usage，已知問題；後續精算再補）

---

## 4. v1.3.1 — 可觀察性層 1 + Skill 多 md

### 4-1 Memory Worker 結構化 log

- [ ] `docker logs agents-memory-system-backend-1 --tail=200 | grep memory_worker` → 看到 6 個 step：`enqueue` / `buffer_flush` / `prefilter` / `extract` / `embedding` / `write`，每筆含 `session_uid` / `message_uids` / `step` 結構化欄位 —（AI 驗 2026-04-26：log schema 已通過 — 看到 `step / session / outcome / duration_ms` 結構化欄位（worker idle 中只能看到 `enqueue` / `brpop`）；完整 6 step 待 §3-1 發訊息後再勾）

### 4-2 Admin trace endpoint

- [ ] 對最近一個 session 呼叫 `GET /api/v1/admin/debug/memory/sessions/{uid}` → 200，回時間軸 + 各階段成功 / 失敗 / 耗時

### 4-3 /health 擴充

- [x] `curl http://localhost:8000/api/v1/health | jq` → 含 `memory_queue_len` / `memory_dlq_len`（v1.3.5 後再加 4 個 queue depth，見 §7-7）—（AI 驗 2026-04-26：兩欄位皆存在，回 `0`）

### 4-4 Skill 多 md 拼接

- [ ] 上傳一個 zip 內含 3 個 md（如 `01-foo.md` / `02-bar.md` / `README.md`）的 Skill → 看後端 log 確認 prompt 按字典序拼出 3 段 `### {filename}` 標題
- [ ] 上傳一個單檔超過 8000 字的 md → 後端 log 出現 `logger.warning("skill md exceeds max_chars ...")`

### 4-5 AgentForm hint（v1.3.3 順手完成）

- [ ] 開啟 AgentForm `max_tokens` 欄位 → 旁邊有 hint：「1024 ≈ 750 中文字；長分析 / code review 建議 4096+ 或留空」

---

## 5. v1.3.2 — 記憶 UI 即時性 SSE

### 5-1 SSE 連線

- [ ] 開啟 session 頁面 → DevTools Network → 出現 `events` 請求，狀態 `pending`，Type 為 `eventsource`
- [ ] DevTools Network 點該請求 → EventStream tab 顯示 `event: ping` 每 15s 一次

### 5-2 即時推送

- [ ] 發訊息 → 等 < 60s → 記憶抽屜**自動**新增記憶條目（**不用**手動點 🔄）
- [ ] `docker compose exec redis redis-cli SUBSCRIBE 'chat:session:*:memory'` → memory_worker 寫完時收到 JSON payload `{"memory_uid": "..."}`

### 5-3 連線生命週期

- [ ] 切換到別頁 → DevTools Network 該 `events` 請求變 `(canceled)`（unmount 自動斷）
- [ ] 回到原頁 → 重新建連

### 5-4 Backup polling

- [ ] `docker stop agents-memory-system-backend-1` → 等 30s → DevTools Network 看到 polling refetch 觸發
- [ ] `docker start agents-memory-system-backend-1` → 自動重連 SSE，polling 停止

---

## 6. v1.3.3 — 多 Agent 對話

### 6-1 Schema 遷移驗證

- [x] `SELECT count(*) FROM session_agent WHERE role='primary';` ≈ `SELECT count(*) FROM chat_session WHERE agent_uid IS NOT NULL;`（V39 同檔遷移成功）—（AI 驗 2026-04-26：primary=1；chat_session 5 筆中 4 筆 `is_deleted=TRUE`，V39 INSERT 條件帶 `is_deleted=FALSE` 過濾後對應 1 筆，相符）
- [x] `SELECT count(*) FROM chat_message WHERE responding_agent_uid IS NOT NULL AND role='assistant';` > 0（V40 回填成功）—（AI 驗 2026-04-26：5 筆）

### 6-2 多 Agent API

- [ ] `POST /api/v1/chat/sessions` body `{"agent_uids": [a, b, c]}` → 建立成功，回 session detail 含 3 個 agents
- [ ] `POST /api/v1/chat/sessions` body `{"agent_uid": <legacy>}` → 仍可建立（向後相容）
- [ ] `POST /api/v1/chat/sessions/{uid}/agents` 加新 Agent → session_agent 表新增 row
- [ ] `DELETE /api/v1/chat/sessions/{uid}/agents/{agent_uid}` → 軟刪
- [ ] `PATCH /api/v1/chat/sessions/{uid}/agents/{agent_uid}` body `{"role": "primary"}` → 改 primary，原 primary 變 member
- [ ] `POST /api/v1/chat/sessions/{uid}/messages` 帶 `mentioned_agent_uid` 為**非該 session 成員** → 422 `agent_not_in_session`

### 6-3 Frontend 多 Agent UI

- [ ] 開啟多 Agent session → 上方 SessionAgentBar 顯示所有 Agent badge，primary 帶 ★
- [ ] 訊息卡片左上顯示「🤖 {Agent 名稱}」（v1.3.3 commit `14c3077`）
- [ ] 輸入 `@` → MentionSelector 彈出該 session 的 Agent 列表，選擇後 `mentioned_agent_uid` 帶入
- [ ] 多 Agent 提示橫幅可 ✕ 關閉，重新整理頁面後不再出現

---

## 7. v1.3.4 — 路由分類器

### 7-1 三路分流（重點驗收）

- [ ] 發 `"hi"` → assistant 回固定字串「收到，繼續～」（不等串流） → `SELECT route, model, actual_cost_usd, baseline_cost_usd FROM llm_call_log WHERE purpose='chat' ORDER BY ts DESC LIMIT 1;` → `route='skip'` / `model IS NULL` / `actual=0` / `baseline > 0`
- [ ] 發 `"請問什麼是 RAG?"`（短問答）→ `route='cheap'` / `model='anthropic/claude-haiku-4-5'`
- [ ] 發超過 60 字的長問題 → `route='expensive'` / `model=` 該 Agent 的 model

### 7-2 Multimodal 強制路由

- [ ] 上傳一張圖片 + 任意極短文字（如 `"hi"`）→ `route='expensive'` 走 vision model（**跳過** classifier 文字分流），不被誤判 skip

### 7-3 Classifier 開關

- [ ] `UPDATE system_setting SET value='false' WHERE key='classifier.enabled';` → 重啟 backend → 發 `"hi"` → 走 expensive（仍寫 log，`route='expensive'`）
- [ ] 改回 true 確認回復

### 7-4 Cost 拆桶

- [ ] `GET /api/v1/admin/metrics/cost?group_by=route` → breakdown 含 `skip` / `cheap` / `expensive` 三組

### 7-5 觀察項（≥ 1 週後再評估）

- [ ] 累積 100+ 則對話後查 `saved_pct`，預期 > 20%；若 < 20% 評估提升 cheap 命中或調整閾值
- [ ] 觀察 cheap 命中率，若 < 5% 評估升級 classifier 模型路徑（規則 → DistilBERT）

---

## 8. v1.3.5 — 三層記憶 + RRF + 生命週期硬規範

### 8-1 RRF 三層融合

- [x] `cd backend && pytest tests/services/test_rag_rrf_fuse.py -v` → 6 case 全綠（純算術測試，pgvector 環境亦可跑）—（AI 驗 2026-04-26：在 backend container 內 `python -m pytest`，6 passed in 0.98s；註：dev container base image 不含 pytest，需先 `pip install pytest`）
- [ ] 發訊息 → 後端 log 出現 `logger.info("three_layer_retrieve hits=...")` 含 session/project/user 各層筆數 + 融合後 fused 數

### 8-2 Aggregation Worker

- [ ] 累積某 project ≥ 5 筆 chat_memory + 等 6 小時 idle → project_memory_worker 觸發 → `SELECT count(*) FROM project_memory WHERE chat_project_uid=...;` > 0
- [ ] 跨 project 累積 ≥ 5 筆同主題 + 60% 占比 → user_memory_worker 觸發 → `SELECT count(*) FROM user_memory WHERE owner_user_uid=...;` > 0
- [ ] 兩 worker 的 LLM 呼叫 → `SELECT purpose, route FROM llm_call_log WHERE purpose='memory_extract' AND route IN ('project','user');` 有資料
- [ ] 抽樣兩個 worker 寫入的 `topic` 欄位確認**繁體中文**輸出（propose §2-1）

### 8-3 跨層生命週期硬規範（**最重要**，propose §3-3）

依下表逐項驗證：

| 操作 | chat_memory | project_memory | user_memory |
|------|-------------|----------------|-------------|
| Session 刪除 | 歸零 | 不動 | 不動 |
| Project 刪除 | 該 project 內歸零 | 該 project 歸零 | 不動 |
| User 停用 | 全清 | 全清 | 全清 |

- [ ] **Session 刪除**：刪一個 session → `SELECT count(*) FROM chat_memory WHERE chat_session_uid=...;` = 0；project_memory / user_memory 筆數**不變**
- [ ] **Project 刪除**：刪一個 project（含其下 sessions）→ chat_memory + project_memory 該 project 歸零；user_memory **不變**
- [ ] **User 停用**：`POST /api/v1/admin/users/{uid}/disable` → 三層全清
- [ ] **DB 直接 hard delete chat_session**：`DELETE FROM chat_session WHERE chat_session_uid='<uid>';` → `SELECT source_session_uids FROM project_memory WHERE '<uid>' = ANY(source_session_uids);` 仍有結果（FK **不** cascade，硬規範驗證）

### 8-4 Admin endpoints

- [ ] `POST /api/v1/admin/memory/aggregate/project/{uid}` → 5s 內 worker pickup（看 log）
- [ ] `POST /api/v1/admin/memory/aggregate/user/{uid}` → 同上
- [ ] `GET /api/v1/admin/debug/memory/retrieve?session_uid=...&query=...` → 回 `{session: [...], project: [...], user: [...], fused: [...]}` 完整結構
- [ ] `GET /api/v1/admin/memory/{project|user}/...` 列三層記憶可查

### 8-5 /health 擴充

- [x] `curl http://localhost:8000/api/v1/health | jq` → 4 個新 queue depth 欄位（project / user aggregate 兩 queue × queue / DLQ 各一）—（AI 驗 2026-04-26：`project_memory_queue_len` / `project_memory_dlq_len` / `user_memory_queue_len` / `user_memory_dlq_len` 四欄位齊全）

---

## 9. v1.3.6 — Skill 工廠正式版

### 9-1 三 scope analyzer

- [ ] 累積 user 跨 project ≥ 30 筆 user_memory + 同主題 50% → 觸發 user scope analyzer → `SELECT count(*) FROM agentic_skill_suggestion WHERE scope='user' AND status='pending';` > 0
- [ ] project scope（≥ 20 + 40%）/ session scope（≥ 10 + 30%）同樣驗證
- [ ] 抽樣 5 筆新 suggestion → `name` / `description` / `system_prompt` 為**繁體中文**

### 9-2 Recommender（不呼叫 LLM）

- [ ] 發訊息送達某 Agent → 若有匹配的 pending suggestion → SessionAgentBar 該 Agent 旁出現「建議 N」徽章
- [ ] 點擊徽章 → AgentSkillSuggestionsDrawer 抽屜打開，列出推薦項
- [ ] 抽屜內「接受」→ `POST /api/v1/agents/{uid}/skill-suggestions/{sid}/accept` → 200 → suggestion status → `approved`，`created_skill_uid` 寫入；該 Skill 自動掛到該 Agent
- [ ] 抽屜內「拒絕」→ status → `rejected`

### 9-3 v1.3.3 stub 已接上

- [ ] `GET /api/v1/agents/{uid}/skill-suggestions` → 不再回 `{items: [], hint: 'pending v1.3.6'}`，而是真實推薦清單

### 9-4 Frontend 列表頁

- [ ] 訪問 `/skill-suggestions` 路由 → 列出三 scope 全部 suggestion，可篩選 status
- [ ] 主導航 Sidebar 顯示「Skill 建議」入口 + pending 計數徽章

### 9-5 v1.1.7 Redis 雙讀過渡

- [ ] **2026-05-02 之後**（上線 7 天）→ 開新 commit 移除 `skill_factory_service._legacy_save_session_suggestion` / `_legacy_load_session_suggestions` 與 `list_suggestions` 的 Redis 合併段
- [ ] commit message：`(AI) Refactor: 移除 v1.1.7 PoC Redis suggestion 雙讀過渡路徑（v1.3.6 上線滿 7 天）`

---

## 10. 跨版本整合驗收

證明各版本不互相破壞。

- [ ] 多 Agent session（v1.3.3）裡用 `@AgentName` 觸發 cheap classifier（v1.3.4）→ `route='cheap'` 且 `responding_agent_uid` 正確
- [ ] 三層 RAG（v1.3.5）撈出來的記憶塞 prompt 後 → LLM 呼叫透過 wrapper（v1.3.0）→ `llm_call_log` 含正確 model + cost
- [ ] memory_worker（v1.3.1 結構化 log）→ 寫完發 SSE（v1.3.2）→ 前端記憶抽屜更新（v1.3.2 + 多層由 v1.3.5）
- [ ] Skill 推薦（v1.3.6）→ 接受後該 Skill 加入該 Agent 的 skill_uids（v1.1 既有）→ 下次對話 `_skill_prompt_text`（v1.3.1 多 md 拼接）正常拉到

---

## 11. 已知 follow-up（**不阻擋上線**）

- [ ] **v1.3.0** 的 `extract_memory` / `describe_image` / `generate_skill_suggestion` 三個 client `actual_cost_usd=0`（client 不回 usage）— 後續想精算再補
- [ ] **v1.3.4** 誤判率告警機制（需累積使用者「重問率」訊號後評估）
- [ ] **v1.3.5** 衝突合併 v0.1 先 insert（之後想加 mem0 的 add/update/delete/noop 四向決策）
- [ ] **v1.3.5** user_memory 觸發閾值 N=5 / M=60% 偏寬，視實測調整
- [ ] **v1.3.6** suggestion 過期自動清理 worker（目前 lazy 標記，未做 cron）→ 留 v1.4
- [ ] 觀察 1 個月後評估是否該加 reranker（Arch §7 階段 4）或 Hybrid search（階段 5）

---

## 12. 完成回填

全部 §1–§10 勾完後在本檔案頂部加狀態行：

```markdown
> **狀態：smoke 全綠（YYYY-MM-DD）** — v1.3 系列完整 runtime 驗收通過
```

§11 follow-up 項目持續追蹤，不影響 v1.3 收尾。
