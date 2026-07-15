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
