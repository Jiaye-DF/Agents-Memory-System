# v1.2.5 任務規格：v1.2 殘留補完（Script `visibility` + 公開 Scripts 頁籤 + 排序 chip）

> **狀態：已完成（commit 待提交, 2026-04-24）**

> 前置：[propose-v1.2.0.md §2-1 / §2-4](propose-v1.2.0.md)、[tasks-v1.2.3.md](tasks-v1.2.3.md)（Script 基礎）、[tasks-v1.2.4.md](tasks-v1.2.4.md)（Ranking API）
>
> 對應 fixed.md：[§4](fixed.md)（公開 Scripts 頁籤 + Script `visibility`）、[§5](fixed.md)（公開頁籤排序切換 + Ranking API `order`）

## 版本目標

補齊 v1.2 實作完之後暴露出來的 propose-v1.2.0 規格落差：

- `script` 表欄位與 `agent` / `skill` 對齊：新增 `visibility`，使 Script 可區分「私人」與「公開」
- 儀錶板公開資源瀏覽區補齊第三類 **公開 Scripts 頁籤**，與 §2-4 類型切換一致
- 公開 Agents / Skills / Scripts 頁籤加入排序 chip（**最新 / 最舊 / 最熱門 / 最冷門 / 最多收藏 / 最少收藏**，6 顆平鋪、**禁用 toggle / 方向符號 / asc-desc 英文**）
- Ranking API 擴 `order=asc|desc` 參數（propose §2-1 已定該形態，§2-4 漏列）
- Design-Base `11-ui-ux.md` 補「排序 chip 慣例」規範，鎖定語意化對稱命名原則

### 範圍內

- DB：V37 migration `script.visibility` 欄位（對齊 V5 / V7 的 `CHECK (visibility IN ('public','private'))` + DEFAULT `'private'`）
- 後端：Script schema / repository / service / router 擴 `visibility`；Ranking API 擴 `order`
- 前端：
  - `/scripts` 管理頁卡片 / 新增 / 編輯 Modal 加 `visibility` 欄位
  - `/dashboard` 第三個「公開 Scripts」頁籤
  - 公開頁籤共用排序 chip 列（6 顆，類型切換時保留選擇）
  - RTK Query hooks 補 `order` 傳遞
- 規範：`11-ui-ux.md` 新增「排序 chip 慣例」子節

### 範圍外

- 跨使用者訂閱 / 追蹤 / 推播（→ v1.4 公開 API / API Key）
- Script 可見性審核流程（Agentic Skill 審核機制不延伸到 Script）
- 「本週 / 本月」時效窗排行（→ 未來觀察後再評估）
- AI 語意排行 / 推薦（→ v1.4）
- 排序 chip 的**組合記憶**（不做 localStorage 持久化，重新進頁面預設回「最新」）

---

## 前置現況

- **v1.1 既有**：`agent` / `skill` 表有 `visibility VARCHAR(10) NOT NULL DEFAULT 'private' CHECK (visibility IN ('public','private'))`
- **v1.2.3 已備**：`script` 表建立（V35），但**沒有** `visibility` 欄位
- **v1.2.4 已備**：`GET /api/v1/dashboard/rankings` endpoint，但寫死 `desc`，僅 `order_by` 參數
- **v1.2.2 已備**：`/agents` / `/skills` 管理頁 `<FilterNav>` 三段；`/admin/models` L741-755 有既有「排序：最新 / 最舊」雙 chip pattern 可參考
- **v1.2 fixed.md §2**：已將「你最常用的」面板的排序切換移除，僅保留類型切換；副標明確寫「公開熱度／收藏排行將整合至公開 Agents／Skills／Scripts 頁籤」
- **Dashboard 既有**：`frontend/src/app/(main)/dashboard/page.tsx` L13 `TabKey = "agents" | "skills"`；`publicAgents` / `publicSkills` 以前端 `filter(item.visibility === 'public')` 實現

---

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | `script.visibility` 預設值 | `'private'` — 使用者主動公開，不改變既有 Script 行為 |
| 2 | Dashboard 公開頁籤的 filter 切換 | **不做** — 維持 GitHub Explore 風格單純瀏覽，`全部 / 我的 / 我的收藏` 只屬於管理頁 |
| 3 | 排序 chip UI 形態 | `<FilterChip>` 6 顆**平鋪**、單選、**禁用 toggle / 升降箭頭 / asc-desc 英文** |
| 4 | 排序 chip 命名 | 語意化對稱中文詞：最新 / 最舊 / 最熱門 / 最冷門 / 最多收藏 / 最少收藏 |
| 5 | 排序 chip 位置 | 類型頁籤下方、搜尋框 + 作者 filter **下方**、列表上方 |
| 6 | 排序狀態作用域 | 公開 Agents / Skills / Scripts 三頁籤**共用同一 state**，切換類型時保留選擇；重新進頁面重置為「最新」 |
| 7 | Ranking API `order` 預設 | `desc`（向後相容既有 `/dashboard/rankings` 呼叫） |
| 8 | Agent `download_count` 排序行為 | 恆為 0，選「最熱門 / 最冷門」時 Agent 分別排尾 / 排前（自然發生，不特別處理） |
| 9 | 列表 API `order` 後端 | v1.2.1 + v1.2.3 已實作，僅前端 RTK hook 需補傳遞 |
| 10 | 既有 Script 資料處理 | V37 套用後所有既有 row 自動帶 `visibility='private'`（DEFAULT），不做 data migration |

---

## Phase 0：Migration

### 0-1 V37：script 加 visibility 欄位

- [x] `migrations/sql/V37__add_script_visibility.sql`
  - `ALTER TABLE script ADD COLUMN visibility VARCHAR(10) NOT NULL DEFAULT 'private'`
  - `ALTER TABLE script ADD CONSTRAINT chk_script_visibility CHECK (visibility IN ('public','private'))`
  - `COMMENT ON COLUMN script.visibility IS '可見性：public（公開）或 private（私人）'`

---

## Phase 1：Backend

### 1-1 Script Model / Schema

- [x] `backend/app/models/script.py` 加 `visibility: Mapped[str]` 欄位（對齊 `agent.py` / `skill.py` 寫法）
- [x] `backend/app/schemas/scripts/schemas.py`：
  - `ScriptResponse` 加 `visibility: Literal["public","private"]`
  - `ScriptCreateForm` 加選擇性 `visibility`（預設 `'private'`）
  - `ScriptUpdateRequest` 加 `visibility: Optional[...]`（對齊既有可選欄位 pattern）

### 1-2 Script Repository / Service

- [x] `backend/app/repositories/script_repository.py`：
  - `list_by_owner` 既有行為不動（回使用者自己的資源）
  - **新增** `list_public(order_by, order, page, size, db)`：`WHERE is_deleted=FALSE AND visibility='public'`
  - `create` / `update` 支援 `visibility` 欄位
- [x] `backend/app/services/script_service.py`：
  - `create_script` / `update_script` 接受 `visibility`，未給則用 DB DEFAULT
  - **新增** `list_public_scripts(user_uid, order_by, order, page, size, db)`：呼叫 repo `list_public`，加 `is_favorited_bulk` 折算（user_uid 為 current user）

### 1-3 Scripts Router

- [x] `backend/app/api/v1/scripts/router.py`：
  - `GET /api/v1/scripts` 既有 list 行為不動
  - **新增** `GET /api/v1/scripts/public?order_by=&order=&page=&size=` — 呼叫 `list_public_scripts`
  - `POST /api/v1/scripts` multipart 接受 `visibility` 欄位
  - `PATCH /api/v1/scripts/{uid}` 接受 `visibility`
  - 所有回傳 `ScriptResponse` 含 `visibility`

### 1-4 Ranking API 擴 `order` 參數

- [x] `backend/app/api/v1/dashboard/router.py`：
  - Query 加 `order: Literal["asc","desc"] = Query("desc", ...)`
  - 傳入 `dashboard_service.list_rankings`
- [x] `backend/app/services/dashboard_service.py`：
  - `list_rankings(user_uid, type_filter, order_by, order, limit, db)`
  - 三類資源各自 top N query 依 `order` 決定排序方向
  - 合併後重排亦依 `order`
  - `order_by='created_at'` 時保持時間排序語意正確

### 1-5 公開 Agents / Skills 列表端點確認

- [x] 檢查 `GET /api/v1/agents` 和 `/api/v1/skills` 是否已回傳 `visibility` 欄位給列表呼叫者；若無，於 `AgentResponse` / `SkillResponse` 同步露出（dashboard 既有已依賴前端 filter，若後端已回則此項跳過）
- [x] 確認 `GET /api/v1/agents?order_by=&order=` 參數實際已生效，否則補

---

## Phase 2：Frontend

### 2-1 型別擴充

- [x] `frontend/src/types/scripts.ts`：`Script` 加 `visibility: "public"|"private"`；`ScriptUpdateRequest` 加 `visibility?`；`ScriptCreateParams` 加 `visibility?`
- [x] `frontend/src/types/agents.ts` / `skills.ts`：若 `Agent` / `Skill` 型別未明確標 `visibility`，補型別宣告
- [x] `frontend/src/types/dashboard.ts`：`RankingType` 相關 alias 既有、僅 hook 參數擴 `order`

### 2-2 RTK Query

- [x] `frontend/src/store/scriptsApi.ts`：
  - `useListScriptsQuery` 參數既有不動
  - **新增** `useListPublicScriptsQuery({ orderBy, order, page?, size? })` 打 `/api/v1/scripts/public`
  - `useCreateScriptMutation` / `useUpdateScriptMutation` multipart / body 攜帶 `visibility`
- [x] `frontend/src/store/agentsApi.ts` / `skillsApi.ts`：`useListAgentsQuery` / `useListSkillsQuery` 參數補 `orderBy` / `order`（既有可能只有 `scope`）
- [x] `frontend/src/store/dashboardApi.ts`：`useGetRankingsQuery({ type, orderBy, order, limit? })` 加 `order`

### 2-3 Scripts 管理頁加 visibility

- [x] `frontend/src/app/(main)/scripts/page.tsx`：卡片顯示 `visibility` badge（`public` 顯示「公開」、`private` 不顯示或顯示「私人」— 與 Agents / Skills 管理頁既有 pattern 對齊）
- [x] `frontend/src/app/(main)/scripts/ScriptUploadDialog.tsx`：加 `visibility` 單選（public / private），預設 `private`
- [x] 編輯 Script Modal（若既有）：同樣支援切換 `visibility`

### 2-4 Dashboard 第三個頁籤「公開 Scripts」

- [x] `frontend/src/app/(main)/dashboard/page.tsx`：
  - `TabKey = "agents" | "skills" | "scripts"`
  - 新增 `useListPublicScriptsQuery` 呼叫；或沿用 `useListScriptsQuery` + 前端 filter `visibility==='public'`（與 Agents / Skills 現行做法一致，決策看 §1-2 `list_public_scripts` 是否走專屬端點）—（實作選擇**前端 filter** 沿用 `useListScriptsQuery`，與 Agents / Skills 對稱；後端 `/scripts/public` 端點仍建立（§1-3），保留未來切換的可能）
  - `publicScripts` useMemo
  - 新增 `<TabButton>公開 Scripts ({publicScripts.length})</TabButton>`
  - 新增 `ScriptRow` 元件或沿用 `AgentRow` / `SkillRow` 結構
  - `activeTab === "scripts"` 時的 `manageHref = "/scripts"`、`manageLabel = "Scripts"`
  - `currentAuthors` / `filteredScripts` 同既有兩頁 pattern

### 2-5 排序 chip 列（公開頁籤專用）

- [x] 新增共用 hook `useRankingSort`（或直接於 dashboard 頁內宣告 state）：
  - `sort: { orderBy: 'created_at'|'download_count'|'favorite_count', order: 'asc'|'desc' }`
  - 預設 `{ orderBy: 'created_at', order: 'desc' }`
- [x] `frontend/src/app/(main)/dashboard/page.tsx` 排序 chip 段落：
  - 位置：類型頁籤之下、搜尋框 + 作者 filter 之下
  - 結構沿用 `/admin/models/page.tsx` L741-755 pattern：
    ```tsx
    <div className="flex flex-wrap items-center gap-2">
      <span className="shrink-0 text-sm text-muted">排序：</span>
      <FilterChip active={...} onClick={...}>最新</FilterChip>
      ... 6 顆
    </div>
    ```
  - 6 個 chip 標籤 / state mapping：

    | chip 標籤 | `orderBy` | `order` |
    | --- | --- | --- |
    | 最新 | `created_at` | `desc` |
    | 最舊 | `created_at` | `asc` |
    | 最熱門 | `download_count` | `desc` |
    | 最冷門 | `download_count` | `asc` |
    | 最多收藏 | `favorite_count` | `desc` |
    | 最少收藏 | `favorite_count` | `asc` |

- [x] `FilterChip` 若為 `/admin/models` 頁本地元件，考慮是否提升到 `frontend/src/components/ui/FilterChip.tsx` 共用（若 v1.2.2 的 `FilterNav` 已 export 類似元件，優先複用；避免重複實作）

### 2-6 排序 chip 串接資料

- [x] 三頁籤各自的 `useListAgentsQuery` / `useListSkillsQuery` / `useListPublicScriptsQuery` 呼叫時帶入 `orderBy` / `order` —（第三頁籤改用 `useListScriptsQuery` + 前端 filter，見 §2-4）
- [x] 切換類型時**保留 sort state**（不重置），避免每切一次類型都回「最新」
- [x] 搜尋 + 作者 filter 仍以前端 `filter(matchItem(...))` 套用於 API 已排序的結果上（排序在 API、篩選在前端，維持既有 dashboard pattern）

### 2-7 Ranking Panel（「你最常用的」）確認

- [x] `frontend/src/components/dashboard/RankingPanel.tsx` 既有已移除排序切換（fixed.md §2），本版**不動**（「你最常用的」仍以 `order_by=download_count`、`order=desc` 固定呼叫）
- [x] 若 `useGetRankingsQuery` 因 §2-2 hook 簽名變化而 TypeScript error，補預設 `order: 'desc'` 即可

---

## Phase 3：Design-Base 規範補充

### 3-1 11-ui-ux.md 新增「排序 chip 慣例」

- [x] `docs/Design-Base/11-ui-ux.md` 於「篩選 / Chip 元件」段落（若不存在則新建）**新增子節 §排序 chip 慣例**：
  - **用途**：單軸時間排序 / 雙軸（數值 × 方向）混合排序
  - **元件**：沿用既有 `<FilterChip>` / `<FilterNav>`，禁用方向箭頭 toggle
  - **前綴標籤**：一律 `<span className="shrink-0 text-sm text-muted">排序：</span>`
  - **命名原則**（語意化對稱中文詞）：
    - 時間：**最新 / 最舊**
    - 下載熱度：**最熱門 / 最冷門**
    - 收藏熱度：**最多收藏 / 最少收藏**
    - 後續加新維度時，延伸同樣對稱化語意詞（禁用 ↑↓、asc/desc、由高到低、由低到高 等方向 / 英文表述）
  - **單選 vs toggle**：chip 數量 ≤ 2 可單選（如 `/admin/models` 的最新 / 最舊）；> 2 一律平鋪、單選切換、不用 toggle
  - **範例參考**：`/admin/models` L741-755（單軸雙 chip）、`/dashboard` 公開頁籤（雙軸 6 chip）
- [x] 若 `11-ui-ux.md` 已有 §Filter / §Chip 節，將上述內容併入；否則建立新節編號 `§篩選與排序 chip`

---

## Phase 4：驗收

### Script visibility
- [x] V37 套用後 `script` 表有 `visibility` 欄位、CHECK 約束、COMMENT 齊全
- [x] 既有 Script row 自動帶 `visibility='private'`（DEFAULT 生效）
- [x] `POST /api/v1/scripts`（multipart）可傳 `visibility=public`，DB 寫入正確
- [x] `PATCH /api/v1/scripts/{uid}` 可切換 `visibility`
- [x] `GET /api/v1/scripts/public` 只回傳 `visibility='public' AND is_deleted=FALSE` 的資料
- [x] Swagger `/api/docs` 顯示 `visibility` 於 Script 相關 schema

### Ranking API order
- [x] `GET /dashboard/rankings?order_by=download_count&order=asc` 正確回傳 asc 排序結果
- [x] `GET /dashboard/rankings?order_by=favorite_count&order=desc`（預設）結果與 v1.2.4 既有呼叫相容
- [x] Swagger 顯示 `order` query 為 `Literal["asc","desc"]`，超出值回 422

### Dashboard 第三個頁籤
- [x] `/dashboard` 上方顯示 **3 顆** TabButton：`[公開 Agents (n)] [公開 Skills (n)] [公開 Scripts (n)]`
- [x] 點「公開 Scripts」顯示公開 Script 列表，卡片樣式與 Agents / Skills 列表視覺一致
- [x] 公開 Scripts 頁籤的作者 filter 可依 `owner_username` 正確篩選
- [x] 「管理我的 {類型} →」連結依當前頁籤切到 `/agents` / `/skills` / `/scripts`

### 排序 chip
- [x] 6 顆 chip 依序顯示為：`最新 / 最舊 / 最熱門 / 最冷門 / 最多收藏 / 最少收藏`
- [x] 預設選中「最新」、chip 列有前綴文字「排序：」
- [x] 切換類型（Agents ↔ Skills ↔ Scripts）**保留** sort 選擇
- [x] 點每顆 chip 列表實際按對應 `orderBy` / `order` 重排
- [x] 窄寬度（< 600px）chip 自然 wrap，無水平捲軸
- [x] 未出現 toggle / ↑↓ / asc-desc 英文

### 「你最常用的」面板
- [x] `RankingPanel` 行為無變化（仍只顯示類型切換、無排序）、列表仍以 `download_count desc` 呈現
- [x] 點收藏 / 取消收藏時仍走 `Rankings` tag invalidate 即時同步

### Design-Base
- [x] `11-ui-ux.md` 新增 §排序 chip 慣例 子節，涵蓋前綴、命名原則、範例參考

### 整合
- [x] Flyway V33 → V34 → V35 → V36 → V37 順序套用無 out-of-order
- [x] 前端 `tsc --noEmit` 零錯、`npm run lint` 無新增 warning
- [x] fixed.md §4 / §5 處理狀態欄位由 `⏳ 待修` 更新為 `✅ 已修（commit hash）`
