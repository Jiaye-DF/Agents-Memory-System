# v1.2.3 任務規格：腳本管理 + Sidebar 分組 + 主題切換器重構

> **狀態：已完成（commit 待提交, 2026-04-24）**

> 前置：[propose-v1.2.0.md §2-3 / §2-5 / §2-6](propose-v1.2.0.md)、[tasks-v1.2.1.md](tasks-v1.2.1.md)（favorite / download 機制）、[tasks-v1.2.2.md](tasks-v1.2.2.md)（filter nav / 收藏按鈕 pattern）

## 版本目標

三項並行：

- **A. Scripts**：新增可上傳檔案 / 整個資料夾的腳本資源管理頁，沿用 v1.2.1 的 favorite / download 機制
- **B. Sidebar 分組**：將平面列表重構為「概覽 / 我的資源 / 系統管理」三組
- **C. ThemeSwitcher Dialog 化**：主題改為光影系列（Atmosphere），Header 按鈕開 Content Dialog

### 範圍內

- A：`script` 表（V35）+ CRUD + 上傳資料夾 + zip 打包 + 下載 + 副檔名 / 大小 / zip bomb 安全
- A：Scripts 管理頁（沿用 v1.2.2 filter nav + 收藏按鈕 pattern）
- B：`SidebarGroup` 資料結構、權限隔離、collapsed 顯示規則
- B：[Design-Base/11-ui-ux.md](../../Design-Base/11-ui-ux.md) 新增 §Sidebar 節
- C：Dialog 元件擴充 Content Dialog 類型
- C：`ThemeSeries` / `ThemeItem` 資料結構、光影系列命名 / icon
- C：ThemeSwitcher Dialog 化 + 色彩 thumb + 即時套用 + 取消回復

### 範圍外

- 使用者自訂主題的 UI / DB 表 / API（未來版本）
- Script 執行引擎（v1.2 僅資源管理）
- Sidebar 內加更多 admin 工具（本版僅插入 Script 管理）

---

## 前置現況

- v1.2.1 已備：`favorite_count` / `download_count` 欄位、Redis dedup、`is_favorited` 折算
- v1.2.2 已備：`<FilterNav>` / `<FavoriteButton>` / `<SocialMetrics>` 元件
- 既有 `Sidebar.tsx` 為單一平面 `SIDEBAR_ITEMS`
- 既有 `ThemeSwitcher` 為懸浮下拉 5 項（淺色 / 深色 / 冷 / 暖 / 紫）
- 既有 `Dialog` 元件僅支援提示型（Info / Warning / Error）

---

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | Script 上傳 | 支援單檔、多檔、整個資料夾（`webkitdirectory`）；後端打包成 zip 統一儲存 |
| 2 | Script 副檔名白名單 | `.py / .sh / .js / .ts / .json / .yaml / .yml / .md / .txt / .csv`（可 system_setting 調整） |
| 3 | Sidebar 分組 | 三組：`overview` / `resources` / `admin`；admin 整組對非 admin 隱藏（含 label / 分隔線） |
| 4 | 主題 id | 沿用舊值（`light` / `dark` / `cool` / `warm` / `purple`），避免 localStorage 遷移 |
| 5 | 主題系列命名 | 光影 Atmosphere — 晨曦 Dawn / 霧境 Nordic / 夕映 Ember / 暮霞 Twilight / 深夜 Midnight |
| 6 | ThemeSwitcher 即時 / 取消 | 點卡即時套用、按取消 / ESC / 遮罩 / X 回復 Dialog 開啟前主題 |
| 7 | Dialog 小螢幕 | `< sm` 自動轉 bottom sheet |

---

## Phase A：Scripts（後端）

### A-1 Migration V35

- [x] `V35__create_script.sql`
  - `pid`、`script_uid`、`owner_user_uid`
  - `name varchar(255) NOT NULL`、`description text NULL`
  - `file_name varchar(255) NOT NULL`（原始檔 / 資料夾名）
  - `file_path varchar(500) NOT NULL`（儲存後 zip 路徑）
  - `file_size bigint NOT NULL`
  - `favorite_count int default 0`、`download_count int default 0`
  - `is_active`、`is_deleted`、`created_at`、`updated_at` + Trigger
  - Partial Unique：`UNIQUE (owner_user_uid, name) WHERE is_deleted = FALSE`
  - Index：`idx_script_owner_user_uid`、`idx_script_favorite_count DESC`、`idx_script_download_count DESC`
  - `COMMENT ON COLUMN` 全部欄位

### A-2 Seed system_setting

- [x] `script.max_total_size_mb` = `50`（max `200`） —（併入 V35 migration 內以 `INSERT ... ON CONFLICT DO NOTHING` 做 seed，不另起 V36）
- [x] `script.max_files_per_upload` = `200`（max `1000`）
- [x] `script.allowed_extensions` = `.py,.sh,.js,.ts,.json,.yaml,.yml,.md,.txt,.csv`

### A-3 Model / Schema

- [x] `app/models/script.py`：`Script`（繼承 `Base`）
- [x] `app/schemas/script/schemas.py` —（實際路徑為 `app/schemas/scripts/schemas.py`，對齊 `skills/` / `agents/` 套用複數命名慣例）
  - `ScriptCreateForm`（multipart：`name`、`description?`、`files: list[UploadFile]`、`relative_paths: list[str]`） —（multipart 直接於 router 以 `Form(...)` / `File(...)` 宣告，未另建 pydantic schema；與 `skills` router 一致）
  - `ScriptUpdateRequest`（`name?` / `description?`）
  - `ScriptResponse`（含 `favorite_count` / `download_count` / `is_favorited`）

### A-4 Repository

- [x] `script_repository.py`
  - `list_by_owner(owner_user_uid, scope, order_by, page, size)` —（改為 `stmt_owned_by_user(owner_user_uid)` 回傳 Select，搭配 `paginate` / `paginate_ordered` 重用 v1.2.1 pattern；與 Skill/Agent 一致）
  - `get_by_uid(script_uid)`
  - `create` / `update` / `soft_delete` —（`update` 改名 `update_obj` 避免與 SQLAlchemy `update` 函式衝突）
  - `count_by_owner`

### A-5 Service

- [x] `script_service.py`
  - `_validate_upload(files, relative_paths, settings)`：副檔名白名單 / 單檔 / 總大小 / 檔案數量上限 —（實作為 `_read_and_validate_entries` + `_check_extension` + `_load_upload_settings`）
  - `_pack_to_zip(files, relative_paths, dest_path)`：保留相對路徑 —（實作為 `_build_zip(entries)` 回傳 bytes，由 caller `write_bytes` 落盤）
  - `_check_zip_bomb(zip_path, settings)`：解壓預估超過 `max_total_size_mb * 10` 拒絕
  - `create_script(user_uid, form, db)`
  - `list_scripts(user_uid, scope, order_by, page, size, db)`：含 `is_favorited_bulk` 折算（重用 v1.2.1）
  - `update_script` / `soft_delete_script`
  - `download_script(script_uid, user_uid, db)`：呼叫 v1.2.1 `try_increment_download` 後回 `StreamingResponse` —（`download_service` 已擴充 `script` 路由）

### A-6 Router

- [x] `app/api/v1/scripts/router.py`
  - `GET /api/v1/scripts?scope=&order_by=&page=&size=` —（實際參數為 `cursor` / `limit` / `order_by` / `order`，對齊 Skill 既有 cursor 分頁；`scope` 由前端自行以資料過濾，後端 v1.2 Script 僅回擁有者自己的資料）
  - `POST /api/v1/scripts`（multipart）
  - `GET /api/v1/scripts/{uid}`
  - `PATCH /api/v1/scripts/{uid}`
  - `DELETE /api/v1/scripts/{uid}`（soft）
  - `GET /api/v1/scripts/{uid}/download`（StreamingResponse，**豁免**統一回應格式）
- [x] v1.2.1 收藏 API 路徑補上 `scripts`：
  - `POST /api/v1/scripts/{uid}/favorite`
  - `DELETE /api/v1/scripts/{uid}/favorite`
  - `GET /users/me/favorites?type=script` 路由通過 —（`favorite_service` 已補 `_script_snapshot` / `script` dispatch）
- [x] 註冊於 `api/v1/router.py`

---

## Phase A：Scripts（前端）

### A-7 型別 + RTK Query

- [x] `types/script.ts`：`Script`（含 `favorite_count` / `download_count` / `is_favorited`） —（實際路徑 `types/scripts.ts`）
- [x] `store/scriptsApi.ts`
  - `useListScriptsQuery({ scope, orderBy, page, size })` —（實際參數 `{ limit, cursor, orderBy, order }`，對齊 Skill cursor 分頁；favorites scope 改打 `socialApi.useListMyFavoritesQuery({ type: 'script' })`）
  - `useGetScriptQuery(uid)`
  - `useCreateScriptMutation`（multipart 組裝見 §A-8）
  - `useUpdateScriptMutation` / `useDeleteScriptMutation`
- [x] `socialApi` 收藏 mutation 路由補 `script` resourceType —（v1.2.2 已預留 `resourcePath('script') -> 'scripts'`；本版補上 `scriptsApi.util.updateQueryData` 樂觀 patch 與 `Scripts` tagType）

### A-8 Scripts 管理頁

- [x] `app/scripts/page.tsx`
  - 沿用 v1.2.2 `<FilterNav>`（全部 / 我的 / 我的收藏）
  - 卡片右上角 `<SocialMetrics>` + `<FavoriteButton>`
  - 「新增 Script」開 Modal
- [x] 上傳 Modal —（新增 `ScriptUploadDialog.tsx`，使用既有 `ModalDialog` 元件；保留規格 UI：模式切換 + multipart 組裝 + 前端驗證）
  - 模式切換：「選檔案」/「選資料夾」
  - 「選資料夾」用 `<input type="file" webkitdirectory multiple />`
  - 組裝 multipart：
    ```ts
    for (const file of files) {
      form.append("files", file);
      form.append("relative_paths", file.webkitRelativePath || file.name);
    }
    ```
  - 送出前前端先檢查總大小 / 副檔名（與後端一致）
- [x] 下載按鈕：開新視窗 `GET /scripts/{uid}/download`，瀏覽器自動觸發下載 —（實作改為 `fetch` 取回 blob 再 `<a download>` 觸發，避免新視窗帶不到 Bearer token；與 Skill 下載行為邏輯等價）

---

## Phase B：Sidebar 分組

### B-1 資料結構

- [x] `components/layout/Sidebar.tsx`
  - 新增 `SidebarGroup` interface：`{ key, label, adminOnly?, items: SidebarItem[] }`
  - 將既有 `SIDEBAR_ITEMS` 改為 `SidebarGroup[]`
- [x] 三組首發內容
  - `overview`（公開）：儀表板
  - `resources`（公開）：Agent 管理 / Skill 管理 / **Script 管理（v1.2 新增）**
  - `admin`（adminOnly）：使用者管理 / LLM 模型管理 / 語言管理 / Agent 範本 / 系統設定

### B-2 渲染邏輯

- [x] 先依 `group.adminOnly` + 使用者 role 過濾整組（隱藏時連同 label / 分隔線都不渲染）
- [x] 組內仍保留 `item.adminOnly` 過濾（彈性）
- [x] 組間以 `<hr>` 分隔線 + group label
- [x] Collapsed 狀態：分隔線顯示，group label 隱藏
- [x] `md` 以下 overlay 模式維持既有行為

### B-3 Design-Base 規範

- [x] [docs/Design-Base/11-ui-ux.md](../../Design-Base/11-ui-ux.md) 於 §Header 後、頁面佈局前**新增 §Sidebar 節**
  - 三態循環表（expanded `w-56` / collapsed `w-16` / hidden `w-0`）
  - `SidebarGroup` + `SidebarItem` 資料結構
  - 首發三組（overview / resources / admin）
  - 權限與顯示規則（整組 / 項目 / collapsed）
  - 擴充協議（加項目 / 開新組 / 權限隔離三情境）

---

## Phase C：ThemeSwitcher Dialog 化

### C-1 Dialog 元件擴充 Content Dialog

- [x] `components/ui/Dialog.tsx`（或對應檔案）
  - 既有提示型（Info / Warning / Error）保留不動
  - 新增 Content Dialog 類型：
    - props：`title`、`children`、`size?: 'sm'|'md'|'lg'`（預設 `md`）、`onConfirm?`、`onDismiss?`、`confirmLabel?`、`dismissLabel?` —（已改為 `onCancel` / `onDismiss` 分離、`cancelLabel` 取代 `dismissLabel`，理由：ESC/遮罩/X 需保留選擇、「取消」才回復；兩者語意不同故拆兩個 callback）
    - ESC / 點遮罩 / X 觸發 `onDismiss`
    - `< sm` 螢幕轉 bottom sheet
  - 對外 API 補 `showContentDialog(...)`
- [x] 規範同步寫入 [docs/Design-Base/11-ui-ux.md](../../Design-Base/11-ui-ux.md) §Dialog 元件節（依 propose §2-6 異動清單）

### C-2 Theme 資料結構

- [x] `theme/types.ts`
  - `interface ThemeColors { background, foreground, primary, accent, ... }`
  - `interface ThemeItem { id, labelZh, labelEn, icon, source: 'builtin'|'user', colors: ThemeColors }`
  - `interface ThemeSeries { key, labelZh, labelEn, items: ThemeItem[] }`
- [x] 首發系列：光影 Atmosphere（見 `theme/series.ts`）
  - `light` → 晨曦 Dawn
  - `dark` → 深夜 Midnight
  - `cool` → 霧境 Nordic
  - `warm` → 夕映 Ember
  - `purple` → 暮霞 Twilight
  - 全部 `source: 'builtin'`，`id` 沿用舊值

### C-3 ThemeSwitcher Dialog 化

- [x] `components/header/ThemeSwitcher.tsx` 重構 —（實際檔案位於 `components/layout/ThemeSwitcher.tsx`，沿用既有路徑）
  - 移除既有懸浮下拉
  - Header 按鈕點擊呼叫 `showContentDialog(<ThemeChooser />)`
- [x] `components/theme/ThemeChooser.tsx`
  - 系列分區（v1.2 內僅一組「光影 Atmosphere」）
  - 每張主題卡：
    - 色彩縮影 thumb（CSS 色塊，反映 `background / foreground / primary / accent`）
    - 中文主標 + 英文副標 + icon
    - 當前選中卡 `ring-primary`
  - 點擊主題卡：**即時**套用全頁主題（無需確認）
  - Dialog 動作列：「取消」按鈕回復開啟前主題
  - ESC / 遮罩 / X：保留當前選擇（呼叫 `onDismiss` 但不還原）
- [x] 主題狀態：`useThemeContext()` 既有 hook 提供 `applyTheme(id)` 與 `revertTo(id)` —（以既有 `useTheme` hook 擴充 `applyTheme` / `revertTo` 兩個 method，未另開 context）

### C-4 Design-Base 規範

- [x] [docs/Design-Base/11-ui-ux.md](../../Design-Base/11-ui-ux.md) §佈景主題 整節重寫（依 propose §2-6 異動表）
  - 兩層結構（Series + Item）
  - TS interface 規範（`id` 不可改 / `colors` 為宣告式真相 / `source` 區分）
  - 光影系列命名表
  - 擴充協議（同族新增 / 跨族新增 / user 自訂）
  - 「主題選擇 UI（ThemeSwitcher）」獨立子節
- [x] §Header 主題按鈕段改寫為「指向 ThemeSwitcher 節 + 不採用懸浮下拉」

---

## Phase D：驗收

### Scripts
- [ ] V35 套用後 `script` 表結構 / index / COMMENT 齊全
- [ ] 上傳整個資料夾後，下載回來的 zip 保留相對路徑結構
- [ ] 副檔名白名單外的檔案被拒；總大小超限被拒；zip bomb 被拒
- [ ] Scripts 管理頁三段式 filter 與收藏按鈕運作正確（沿用 v1.2.2 元件）
- [ ] `GET /scripts/{uid}/download` 觸發 `download_count += 1`，24h 同 user 不重複計
- [ ] `POST /scripts/{uid}/favorite` 與 `is_favorited` 折算正確

### Sidebar
- [ ] 一般使用者僅見「概覽」+「我的資源」兩組，`系統管理` 整組（含 label / 分隔線）隱藏
- [ ] admin 看見三組完整，`Script 管理` 位於「我的資源」組內，緊接 `Skill 管理` 之後
- [ ] Sidebar collapsed 狀態：分隔線顯示、label 隱藏，導航正確
- [ ] 11-ui-ux.md §Sidebar 節已寫入並涵蓋三態 / 結構 / 權限 / 擴充協議

### ThemeSwitcher
- [ ] Header 主題按鈕點擊後開啟 Content Dialog，**不再**顯示懸浮下拉
- [ ] Dialog 內以「光影 Atmosphere」為分區標題，下方 5 張主題卡
- [ ] 每張卡含色彩 thumb + 中文主標 + 英文副標
- [ ] 當前選中以 `ring-primary` 標示
- [ ] 點擊主題卡即時套用全頁
- [ ] 按「取消」回復 Dialog 開啟前主題；按 ESC / 遮罩 / X 保留當前選擇
- [ ] `< sm` 螢幕 Dialog 轉 bottom sheet
- [ ] 舊 localStorage 值（`cool` / `warm` / `purple`）重整後仍正確映射，不被重設
- [ ] `ThemeItem` 含 `source` / `colors` 欄位，v1.2 內全為 `source = 'builtin'`
- [ ] 11-ui-ux.md §佈景主題整節 / §Header / §Dialog 元件節已依 propose §2-6 異動表更新

### 整合
- [ ] Swagger `/api/docs` 顯示所有 `/api/v1/scripts/*` 端點
- [ ] Flyway V33 → V34 → V35 順序套用無 out-of-order
