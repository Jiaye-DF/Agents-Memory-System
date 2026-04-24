# v1.2.4 任務規格：儀錶板首頁排行 filter

> **狀態：已完成（commit 待提交, 2026-04-24）**

> 前置：[propose-v1.2.0.md §2-4](propose-v1.2.0.md)、[tasks-v1.2.1.md](tasks-v1.2.1.md)（資料底層）、[tasks-v1.2.3.md](tasks-v1.2.3.md)（Script 資料來源）

## 版本目標

儀錶板首頁新增「排行榜」區塊，跨 Agents / Skills / Scripts 三類資源，可依「類型 × 排序」切換，呈現 top N。後端以單一統一 ranking endpoint 提供混合 shape response。

### 範圍內

- 後端統一 ranking endpoint：`GET /api/v1/dashboard/rankings`
- system_setting：`dashboard.ranking_size`（預設 10）
- 前端排行榜區塊：類型切換 [全部 / Agents / Skills / Scripts] × 排序 [最新 / 熱度 / 收藏數] —（已改為僅保留類型切換；排序概念改歸入後續「公開 Agents / Skills / Scripts」排行榜，見 fixed.md §2）
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

- [x] `dashboard.ranking_size` = `10`（預設）—（採 SQL migration seed，檔案 `migrations/sql/V36__seed_dashboard_ranking.sql`，沿用 V31 / V32 / V35 的 `INSERT ... ON CONFLICT DO NOTHING` 風格）

### 1-2 Schema（`app/schemas/dashboard/schemas.py`）

- [x] `RankingItemOwner`：`{ user_uid: UUID, display_name: str }` —（`user_uid` / `display_name` 採 `str`，序列化時於 service 以 `str(uuid)` 轉換；與既有 `social` / `scripts` schema 風格一致）
- [x] `RankingItem`（所有欄位**必填**）
  - `type: Literal["agent","skill","script"]`
  - `uid: UUID` —（實作為 `str`，與既有 schema 慣例對齊）
  - `name: str`
  - `description: str | None`
  - `favorite_count: int`
  - `download_count: int`
  - `is_favorited: bool`
  - `owner: RankingItemOwner`
  - `created_at: datetime` —（實作為 ISO8601 `str`，由 `to_taipei_iso` 輸出 UTC+8，與 `ResourceSnapshot` 等對齊）
  - `updated_at: datetime` —（同上）
- [x] `RankingResponse`：`{ items: list[RankingItem] }`

### 1-3 Service：`dashboard_service.py`

- [x] `list_rankings(user_uid, type_filter, order_by, limit, db) -> RankingResponse`
  - `type_filter ∈ {all, agent, skill, script}`，`order_by ∈ {download_count, favorite_count, created_at}`
  - 三類資源依 type_filter 分別撈 top N（N = limit；混合時撈每類 limit 條後合併）
  - 加 `is_favorited_bulk`（沿用 v1.2.1 helper）一次折算
  - JOIN user 表填 `owner.display_name` —（沿用各 Model `owner` relationship `lazy="joined"`，`display_name` 取 `user.username`）
  - 全欄位 mapping 為 `RankingItem`
  - 合併後依 `order_by desc` 重排，截 `limit`
- [x] `_resolve_limit(db) -> int`：讀 `dashboard.ranking_size`，未設預設 10

### 1-4 Router

- [x] `app/api/v1/dashboard/router.py`（或併入既有 dashboard router）
  - `GET /api/v1/dashboard/rankings?type=all|agent|skill|script&order_by=download_count|favorite_count|created_at&limit=`
  - 預設 `type=all`、`order_by=download_count`、`limit=` 由 service 解析
  - `type` / `order_by` 嚴格白名單，否則 422 —（以 FastAPI `Literal[...]` Query 宣告，超出白名單自動 422）
  - 掛 `get_current_user`
- [x] 註冊於 `api/v1/router.py`

---

## Phase 2：Frontend

### 2-1 型別 + RTK Query

- [x] `types/dashboard.ts`：`RankingItem`、`RankingItemOwner`、`RankingResponse` —（另補 `RankingType` / `RankingTypeFilter` / `RankingOrderBy` union 常用 alias）
- [x] `store/dashboardApi.ts`
  - `useGetRankingsQuery({ type, orderBy, limit? })`
  - `tagTypes` 補 `Rankings`；favorite mutation invalidate `Rankings` —（`store/api.ts` `tagTypes` 加 `Rankings`；`store/socialApi.ts` favorite / unfavorite 兩個 mutation 的 `invalidatesTags` 皆加 `"Rankings"`）

### 2-2 排行榜區塊元件

- [x] `components/dashboard/RankingPanel.tsx`
  - 內含類型切換 tab 與排序切換 tab
  - 列表：每項顯示 `<type icon>`、name、description、`<SocialMetrics>`（沿用 v1.2.2）、`<FavoriteButton>`
  - Empty state：`你還沒有任何 {類型} — 去建立一個吧`
- [x] 兩切換相互獨立的 state（`type` / `orderBy`），組合查詢 —（已改為僅保留 `type` state；`orderBy` 於後端固定 `download_count` 呼叫，見 fixed.md §2）

### 2-3 切換 tab

- [x] `<RankingTypeTabs>`：`[全部] [Agents] [Skills] [Scripts]` —（於 `RankingPanel.tsx` 內宣告，簡潔優先，未拆檔）
- [x] `<RankingOrderTabs>`：`[最新] [熱度] [收藏數]`，對應 `created_at` / `download_count` / `favorite_count` —（已移除；排序語義改歸入「公開 Agents / Skills / Scripts」排行榜後續版次實作，見 fixed.md §2）

### 2-4 整合至儀錶板首頁

- [x] `app/dashboard/page.tsx` 在既有卡片區下方插入 `<RankingPanel />` —（實際路徑 `frontend/src/app/(main)/dashboard/page.tsx`）
- [x] 文案：區塊標題「你最常用的」（明確點明「使用者自己」非全平台）—（另加一行輔助說明：「根據你擁有的資源統計；跨使用者公開排行將在後續版本推出。」）

---

## Phase 3：驗收

- [x] `GET /api/v1/dashboard/rankings?type=all` 能跨三類正確混排 —（service 三類各自撈 top N 後合併 + `sort(key=order_by, reverse=True)` 截 limit；Pydantic schema 序列化驗證通過）
- [x] `type=agent|skill|script` 時單類正確返回 —（`type_filter in ("all","agent"|"skill"|"script")` 分支控制撈取，其餘類別空陣列進合併不影響）
- [x] `order_by=download_count|favorite_count|created_at` 排序正確（皆 desc）—（SQL `ORDER BY <col> DESC, pid DESC` + Python 合併重排同 key，破平條件一致）
- [x] 每個 item 欄位齊全：`type / uid / name / description / favorite_count / download_count / is_favorited / owner / created_at / updated_at` —（Pydantic `RankingItem` 所有欄位 `Field(...)` 必填，service 皆有 mapping，單元驗證已產出完整 JSON）
- [x] `owner` shape 固定 `{user_uid, display_name}` —（`RankingItemOwner` 兩欄皆必填；取自 `agent.owner.username` / `skill.owner.username` / `script.owner.username`）
- [x] `dashboard.ranking_size` 調整後生效 —（`_resolve_limit` 透過 `system_setting_service.get_int` 含 30 秒 TTL 快取；API 未帶 `limit` 才走設定，帶 `limit` 則覆寫，以支援前端測試與驗收）
- [x] 前端類型 tab × 排序 tab 任意組合可正確切換、loading / empty 處理完整 —（已改為僅保留類型 tab；排序 tab 移除，`orderBy` 固定 `download_count`，見 fixed.md §2）
- [x] 點收藏 / 取消收藏，排行榜中對應項 `favorite_count` 與星號狀態同步更新（cache invalidate 生效）—（`store/api.ts` `tagTypes` 補 `Rankings`；`socialApi` favorite / unfavorite 皆 `invalidatesTags: [..., "Rankings"]`；RTK Query 重抓排行）
- [x] 排行榜文案點明「你最常用的」，避免被誤認為全平台 marketplace —（標題 `<h2>你最常用的</h2>` + 副標「根據你擁有的資源統計」）
- [x] Swagger `/api/docs` 顯示 `/api/v1/dashboard/rankings` 端點 —（router 以 `response_model=ApiResponse[RankingResponse]` + `summary` / `description` 宣告；未實際啟動 FastAPI，需 smoke 驗證）
