# v1.2.1 任務規格：收藏 / 下載計數 + user_favorite + API（最底層）

> 前置：[propose-v1.2.0.md §2-1](propose-v1.2.0.md)
> 後續依賴：v1.2.2 / v1.2.3 / v1.2.4 皆需此版完成才能開工

## 版本目標

建立社群互動統計的資料底層與 API：

- `agent` / `skill` 表加 `favorite_count` / `download_count` 欄位
- 新增 `user_favorite` 表（泛型 `resource_type` + `resource_uid`，不綁 DB FK）
- 收藏 / 取消收藏 API、下載計數原子遞增、列表 API 擴 `order_by` 與 `is_favorited`
- 引入 Redis 做下載 dedup（24h TTL）

### 範圍內

- DB Migration：V33（agent / skill 加欄位）、V34（user_favorite 表）
- Redis 服務與後端 client 封裝（docker-compose + env + 連線池）
- 收藏 / 取消收藏 / 我的收藏列表 API
- Agent / Skill 列表 API 加 `order_by` / `is_favorited`
- Skill 既有 `/download` handler 加 `download_count += 1` + Redis dedup
- Tombstone 行為（被刪除資源在「我的收藏」回傳 `resource = null` + `tombstone_reason`）

### 範圍外

- `script` 表（→ v1.2.3 §A-1，V35 在那邊建立）
- 前端管理頁的收藏按鈕 / filter nav（→ v1.2.2）
- 儀錶板排行 API（→ v1.2.4）

---

## 前置現況

- v1.1 / v1.1 延伸：Agents / Skills 管理已具備、Skill zip 下載 API 既有
- 既有技術棧**未部署 Redis** — 本版需補 compose 服務與 client 封裝
- `app/models/base.py` 提供 `is_active` / `is_deleted` / `created_at` / `updated_at` 共用欄位

---

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | 計數儲存策略 | denormalized 欄位 + 寫入時即時更新；同 transaction 內 `UPDATE ... SET count = count +/- 1` |
| 2 | 並發保護 | 依賴 Postgres row-level lock，不做應用層快取 |
| 3 | `user_favorite` 對目標表 FK | **不綁** DB FK，泛型 `resource_type` + `resource_uid` |
| 4 | 被刪除資源行為 | 收藏紀錄保留，前端顯示 tombstone 卡片，使用者自行清除 |
| 5 | 下載計數時機 | `StreamingResponse` 即將回傳前才 +1（HEAD / 預覽不計） |
| 6 | 下載 dedup | Redis `download:dedup:{resource_uid}:{user_uid}` TTL 24h |
| 7 | Agent 的 `download_count` | v1.2 內恆為 0（保留欄位，前端可隱藏），未來 export / import 用 |

---

## Phase 0：基礎設施

### 0-1 Redis 服務

- [ ] `docker-compose.yml` 新增 `redis:7-alpine` 服務（暴露 6379，掛 named volume）
- [ ] `.env.example` 新增 `REDIS_HOST` / `REDIS_PORT` / `REDIS_DB`
- [ ] `.env` 同步補上對應值
- [ ] 後端依賴 `redis>=5` 加入 `pyproject.toml` / `requirements.txt`

### 0-2 Redis Client 封裝

- [ ] `app/clients/redis_client.py`：建立 `get_redis()` 依賴注入；連線池 + lifespan 啟動關閉
- [ ] `app/main.py` lifespan 補上 redis ping check
- [ ] 失敗策略：Redis 不通時下載 dedup 退化為「直接 +1，不去重」（log warning）

---

## Phase 1：Backend — Migration

### 1-1 V33：agent / skill 加計數欄位

- [ ] `V33__add_social_counters.sql`
  - `ALTER TABLE agent ADD COLUMN favorite_count INT NOT NULL DEFAULT 0`
  - `ALTER TABLE agent ADD COLUMN download_count INT NOT NULL DEFAULT 0`
  - `ALTER TABLE skill ADD COLUMN favorite_count INT NOT NULL DEFAULT 0`
  - `ALTER TABLE skill ADD COLUMN download_count INT NOT NULL DEFAULT 0`
  - `CREATE INDEX idx_agent_favorite_count ON agent(favorite_count DESC)`
  - `CREATE INDEX idx_agent_download_count ON agent(download_count DESC)`
  - `CREATE INDEX idx_skill_favorite_count ON skill(favorite_count DESC)`
  - `CREATE INDEX idx_skill_download_count ON skill(download_count DESC)`
  - `COMMENT ON COLUMN` 全部新欄位

### 1-2 V34：user_favorite 表

- [ ] `V34__create_user_favorite.sql`
  - `pid bigserial PK`、`user_favorite_uid uuid default gen_random_uuid() UNIQUE`
  - `owner_user_uid uuid NOT NULL`（**不綁 FK**，跨表泛型）
  - `resource_type varchar(20) NOT NULL CHECK (resource_type IN ('agent','skill','script'))`
  - `resource_uid uuid NOT NULL`（**不綁 FK**，泛型 + 容忍刪除）
  - `is_active`、`is_deleted`、`created_at`、`updated_at` + Trigger
  - Partial Unique：`UNIQUE (owner_user_uid, resource_type, resource_uid) WHERE is_deleted = FALSE`
  - Index：`idx_user_favorite_owner_type ON (owner_user_uid, resource_type)`
  - `COMMENT ON COLUMN` 全部欄位

---

## Phase 2：Backend — Model / Schema / Repository

### 2-1 Model

- [ ] `app/models/agent.py` 加 `favorite_count` / `download_count`
- [ ] `app/models/skill.py` 加 `favorite_count` / `download_count`
- [ ] `app/models/user_favorite.py`：`UserFavorite`（繼承 `Base`）

### 2-2 Schema（`app/schemas/social/schemas.py`）

- [ ] `FavoriteToggleResponse`：`{ favorited: bool, favorite_count: int }`
- [ ] `MyFavoriteItem`：`{ user_favorite_uid, resource_type, resource_uid, resource: <ResourceSnapshot|null>, tombstone_reason: str|null, created_at }`
- [ ] `MyFavoritesResponse`：`{ items: list[MyFavoriteItem], page, size, total }`
- [ ] 既有 `AgentResponse` / `SkillResponse` 加欄位：`favorite_count`、`download_count`、`is_favorited`

### 2-3 Repository

- [ ] `user_favorite_repository.py`
  - `add(owner_user_uid, resource_type, resource_uid)`：UPSERT（若存在但 `is_deleted=true` 則復活）
  - `remove(owner_user_uid, resource_type, resource_uid)`：軟刪
  - `list_by_owner(owner_user_uid, resource_type=None, page, size)`
  - `is_favorited_bulk(owner_user_uid, resource_type, resource_uids: list) -> set[uid]`（給列表 API 用）
- [ ] `agent_repository.py` / `skill_repository.py` 既有 `list_by_owner` 擴 `order_by` 參數
  - 白名單：`download_count` / `favorite_count` / `created_at` / `updated_at`
  - 預設 `created_at desc`

---

## Phase 3：Backend — Service

### 3-1 favorite_service.py

- [ ] `add_favorite(user_uid, resource_type, resource_uid, db)`
  - 同 transaction：`user_favorite` 寫入 + 對應表 `favorite_count += 1`
  - 若已收藏則 idempotent 回 200（不重複加計數）
- [ ] `remove_favorite(user_uid, resource_type, resource_uid, db)`
  - 同 transaction：`user_favorite` 軟刪 + 對應表 `favorite_count -= 1`
  - 若未收藏則 idempotent 回 200（不重複扣計數）
- [ ] `list_my_favorites(user_uid, resource_type, page, size, db)`
  - LEFT JOIN 目標表，`is_deleted=true` 或不存在則 `resource=null` + `tombstone_reason="resource_removed"`
- [ ] `_dispatch_count_update(resource_type, resource_uid, delta, db)`：依 `resource_type` 路由到對應表 UPDATE

### 3-2 列表 API 的 is_favorited 折算

- [ ] `agent_service.list_agents` / `skill_service.list_skills` 在組 response 前
  - `is_favorited_bulk(current_user, type, uids)` 一次撈
  - 每個 item 折成 bool 寫入 `is_favorited`

### 3-3 download_service（共用）

- [ ] `app/services/download_service.py` 新增 `try_increment_download(resource_type, resource_uid, user_uid, db) -> bool`
  - Redis SETNX `download:dedup:{type}:{uid}:{user_uid}` TTL 86400
  - 若 SETNX 成功（首次），同 transaction `UPDATE ... SET download_count = download_count + 1`，回 True
  - 若 Redis 不通：log warning，仍執行 +1（fallback 不去重）
- [ ] `skill_service` 既有 download handler 在 StreamingResponse 回傳前呼叫 `try_increment_download`

---

## Phase 4：Backend — Router

### 4-1 收藏 API

- [ ] `app/api/v1/social/router.py` 新增（或併入既有合適 router）
  - `POST /api/v1/{agents|skills}/{uid}/favorite` → `add_favorite`
  - `DELETE /api/v1/{agents|skills}/{uid}/favorite` → `remove_favorite`
  - `GET /api/v1/users/me/favorites?type=agent|skill&page=&size=` → `list_my_favorites`
  - 注意：path 中的 `{agents|skills}` 對應 `resource_type`；`scripts` 路徑由 v1.2.3 補
- [ ] 全部端點掛 `get_current_user`
- [ ] `api/v1/router.py` 註冊 social router

### 4-2 既有列表 API 擴參

- [ ] `GET /api/v1/agents` 加 `order_by` 與 `order` 參數（白名單見 §2-3）
- [ ] `GET /api/v1/skills` 加 `order_by` 與 `order` 參數
- [ ] response 補 `favorite_count` / `download_count` / `is_favorited`

---

## Phase 5：驗收

- [ ] V33 / V34 套用後，欄位與表結構正確、COMMENT 齊全
- [ ] Redis 容器於 docker-compose 啟動正常，後端 ping 通
- [ ] `POST /favorite` 第二次呼叫不會重複 +1（idempotent）
- [ ] `DELETE /favorite` 對未收藏項回 200，`favorite_count` 不變為負
- [ ] 同 user 24h 內重複下載同一 Skill，`download_count` 只 +1
- [ ] Redis 暫時離線時，下載仍能完成（fallback 直接 +1）
- [ ] `GET /api/v1/agents` / `/skills` response 每項含 `is_favorited`，未登入 / 未收藏為 `false`
- [ ] `GET /users/me/favorites` 對已被刪除的 resource 回傳 `resource=null` + `tombstone_reason="resource_removed"`
- [ ] `order_by=download_count&order=desc` 查詢結果正確排序
- [ ] Swagger `/api/docs` 顯示所有新增端點與欄位
