# dev-v1.3-extended.md

> 本檔記錄 `df-dev-v1.3-extended` 分支的延伸修正項目, 供另一分支合併參考。
> 條目格式參照 [docs/Design-Base/90-code-fixed.md](../../Design-Base/90-code-fixed.md)。

---

## 1. Dashboard 多軸排序 chip 從垂直改水平排列〔2026-04-28 10:30:00〕

**問題**

`/dashboard` 頁面的「按時間 / 按收藏 / 按熱度」三組排序 chip 在桌面寬度下仍以**垂直**方式堆疊, 占用過多縱向空間, 與其他並列 filter 區塊風格不一致。

**根因**

外層容器 className 為 `flex flex-col gap-2`, 沒有在 `md` 以上斷點切回水平。

**修正**

外層改為 `flex flex-col gap-2 md:flex-row md:flex-wrap md:items-center md:gap-x-6`:

- 手機 (<768px) 維持垂直堆疊避免擠壓
- 桌面 (≥768px) 三組並排, `gap-x-6` 拉開組間距

**影響檔案**

- [frontend/src/app/(main)/dashboard/page.tsx](../../../frontend/src/app/(main)/dashboard/page.tsx)（`SORT_GROUPS` 渲染外層）

---

## 2. 作者 chip 點選後過濾結果為空（含空格 username 被 `\s+` 切壞）〔2026-04-28 10:50:00〕

**問題**

`/dashboard` 頁面的「作者：」chip 點選後, 列表瞬間變成 0 筆, 不顯示任何符合資料。

**根因**

舊版實作把 chip 選擇序列化進**單一搜尋字串** (`@username` token, 空白分隔), 再用 `parseSearch` 以 `\s+` 切回。username 為純英數時 round-trip 沒事; 但本專案 `owner.username` 採顯示名格式（例: `IT-Jiaye He 何佳曄`）, 含空格與中文字元, round-trip 會被切碎:

1. 點 chip → query 變成 `@IT-Jiaye He 何佳曄`
2. `parseSearch` 切空白 → 只有 `IT-Jiaye` 進 `parsed.authors`, `He` 與 `何佳曄` 落入 text 搜尋
3. `matchItem` 拿 `it-jiaye` 比對 `it-jiaye he 何佳曄` → 不相等 → 0 筆

歷史脈絡: 早期 username 規格純英數, 此設計可行; v1.3 起接入 SSO display name 後才暴露問題。

**修正**

把 chip 選擇從 query 字串拆出來, 改為**獨立 state**, 不再走 `\s+` 序列化:

1. 升級 `frontend/src/utils/search.ts`:
   - `matchByTextAndAuthor(name, description, author, parsed, selectedAuthors = [])` 多收 `selectedAuthors`（預設 `[]`, 向下相容）
   - 新增 `toggleAuthorChip(selected, author)` 取代舊 `toggleAuthorInQuery`
   - 移除 `toggleAuthorInQuery`
2. `parsed.authors`（搜尋框手打 `@author`）與 `selectedAuthors`（chip 點選）在 `matchByTextAndAuthor` 取**聯集**
3. 各頁面 chip 的 `isSelected` 同時檢查兩個來源

兩個來源並存的理由:

- 搜尋框手打 `@author` 仍為合法輸入語法（純英數 username 仍可靠）
- chip 點選需支援含空格 username, 不能再走 query 字串

**影響檔案**

- [frontend/src/utils/search.ts](../../../frontend/src/utils/search.ts)（util 升級）
- [frontend/src/app/(main)/dashboard/page.tsx](../../../frontend/src/app/(main)/dashboard/page.tsx)（移除 local `parseSearch`/`matchItem`, 改用共用 util; 新增 `selectedAuthors` state）
- [frontend/src/app/(main)/agents/page.tsx](../../../frontend/src/app/(main)/agents/page.tsx)（chip 改用 `selectedAuthors`, 不再 mutate query）
- [frontend/src/app/(main)/skills/page.tsx](../../../frontend/src/app/(main)/skills/page.tsx)（補上作者 chip UI + state）
- [frontend/src/app/(main)/scripts/page.tsx](../../../frontend/src/app/(main)/scripts/page.tsx)（補上作者 chip UI + state）

**驗證方式**

- 用 username 含空格的帳號（如 `IT-Jiaye He 何佳曄`）建立資源, 在 `/dashboard`、`/agents`、`/skills`、`/scripts` 點該作者 chip → 列表應正確過濾
- 搜尋框手打 `@<純英數 username>` → 仍可正常過濾
- 同時點 chip + 手打不同 author → 取聯集（任一命中即顯示）

**殘留 / 後續**

`parseSearch` 仍以 `\s+` tokenize, 因此搜尋框**手打**含空格的 `@author` 字串仍會解析錯誤（無 UI 路徑會觸發, 但若使用者直接貼上仍會失效）。可接受的取捨——chip 為主要互動入口, 手打 `@author` 為補充語法。未來若需求要支援手打含空格 author, 可考慮引號包裝 `@"name with spaces"` 或使用不可見分隔符。

---

## 3. Dashboard 文案統一:「你最常用的」→「最常使用」〔2026-04-28 10:55:00〕

**問題**

`/dashboard` 頁籤與右側 `RankingPanel` 標題均為「你最常用的」, 主詞與動詞混用, 與其他「按時間 / 按收藏 / 按熱度」等以動作為主的標題不一致。

**修正**

統一改為「最常使用」, 去掉主詞「你」、改名詞化動詞「使用」。

**影響檔案**

- [frontend/src/app/(main)/dashboard/page.tsx:444](../../../frontend/src/app/(main)/dashboard/page.tsx#L444)（頁籤）
- [frontend/src/components/dashboard/RankingPanel.tsx:199](../../../frontend/src/components/dashboard/RankingPanel.tsx#L199)（區塊標題）

---

## 4. FilterNav 文案精簡:「我的收藏」→「收藏」〔2026-04-28 11:05:00〕

**問題**

`/agents`、`/skills`、`/scripts` 三個管理頁左側 sub-nav 的「我的收藏」與右側區塊「我的」並列, 主詞重複、字數不對齊。

**修正**

`DEFAULT_LABELS.favorites` 從「我的收藏」改為「收藏」, 與「我的」（owned）對稱成兩字標籤, 提升 nav 整齊度。

**影響檔案**

- [frontend/src/components/social/FilterNav.tsx:14](../../../frontend/src/components/social/FilterNav.tsx#L14)

---

## 5. 多頁作者 chip 行為統一（補齊 /skills、/scripts UI）〔2026-04-28 11:09:00〕

**問題**

`/dashboard`、`/agents` 有作者 chip UI, 但 `/skills`、`/scripts` 沒有, 互動體驗不一致。

**修正**

在 `/skills` 與 `/scripts` 補上作者 chip 區塊, 與 `/agents` 完全對齊:

- 新增 `selectedAuthors` state
- 新增 `authorOptions` useMemo（從 `scopedSkills` / `scopedScripts` 收集去重 owner_username）
- 新增 `handleToggleAuthor` callback（用 util `toggleAuthorChip`）
- 在 sort chip 區塊下方加上 `{authorOptions.length > 0 && ...}` 條件渲染區塊
- chip `isSelected` 同時檢查 `parsed.authors` 與 `selectedAuthors`

四頁（dashboard / agents / skills / scripts）現在共用同一條規則:「搜尋框手打 `@author`（純英數可靠）+ chip 點選含空格 username（獨立 state, 不寫回 query）」, 兩來源在 `matchByTextAndAuthor` 取聯集。

**影響檔案**

- [frontend/src/app/(main)/skills/page.tsx](../../../frontend/src/app/(main)/skills/page.tsx)
- [frontend/src/app/(main)/scripts/page.tsx](../../../frontend/src/app/(main)/scripts/page.tsx)

> §2 與 §5 在同一輪 refactor 完成, 拆兩條是因前者是 bug fix（改 util + 修舊頁）、後者是 UI 一致性回補（新加 chip 區塊到原本沒有的頁面）。
