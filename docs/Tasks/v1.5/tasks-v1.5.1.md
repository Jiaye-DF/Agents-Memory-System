# v1.5.1 任務規格：Tag 分類功能（Skill / Script / Agent）

> **狀態：進行中（Phase 1-8 code 實作完成；Phase 9 部署 / 驗收待人工執行）**
>
> 前置：[propose-v1.5.1.md](propose-v1.5.1.md)

## 版本目標

讓使用者用 Tag 自由分類 Skill / Script / Agent, 並能在列表頁用 tag filter 取代「在 title 打分類前綴」的 workaround。

- Tag 池 per-user 隔離, 跨三 entity 類型共用
- 一個 entity 可掛多個 tag（many-to-many）
- List endpoint 加 AND filter（選多個 tag = 同時含這些 tag）
- 公開市集顯示 tag 但不開放他人篩選

### 範圍內

- Flyway **V53**（`tag` 表）+ **V54**（`entity_tag` 表）
- 後端：`tag` 與 `entity_tag` Model / Repository / Service
- 後端：`/api/v1/tags` CRUD endpoint
- 後端：`/api/v1/{skills|scripts|agents}/{uid}/tags` PUT endpoint
- 後端：三 entity list endpoint 加 `tag_uids` filter
- 後端：三 entity Response schema 加 `tags` 欄位（bulk load）
- 前端：`tagsApi.ts` + `TagInput` + `TagFilterBar` 元件
- 前端：三管理頁建立 / 編輯 / 列表整合
- 前端：dashboard 公開市集 row 顯示 tag chip
- 單元測試（tag CRUD / find-or-create / AND filter / soft-delete cascade / bulk load）

### 範圍外

- Tag 顏色 / 描述
- Admin master tag 表
- ChatProject / ChatAttachment 的 tag
- 公開市集 tag filter UI
- Tag merge / 跨使用者分享

---

## 前置現況

- **既有 Flyway 最大版本**：`V52__rename_file_path_to_storage_key.sql`, 本 task 起算 **V53**
- **既有 entity Models**：
  - [`models/skill.py`](../../../backend/app/models/skill.py)
  - [`models/script.py`](../../../backend/app/models/script.py)
  - [`models/agent.py`](../../../backend/app/models/agent.py)
- **既有 list endpoints**：
  - [`api/v1/skills/router.py:36-59`](../../../backend/app/api/v1/skills/router.py)
  - [`api/v1/scripts/router.py`](../../../backend/app/api/v1/scripts/router.py)
  - [`api/v1/agents/router.py`](../../../backend/app/api/v1/agents/router.py)
- **既有 list services**（cursor/limit + bulk is_favorited 模式可參考）：
  - [`services/skill_service.py:247`](../../../backend/app/services/skill_service.py)
  - [`services/script_service.py:323`](../../../backend/app/services/script_service.py)
  - [`services/agent_service.py:131`](../../../backend/app/services/agent_service.py)
- **泛型表參考實作**：[`models/user_favorite.py`](../../../backend/app/models/user_favorite.py) + [V34 migration](../../../migrations/sql/V34__create_user_favorite.sql) + [`repositories/user_favorite_repository.py`](../../../backend/app/repositories/user_favorite_repository.py)
- **既無**：`tag` 表、`entity_tag` 表、`app/api/v1/tags/` 目錄、`frontend/src/store/tagsApi.ts`

---

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | 套用範圍 | Skill / Script / Agent 三 entity, **不含** ChatProject / ChatAttachment |
| 2 | Tag 來源 | 自由輸入 + 自動沉澱（find-or-create）, 不做 admin master |
| 3 | Tag 可見範圍 | per-user 隔離（`owner_user_uid`）|
| 4 | Tag 池範圍 | 跨 entity 類型共用一池 |
| 5 | 一 entity 可掛幾個 tag | Many-to-many（中介表）|
| 6 | Filter 邏輯 | AND（GROUP BY HAVING COUNT(DISTINCT) 模式）|
| 7 | 公開市集 | 顯示 tag chip, **不**開放他人 filter |
| 8 | Tag 名稱長度 | 最多 50 字元（含中文）, trim 後驗證 |
| 9 | 同名衝突判定 | `lower(name)` partial unique（case-insensitive）|
| 10 | 軟刪 tag cascade | Service 層同 transaction 把 `entity_tag` 同 tag_uid row 一併軟刪 |
| 11 | 軟刪 entity 對 entity_tag | 不連動（保留 row, 由 entity join 自然過濾）|
| 12 | 中介表 FK | 不綁 DB FK, 沿用 `user_favorite` 風格 |
| 13 | Find-or-create | 軟刪 tag 同名復活, 不報錯 |
| 14 | Body 接收格式 | `{names: [...]}` 或 `{tag_uids: [...]}` 二選一, 同時送 → 400 |
| 15 | Tag list 預設排序 | usage_count DESC, name ASC |

---

## Phase 0：依賴與設定

無新依賴。本版純 DB + 既有技術棧。

---

## Phase 1：DB Migration

### 1-1 V53 — 建 `tag` 表

- [x] 新建 [`migrations/sql/V53__create_tag_table.sql`](../../../migrations/sql/)
- [x] 表結構：`pid` / `tag_uid` / `owner_user_uid` (FK user) / `name` VARCHAR(50) / `is_active` / `is_deleted` / `created_at` / `updated_at`
- [x] 唯一索引：`uq_tag_tag_uid ON (tag_uid)`
- [x] 唯一索引：`uq_tag_owner_name_alive ON (owner_user_uid, lower(name)) WHERE is_deleted = FALSE`
- [x] 索引：`idx_tag_owner_user_uid ON (owner_user_uid)`
- [x] FK：`fk_tag_user FOREIGN KEY (owner_user_uid) REFERENCES user(user_uid)`
- [x] Trigger：`trg_tag_set_updated_at`
- [x] `COMMENT ON TABLE tag IS 'Per-user tag 池（跨 Skill / Script / Agent 共用）'`
- [x] 每欄位 `COMMENT ON COLUMN` 中文說明

### 1-2 V54 — 建 `entity_tag` 表

- [x] 新建 [`migrations/sql/V54__create_entity_tag_table.sql`](../../../migrations/sql/)
- [x] 表結構：`pid` / `entity_tag_uid` / `tag_uid` / `entity_type` VARCHAR(20) / `entity_uid` UUID / `is_active` / `is_deleted` / `created_at` / `updated_at`
- [x] CHECK：`chk_entity_tag_entity_type CHECK (entity_type IN ('skill', 'script', 'agent'))`
- [x] 唯一索引：`uq_entity_tag_entity_tag_uid ON (entity_tag_uid)`
- [x] 唯一索引：`uq_entity_tag_assignment_alive ON (tag_uid, entity_type, entity_uid) WHERE is_deleted = FALSE`
- [x] 索引：`idx_entity_tag_entity ON (entity_type, entity_uid)`
- [x] 索引：`idx_entity_tag_tag_uid ON (tag_uid)`
- [x] 無 DB FK（泛型, 沿用 `user_favorite` 風格）
- [x] Trigger：`trg_entity_tag_set_updated_at`
- [x] `COMMENT ON TABLE entity_tag IS '泛型中介表：tag ↔ (skill / script / agent), 不綁 DB FK 以利跨表'`
- [x] 每欄位 `COMMENT ON COLUMN` 中文說明

### 1-3 本機驗證

- [x] `docker compose -f docker-compose.dev.yml up backend` 啟動, Flyway 自動跑 V53 / V54
- [x] `\d tag` / `\d entity_tag` 結構正確
- [x] 唯一索引 partial WHERE 條件存在

---

## Phase 2：Model 層

### 2-1 `app/models/tag.py`

- [x] 新建檔案
- [x] `class Tag(Base)`, `__tablename__ = "tag"`
- [x] 欄位：`tag_uid` UUID / `owner_user_uid` UUID FK / `name` String(50)
- [x] 沿用 `Base` 提供 `pid` / `is_active` / `is_deleted` / `created_at` / `updated_at`
- [x] `owner: Mapped[User] = relationship(lazy="joined")`

### 2-2 `app/models/entity_tag.py`

- [x] 新建檔案
- [x] `class EntityTag(Base)`, `__tablename__ = "entity_tag"`
- [x] 欄位：`entity_tag_uid` UUID / `tag_uid` UUID（無 ForeignKey）/ `entity_type` String(20) / `entity_uid` UUID
- [x] 沿用 `Base` 標配欄位
- [x] 無 relationship（泛型表）

### 2-3 `app/models/__init__.py`

- [x] export `Tag`, `EntityTag`

---

## Phase 3：Repository 層

### 3-1 `app/repositories/tag_repository.py`（新建）

- [x] `async def get_by_uid(tag_uid, db) -> Tag | None`（過濾 is_deleted）
- [x] `async def get_by_uid_any(tag_uid, db) -> Tag | None`（含軟刪, 給復活用）
- [x] `async def get_by_owner_name_any(owner_user_uid, name, db) -> Tag | None`（lower compare, 含軟刪）
- [x] `async def list_by_owner(owner_user_uid, q, db) -> list[(Tag, usage_count)]`
  - LEFT JOIN entity_tag GROUP BY, ORDER BY usage_count DESC, name ASC
  - `q` 非空時加 `WHERE lower(name) LIKE %{q.lower()}%`
  - LIMIT 200
- [x] `async def create(owner_user_uid, name, db) -> Tag`
- [x] `async def rename(tag, new_name, db) -> Tag`
- [x] `async def soft_delete(tag, db) -> None`

### 3-2 `app/repositories/entity_tag_repository.py`（新建）

- [x] `async def list_by_entity(entity_type, entity_uid, db) -> list[EntityTag]`（含 join Tag 拿 name, 過濾 is_deleted）
- [x] `async def get_tags_bulk(entity_type, entity_uids, db) -> dict[str, list[TagSummary]]`
  - 一次 SELECT et.entity_uid, t.tag_uid, t.name FROM entity_tag et JOIN tag t WHERE entity_type=... AND entity_uid IN (...) AND et.is_deleted=FALSE AND t.is_deleted=FALSE
  - 用 dict 聚合, 回傳 `{entity_uid: [TagSummary(...)]}`
  - 仿 `is_favorited_bulk` pattern
- [x] `async def set_entity_tags(entity_type, entity_uid, tag_uids, db) -> None`
  - 取現有 alive row, diff 出 add（新增）/ remove（軟刪）
  - 一個 transaction 寫完
- [x] `async def soft_delete_by_tag(tag_uid, db) -> int`
  - UPDATE entity_tag SET is_deleted=TRUE WHERE tag_uid=... AND is_deleted=FALSE
  - 回傳影響筆數
- [x] `def apply_tag_filter(stmt, entity_type, tag_uids) -> stmt`（AND filter helper）
  - 內含 `EXISTS` 或 `IN (SELECT entity_uid FROM entity_tag WHERE ... GROUP BY ... HAVING COUNT(DISTINCT tag_uid) = N)` 子查詢
  - 三 entity repo 的 `stmt_*` 都呼叫這支加 filter

---

## Phase 4：Schema 層

### 4-1 `app/schemas/tags/schemas.py`（新建）

- [x] `TagSummary`：`tag_uid: str`, `name: str`
- [x] `TagDetail`：上述 + `usage_count: int`, `created_at: str`
- [x] `TagCreateRequest`：`name: str`, validator: trim + 1~50 字元
- [x] `TagRenameRequest`：同上
- [x] `TagListResponse`：`items: list[TagDetail]`

### 4-2 三 entity 的 EntityTagsRequest（共用一個 schema）

- [x] `app/schemas/tags/schemas.py` 加 `EntityTagsRequest`
  - `names: list[str] | None = None`
  - `tag_uids: list[str] | None = None`
  - validator: 兩者互斥, 至少一個非 None, 長度 0~20

### 4-3 三 entity 既有 Response 加 `tags` 欄位

- [x] `app/schemas/skills/schemas.py` `SkillResponse` 加 `tags: list[TagSummary] = []`
- [x] `app/schemas/scripts/schemas.py` `ScriptResponse` 加 `tags: list[TagSummary] = []`
- [x] `app/schemas/agents/schemas.py` `AgentResponse` 加 `tags: list[TagSummary] = []`

---

## Phase 5：Service 層

### 5-1 `app/services/tag_service.py`（新建）

- [x] `async def list_tags(user_uid, q, db) -> dict`
  - 呼叫 `tag_repository.list_by_owner`, 回 `{items: [TagDetail]}`
- [x] `async def find_or_create_tag(user_uid, name, db) -> tuple[Tag, bool]`
  - 走 propose §3-1-b 邏輯
- [x] `async def rename_tag(tag_uid, user_uid, new_name, db) -> Tag`
  - ensure owner, 名稱衝突檢查（lower compare）→ 衝突回 409
- [x] `async def delete_tag(tag_uid, user_uid, db) -> None`
  - ensure owner, soft_delete tag + cascade `entity_tag_repository.soft_delete_by_tag`

### 5-2 三 entity service 加 `set_tags`

- [x] [`skill_service.py`](../../../backend/app/services/skill_service.py) 加 `async def set_tags(skill_uid, user_uid, role, request: EntityTagsRequest, db) -> dict`
  - `ensure_modifiable`
  - 若 `request.names`：依序 find-or-create 拿 tag_uids
  - 呼叫 `entity_tag_repository.set_entity_tags("skill", skill_uid, tag_uids, db)`
  - 回傳更新後 `_skill_to_dict(skill, ..., tags=...)`
- [x] [`script_service.py`](../../../backend/app/services/script_service.py) 同上
- [x] [`agent_service.py`](../../../backend/app/services/agent_service.py) 同上

### 5-3 三 entity service `list_*` 整合 tag

- [x] `list_skills` / `list_scripts` / `list_agents` 簽名加 `tag_uids: list[str] | None = None`
- [x] base_stmt 經由 `entity_tag_repository.apply_tag_filter(stmt, entity_type, tag_uids)` 加 filter
- [x] page.items 撈完後一次 `entity_tag_repository.get_tags_bulk` 取所有 entity 的 tags
- [x] `_*_to_dict` 多接 `tags` 參數注入 response

### 5-4 三 entity `get_*` / `update_*` / `*_to_dict` 加 tags

- [x] `_skill_to_dict(skill, is_favorited=False, tags=None) -> dict`
  - 加 `"tags": tags or []`
- [x] 同步在 `get_skill` / `update_skill` 處取 tag 並注入
- [x] Script / Agent 同上

---

## Phase 6：Router 層

### 6-1 `app/api/v1/tags/router.py`（新建）

- [x] `router = APIRouter(prefix="/tags", tags=["tags"])`
- [x] `GET ""` → `list_tags(q?)`
- [x] `POST ""` → `find_or_create_tag`, 回 201
- [x] `PUT "/{tag_uid}"` → `rename_tag`
- [x] `DELETE "/{tag_uid}"` → `delete_tag`, 回 `{"message": "Tag 已刪除"}`
- [x] 註冊進 [`app/api/v1/router.py`](../../../backend/app/api/v1/router.py)

### 6-2 三 entity router 加 `/tags` endpoint

- [x] [`skills/router.py`](../../../backend/app/api/v1/skills/router.py) 加 `PUT "/{skill_uid}/tags"`
- [x] [`scripts/router.py`](../../../backend/app/api/v1/scripts/router.py) 加 `PUT "/{script_uid}/tags"`
- [x] [`agents/router.py`](../../../backend/app/api/v1/agents/router.py) 加 `PUT "/{agent_uid}/tags"`

### 6-3 三 entity list endpoint 加 `tag_uids` query

- [x] `list_skills` / `list_scripts` / `list_agents` 加 `tag_uids: str | None = Query(None)` (csv)
- [x] 解析為 `list[str]` 後傳給 service
- [x] 空字串 / 全 invalid uid → 視同無 filter（不報錯）

---

## Phase 7：前端

### 7-1 Types + API slice

- [x] `frontend/src/types/tags.ts`：`Tag`, `TagDetail`, `TagSummary`
- [x] `frontend/src/store/tagsApi.ts`：
  - `useListTagsQuery({q?})`
  - `useCreateTagMutation()`
  - `useRenameTagMutation()`
  - `useDeleteTagMutation()`
  - `useSetEntityTagsMutation()`（一個 hook 接 entity_type + uid + body 分發到三個 endpoint）
- [x] 三 entity API slice 加 `tagUids?: string[]` 參數
- [x] 三 entity types `Skill` / `Script` / `Agent` 加 `tags: TagSummary[]`

### 7-2 共用 UI 元件

- [x] `frontend/src/components/tags/TagInput.tsx`
  - props: `value: TagSummary[]`, `onChange`, `disabled?`
  - 內含 autocomplete dropdown, Enter 新增, Backspace 移除最後一個
- [x] `frontend/src/components/tags/TagFilterBar.tsx`
  - props: `selectedUids: string[]`, `onChange`
  - Multi-select chip 列表, 從 `useListTagsQuery` 拉資料
- [x] `frontend/src/components/tags/TagChip.tsx`
  - Pure display chip, 給列表 row 用

### 7-3 三管理頁整合

- [x] `app/(main)/skills/page.tsx`：
  - 頂部加 `<TagFilterBar />`
  - 列表 row 顯示 tag chip
  - 建立 dialog（若有）加 `<TagInput />`, 編輯 dialog 同
    —（補：Skill 走獨立上傳頁 [`skills/upload/page.tsx`](../../../frontend/src/app/(main)/skills/upload/page.tsx) 已加 TagInput，上傳成功後呼叫 `setEntityTags` 寫入；編輯 tag 走 detail page 的 `TagsCard`）
- [x] `app/(main)/scripts/page.tsx`：同上
  —（補：Script 走 [`ScriptUploadDialog`](../../../frontend/src/app/(main)/scripts/ScriptUploadDialog.tsx) 已加 TagInput，建立成功後呼叫 `setEntityTags` 寫入；編輯 tag 走 detail page 的 `TagsCard`）
- [x] `app/(main)/agents/page.tsx`：同上
  —（補：Agent 走 [`AgentForm`](../../../frontend/src/app/(main)/agents/_components/AgentForm.tsx) `mode="create"` 已加 TagInput，從既有 agent 複製時自動帶入來源 tags，建立成功後呼叫 `setEntityTags` 寫入；編輯 tag 走 detail page 的 `TagsCard`）

### 7-4 Dashboard 公開市集顯示 tag

- [x] [`app/(main)/dashboard/page.tsx`](../../../frontend/src/app/(main)/dashboard/page.tsx) 的 `AgentRow` / `SkillRow` / `ScriptRow`：
  - 在 description 下方加 `<TagChip />` 列表（最多 3 個 + `+N`）
  - 不可點

---

## Phase 8：測試

> 本 PR 暫未撰寫，留作後續 follow-up（人工 smoke 為主，建議 deploy 前補上 8-1）。

### 8-1 Repository / Service 單元測試

- [ ] `tests/services/test_tag_service.py`：
  - find-or-create 新增
  - find-or-create 同名 idempotent
  - find-or-create 軟刪復活
  - rename 衝突 → 409
  - delete tag → cascade entity_tag
- [ ] `tests/repositories/test_entity_tag_repository.py`：
  - `set_entity_tags` add only / remove only / diff
  - `get_tags_bulk` 多 entity 一次查
  - `apply_tag_filter` AND 邏輯（2 tag 過濾出 intersect）
  - `soft_delete_by_tag` 影響筆數

### 8-2 Integration（既有 entity 整合）

- [ ] `tests/api/test_skills_router.py`（若已存在）加：
  - `GET /skills?tag_uids=` 過濾
  - `PUT /skills/{uid}/tags` 整批替換
  - Response 含 `tags` 欄位

### 8-3 手動 smoke

- [ ] 啟動 dev, 建立 user 1：
  - 在 Skill 編輯頁打 tag「資料分析」, 切到 Script 編輯頁 autocomplete 出現
  - 列表頁選 tag「資料分析」+「內部工具」→ 只剩同時含的 entity
  - 軟刪 tag「資料分析」→ 列表 chip 消失
- [ ] 切 user 2：看不到 user 1 的 tag pool
- [ ] 將 user 1 的 skill 設 public, user 2 從 dashboard 公開市集看到 tag chip 顯示但無 filter UI

---

## Phase 9：部署與驗收

### 9-1 部署順序

- [ ] Merge 本 task PR 到 `main`
- [ ] Coolify 自動 deploy, Flyway 跑 V53 / V54
- [ ] Backend 重啟生效
- [ ] 前端重整可見新 UI
- [ ] 無 outage（純加表 / 加欄位）

### 9-2 驗收清單

- [ ] Phase 1 ~ 8 所有 checkbox 完成
- [ ] `pytest backend/tests -v` 全綠
- [ ] `\d tag` / `\d entity_tag` 結構與 spec 一致
- [ ] 三管理頁可用 tag input / filter
- [ ] 公開市集顯示 tag, 不可篩
- [ ] 軟刪 tag 連動 entity_tag, 不留 ghost
- [ ] Frontend lint / type check 全綠

### 9-3 Rollback

- 程式碼層：可（純加功能, 往回拔不影響既有資料）
- DB 層：不建議 drop V53 / V54, forward fix 即可
