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

## 7. 收藏 Agent / Skill API 觸發 500 — 本地 `update` 函式 shadow 掉 SQLAlchemy `update`  〔2026-04-25 08:33:00〕

**問題**：`POST /api/v1/agents/{uid}/favorite`（skill 同路徑同症狀）回 500。後端 log：

```
TypeError: update() missing 2 required positional arguments: 'update_data' and 'db'
  File "/app/app/repositories/agent_repository.py", line 94, in increment_favorite_count
    update(Agent)
```

**根因**：`agent_repository.py` / `skill_repository.py` 同時 `from sqlalchemy import ... update` 並定義 `async def update(entity, update_data, db)`，模組層的本地函式覆蓋了 SQLAlchemy 的 `update()`；`increment_favorite_count` / `increment_download_count` 內 `update(Agent)` 實際命中本地 async 函式，傳參不符 → TypeError。`script_repository` 已將本地函式命名為 `update_obj` 規避，agent / skill 兩個 repo 漏了。

**修正**：

1. `agent_repository.update` / `skill_repository.update` → `update_obj`（對齊 `script_repository` 既有慣例）
2. `agent_service.py` / `skill_service.py` 對應 caller 同步改名
3. 順手簡化 `favorite_service.list_my_favorites`：抽出 `_build_snapshot_map(favs, resource_type, db)` helper，主函式從約 70 行縮到 25 行（語意不變、tombstone 規則未動）

**影響檔案**：

- `backend/app/repositories/agent_repository.py`
- `backend/app/repositories/skill_repository.py`
- `backend/app/services/agent_service.py`
- `backend/app/services/skill_service.py`
- `backend/app/services/favorite_service.py`

---

## 8. /scan-project 掃出的規範落差批量修補（Design-Base + 程式碼層）  〔2026-04-25 08:33:11〕

**問題**：執行 `/scan-project`（報告寫入 `docs/Tasks/scan-project/Issue-Scan-Project-260425083311.md`）後，識別出 5 處 Design-Base 自身落差與 4 處程式碼層違規 / 隱性 bug，集中於本條一次修補。

根因：v1.0 ~ v1.2 期間，後端 `api/v1/` 與前端路由持續擴充（scripts、dashboard、agent-templates、social favorite），但 Design-Base 規範樹節錄與權限對照表未同步生長；同時 `schemas/system_settings/` 與 `api/v1/settings/` 命名漂移、`scripts/page.tsx` 下載流程未走共用 `lib/api/download.ts`、`skill_factory_service` 殘留 `Any`。皆屬「規範與實作雙向漂移、缺一次系統性對齊」的累積。

**修正**：

1. **Design-Base 五處同步擴充**：
   - `40-permission.md`：`/api/v1/conversations/*` 改為 `/api/v1/chat/*`；member + admin 共用端點補進 scripts / chat / dashboard / agent-templates / 收藏端點 / `users/me/favorites`；admin 專屬區補 `agent-templates/*`；表格寬度同步對齊
   - `10-frontend.md § 目錄結構` 補 `scripts/page.tsx`
   - `20-backend.md § 目錄結構與分層` 同步擴充 `api/v1/` 與 `schemas/` 兩棵樹（含 scripts / agent_languages / agent_templates / dashboard / models / settings / social / common.py）
   - `00-overview.md` 新增 `## Monorepo 目錄結構` 小節，列實際頂層目錄
2. **`schemas/system_settings/` → `schemas/settings/` rename**（對齊 `api/v1/settings/`）：
   - 新建 `schemas/settings/{__init__.py, schemas.py}` 內容沿用
   - `admin/router.py`、`system_setting_service.py` import 路徑更新
   - 移除舊目錄 `schemas/system_settings/`
3. **`skill_factory_service.py` 移除 `Any`**：以 `TypedDict`（`_LogItem` / `_LogListResult`）取代 `dict[str, Any]`，`event` 改為 `dict[str, object]`；回傳型別由裸 `dict` 改為具型別的 `_LogListResult`
4. **`scripts/page.tsx` 下載流程改用 `lib/api/download.ts`**：移除頁面內 `getAccessToken` + 手動 `fetch` + 手動 filename 解析 + 手動 `URL.createObjectURL` / `<a>` click；改用 `downloadBlob` + `extractFilename` + `triggerBrowserDownload` 三段呼叫。**順帶修正潛在 bug**：原寫法 `${API_BASE_URL}/api/v1/scripts/...` 在 `NEXT_PUBLIC_API_URL` 已含 `/api/v1` 的情境下會造成雙前綴 `/api/v1/api/v1/...`，改走 `download.ts` 後 path 統一從 `/scripts/...` 開始，自動避開重複。
5. **`config.py` 補 LINE / Telegram token 占位宣告**：`LINE_CHANNEL_ACCESS_TOKEN` / `LINE_CHANNEL_SECRET` / `TELEGRAM_BOT_TOKEN` 三項 `str = ""`，配合 `.env.example` 既有變數對齊；v1.3+ 啟動 LINE / Telegram 整合時可直接使用，不再需要回頭補 Settings

**影響檔案**：

- `docs/Design-Base/00-overview.md`
- `docs/Design-Base/10-frontend.md`
- `docs/Design-Base/20-backend.md`
- `docs/Design-Base/40-permission.md`
- `backend/app/schemas/settings/__init__.py`（新增）
- `backend/app/schemas/settings/schemas.py`（新增，沿用舊內容）
- `backend/app/schemas/system_settings/`（移除）
- `backend/app/api/v1/admin/router.py`
- `backend/app/services/system_setting_service.py`
- `backend/app/services/skill_factory_service.py`
- `backend/app/core/config.py`
- `frontend/src/app/(main)/scripts/page.tsx`

**驗證方式**：

- 後端：`backend/app` 全域 grep `system_settings` 無命中、`from typing import Any` 在 skill_factory_service 無命中
- 前端：`scripts/page.tsx` 全檔無 `API_BASE_URL` / `getAccessToken` / 直接 `fetch` 命中
- 規範：`docs/Tasks/scan-project/Issue-Scan-Project-260425083311.md` §三 條目全數標 `[x]`

**殘留 / 後續**：

- `clients/line/` / `clients/telegram/` 子目錄與實際整合留 v1.3+；目前僅完成 Settings 占位
- `docker-compose.dev.yml` 暫不傳遞 LINE / Telegram env（待真實整合時再補 environment 區塊）

---

## 9. 排序 chip 全站統一為「軸前綴 + 方向 chip」格式  〔2026-04-25 08:55:17〕

**問題**：§6 推翻原「最新 / 最舊」單軸短形式、改為 dashboard 採「軸前綴 + 方向」分軸分向後，遺留 `/admin/models`、`/agents`、`/skills`、`/scripts` 個人管理頁仍混用兩種變形：

- `/agents`、`/skills`、`/scripts`：前綴 `排序：` + chip `由新到舊 / 由舊到新`（前綴未對齊軸命名）
- `/admin/models`：前綴 `排序：` + chip `最新 / 最舊`（chip label 也是舊短形式）

§6 殘留段落原本標記為「暫留決策，待使用者要求再開 task」，本回合使用者明確要求現在統一。

根因：v1.2.5 新增規範 `11-ui-ux.md § 排序 chip 慣例` 時保留「單軸場景可用短形式雙 chip」例外；fixed.md §6 改寫 dashboard 為多軸後未一併遷移其他頁面，造成風格分裂。

**修正**：

1. **四個列表頁前綴 / chip label 統一**：
   - `/agents`、`/skills`、`/scripts`：`排序：` → `按時間：`（chip label 已對齊不動）
   - `/admin/models`：`排序：` → `按時間：`，chip label `最新` → `由新到舊`、`最舊` → `由舊到新`
2. **`11-ui-ux.md § 排序 chip 慣例` 規範統一**：
   - 移除「單軸排序短形式雙 chip」例外
   - 改寫為「全站一律採用軸前綴 + 方向 chip」原則
   - 單軸場景仍渲染 `按時間：` 一列；多軸場景每軸獨立一列縱向堆疊
   - 範例參考更新為四個個人 / admin 列表頁 + dashboard

**影響檔案**：

- `docs/Design-Base/11-ui-ux.md`（§ 排序 chip 慣例 改寫）
- `frontend/src/app/(main)/agents/page.tsx`
- `frontend/src/app/(main)/skills/page.tsx`
- `frontend/src/app/(main)/scripts/page.tsx`
- `frontend/src/app/(main)/admin/models/page.tsx`

**驗證方式**：

- `grep -rn "排序：" frontend/src/app` 應僅命中 `agent-templates/page.tsx` L550、`agent-languages/page.tsx` L308 兩處（皆為 `{x.sort_order}` 資料欄位顯示，非排序 chip 前綴），無「排序：」前綴殘留於排序 chip 上下文
- 四個列表頁實測排序行為：點「由舊到新」列表確實按 `created_at asc` 重排

**交叉引用**：本條結清 §6 殘留段落「`/admin/models` 與其他頁面既有排序 UI 未同步遷移」。

---

## 10. Agent 下載 / 收藏在儀錶板與管理頁顯示落差，Script 上傳描述應為必填  〔2026-04-25 09:17:38〕

**問題**：

1. **下載 Agent 不計數**：`agent_service.download_agent()` 直接回傳 markdown，未呼叫 `try_increment_download`，`Agent.download_count` 恆為 0，且關聯 Skills 也未連動。
2. **儀錶板公開列表缺收藏 / 下載數與收藏按鈕**：`/dashboard` 三個公開頁籤的 row 整列為 `<Link>`，沒有 `SocialMetrics` 也沒有 `FavoriteButton`，使用者切「按熱度／按收藏」排序卻看不到對應數值，也無法直接收藏。
3. **Agents 管理頁缺下載數**：`/agents` 兩處 `SocialMetrics` 只傳 `favoriteCount`，未傳 `downloadCount`，與 Skills / Scripts 管理頁不一致。
4. **Script 上傳「描述」應為必填**：原 `ScriptUploadDialog` 描述欄為選填（placeholder `（選填）`）、後端 `Form(None)`，與本輪確認的規格不符。

**根因**：

- v1.2.1 §7 規格原訂「Agent 的 `download_count` 恆為 0（保留欄位，前端可隱藏），未來 export / import 用」— 但 Agent 下載已實作 `AGENTS.md` 產出（含關聯 Skills 清單），實質為使用行為，原規格已不適用。
- 儀錶板與 Agents 管理頁的 `SocialMetrics` / `FavoriteButton` 在 v1.2.4 跨頁實作時未統一收尾。
- Script 描述必填規格本輪確認，前後端原本皆允許空。

**修正**：

- **後端**：
  - `agent_service.download_agent()` 結尾呼叫 `download_service.try_increment_download("agent", ...)`，並對所有未軟刪的關聯 Skills 各自 `try_increment_download("skill", ...)`（連動下載；收藏不連動，dedup keys 各自獨立）。
  - `scripts/router.py` `description` 由 `Form(None, ...)` 改 `Form(..., ...)`，`script_service.create_script()` 簽名 `description: str` + 空字串 raise 422。
- **前端**：
  - `/dashboard` 的 AgentRow / SkillRow / ScriptRow 拆掉外層 `<Link>` 改為 RankingRow 同款結構（容器 `<div>` + 標題獨立 `<Link>` + `SocialMetrics` + `FavoriteButton`），三個 row 都顯示對應收藏 / 下載數。
  - `RankingPanel` 移除 `showDownload` prop 與 `item.type !== "agent"` 判斷，所有類型一致顯示下載數。
  - `/agents` 兩處 `SocialMetrics` 補上 `downloadCount`。
  - `ScriptUploadDialog`：描述 label 加紅色 `*`、placeholder 改「輸入 Script 描述」、新增 `descriptionError` state、submit 驗證、payload 直接送 trim 字串。
- **文件**：`tasks-v1.2.1.md` 規範表 #7 加註「已改為下載即計數，並連動關聯 Skills；收藏不連動」。

**影響檔案**：

- 後端：`backend/app/services/agent_service.py`、`backend/app/services/script_service.py`、`backend/app/api/v1/scripts/router.py`
- 前端：`frontend/src/app/(main)/dashboard/page.tsx`、`frontend/src/app/(main)/agents/page.tsx`、`frontend/src/app/(main)/scripts/ScriptUploadDialog.tsx`、`frontend/src/components/dashboard/RankingPanel.tsx`
- 文件：`docs/Tasks/v1.2/tasks-v1.2.1.md`

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
| 7 | 收藏 API 500 — `update` shadow 修正 + favorite_service helper 抽出 | ✅ 已修 | — 待 commit-all |
| 8 | /scan-project 規範落差批量修補（Design-Base + 程式碼層） | ✅ 已修 | — 待 commit-all |
| 9 | 排序 chip 全站統一為「軸前綴 + 方向 chip」格式（結清 §6 殘留） | ✅ 已修 | — 待 commit-all |
| 10 | Agent 下載連動 Skills 計數 + 儀錶板 / 管理頁收藏下載顯示一致化 + Script 描述必填 | ✅ 已修 | — 待 commit-all |

---

## 殘留清理項

§4 / §5 已於 v1.2.5 完成（詳見 `tasks-v1.2.5.md`）：

- §4 公開 Scripts 頁籤 + Script `visibility` 欄位 — ✅ 已於 v1.2.5 完成
- §5 公開頁籤排序切換 chip + Ranking API `order` 參數 — ✅ 已於 v1.2.5 完成（chip 標籤表已於 §6 推翻）
- §6 `/admin/models` 等其他頁面排序 UI 是否需統一至多軸分向格式 — 暫留決策
