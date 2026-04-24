# v1.2 修正記錄

> 驗收 v1.2.1 ~ v1.2.4（社群互動底層、管理頁收藏、Script 管理、儀錶板排行）期間發現的 UI 異常與既有規格實作偏差。

---

## 1. Admin 管理頁表格於中等視窗擠壓、內容被強制換行  〔2026-04-24 05:20:00〕

**問題**：`/admin/models` 等 Admin 管理頁於約 1100px 寬視窗下，表格每個儲存格（「顯示名稱」、「最大 Token」、「建立時間」、「操作」按鈕組）都被強制折成兩行，右側「刪除」按鈕被容器切掉，閱讀體驗明顯劣化。

```text
Provider | Model ID            | 顯示 | 預設 | 最大    | 狀 | 建立時間   | 操
         |                     | 名稱 |     | Token  | 態 |            | 作
OpenRouter anthropic/claude... Claude      8192  啟  2026/04/24   編輯
                               Sonnet            用  08:44:49     停用 刪除
                               4                                         ←被切
```

根因為兩個互相疊加的設計缺陷：

1. **儲存格允許自動換行**：`<th>` / `<td>` 沒掛 `whitespace-nowrap`，Tailwind 預設 `white-space: normal`，當容器寬度不足以容納所有欄位時，每個儲存格先嘗試折行收斂，導致每行高度暴漲、版面零碎。
2. **卡片替代斷點設得太保守**：`Table.tsx` 在 `md` (768px) 以下才切卡片，768–1279px 這段「中等寬度」剛好會進入表格模式但又無法漂亮呈現 8 欄，Tailwind 預設斷點（`md=768 / lg=1024 / xl=1280`）之間恰好有個跑版區間。

**修正**：

1. `Table.tsx` 表頭 `<th>` / 儲存格 `<td>` 一律加 `whitespace-nowrap`，配合既有 `overflow-x-auto`，過寬時改以容器內水平捲軸承載。
2. 卡片 / 表格切換斷點由 `md` 拉高到 `xl`（< 1280px 一律顯示卡片模式）。
3. 同步將 **RWD 斷點選擇原則**寫入 `docs/Design-Base/11-ui-ux.md`：若 UI 於 Tailwind 預設斷點之間（例：1100px）跑版，必須提前用**上一級**斷點切 layout（此例選 `xl` 而非 `lg`），寧可提前切到保守版本，不讓使用者看到中間跑版態。

**影響檔案**：

- `frontend/src/components/ui/Table.tsx`
- `docs/Design-Base/11-ui-ux.md`

**驗證方式**：於 1100px 左右視窗檢視 `/admin/models` → 應直接顯示卡片；於 1280px 以上 → 應顯示表格且每列單行水平顯示，過寬時容器內出現水平捲軸。

**影響範圍**：此調整透過共用 `<Table>` 元件一併影響 `/admin/users`、`/admin/models`、`/admin/agent-languages`、`/admin/agent-templates` 四頁；四頁均已實作 `cardRender`，無副作用。

---

## 2. 儀錶板「你最常用的」混入公開排行榜語義  〔2026-04-24 05:22:00〕

**問題**：v1.2.4 實作的 `RankingPanel`（「你最常用的」）同時呈現「類型切換 [全部 / Agents / Skills / Scripts]」與「排序切換 [最新 / 熱度 / 收藏數]」兩組切換。但本面板資料源**僅限使用者擁有的資源**（副標「根據你擁有的資源統計」），對使用者個人自己的資源做「熱度／收藏數」排序沒有跨人比較的意義，且會與後續將建立的**公開 Agents / 公開 Skills / 公開 Scripts** 排行榜概念重疊混淆。

根因：v1.2.4 規格（見 [tasks-v1.2.4.md §2-3](tasks-v1.2.4.md)）把 `<RankingOrderTabs>` 直接併入「你最常用的」區塊，設計當時未釐清「個人擁有資源統計」與「跨使用者公開排行」應屬兩個獨立概念 — 前者的正確呈現維度只有**類型**，後者才需要「熱度 vs 收藏」與「升 vs 降序」的排序切換，且應放在儀錶板上方的公開 Agents / Skills / Scripts 頁籤內。

**修正**：

1. `RankingPanel.tsx` 移除 `ORDER_TABS` 常數、`RankingOrderTabs` 元件、`orderBy` state 與分隔線。
2. API 呼叫固定帶入 `orderBy: "download_count"`（「最常用」語義上與下載／使用次數最接近；後端 `/dashboard/rankings` 仍保留參數供未來擴充）。
3. 副標文案由「跨使用者公開排行將在後續版本推出」改為「公開熱度／收藏排行將整合至公開 Agents／Skills／Scripts 頁籤」，明確劃分兩個面板的職責。
4. `tasks-v1.2.4.md` 相關規格項目保留 `[x]` 並於後方加註「已改為 xxx，見 fixed.md §2」（遵循 CLAUDE.md「任務文件回填」規則）。

**影響檔案**：

- `frontend/src/components/dashboard/RankingPanel.tsx`
- `docs/Tasks/v1.2/tasks-v1.2.4.md`

**驗證方式**：/dashboard 畫面「你最常用的」區塊右側應僅剩類型切換 `[全部] [Agents] [Skills] [Scripts]`，不再顯示 `[最新] [熱度] [收藏數]`；切換類型後列表仍依 `download_count` 降序呈現。

**殘留 / 後續**：

- 公開 Scripts 頁籤尚未於 `/dashboard` 新增（目前僅有公開 Agents / 公開 Skills 兩頁籤）
- 公開 Agents / Skills / Scripts 三頁籤的「熱度／收藏排行」與「升／降序」切換尚未實作
- 以上兩項應歸入 v1.2 後續版次或 v1.3，待單獨任務規格化

---

## 3. Admin 卡片模式 Y 軸高度過大、資訊密度過低  〔2026-04-24 05:29:36〕

**問題**：接續 §1 將 Admin 管理頁卡片斷點由 `md` 拉到 `xl` 後，實際瀏覽 `/admin/models`、`/admin/users`、`/admin/agent-languages`、`/admin/agent-templates` 發現**每張卡片高度過大**（約 150–180px），單一 viewport 可見筆數過少、滾動成本高。

根因：四張 Card 元件（`UserCard` / `ModelCard` / `LanguageCard` / `TemplateCard`）皆採同一種「每個欄位獨立一行」的 `flex flex-col gap-3` 垂直堆疊：主名稱、徽章、metadata 1、metadata 2、建立時間、按鈕群各占一行，共 4–6 列。原本為 `md` 以下才會啟用的行動裝置布局，拉高到 `xl` 後仍沿用手機期間的稀疏排版，導致桌機中等寬度（768–1279px）看到的資訊密度極低。

**修正**：四張卡片統一改為 **2–3 列緊湊布局**：

1. **Row 1（主資訊列）**：名稱 + 預設/狀態徽章（`text-xs`）+ 右推（`ml-auto`）操作按鈕群；整列用 `flex flex-wrap items-center gap-2`，窄寬度時按鈕自然 wrap。
2. **Row 2（metadata 列）**：provider / code / template_key / 排序 / 建立時間用 `·` 分隔符 inline 排列，`flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted`。
3. **Row 3（選用，僅 TemplateCard）**：`description` 以 `line-clamp-1` 呈現，原本 `line-clamp-2` 改 1 行避免撐高。
4. 卡片內部 `gap` 由 `gap-3` 收到 `gap-1.5`；`Table.tsx` 卡片容器外距由 `p-4` 改 `px-3 py-2`、`gap-4` 改 `gap-2`；徽章字級由 `text-sm` 改 `text-xs`。
5. `UserCard` 把 role select 也合併進 Row 1（移除「角色：」前綴，保留 aria-label），並把鎖定狀態訊息併入 metadata 列，節省兩列。

最終每張卡片高度降至約 60–80px，單一 viewport 可見筆數約提升 2 倍。

**影響檔案**：

- `frontend/src/components/ui/Table.tsx`
- `frontend/src/app/(main)/admin/users/page.tsx`
- `frontend/src/app/(main)/admin/models/page.tsx`
- `frontend/src/app/(main)/admin/agent-languages/page.tsx`
- `frontend/src/app/(main)/admin/agent-templates/page.tsx`

**驗證方式**：於 1100px 視窗檢視上述四頁 → 卡片應每張高度約 60–80px、每項僅 2 行（有描述的 template 為 3 行）、操作按鈕貼右；視窗縮到 400px 仍可正常 wrap 不溢出。

---

## 處理狀態

| # | 項目 | 狀態 | Commit |
| --- | --- | --- | --- |
| 1 | Admin 表格中等視窗擠壓 + RWD 斷點原則 | ✅ 已修 | — 待 commit-all |
| 2 | 儀錶板「你最常用的」移除 orderBy 切換 | ✅ 已修 | — 待 commit-all |
| 3 | Admin 卡片模式 Y 軸高度過大 | ✅ 已修 | — 待 commit-all |

---

## 殘留清理項

- 儀錶板公開 Scripts 頁籤尚未建立（見 §2 殘留 / 後續）
- 公開 Agents / Skills / Scripts 排行榜升降序切換尚未實作（見 §2 殘留 / 後續）
