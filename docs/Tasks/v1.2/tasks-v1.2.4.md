# v1.2.4 任務規格：儀錶板首頁排行 filter

> 前置：[propose-v1.2.0.md §2-4](propose-v1.2.0.md)、[tasks-v1.2.1.md](tasks-v1.2.1.md)（資料底層）、[tasks-v1.2.3.md](tasks-v1.2.3.md)（Script 資料來源）

## 版本目標

儀錶板首頁新增「排行榜」區塊，跨 Agents / Skills / Scripts 三類資源，可依「類型 × 排序」切換，呈現 top N。後端以單一統一 ranking endpoint 提供混合 shape response。

### 範圍內

- 後端統一 ranking endpoint：`GET /api/v1/dashboard/rankings`
- system_setting：`dashboard.ranking_size`（預設 10）
- 前端排行榜區塊：類型切換 [全部 / Agents / Skills / Scripts] × 排序 [最新 / 熱度 / 收藏數]
- Mixed-shape item response（含 `is_favorited` 與 `owner` 物件）

### 範圍外

- 「本週熱門」/「本月熱門」時效窗排行（v1.2 僅 all-time，未來觀察後再加）
- AI 語意查詢（→ v1.4）
- 跨使用者公開可見的 marketplace ranking（→ v1.4）

---

## 前置現況

- v1.2.1 已備：`favorite_count` / `download_count` denormalized 欄位、`is_favorited` 折算
- v1.2.3 已備：`script` 表存在
- 既有儀錶板首頁為靜態卡片，無排行
- `system_setting_service` 既有

---

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | API 形態 | 單一 endpoint 跨三類資源，混合 shape response |
| 2 | 權限範圍 | 本版僅顯示「使用者擁有的資源」（公開可見性留 v1.4），UI 文案「你最常用的」 |
| 3 | 聚合策略 | 三類各自 query top N → 合併 → 依 `order_by` 重排 → 截 limit |
| 4 | top N 預設 | 10，可由 `dashboard.ranking_size` 調整 |
| 5 | Agent `download_count` | 恆為 0，UI 排序選 `download_count` 時 Agent 排尾 |
| 6 | Response 欄位完整性 | 所有欄位**必填**不可省略（`owner` shape 固定 `{user_uid, display_name}`） |

---

## Phase 1：Backend

### 1-1 Seed system_setting

- [ ] `dashboard.ranking_size` = `10`（預設）

### 1-2 Schema（`app/schemas/dashboard/schemas.py`）

- [ ] `RankingItemOwner`：`{ user_uid: UUID, display_name: str }`
- [ ] `RankingItem`（所有欄位**必填**）
  - `type: Literal["agent","skill","script"]`
  - `uid: UUID`
  - `name: str`
  - `description: str | None`
  - `favorite_count: int`
  - `download_count: int`
  - `is_favorited: bool`
  - `owner: RankingItemOwner`
  - `created_at: datetime`
  - `updated_at: datetime`
- [ ] `RankingResponse`：`{ items: list[RankingItem] }`

### 1-3 Service：`dashboard_service.py`

- [ ] `list_rankings(user_uid, type_filter, order_by, limit, db) -> RankingResponse`
  - `type_filter ∈ {all, agent, skill, script}`，`order_by ∈ {download_count, favorite_count, created_at}`
  - 三類資源依 type_filter 分別撈 top N（N = limit；混合時撈每類 limit 條後合併）
  - 加 `is_favorited_bulk`（沿用 v1.2.1 helper）一次折算
  - JOIN user 表填 `owner.display_name`
  - 全欄位 mapping 為 `RankingItem`
  - 合併後依 `order_by desc` 重排，截 `limit`
- [ ] `_resolve_limit(db) -> int`：讀 `dashboard.ranking_size`，未設預設 10

### 1-4 Router

- [ ] `app/api/v1/dashboard/router.py`（或併入既有 dashboard router）
  - `GET /api/v1/dashboard/rankings?type=all|agent|skill|script&order_by=download_count|favorite_count|created_at&limit=`
  - 預設 `type=all`、`order_by=download_count`、`limit=` 由 service 解析
  - `type` / `order_by` 嚴格白名單，否則 422
  - 掛 `get_current_user`
- [ ] 註冊於 `api/v1/router.py`

---

## Phase 2：Frontend

### 2-1 型別 + RTK Query

- [ ] `types/dashboard.ts`：`RankingItem`、`RankingItemOwner`、`RankingResponse`
- [ ] `store/dashboardApi.ts`
  - `useGetRankingsQuery({ type, orderBy, limit? })`
  - `tagTypes` 補 `Rankings`；favorite mutation invalidate `Rankings`

### 2-2 排行榜區塊元件

- [ ] `components/dashboard/RankingPanel.tsx`
  - 內含類型切換 tab 與排序切換 tab
  - 列表：每項顯示 `<type icon>`、name、description、`<SocialMetrics>`（沿用 v1.2.2）、`<FavoriteButton>`
  - Empty state：`你還沒有任何 {類型} — 去建立一個吧`
- [ ] 兩切換相互獨立的 state（`type` / `orderBy`），組合查詢

### 2-3 切換 tab

- [ ] `<RankingTypeTabs>`：`[全部] [Agents] [Skills] [Scripts]`
- [ ] `<RankingOrderTabs>`：`[最新] [熱度] [收藏數]`，對應 `created_at` / `download_count` / `favorite_count`

### 2-4 整合至儀錶板首頁

- [ ] `app/dashboard/page.tsx` 在既有卡片區下方插入 `<RankingPanel />`
- [ ] 文案：區塊標題「你最常用的」（明確點明「使用者自己」非全平台）

---

## Phase 3：驗收

- [ ] `GET /api/v1/dashboard/rankings?type=all` 能跨三類正確混排
- [ ] `type=agent|skill|script` 時單類正確返回
- [ ] `order_by=download_count|favorite_count|created_at` 排序正確（皆 desc）
- [ ] 每個 item 欄位齊全：`type / uid / name / description / favorite_count / download_count / is_favorited / owner / created_at / updated_at`
- [ ] `owner` shape 固定 `{user_uid, display_name}`
- [ ] `dashboard.ranking_size` 調整後生效
- [ ] 前端類型 tab × 排序 tab 任意組合可正確切換、loading / empty 處理完整
- [ ] 點收藏 / 取消收藏，排行榜中對應項 `favorite_count` 與星號狀態同步更新（cache invalidate 生效）
- [ ] 排行榜文案點明「你最常用的」，避免被誤認為全平台 marketplace
- [ ] Swagger `/api/docs` 顯示 `/api/v1/dashboard/rankings` 端點
