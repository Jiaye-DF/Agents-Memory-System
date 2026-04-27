# v1.3.7 任務規格：owner 欄位命名統一 + `core/access.py` 三 service 整合（純 refactor）

> **狀態：程式碼實作完成（2026-04-27 21:47），Phase 7 runtime smoke 待使用者於 dev-up 後驗證**
> 前置：[v1.3/fixed.md §7](fixed.md)、[Issue-Scan-Project-260427210223.md](../scan-project/Issue-Scan-Project-260427210223.md) 中優先 §6
> 後續依賴：（無 — v1.3 系列收尾）
> 詳細修正記錄見 [v1.3/fixed.md §10](fixed.md)

## 版本目標

掃描出 v1.0~v1.3.6 累積的兩類命名 / 共用層既存問題，本版以**純 refactor**方式收斂（不引入新功能、不改業務行為）：

1. **owner 欄位命名統一**：`Agent.owner_uid` / `Skill.owner_uid` 改為 `owner_user_uid`，與 `Script` / `ChatProject` / `ChatSession` / `ChatAttachment` / `UserFavorite` / `UserMemory` / `AgenticSkillSuggestion` 七張表對齊（v1.0 兩張表的歷史短形式統一收編）
2. **三 service `_ensure_owner` 整合**：`agent_service` / `skill_service` / `script_service` 的本地 `_ensure_owner*` helper 改用 [core/access.py](../../../backend/app/core/access.py) 的 `ensure_readable` / `ensure_modifiable` / `ensure_owner` 三段式（[v1.3/fixed.md §7 殘留 / 後續](fixed.md) 排定）

### 範圍內

- **Migration**：V51 — `agent` / `skill` 表 `RENAME COLUMN owner_uid TO owner_user_uid`；同步重命名 `idx_agent_owner_uid` / `idx_skill_owner_uid` 為 `idx_agent_owner_user_uid` / `idx_skill_owner_user_uid`；更新 column comment
- **Backend - Models**：`Agent.owner_uid` / `Skill.owner_uid` Mapped 屬性改名
- **Backend - Repositories**：`agent_repository` / `skill_repository` 查詢欄位 + 函式參數名
- **Backend - Services**：8 支 service 內 `agent.owner_uid` / `skill.owner_uid` 屬性讀取改名 + payload dict key 改名
- **Backend - Schemas**：`AgentResponse` / `SkillResponse` / `FavoriteResource`（social）內 `owner_uid` 欄位改 `owner_user_uid`
- **Backend - core/access.py**：`_OwnedVisible` Protocol 屬性名 `owner_uid` → `owner_user_uid`
- **Backend - 三 service 整合 access.py**：
  - `script_service`：本地 `_ensure_readable` / `_ensure_modifiable` / `_ensure_owner` 移除，改 import [core/access.py](../../../backend/app/core/access.py) 三 helper（命名統一後 Protocol 即可滿足 Script / Agent / Skill）
  - `skill_service`：補 `ensure_readable` / `ensure_modifiable` 到所有讀 / 改 endpoint
  - `agent_service`：同上
- **Frontend - Types**：`agents.ts` / `skills.ts` / `social.ts` 三檔 `owner_uid` 改 `owner_user_uid`
- **Frontend - 消費端**：5 支 page / component 比對 `agent.owner_uid === userUid` / `skill.owner_uid === userUid` 改名
- **API 一次性 breaking change**：response payload 由 `owner_uid` 改為 `owner_user_uid`，**不**保留舊欄位 alias（純 refactor + 同 commit 前後端，避免半遷移狀態）

### 範圍外

- 任何業務邏輯 / 端點 / 權限規則改動 — 嚴格純 refactor
- 其他不一致命名（如 `download_count` / `favorite_count` 散落於三個資源 model 沒抽 mixin）— 不在本輪
- v1.1.7 Redis 暫存退場（時間驅動）
- Skill 服務同步 IO 改 `aiofiles`
- LINE / Telegram clients 實作

---

## 影響面盤點（refactor 前完成）

### Backend（16 檔）

| 類別 | 檔案 | 動作 |
| --- | --- | --- |
| Model | [models/agent.py:16](../../../backend/app/models/agent.py) | `owner_uid` Mapped 屬性 → `owner_user_uid` |
| Model | [models/skill.py:16](../../../backend/app/models/skill.py) | 同上 |
| Repository | [repositories/agent_repository.py:39,43](../../../backend/app/repositories/agent_repository.py) | `stmt_visible_to_user` 參數名 + `Agent.owner_uid` 引用 |
| Repository | [repositories/skill_repository.py:22,26](../../../backend/app/repositories/skill_repository.py) | 同上 |
| Service | [services/agent_service.py:26,88](../../../backend/app/services/agent_service.py) | payload dict key + `agent.owner_uid` 讀取 |
| Service | [services/skill_service.py:82,223,553](../../../backend/app/services/skill_service.py) | 同上 + ownership check |
| Service | [services/chat_service.py:628](../../../backend/app/services/chat_service.py) | `agent.owner_uid` 比對 |
| Service | [services/dashboard_service.py:81,104,150,169](../../../backend/app/services/dashboard_service.py) | 排行榜 query + payload |
| Service | [services/favorite_service.py:193,208,223](../../../backend/app/services/favorite_service.py) | 三資源 normalize：`agent` / `skill` 改 `owner_user_uid`；script 已是 `owner_user_uid`（line 223）— 三者同名後可移除 normalize 內部分支 |
| Service | [services/agentic_skill_suggestion_service.py:209](../../../backend/app/services/agentic_skill_suggestion_service.py) | `target_agent.owner_uid` 比對 |
| Service | [services/skill_recommender_service.py:449](../../../backend/app/services/skill_recommender_service.py) | `agent.owner_uid` 比對 |
| Service | [services/script_service.py:80](../../../backend/app/services/script_service.py) | docstring 註解「其他資源用 `owner_uid`」改為「全站統一 `owner_user_uid`」；本地三 helper 移除改 import access.py |
| Schema | [schemas/agents/schemas.py:73](../../../backend/app/schemas/agents/schemas.py) | `AgentResponse.owner_uid` → `owner_user_uid` |
| Schema | [schemas/skills/schemas.py:52](../../../backend/app/schemas/skills/schemas.py) | `SkillResponse.owner_uid` → `owner_user_uid` |
| Schema | [schemas/social/schemas.py:23](../../../backend/app/schemas/social/schemas.py) | `FavoriteResource.owner_uid` → `owner_user_uid` + description 同步 |
| Core | [core/access.py:7,12](../../../backend/app/core/access.py) | Protocol `owner_uid` → `owner_user_uid` |

### Frontend（8 檔）

| 類別 | 檔案 | 動作 |
| --- | --- | --- |
| Type | [types/agents.ts:8](../../../frontend/src/types/agents.ts) | `owner_uid` 欄位 → `owner_user_uid` |
| Type | [types/skills.ts:3](../../../frontend/src/types/skills.ts) | 同上 |
| Type | [types/social.ts:14](../../../frontend/src/types/social.ts) | `FavoriteResource.owner_uid` → `owner_user_uid` |
| Page | [agents/page.tsx:252,490](../../../frontend/src/app/(main)/agents/page.tsx) | filter / `isOwner` |
| Page | [agents/[uid]/page.tsx:72](../../../frontend/src/app/(main)/agents/[uid]/page.tsx) | `isOwner` 比對 |
| Page | [skills/page.tsx:228,438](../../../frontend/src/app/(main)/skills/page.tsx) | filter / `isOwner` |
| Page | [skills/[uid]/page.tsx:740](../../../frontend/src/app/(main)/skills/[uid]/page.tsx) | `isOwner` 比對 |
| Component | [components/ui/AgentSelect.tsx:32](../../../frontend/src/components/ui/AgentSelect.tsx) | `isOwn` 比對 |

### Migration（不動 V5 / V7 / V11）

- 規範 [21-database.md § Migration](../../Design-Base/21-database.md) 「**禁止**修改已合併至 main 的 Migration 檔案」 — V5 / V7 / V11 一律不動
- 新建 V51：`ALTER TABLE ... RENAME COLUMN` + `ALTER INDEX ... RENAME TO` + `COMMENT ON COLUMN`
- `migrations/snapshot/V1__init.sql` 為 dev 用 schema dump（[00-overview.md § Monorepo 目錄結構](../../Design-Base/00-overview.md) 已說明屬「非版控真相」），不動

> **V 號規劃**：本任務原排 V50；後續 [V50](../../../migrations/sql/V50__add_vendor_to_llm_model.sql)（llm_model 加 vendor 欄位）由獨立工作搶用，故本任務 migration 編號**改為 V51**。實作前若再有版號被搶用，往後遞延即可。

---

## Phase 0：Migration

### 0-1 V51：agent / skill 重命名 owner_uid

- [x] 新增 [migrations/sql/V51__rename_owner_uid_to_owner_user_uid.sql](../../../migrations/sql/V51__rename_owner_uid_to_owner_user_uid.sql)：
  - `ALTER TABLE agent RENAME COLUMN owner_uid TO owner_user_uid;`
  - `ALTER TABLE skill RENAME COLUMN owner_uid TO owner_user_uid;`
  - `ALTER INDEX IF EXISTS idx_agent_owner_uid RENAME TO idx_agent_owner_user_uid;`
  - `ALTER INDEX IF EXISTS idx_skill_owner_uid RENAME TO idx_skill_owner_user_uid;`
  - `COMMENT ON COLUMN agent.owner_user_uid IS '擁有者 UID（關聯 user.user_uid）';`
  - `COMMENT ON COLUMN skill.owner_user_uid IS '擁有者 UID（關聯 user.user_uid）';`
  - **不**重命名 FK constraint（`fk_agent_user` / `fk_skill_user` 名稱不含 `owner_uid`，PostgreSQL 會自動更新 FK 對欄位的內部引用）

> **PostgreSQL 行為說明**：`ALTER TABLE ... RENAME COLUMN` 會自動更新所有內部 metadata（含 FK constraint、check constraint、index 對欄位的引用）。**不會**自動改的：index 自身的名字（需手動 ALTER INDEX RENAME）、column comment（需手動 COMMENT ON）。

---

## Phase 1：Backend Refactor

### 1-1 Models / Repositories

- [x] [models/agent.py](../../../backend/app/models/agent.py)：`owner_uid: Mapped[uuid.UUID]` → `owner_user_uid`
- [x] [models/skill.py](../../../backend/app/models/skill.py)：同上
- [x] [repositories/agent_repository.py](../../../backend/app/repositories/agent_repository.py)：`stmt_visible_to_user(owner_uid: str)` 參數名改 `user_uid`（避免與 column 同名混淆）；`Agent.owner_uid` → `Agent.owner_user_uid`
- [x] [repositories/skill_repository.py](../../../backend/app/repositories/skill_repository.py)：同上

### 1-2 core/access.py

- [x] [core/access.py:6-12](../../../backend/app/core/access.py)：`_OwnedVisible` Protocol `owner_uid: object` → `owner_user_uid: object`；`_is_owner` 內 `entity.owner_uid` → `entity.owner_user_uid`
- [x] 三 helper signature 與 docstring 不變（對外 API 一致）

### 1-3 Schemas

- [x] [schemas/agents/schemas.py:73](../../../backend/app/schemas/agents/schemas.py)：`AgentResponse.owner_uid` → `owner_user_uid`
- [x] [schemas/skills/schemas.py:52](../../../backend/app/schemas/skills/schemas.py)：同上
- [x] [schemas/social/schemas.py:23](../../../backend/app/schemas/social/schemas.py)：`FavoriteResource.owner_uid` → `owner_user_uid`；description 文字保留「資源擁有者 user_uid」即可

### 1-4 Services（屬性讀取 + payload key）

- [x] [services/agent_service.py:26,88](../../../backend/app/services/agent_service.py)：payload dict `"owner_uid"` key → `"owner_user_uid"`；`agent.owner_uid` 讀取
- [x] [services/skill_service.py:82,223](../../../backend/app/services/skill_service.py)：同上
- [x] [services/chat_service.py:628](../../../backend/app/services/chat_service.py)：`agent.owner_uid` 比對
- [x] [services/dashboard_service.py:81,104,150,169](../../../backend/app/services/dashboard_service.py)：query + payload 全改
- [x] [services/agentic_skill_suggestion_service.py:209](../../../backend/app/services/agentic_skill_suggestion_service.py)：`target_agent.owner_uid` 比對
- [x] [services/skill_recommender_service.py:449](../../../backend/app/services/skill_recommender_service.py)：`agent.owner_uid` 比對

### 1-5 favorite_service：三資源 owner key 統一

- [x] [services/favorite_service.py:193,208,223](../../../backend/app/services/favorite_service.py)：三 normalize 分支內 `"owner_uid": str(...)` 統一改為 `"owner_user_uid": str(<resource>.owner_user_uid)`
  - agent 分支：`agent.owner_uid` → `agent.owner_user_uid`（refactor 後同名）
  - skill 分支：同上
  - script 分支：`script.owner_user_uid` 已是長形式，dict key 改 `"owner_user_uid"`
- [x] **可選簡化**：三分支現在欄位完全一致，可考慮抽 helper —（範圍外，明確留下次純 refactor）

### 1-6 三 service `_ensure_owner` 整合 core/access.py

- [x] [services/script_service.py:74-128](../../../backend/app/services/script_service.py)：移除本地 `_ensure_readable` / `_ensure_modifiable` / `_ensure_owner`，改 `from app.core import access` 並使用 `access.ensure_readable(script, user_uid, role, "找不到 Script")` 等；docstring 「其他資源用 `owner_uid`」改為「全站統一 `owner_user_uid`」
- [x] [services/skill_service.py:545-...](../../../backend/app/services/skill_service.py)：移除本地 `_ensure_owner_only`；讀 / 下載 / 改 / 刪 / 切可見性對應 `access.ensure_readable` / `ensure_modifiable` / `ensure_owner`（v1.3.6 fixed.md §7 已對 Script 完成同類分權，本輪移植到 Skill）
- [x] [services/agent_service.py](../../../backend/app/services/agent_service.py)：類似補 access.py 三段式（如本檔尚未引入），保持與 Skill / Script 一致
- [x] **驗證**：[40-permission.md § 資源存取控制](../../Design-Base/40-permission.md) 四象限對照表行為**完全不變**（純 refactor，純內部結構統一）

---

## Phase 2：Frontend Refactor

### 2-1 Types

- [x] [types/agents.ts:8](../../../frontend/src/types/agents.ts)：`owner_uid: string` → `owner_user_uid: string`
- [x] [types/skills.ts:3](../../../frontend/src/types/skills.ts)：同上
- [x] [types/social.ts:14](../../../frontend/src/types/social.ts)：`FavoriteResource.owner_uid` → `owner_user_uid`

### 2-2 消費端比對

- [x] [agents/page.tsx:252,490](../../../frontend/src/app/(main)/agents/page.tsx)：`a.owner_uid` / `agent.owner_uid` → `owner_user_uid`
- [x] [agents/[uid]/page.tsx:72](../../../frontend/src/app/(main)/agents/[uid]/page.tsx)：`agent.owner_uid` → `owner_user_uid`
- [x] [skills/page.tsx:228,438](../../../frontend/src/app/(main)/skills/page.tsx)：`s.owner_uid` / `skill.owner_uid` → `owner_user_uid`
- [x] [skills/[uid]/page.tsx:740](../../../frontend/src/app/(main)/skills/[uid]/page.tsx)：`skill.owner_uid` → `owner_user_uid`
- [x] [components/ui/AgentSelect.tsx:32](../../../frontend/src/components/ui/AgentSelect.tsx)：`a.owner_uid` → `owner_user_uid`

---

## Phase 3：驗證

### 3-1 Static check

- [x] backend：`grep -rn "\.owner_uid" backend/app/` 應無命中（外部 user 表的 user_uid 不影響，本輪只動 agent / skill 模組）
- [x] backend：`grep -rn "owner_uid" backend/app/` 結果僅可能殘留於 string literal（如 commit / log 訊息）— 全數覆核
- [x] frontend：`grep -rn "owner_uid" frontend/src/` 應無命中
- [ ] migrations：V51 套用後 `\d agent` / `\d skill` 欄位應為 `owner_user_uid`，index 名 `idx_agent_owner_user_uid` / `idx_skill_owner_user_uid`

### 3-2 Runtime smoke（Phase 7 規格附帶）

- [ ] `flyway migrate` 套用 V51 後 backend 啟動無 NameError
- [ ] 登入後開啟 `/agents`、`/skills` 列表頁，個人資源 / 公開資源篩選正常
- [ ] `GET /api/v1/agents/{uid}` 回應 body 含 `owner_user_uid` 欄位（不含 `owner_uid`）
- [ ] `GET /api/v1/users/me/favorites` 回應 body 三資源 normalize 後均為 `owner_user_uid`
- [ ] `POST /api/v1/agents/{uid}/favorite` / 取消 / dashboard 排行 全部沒爆 500
- [ ] admin 與一般使用者交叉測試：admin 讀他人 agent / skill OK、改 OK、不能刪；一般使用者只能讀公開 + 自己的（[40-permission.md § 資源存取控制](../../Design-Base/40-permission.md) 四象限不變）

---

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | 統一方向 | `owner_user_uid`（長形式）— 語意精確、與其他 7 張表一致；只動 v1.0 兩張短形式 |
| 2 | API breaking change 處理 | **不**保留 `owner_uid` 舊欄位 alias；前後端同 commit 一次切；純 refactor 適合斷然處理 |
| 3 | FK constraint 是否重命名 | **不重命名**（`fk_agent_user` / `fk_skill_user` 不含 `owner_uid` 字串） |
| 4 | Index 重命名 | `idx_agent_owner_uid` / `idx_skill_owner_uid` 重命名為 `idx_*_owner_user_uid`（與欄位名對齊） |
| 5 | 三 service `_ensure_owner` 整合 | 與本版一併處理（命名統一後 Protocol 即可滿足三資源） |
| 6 | snapshot/V1__init.sql 是否更新 | **不更新**（dev schema dump、非版控真相，下次重新 dump 自然反映） |
| 7 | favorite_service normalize 抽 helper | **不抽**（純 refactor 範圍外；留待下次） |

---

## Definition of Done

- [ ] V51 migration 套用後 DB schema 欄位名 + index 名與規範一致
- [x] `grep -rn "\.owner_uid" backend/app/` 與 `grep -rn "owner_uid" frontend/src/` 皆無命中
- [ ] 全 backend `python -c "import app.main"` 正常
- [ ] frontend `npm run build` TypeScript 嚴格通過
- [x] [v1.3/fixed.md](fixed.md) 補一條 §10「owner 欄位命名統一 + access.py 整合」記錄此次純 refactor 的根因 / 修正 / 影響檔案
- [ ] [40-permission.md § 資源存取控制](../../Design-Base/40-permission.md) 四象限行為**完全未變**（runtime smoke 確認）

> 本任務**禁止**夾帶任何業務邏輯改動或新功能；發現順手要修的 bug 走獨立 fixed.md 條目，**不**併入本版 commit。
