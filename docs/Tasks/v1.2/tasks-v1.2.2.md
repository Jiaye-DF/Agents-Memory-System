# v1.2.2 任務規格：管理頁三段式 filter + 收藏按鈕

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

- [ ] `Agent` / `Skill` 加 `favorite_count: number` / `download_count: number` / `is_favorited: boolean`
- [ ] 新增 `MyFavoriteItem`：`{ user_favorite_uid, resource_type, resource_uid, resource: <Agent|Skill|null>, tombstone_reason: string|null, created_at }`
- [ ] 新增 `FilterScope = 'all' | 'mine' | 'favorites'`

### 1-2 RTK Query

- [ ] `agentsApi.useListAgentsQuery({ scope, page, size })`：`scope='favorites'` 時改打 `/users/me/favorites?type=agent`
- [ ] `skillsApi.useListSkillsQuery({ scope, page, size })`：同上 `type=skill`
- [ ] 新增 `socialApi`
  - `useFavoriteMutation({ resourceType, resourceUid })`
  - `useUnfavoriteMutation({ resourceType, resourceUid })`
  - 兩者帶**樂觀更新**：手動 patch 對應 list cache 的 `is_favorited` 與 `favorite_count`
- [ ] `tagTypes` 補 `Favorites`；favorite mutation 觸發 invalidate `Favorites`

---

## Phase 2：共用元件

### 2-1 `<FilterNav>`

- [ ] `components/social/FilterNav.tsx`
  - props：`value: FilterScope`、`onChange(scope)`、`labels?: Partial<Record<FilterScope,string>>`
  - 三段 tab：`全部` / `我的` / `我的收藏`，當前項目以 `bg-primary text-primary-foreground` 標示
  - 與 11-ui-ux.md 既有 tab 風格一致

### 2-2 `<SocialMetrics>`

- [ ] `components/social/SocialMetrics.tsx`
  - props：`favoriteCount: number`、`downloadCount?: number`（undefined 時隱藏）
  - 顯示：`⭐ {n}` `⬇ {n}`，並排小字
  - Agent 卡片傳 `downloadCount={undefined}` 隱藏 ⬇

### 2-3 `<FavoriteButton>`

- [ ] `components/social/FavoriteButton.tsx`
  - props：`resourceType`、`resourceUid`、`isFavorited`、`onToggled?`
  - 點擊呼叫 `useFavoriteMutation` / `useUnfavoriteMutation`
  - 失敗時 rollback 並用既有 `useToast` 顯示錯誤
  - 視覺：實心 / 空心星 + transition

---

## Phase 3：Agents / Skills 管理頁整合

### 3-1 Agents 管理頁

- [ ] `app/agents/page.tsx`（或對應路徑）
  - 頁首加 `<FilterNav>`（state `scope`，預設 `mine`）
  - 卡片右上角嵌 `<SocialMetrics>` + `<FavoriteButton>`
  - `scope='favorites'` 時切換到「我的收藏」資料來源（見 §1-2）

### 3-2 Skills 管理頁

- [ ] 同 §3-1，套用至 Skills 頁

### 3-3 Tombstone 卡片

- [ ] 「我的收藏」清單渲染時，若 `resource === null`：
  - 渲染 `<TombstoneCard>`（灰底 + ⚠ + 「此 {Agent|Skill} 已被移除」）
  - 提供「從收藏移除」按鈕，呼叫 `unfavorite` 並 invalidate

---

## Phase 4：驗收

- [ ] Agents / Skills 管理頁三段式 filter 切換正確（全部 / 我的 / 我的收藏）
- [ ] 卡片右上角穩定顯示 `⭐ N` 與 `⬇ N`（Agent 隱藏 ⬇）
- [ ] 點收藏按鈕：星號立刻變實心、`favorite_count` +1；失敗則回滾並 toast
- [ ] 點取消收藏：星號立刻變空心、`favorite_count` -1
- [ ] 「我的收藏」分頁能正確只列出當前使用者收藏項
- [ ] 收藏項對應的 Agent / Skill 被刪除後，「我的收藏」顯示 tombstone 卡片並可移除
- [ ] 沒有任何頁面 reload；切 tab、收藏、取消收藏皆走 RTK cache 樂觀更新
- [ ] 與 v1.2.1 列表 API 的 `is_favorited` 一致，無 stale UI
