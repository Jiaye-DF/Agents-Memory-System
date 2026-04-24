# v1.2 修正記錄

> 驗收 v1.2.1 ~ v1.2.4（社群互動底層、管理頁收藏、Script 管理、儀錶板排行）期間發現的 UI 異常與既有規格實作偏差。

---

## 1. Admin 管理頁表格於中等視窗擠壓、內容被強制換行  〔2026-04-24 05:20:00〕

**問題**：`/admin/models` 等頁在約 1100px 視窗下表格儲存格強制換行、右側按鈕被切。

**根因**：儲存格未加 `whitespace-nowrap`；卡片斷點只設到 `md`，768–1279px 落入跑版區。

**修正**：`Table.tsx` 儲存格加 `whitespace-nowrap`、卡片斷點由 `md` 拉到 `xl`；RWD 斷點原則寫入 `docs/Design-Base/11-ui-ux.md`（預設斷點間跑版時提前用上一級切 layout）。

**影響檔案**：`frontend/src/components/ui/Table.tsx`、`docs/Design-Base/11-ui-ux.md`。

---

## 2. 儀錶板「你最常用的」混入公開排行榜語義  〔2026-04-24 05:22:00〕

**問題**：`RankingPanel` 同時呈現類型切換與「最新 / 熱度 / 收藏數」排序切換，但資料源僅限個人擁有資源，對個人資源做熱度／收藏排序無跨人比較意義，且與公開排行榜概念混淆。

**修正**：移除 `RankingPanel` 的 `orderBy` 切換，API 固定帶 `orderBy: "download_count"`；副標改註明「公開排行將整合至公開 Agents／Skills／Scripts 頁籤」;`tasks-v1.2.4.md` 相關項目加註「見 fixed.md §2」。

**影響檔案**：`frontend/src/components/dashboard/RankingPanel.tsx`、`docs/Tasks/v1.2/tasks-v1.2.4.md`。

**後續**：公開 Scripts 頁籤與公開排行排序切換歸入 §4、§5。

---

## 3. Admin 卡片模式 Y 軸高度過大、資訊密度過低  〔2026-04-24 05:29:36〕

**問題**：§1 將卡片斷點拉到 `xl` 後，桌機中等寬度看到的卡片每張 120–180px（4–6 列垂直堆疊），資訊密度太低。

**根因**：四張 Card 與 `SettingRow` 都用 `flex flex-col gap-3` 每欄位獨立一行，手機式稀疏排版沿用到桌機。

**修正**：五張卡片／列統一改 2–3 列緊湊布局 —
- Row 1：名稱 + 徽章 + 右推操作按鈕（`flex flex-wrap items-center`）
- Row 2：metadata 用 `·` 分隔 inline 排列
- Row 3（選用）：長描述 `line-clamp-1` + tooltip

同步收斂間距與字級（`gap-3` → `gap-1.5`、徽章 `text-sm` → `text-xs`、settings 頁首與 group header 合併同行）。最終卡片高度降至 60–80px。

**影響檔案**：`frontend/src/components/ui/Table.tsx`、`frontend/src/app/(main)/admin/{users,models,agent-languages,agent-templates,settings}/page.tsx`。

---

## 4. 儀錶板缺「公開 Scripts」頁籤、Script 表缺 `visibility` 欄位  〔2026-04-24 05:48:56〕

**問題**：`/dashboard` 上方頁籤目前僅 `[公開 Agents] [公開 Skills]`（見 `frontend/src/app/(main)/dashboard/page.tsx` L13 `TabKey = "agents" | "skills"`、L251-258 TabButton 兩顆），**缺第三顆「公開 Scripts」**。無法讓使用者在儀錶板瀏覽他人公開的腳本資源，與 propose-v1.2.0 §2-4「類型切換：[全部] [Agents] [Skills] [Scripts]」規格不一致。

根因：v1.2.3 Phase A 實作 `script` 表（V35）時沿用 v1.2 範圍外約束「跨使用者公開 marketplace 留 v1.4」，**刻意未加 `visibility` 欄位** — 不像 V5（agent）/ V7（skill）在 v1.1 就具備 `visibility VARCHAR(10) DEFAULT 'private' CHECK (visibility IN ('public','private'))`。儀錶板既有「公開 X」頁籤透過前端 `filter(item.visibility === 'public')` 實現，Script 因無此欄位也無從實作頁籤。propose-v1.2.0 §2-4 雖明示類型切換含 Scripts，但因 script 欄位設計未同步延伸，落入 v1.2 殘留。

**待修範圍**（規劃歸入 tasks-v1.2.5.md）：

1. **V37 migration**：`ALTER TABLE script ADD COLUMN visibility VARCHAR(10) NOT NULL DEFAULT 'private'` + CHECK constraint + COMMENT，與 agent / skill 對齊
2. **後端 Script 擴充**：
   - `backend/app/models/script.py` 加 `visibility` 欄位
   - `backend/app/schemas/scripts/schemas.py` `ScriptResponse` / `ScriptCreateForm` / `ScriptUpdateRequest` 加 `visibility`
   - `backend/app/repositories/script_repository.py` `list_by_owner` 支援 `visibility='public'` 過濾（或由 service 層處理）
   - `backend/app/api/v1/scripts/router.py` list 端點已能透過前端 filter，或擴 `visibility` query（看設計取捨）
3. **Dashboard 頁籤擴 Scripts**：
   - `TabKey = "agents" | "skills" | "scripts"`
   - 新增 TabButton「公開 Scripts ({n})」
   - `publicScripts` useMemo 以同 pattern filter `visibility === 'public'`
   - `ScriptRow` 元件或沿用 `AgentRow` / `SkillRow` 樣式
4. **Scripts 管理頁**：卡片 / 編輯 Modal 加 `visibility` 切換（預設 `private`），對齊 Agents / Skills 管理頁既有行為

**已確認決策**：
- `visibility` 預設 `'private'`（使用者主動公開、不改變既有 Script 行為）
- Dashboard 公開頁籤**維持單純瀏覽場景**（GitHub explore 風格），不加「全部 / 我的 / 我的收藏」filter — 這三段只存在於 `/agents` / `/skills` / `/scripts` 管理頁
- 公開資源的可見性政策範圍僅限「自己擁有 vs 公開瀏覽」；跨使用者訂閱 / 審核 / API scope 仍歸 v1.4 公開 API 處理

**影響檔案**（預期）：

- `migrations/sql/V37__add_script_visibility.sql`（新增）
- `backend/app/models/script.py`
- `backend/app/schemas/scripts/schemas.py`
- `backend/app/repositories/script_repository.py`
- `backend/app/services/script_service.py`
- `backend/app/api/v1/scripts/router.py`
- `frontend/src/types/scripts.ts`
- `frontend/src/store/scriptsApi.ts`
- `frontend/src/app/(main)/dashboard/page.tsx`
- `frontend/src/app/(main)/scripts/page.tsx`
- `docs/Tasks/v1.2/tasks-v1.2.5.md`（新增，規格化待辦）

---

## 5. 公開頁籤缺排序切換、Ranking API 缺 `order=asc|desc` 參數  〔2026-04-24 05:48:56〕

**問題**：原 v1.2.4 `RankingPanel` 含「[最新] [熱度] [收藏數]」排序切換於 propose-v1.2.0 §2-4 明文規格，但 fixed.md §2 將其從「你最常用的」區塊移除（因個人資源做熱度 / 收藏排序無跨人意義），改口說「排序概念改歸入後續公開 Agents / Skills / Scripts 頁籤」— 公開頁籤至今**未新增任何排序 chip**，且後端 `GET /api/v1/dashboard/rankings` router 寫死 `desc`（見 `backend/app/api/v1/dashboard/router.py` L37 comment「排序欄位 order_by 皆為 desc」、L47 僅 `order_by` Query 無 `order`）。propose-v1.2.0 §2-1 L119-121 已為列表 API 定下 `order=desc` 參數，ranking API 卻未延伸此參數，規格落差。

根因：
1. **v1.2.4 設計盲點**：原規格把排序 chip 放在「你最常用的」面板，後驗收時才發現「個人擁有資源的熱度排序」語意模糊，fixed.md §2 快速處置為移除；但移除後「排序切換搬到公開頁籤」一事未同步開 task 落地
2. **Ranking API 規格漏設 `order` 參數**：propose-v1.2.0 §2-4 的 `GET /api/v1/dashboard/rankings` 範例 URL 僅列 `type` / `order_by` / `limit`，未如 §2-1 明示 `order=desc`；v1.2.4 實作者依規格辦事、寫死 `desc`，升序路徑完全缺席
3. **命名規格空白**：專案既有 `/admin/models` 頁 L741-755 用 `<FilterChip>` + 前綴「排序：」+ **語意化對稱命名**（最新 / 最舊）做單軸排序，但排行榜的「雙軸三向」（時間 / 熱度 / 收藏 × 高 / 低）未於任何 propose 或 Design-Base 文件規格化 chip 命名慣例

**待修範圍**（規劃歸入 tasks-v1.2.5.md）：

1. **後端 Ranking API 擴 `order` 參數**：
   - `GET /api/v1/dashboard/rankings?type=&order_by=&order=asc|desc&limit=`
   - `dashboard_service.list_rankings` 依 `order` 參數決定三類各自 top N query 的排序方向 + 合併後重排方向
   - `Literal["asc", "desc"]` 白名單，預設 `desc`
2. **列表 API 的 `order` 參數**（前端補串接）：`/api/v1/agents` / `/skills` / `/scripts` 後端已支援（v1.2.1 + v1.2.3 實作），前端既有 RTK Query hook 需補 `order` 欄位傳遞
3. **前端排序 chip（沿用既有 pattern）**：
   - 位置：類型頁籤下方、搜尋框 + 作者 filter **下方**
   - 元件：沿用 `FilterChip` + 前綴 `<span>排序：</span>`（與 `/admin/models` L741-755 一致）
   - 布局：`flex flex-wrap items-center gap-2`（窄寬度自然 wrap）
   - 共 6 顆 chip、預設選中「最新」
4. **chip 標籤對照表**（**語意化對稱命名、禁用方向符號 / toggle**）：

   | `order_by` | `order` | chip 標籤 |
   | --- | --- | --- |
   | `created_at` | `desc` | 最新 |
   | `created_at` | `asc` | 最舊 |
   | `download_count` | `desc` | 最熱門 |
   | `download_count` | `asc` | 最冷門 |
   | `favorite_count` | `desc` | 最多收藏 |
   | `favorite_count` | `asc` | 最少收藏 |

5. **chip 使用情境**：
   - 公開 Agents / Skills / Scripts 三頁籤**共用**同一排序列
   - 切換類型時**保留**當前排序選擇（UX：避免使用者在三個頁籤反覆設定）
   - 搜尋框 / 作者 filter 仍生效於排序結果上

**已確認決策**：
- chip 命名不使用「↑↓」、「由高到低」、「asc/desc」等方向 / 英文符號，一律中文語意化對稱詞
- 「最新」/「最舊」必須成對出現（對稱性；使用者明確要求）
- 排序 chip **不做 toggle** — 6 顆平鋪、單選切換
- Ranking API 預設維持 `order=desc`（向後相容既有 ranking 呼叫）
- 列表 API 的 `order=asc` 路徑後端已可用、前端補 UI 即通

**影響檔案**（預期）：

- `backend/app/api/v1/dashboard/router.py`（擴 `order` Query）
- `backend/app/services/dashboard_service.py`（接 `order` 參數）
- `backend/app/schemas/dashboard/schemas.py`（若 request schema 化則同步）
- `frontend/src/app/(main)/dashboard/page.tsx`（排序 chip + API 串接）
- `frontend/src/store/dashboardApi.ts`（hook 參數加 `order`）
- `frontend/src/store/agentsApi.ts` / `skillsApi.ts` / `scriptsApi.ts`（若既有 hook 未暴露 `order` 則擴）
- `docs/Design-Base/11-ui-ux.md`（**新增排序 chip 慣例**子節：語意化對稱命名、前綴「排序：」、`<FilterChip>` 複用規則）
- `docs/Tasks/v1.2/tasks-v1.2.5.md`（新增，規格化待辦）

---

## 6. 排序 chip 分軸分向重構 + 「你最常用的」改 tab  〔2026-04-24 23:16:26〕

**問題**：使用者檢視 `/dashboard` 後認定兩項 UI 需調整 —

1. 排序列 6 顆扁平 chip（最新 / 最舊 / 最熱門 / 最冷門 / 最多收藏 / 最少收藏）閱讀負擔重，軸與方向混在同一列，掃視不直覺
2. 「你最常用的」排行榜自 v1.2.4 起一直放在公開頁籤**下方**作為獨立區塊，與上方公開頁籤的視覺層級模糊、進入點不明

根因：

1. **§5 的 chip 命名規範被本模型過度設計**：fixed.md §5 與當時新寫入的 Design-Base §2-5 強推「語意化對稱中文詞、禁用方向表述」，把排序欄位 × 方向硬壓成單一詞（最熱門 / 最冷門等）。使用者實際體感是「軸 + 方向」兩個概念，一體成形的單詞反而要多一層轉譯。此規則是**前代 Claude 回合自行擴寫**進 Design-Base、使用者未主動背書。
2. **§2 的「你最常用的」擺放沿用自 v1.2.4 原始規格**：當時無公開 Scripts 頁籤、資訊層級少，放在下方 OK；v1.2.5 補上公開 Scripts 頁籤後，「個人最常用 vs 公開瀏覽」在同一頁面應為**並行切換**而非**上下堆疊**。

**修正**：

1. **排序 UI 改分軸分向**：以「軸」為前綴標籤，每軸兩顆方向 chip（見 `docs/Design-Base/11-ui-ux.md` §2-5 改寫後表格）
   - `按時間：` [由新到舊] [由舊到新]
   - `按收藏：` [由多到少] [由少到多]
   - `按熱度：` [由多到少] [由少到多]
2. **Design-Base §2-5 改寫**：多軸排序以「軸前綴 + 方向 chip」為 canonical；單軸場景（`/admin/models`）保留「最新 / 最舊」短形式；移除「禁用方向表述」限制
3. **新增「你最常用的」tab**：`TabKey` 加 `"favorites"`；tab 位置在「公開 Scripts」右側、「管理我的 … →」左側
4. **RankingPanel 從頁面底部移除**：僅在 `favorites` tab active 時呈現；公開 tab active 時不渲染

交叉引用：

- 本次操作推翻 **§5 chip 標籤對照表**（符合 §5「使用者明確要求」當時語境，但經本次確認使用者最終偏好為分軸分向）
- 本次操作推翻 **§2 RankingPanel 擺放位置**（自區塊升為 tab）

**影響檔案**：

- `docs/Design-Base/11-ui-ux.md`（§2-5 改寫）
- `frontend/src/app/(main)/dashboard/page.tsx`（TabKey 擴 `favorites` + 排序列改 `SORT_GROUPS` 結構 + 條件渲染）
- `frontend/src/components/dashboard/RankingPanel.tsx`（僅 Prettier 自動格式化，無行為變更）

**殘留**：`/admin/models` 與其他頁面既有排序 UI 未同步遷移，暫留單軸短形式；若後續使用者要求統一再開 task。

---

## 處理狀態

| # | 項目 | 狀態 | Commit |
| --- | --- | --- | --- |
| 1 | Admin 表格中等視窗擠壓 + RWD 斷點原則 | ✅ 已修 | — 待 commit-all |
| 2 | 儀錶板「你最常用的」移除 orderBy 切換 | ✅ 已修 | — 待 commit-all |
| 3 | Admin 卡片模式 Y 軸高度過大 | ✅ 已修 | — 待 commit-all |
| 4 | 儀錶板缺公開 Scripts 頁籤 + Script 缺 visibility | ✅ 已修 | — 待 commit-all |
| 5 | 公開頁籤缺排序切換 + Ranking API 缺 `order` | ✅ 已修 | — 待 commit-all |
| 6 | 排序 chip 分軸分向重構 + 「你最常用的」改 tab | ✅ 已修 | — 待 commit-all |

---

## 殘留清理項

§4 / §5 已於 v1.2.5 完成（詳見 `tasks-v1.2.5.md`）：

- §4 公開 Scripts 頁籤 + Script `visibility` 欄位 — ✅ 已於 v1.2.5 完成
- §5 公開頁籤排序切換 chip + Ranking API `order` 參數 — ✅ 已於 v1.2.5 完成（chip 標籤表已於 §6 推翻）
- §6 `/admin/models` 等其他頁面排序 UI 是否需統一至多軸分向格式 — 暫留決策
