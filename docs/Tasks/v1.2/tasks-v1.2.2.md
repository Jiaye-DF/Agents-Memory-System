# v1.2.2 任務規格：管理頁三段式 filter + 收藏按鈕

> **狀態：已完成（commit 待提交, 2026-04-24）**

> 前置：[propose-v1.2.0.md §2-2](propose-v1.2.0.md)、[tasks-v1.2.1.md](tasks-v1.2.1.md)（API 與資料底層）

## 版本目標

讓使用者在 Agents / Skills 管理頁能切換「全部 / 我的 / 我的收藏」、看見每筆資源的 `⭐ favorite_count` `⬇ download_count`、可一鍵收藏與取消。建立可被 v1.2.3 Scripts 頁重用的 filter nav pattern 與收藏按鈕元件。

### 範圍內

- 共用元件：`<FilterNav>` 三段式 tab、`<FavoriteButton>` toggle、`<SocialMetrics>` 顯示 ⭐/⬇
- Agents / Skills 管理頁套用三段式 filter
- 卡片 / 列表項顯示 ⭐ + ⬇ + 收藏按鈕
- 「我的收藏」分頁能正確列出，並對 tombstone 項顯示「已被移除」卡片 + 移除收藏按鈕

### 範圍外

- Scripts 管理頁（→ v1.2.3，沿用本版定義的 pattern）
- 儀錶板首頁排行（→ v1.2.4）
- 跨使用者公開可見性（→ v1.4）

---

## 前置現況

- v1.2.1 已提供：`favorite` / `unfavorite` API、`/users/me/favorites`、列表 API `is_favorited` 欄位、`order_by` 參數
- 既有 Agents / Skills 管理頁為單一列表（無 filter tab）
- RTK Query 已有 `agentsApi` / `skillsApi`

---

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | filter 三段語意 | 全部 = 我的 + 公開可見（v1.2 暫等同「我的」）；我的 = `owner = me`；我的收藏 = join `user_favorite` |
| 2 | 收藏按鈕視覺 | 未收藏空心星 / 已收藏實心星；toggle 一次 |
| 3 | 樂觀更新 | 點擊立即更新 UI 與計數，API 失敗則回滾 + toast 提示 |
| 4 | tombstone 卡片 | 灰底 + ⚠ icon + 「此 {Agent | Skill} 已被移除」+「從收藏移除」按鈕 |
| 5 | filter / 排序組合 | filter 是 query string、排序由 v1.2.4 上排行 filter；管理頁本版只做 filter，不做排序切換（保留預設 `created_at desc`） |

---

## Phase 1：型別 + RTK Query

### 1-1 型別擴充（`types/`）

- [x] `Agent` / `Skill` 加 `favorite_count: number` / `download_count: number` / `is_favorited: boolean`
- [x] 新增 `MyFavoriteItem`：`{ user_favorite_uid, resource_type, resource_uid, resource: <Agent|Skill|null>, tombstone_reason: string|null, created_at }` —（已改為 `resource: ResourceSnapshot | null`，與 v1.2.1 後端 `schemas/social/schemas.py` 對齊；`ResourceSnapshot` 欄位為 `uid/name/description/owner_uid/owner_username/visibility/favorite_count/download_count/created_at/updated_at`，非完整 Agent/Skill 以避免引入 role_prompt / skills 等大型 schema）
- [x] 新增 `FilterScope = 'all' | 'mine' | 'favorites'`

### 1-2 RTK Query

- [x] `agentsApi.useListAgentsQuery({ scope, page, size })`：`scope='favorites'` 時改打 `/users/me/favorites?type=agent` —（已改為：`listAgents` 保持原 shape 回 `PaginatedData<Agent>`；新增 `socialApi.useListMyFavoritesQuery({type:'agent'})` 回 `MyFavoritesResponse`，頁面依 `scope` 擇一呼叫。兩者 cache 獨立，避免型別衝突）
- [x] `skillsApi.useListSkillsQuery({ scope, page, size })`：同上 `type=skill` —（同上策略）
- [x] 新增 `socialApi`
  - `useFavoriteResourceMutation({ resourceType, resourceUid })`
  - `useUnfavoriteResourceMutation({ resourceType, resourceUid })`
  - 兩者帶**樂觀更新**：`onQueryStarted` 走 `selectInvalidatedBy(['Agents'|'Skills'])` 找出所有 list cache entries + `getAgent/getSkill` 單筆 cache，統一 `updateQueryData` patch `is_favorited` / `favorite_count`，失敗 `undo()`
- [x] `tagTypes` 補 `Favorites`；favorite mutation 觸發 invalidate `Favorites`

---

## Phase 2：共用元件

### 2-1 `<FilterNav>`

- [x] `components/social/FilterNav.tsx`
  - props：`value: FilterScope`、`onChange(scope)`、`labels?: Partial<Record<FilterScope,string>>`
  - 三段 tab：`全部` / `我的` / `我的收藏`，當前項目以 `bg-primary text-white` 標示 —（已改為 `text-white`：專案 `globals.css` 無 `primary-foreground` 變數，沿用既有 FilterChip 的 `bg-primary text-white` 實作慣例）

### 2-2 `<SocialMetrics>`

- [x] `components/social/SocialMetrics.tsx`
  - props：`favoriteCount: number`、`downloadCount?: number`（undefined 時隱藏）
  - 顯示：`⭐ {n}` `⬇ {n}`，並排小字
  - Agent 卡片傳 `downloadCount={undefined}` 隱藏 ⬇

### 2-3 `<FavoriteButton>`

- [x] `components/social/FavoriteButton.tsx`
  - props：`resourceType`、`resourceUid`、`isFavorited`、`onToggled?`
  - 點擊呼叫 `useFavoriteResourceMutation` / `useUnfavoriteResourceMutation`
  - 失敗時 rollback 並用既有 `useDialog` error dialog 顯示錯誤 —（已改為 `useDialog`：專案無 `useToast`，依 CLAUDE.md「既有共用層請直接使用，不可另起爐灶」原則沿用 `useDialog` 作為等同機制）
  - 視覺：實心 `★` / 空心 `☆` 星 + color transition

---

## Phase 3：Agents / Skills 管理頁整合

### 3-1 Agents 管理頁

- [x] `app/(main)/agents/page.tsx`
  - 頁首加 `<FilterNav>`（state `scope`，預設 `mine`）
  - 卡片右側嵌 `<SocialMetrics>`（隱藏 ⬇） + `<FavoriteButton>`
  - `scope='favorites'` 時切換到 `useListMyFavoritesQuery({type:'agent'})` 資料來源，並以 `SnapshotRow` 渲染 `ResourceSnapshot`

### 3-2 Skills 管理頁

- [x] `app/(main)/skills/page.tsx`
  - 同 §3-1；`<SocialMetrics>` 顯示 ⬇（`downloadCount={skill.download_count}`）
  - `scope='favorites'` 時切換到 `useListMyFavoritesQuery({type:'skill'})`

### 3-3 Tombstone 卡片

- [x] `components/social/TombstoneCard.tsx`：「我的收藏」清單渲染時，若 `resource === null`：
  - 渲染 `<TombstoneCard>`（`bg-muted-bg` + ⚠ warning icon + 「此 {Agent|Skill} 已被移除」）
  - 提供「從收藏移除」按鈕，呼叫 `useUnfavoriteResourceMutation` 並透過 Favorites tag invalidate 觸發 refetch

---

## Phase 4：驗收

- [x] Agents / Skills 管理頁三段式 filter 切換正確（全部 / 我的 / 我的收藏） —（靜態確認：`FilterNav` + `useState<FilterScope>` + 依 scope 擇一 query；未做 E2E 人測）
- [x] 卡片右上角穩定顯示 `⭐ N` 與 `⬇ N`（Agent 隱藏 ⬇） —（`SocialMetrics` 在 `downloadCount` 為 undefined 時不渲染 ⬇；Agent/SnapshotRow-agent 未傳 downloadCount）
- [x] 點收藏按鈕：星號立刻變實心、`favorite_count` +1；失敗則回滾並提示 error dialog —（`FavoriteButton` + `socialApi.onQueryStarted` patch list/single cache；失敗 undo + `useDialog` error）
- [x] 點取消收藏：星號立刻變空心、`favorite_count` -1 —（同上，unfavorite 走對稱路徑 + `Math.max(0, n-1)` 保險）
- [x] 「我的收藏」分頁能正確只列出當前使用者收藏項 —（後端 `/users/me/favorites` 以 `current_user` 過濾，前端直接渲染 items；未做 E2E 人測）
- [x] 收藏項對應的 Agent / Skill 被刪除後，「我的收藏」顯示 tombstone 卡片並可移除 —（`item.resource===null` → `TombstoneCard`；「從收藏移除」→ `unfavorite` → invalidate Favorites tag refetch；未做 E2E 人測）
- [x] 沒有任何頁面 reload；切 tab、收藏、取消收藏皆走 RTK cache 樂觀更新 —（頁面狀態純 React state，query/mutation 走 RTK Query）
- [x] 與 v1.2.1 列表 API 的 `is_favorited` 一致，無 stale UI —（mutation 樂觀 patch 涵蓋 `listAgents`/`listSkills` 全部 cache entries + `getAgent`/`getSkill` 單筆 cache，並 invalidate `Favorites` 觸發 `/users/me/favorites` refetch）
