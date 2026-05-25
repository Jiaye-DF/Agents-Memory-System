# v1.5.1 Propose — Tag 分類功能（Skill / Script / Agent）

> 本文件為 v1.5.1 的構想與討論紀錄。定稿後於 [tasks-v1.5.1.md](tasks-v1.5.1.md) 進行實作。
>
> 前置版本：[propose-v1.5.0.md](propose-v1.5.0.md)（S3 儲存切換, 與本版無資料相依）

---

## 0. 前置假設

- v1.5.0 已完成 S3 儲存切換, `storage_key` 欄位定型, 與本版無耦合
- 既有三實體（Skill / Script / Agent）皆已 per-user 隔離（`owner_user_uid`）, 既有 `user_favorite` 已示範「跨資源類型泛型表 + Partial Unique」模式可直接沿用
- 既有列表 endpoint（`/skills` / `/scripts` / `/agents`）僅支援 cursor / limit / order_by, **無**任何 filter 參數可參考, 本版為第一次引入

---

## 1. 版本目標

讓使用者用「Tag」自由分類三類 entity, 並能用 tag 在列表頁過濾, 取代「在 title 打分類前綴」的 workaround。

1. **新增 per-user tag 池**, 跨 Skill / Script / Agent 共用
   - 在 Skill 上打過的 tag, 之後在 Script / Agent 也會出現在輸入建議
2. **每個 entity 可掛多個 tag**（many-to-many）, 用泛型中介表
3. **列表頁加 tag filter**（AND 邏輯：選多個 tag = 同時含這些 tag）
4. **公開市集顯示作者的 tag**, 但不開放他人用 tag 篩選

### 範圍內

- 後端：
  - 新增 `tag` 表（per-user owned, 自由輸入沉澱池）
  - 新增 `entity_tag` 泛型中介表（沿用 `user_favorite` 的 `resource_type + resource_uid` 風格）
  - 新增 `/api/v1/tags` CRUD endpoint（list / create / rename / delete）
  - 新增 `/api/v1/{skills|scripts|agents}/{uid}/tags` PUT endpoint（整批替換綁定, 自動 find-or-create）
  - 三 entity 既有 list endpoint 加 `tag_uids` filter 參數（AND）
  - 三 entity Response schema 加 `tags: [{tag_uid, name}, ...]` 欄位（bulk load 避免 N+1）
- 前端：
  - 新增 tag 輸入元件（autocomplete + Enter 新增）
  - 三管理頁（`/skills` / `/scripts` / `/agents`）建立/編輯 dialog 加 tag 輸入區
  - 三管理頁列表頂部加 tag multi-select filter
  - 列表 row 顯示已掛 tag chip
  - 公開市集（dashboard 頁籤）顯示 tag chip（不可篩）
- DB Migration：V53（tag）+ V54（entity_tag）
- 測試：tag CRUD / find-or-create / AND filter / soft-delete cascade / bulk load

### 範圍外（延後）

- Tag 顏色 / 描述
- Admin 統一管理 tag（不做 master 表）
- ChatProject / ChatAttachment 的 tag
- 公開市集 tag filter UI（spec 僅保留 schema 可讀, UI 不開放）
- Tag merge（v1.6+ 候選, e.g.「資料分析」併入「Data Analysis」）
- Tag 跨使用者共用 / 分享

---

## 2. 資料模型

### 2-1 為什麼是兩張表（不是 entity 內嵌欄位）

| 方案 | 評估 |
| --- | --- |
| Entity 內嵌 `tags JSONB` 陣列 | 資料 denormalized, filter 寫起來醜（`@>` JSONB containment）, 改 tag 名稱要掃所有 entity row 改; 無法做 usage_count |
| 在 entity 表加 `tag_uid` 單欄 | 違反「一個 entity 多個 tag」需求 |
| **兩張表（tag + entity_tag 中介）** ✅ | 標準 many-to-many, 直接對齊既有 `user_favorite` 模式 |

### 2-2 `tag` 表（per-user 自由輸入池）

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `pid` / `is_active` / `is_deleted` / `created_at` / `updated_at` | 標配 | 沿用 Base |
| `tag_uid` | UUID, default `gen_random_uuid()` | 對外識別 |
| `owner_user_uid` | UUID NOT NULL FK → `user.user_uid` | tag 擁有者（per-user 隔離）|
| `name` | VARCHAR(50) NOT NULL | tag 顯示名稱（前端輸入時 trim, 後端 validator 再驗一次）|

- **唯一索引**：`uq_tag_owner_name_alive ON (owner_user_uid, lower(name)) WHERE is_deleted = FALSE`
  - 同一使用者下 tag 名稱不可重複, **case-insensitive**（避免「資料分析」與「資料 分析」視為同義但「Data」與「data」應視同一個）
  - 對中文無影響, 主要保護英文
- 唯一索引：`uq_tag_tag_uid ON (tag_uid)`
- 索引：`idx_tag_owner_user_uid`

### 2-3 `entity_tag` 表（泛型中介表）

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `pid` / `is_active` / `is_deleted` / `created_at` / `updated_at` | 標配 | 沿用 Base |
| `entity_tag_uid` | UUID, default `gen_random_uuid()` | 對外識別 |
| `tag_uid` | UUID NOT NULL | 邏輯外鍵 → `tag.tag_uid`（不綁 DB FK, 沿用 `user_favorite` 解耦風格）|
| `entity_type` | VARCHAR(20) NOT NULL | CHECK IN ('skill', 'script', 'agent') |
| `entity_uid` | UUID NOT NULL | 對應 `skill_uid` / `script_uid` / `agent_uid`（不綁 FK, 容忍 tombstone）|

- **唯一索引**：`uq_entity_tag_assignment_alive ON (tag_uid, entity_type, entity_uid) WHERE is_deleted = FALSE`
  - 同 tag 對同 entity 未軟刪僅一筆, 重複 PUT 走 idempotent 路徑
- 唯一索引：`uq_entity_tag_entity_tag_uid ON (entity_tag_uid)`
- 索引：`idx_entity_tag_entity ON (entity_type, entity_uid)`
  - 「這個 entity 的所有 tag」查詢 / response bulk load
- 索引：`idx_entity_tag_tag_uid ON (tag_uid)`
  - 「這個 tag 掛在哪些 entity」查詢 / filter intersect / delete tag 連動

### 2-4 為什麼 entity_tag 不綁 DB FK

沿用 [`user_favorite`](../../../migrations/sql/V34__create_user_favorite.sql) 的設計理由：

- 跨 entity 類型的泛型, 綁 FK 要靠 CHECK + 多欄位 conditional FK, 不乾淨
- 容忍 tombstone：tag 被刪除（軟刪）→ 對應 `entity_tag` row 由 service 連動軟刪, 不靠 DB cascade
- Service 層保證一致性, 對應 SQLAlchemy `relationship` 不跨 base / 不跨表

### 2-5 軟刪 cascade 策略

- **刪 tag**（`DELETE /tags/{uid}`）：
  - `tag.is_deleted = TRUE`
  - **同 transaction** 把 `entity_tag` 同 `tag_uid` 的所有 row `is_deleted = TRUE`
  - Service 層執行（不靠 DB trigger / cascade）
- **刪 entity**（既有 entity soft-delete 流程, 例 `DELETE /skills/{uid}`）：
  - 既有 `skill.is_deleted = TRUE` 流程**不改**
  - 對應 `entity_tag` row **保留**（軟刪 entity 還可能復活）, 但 list/filter 查詢經由 entity 表 join 自然過濾掉
  - 若實作偏好乾淨, 可選擇也連動軟刪 entity_tag（**先選保留**, 不增複雜度）

---

## 3. API 設計

### 3-1 Tag CRUD endpoint（新建 `app/api/v1/tags/router.py`）

| Method | Path | Body | 用途 |
| --- | --- | --- | --- |
| GET | `/api/v1/tags` | — | 列出我的 tag（含 `usage_count`）, 支援 `q={模糊搜尋}` for autocomplete |
| POST | `/api/v1/tags` | `{name}` | Find-or-create：name 已存在（含軟刪）→ 回傳並復活, 否則新增 |
| PUT | `/api/v1/tags/{tag_uid}` | `{name}` | 重新命名, 與其他 tag 衝突 → 409 |
| DELETE | `/api/v1/tags/{tag_uid}` | — | 軟刪除, 連動 `entity_tag` |

#### 3-1-a `GET /tags` Response

```json
{
  "items": [
    {"tag_uid": "...", "name": "資料分析", "usage_count": 12, "created_at": "..."},
    {"tag_uid": "...", "name": "內部工具", "usage_count": 3,  "created_at": "..."}
  ]
}
```

- 預設依 `usage_count DESC, name ASC`（高使用度 tag 優先顯示在 autocomplete）
- `usage_count` 透過 `LEFT JOIN entity_tag GROUP BY` 一次查出, 不做 N+1

#### 3-1-b `POST /tags` find-or-create 行為（重要）

避免使用者重複手動建立同名 tag：

```python
# pseudocode
existing = tag_repository.get_by_owner_name_any(user_uid, name)
if existing is None:
    return create(...)
if existing.is_deleted:
    existing.is_deleted = False
    return existing  # 復活
return existing  # idempotent
```

回傳 `{tag, created: bool}`, 由前端判斷是否顯示 toast。

### 3-2 Entity ↔ Tag 綁定 endpoint（三個 entity 各自加一條）

| Method | Path | Body | 用途 |
| --- | --- | --- | --- |
| PUT | `/api/v1/skills/{skill_uid}/tags` | `{names: [...]}` 或 `{tag_uids: [...]}` | 整批替換 entity 的 tag |
| PUT | `/api/v1/scripts/{script_uid}/tags` | 同上 | 同上 |
| PUT | `/api/v1/agents/{agent_uid}/tags` | 同上 | 同上 |

#### Body 二選一

- 推薦走 `names`：前端不用先 create tag, 直接送名稱陣列, 後端自動 find-or-create
- `tag_uids`：保留給 autocomplete 已選擇既有 tag 的場景（前端拿到 tag_uid 後直接送）
- 兩者**互斥**, 同時送 → 400

#### 行為

- Idempotent set replacement：取現有 `entity_tag` row, diff 出 add / remove, 一次 transaction 寫完
- 自動 find-or-create 任何不存在的 name
- 權限：僅 entity owner 可改（與既有 `update_skill` 等一致, 由 `ensure_modifiable` 守門）
- Response：回傳更新後完整 entity dict（含 `tags` 欄位）, 與既有 `PUT /skills/{uid}` 模式一致

### 3-3 List filter（三 entity 既有 endpoint 加參數）

| Endpoint | 新增 Query |
| --- | --- |
| GET `/api/v1/skills` | `tag_uids` (csv, AND) |
| GET `/api/v1/scripts` | 同上 |
| GET `/api/v1/agents` | 同上 |

#### AND filter 實作

```sql
-- AND（同時含所有 tag）
SELECT s.*
FROM skill s
WHERE s.is_deleted = FALSE
  AND s.pid IN (
    SELECT et.entity_uid_pid  -- 概念性, 實際走 JOIN 或 EXISTS
    FROM entity_tag et
    WHERE et.entity_type = 'skill'
      AND et.tag_uid IN (<tag_uids>)
      AND et.is_deleted = FALSE
    GROUP BY et.entity_uid
    HAVING COUNT(DISTINCT et.tag_uid) = <len(tag_uids)>
  )
```

實作上 repository 提供 `apply_tag_filter(stmt, entity_type, tag_uids) -> stmt` helper, 給三 entity 各自的 `stmt_visible_to_user` / `stmt_owned_by_user` 加 filter, 不複製 SQL。

#### 公開市集

- `/scripts/public` 等公開 endpoint：**不接受** `tag_uids` filter（v1.5.1 範圍外）
- 但仍會在 response 回傳 `tags` 欄位（顯示用）

### 3-4 三 entity Response 加 `tags` 欄位

| Schema | 既有 | 新增欄位 |
| --- | --- | --- |
| `SkillResponse` | favorite_count / is_favorited / ... | `tags: list[TagSummary]` |
| `ScriptResponse` | 同上 | 同上 |
| `AgentResponse` | 同上 | 同上 |

```python
class TagSummary(BaseModel):
    tag_uid: str
    name: str
```

Bulk load 模式仿 `is_favorited_bulk`：

```python
# repository
async def get_tags_bulk(
    entity_type: str,
    entity_uids: list[str],
    db: AsyncSession,
) -> dict[str, list[TagSummary]]:
    """回傳 entity_uid → [TagSummary] 對應表, 避免 N+1。"""
```

Service 層 list endpoint 撈完 page.items 後一次 bulk load tag。

---

## 4. 前端設計

### 4-1 共用 tag 輸入元件 `components/tags/TagInput.tsx`

- Input + 已選 chip 顯示
- 輸入時打 `GET /tags?q={input}` 模糊搜尋, 顯示下拉建議（含 usage_count）
- Enter / 點建議：加入已選 chip
- Backspace（input 為空時）：移除最後一個 chip
- Submit 時用 `names: [...]` 一次送出, 由後端 find-or-create

### 4-2 TagFilterBar `components/tags/TagFilterBar.tsx`

- 列表頁頂部 multi-select chip bar
- 顯示「我擁有的 tag」（呼叫 `GET /tags`）
- 點 chip 切換選取, AND filter
- URL state（query string `?tags=uid1,uid2`）以便重整保留

### 4-3 RTK Query API slice `store/tagsApi.ts`

| Hook | 對應 endpoint |
| --- | --- |
| `useListTagsQuery({q?})` | GET /tags |
| `useCreateTagMutation()` | POST /tags |
| `useRenameTagMutation()` | PUT /tags/{uid} |
| `useDeleteTagMutation()` | DELETE /tags/{uid} |
| `useSetEntityTagsMutation()` | PUT /{entity}/{uid}/tags（依 entity_type 分發）|

並在 `skillsApi.ts` / `scriptsApi.ts` / `agentsApi.ts` 的 `useList*Query` 加 `tagUids?: string[]` 參數。

### 4-4 三管理頁整合

- `/skills`、`/scripts`、`/agents` 列表頁：
  - 頂部加 `<TagFilterBar />`
  - 建立 / 編輯 dialog 加 `<TagInput />`
  - Row 顯示 tag chip（最多 3 個 + `+N`）
- `/dashboard`（公開市集）三頁籤的 row：
  - 加 tag chip 顯示（最多 3 個 + `+N`, 不可點）
  - **不**加 TagFilterBar

---

## 5. Migration / 部署

### 5-1 Migration 順序

| 版本 | 內容 |
| --- | --- |
| V53 | `CREATE TABLE tag` + 索引 + COMMENT + trigger |
| V54 | `CREATE TABLE entity_tag` + 索引 + COMMENT + trigger |

無資料 backfill（新功能, 初始為空）, 部署完成即可使用。

### 5-2 部署順序

1. Merge PR → Coolify deploy
2. Flyway 自動跑 V53 / V54
3. Backend 重啟生效
4. 前端 dashboard 重整即可看到新 UI

**無 outage window**（純加表 + 加欄位, 既有資料不動）。

### 5-3 Rollback

- 程式碼層 rollback：可（新 endpoint 與 schema 欄位往回拔, 不影響既有資料）
- DB rollback：不建議, V53 / V54 為單向, 真要 rollback 寫新 V55 drop（不會發生, 因新功能無 user 依賴）

---

## 6. 風險與決策

| # | 風險 | 應對 |
| --- | --- | --- |
| 1 | Tag 數量爆量導致 autocomplete 慢 | `GET /tags` 預設依 usage_count DESC, 前端只顯示 top 20; 後端 query 加 `LIMIT 200` |
| 2 | 同名 tag 大小寫衝突誤判 | `lower(name)` partial unique, 但允許首字母大寫存原樣顯示（DB 存原 name, 比對用 lower）|
| 3 | 中文 trim 後 unicode 不同形（NFC/NFD）視為不同 tag | v1.5.1 不處理, 列為已知限制（前端 input 不會主動 normalize, 中文使用者實務上不會碰到）|
| 4 | AND filter 多 tag 時 SQL 不夠快 | v1.5.1 不做指標監控, 假設 per-user tag < 100, 自然不慢; v1.6+ 視實況加 explain |
| 5 | 公開 entity 的 tag 被作者刪除後顯示空白 | tag 軟刪後 entity_tag 連動軟刪, response join 自然消失, 不會顯示 ghost tag |

---

## 7. 驗收標準

- [ ] V53 / V54 跑通, `\d tag` / `\d entity_tag` 可見
- [ ] 我可以在 skill 編輯頁打 tag「資料分析」, 切到 script 編輯頁 autocomplete 就出現
- [ ] 公開市集顯示作者的 tag chip, 我這邊不能用它篩
- [ ] 列表頁選 tag A + B → 只剩同時含 A 與 B 的 entity
- [ ] 軟刪 tag A → 列表頁不再出現 tag A, 既有掛 A 的 entity 不再顯示 A
- [ ] `pytest backend/tests -v` 全綠
