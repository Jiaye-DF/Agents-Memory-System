# v1.6 修正記錄

> v1.6 部署驗證階段陸續發現的問題修正。

---

## 1. Worker BRPOP 在部署環境持續刷「Timeout reading from redis:6379」warning  〔2026-07-15〕

**問題**：development 部署環境的 backend log 持續出現：

```json
{"level": "WARNING", "logger": "app.workers.skill_factory_worker", "msg": "skill_factory_worker BRPOP 失敗: Timeout reading from redis:6379"}
{"level": "WARNING", "logger": "app.workers.project_memory_worker", "msg": "project_memory_worker step=brpop ... error=Timeout reading from redis:6379"}
```

四個佇列 worker（memory / project_memory / user_memory / skill_factory）皆會出現，佇列閒置時反覆觸發，log 非常吵。

**根因**：`Timeout reading` 代表「連線已建立、但讀取逾時內沒等到回應」——不是 Redis 掛掉（那會是 `Connection refused`）。repo 內 `.env` 的 `REDIS_URL` 不帶參數、`app/core/redis.py` 建 client 也未設 `socket_timeout`（預設無限等待），因此本機不會發生；但 **redis-py 的規則是 URL query 參數優先於程式碼 kwargs**，部署端（Coolify）環境變數的 `REDIS_URL` 若帶 `socket_timeout` 之類參數且小於 worker 的 `BRPOP_TIMEOUT = 5`，佇列閒置等待就會被 socket 讀取逾時提前掐斷、誤判為錯誤。功能實際不受影響（佇列有任務時 BRPOP 立即返回），純屬噪音，但掩蓋真實錯誤。

**修正**（治本，程式碼層對環境參數免疫）：

1. `app/core/redis.py` 新增 `get_blocking_redis()`：阻塞型命令（BRPOP 等）專用 client 池，建立時剝除 URL 上的 `socket_timeout` / `socket_connect_timeout` 參數，並明確設 `socket_timeout=None`（阻塞等待是常態，不設讀取逾時）、`socket_connect_timeout=5`（連線建立仍 fail-fast）、`health_check_interval=30`（閒置連線自動健檢、斷線自癒）。一般操作照舊走 `get_redis()`，尊重運維在 URL 上的設定。`close_redis()` 連同關閉兩池。
2. 四個 worker 的 BRPOP 主迴圈改用 `get_blocking_redis()`。
3. 防禦縱深：四個 worker 的 BRPOP `except` 鏈補 `except RedisTimeoutError: continue`——即使未來又有管道設出 socket timeout，閒置逾時也視同 idle 靜默續跑（與既有 `item is None` 同語意），真正的連線錯誤仍走原 warning 路徑。

**影響檔案**：

- `backend/app/core/redis.py`
- `backend/app/workers/memory_worker.py`
- `backend/app/workers/project_memory_worker.py`
- `backend/app/workers/user_memory_worker.py`
- `backend/app/workers/skill_factory_worker.py`

**驗證方式**：`python -m py_compile` 五檔通過；`pytest tests -q` 48 passed 全綠。部署後觀察佇列閒置時 log 應不再出現該 warning；實際丟任務進佇列（如觸發記憶抽取）確認消費正常。

**殘留 / 後續**：建議順手檢查 Coolify 的 `REDIS_URL` 是否帶 timeout 參數並評估是否移除（本修正已讓 worker 免疫，但該參數對其他直連使用者仍生效）；SSE 的 `pubsub.get_message(timeout=...)` 為輪詢模式且自帶容錯，暫不納入本修正範圍。
—（後補：使用者回報 Coolify 的 `REDIS_URL` 為乾淨的 `redis://redis:6379/0`，socket_timeout 假說不成立，實際觸發原因待部署後續觀察；本修正的防禦縱深（`RedisTimeoutError` idle 守門 + 專用阻塞連線）不受影響，仍能消除該噪音。）

---

## 2. skill.rag.min_score 預設 0.5 過嚴 — 單詞查詢對同名 Skill 僅 0.49，語意檢索必空  〔2026-07-15〕

**問題**：v1.6 部署後，dashboard「AI 分析」搜尋「Coolify」永遠回「找不到語意相近的 Skill」，即使該環境唯一的公開 Skill 名稱就叫「Coolify Deploy 上傳部署文件」。逐層排查：backfill 已寫入向量（DB 自比 score = 1.0）、`llm_call_log` embedding 全部成功（error NULL）、前端 `.unwrap()` 與渲染正確。

**根因**：本機以真實 OpenRouter embedding + pgvector 完整重演（建同名 public skill → 以「Coolify」單詞查詢）實測：

| 查詢 | cosine score |
| --- | --- |
| 「Coolify」（單詞） | **0.4930** |
| 「幫我把服務部署到 Coolify」（自然語句） | 0.7496 |

單詞 query 與長文檔（name + description + 檔案內容，至多 8000 字元）的 embedding 相似度天然偏低——**連名稱完全相同的單詞都只有 0.49，低於出廠預設 `skill.rag.min_score = 0.5`**，導致合理命中被門檻全數擋掉。v1.6.0 規格沿用記憶層 0.6~0.7 的直覺打了 0.5 折扣，但記憶層是「短查詢 vs 短記憶」，Skill 檢索是「短查詢 vs 長文檔」，性質不同，0.5 仍然過嚴。程式碼本身（`search_similar` 兩段式 hydrate / scope 條款 / RRF 無涉）經實測完全正確。

**修正**：

1. **V58**（`migrations/sql/V58__calibrate_skill_rag_min_score.sql`）：`skill.rag.min_score` 出廠值 `'0.5'` → `'0.35'`，僅在仍為出廠值時更新（保留人工調整）。
2. 已部署環境若管理後台已被人工改過，不受 V58 影響；建議值 0.35。

**影響檔案**：

- `migrations/sql/V58__calibrate_skill_rag_min_score.sql`

**驗證方式**：本機重現腳本（scratchpad `repro_search.py`，真 DB + 真 embedding）：`min_score=0.35` 時「Coolify」單詞命中 score=0.4930，自然語句 0.7496；`pytest tests -q` 全綠不受影響。

**殘留 / 後續**：部署環境當時「將 min_score 調成 0.2 / 0 仍空」與本機實測矛盾——高度懷疑管理後台改到同名的其他鍵（`rag.min_score` / `rag.session.min_score` 等共五個 `*min_score` 鍵），待使用者以 `SELECT key, value FROM system_setting WHERE key LIKE '%min_score%'` 確認；若該鍵確實已為 0 仍空，則為部署 image 未更新（重 deploy 即解）。日後為避免此類誤操作，可考慮管理後台設定頁為鍵名加分類分組顯示（候選 backlog，不入本版）。
