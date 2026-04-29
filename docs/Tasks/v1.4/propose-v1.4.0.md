# v1.4 Propose

> 本文件為 v1.4 的構想與討論紀錄。定稿後拆為 `tasks-v1.4.*.md` 規格文件再進行實作。
>
> 前置版本：[v1.3 propose](../v1.3/propose-v1.3.0.md)、[v1.3-extended 修正記錄](../v1.3/dev-v1.3-extended.md)

---

## 0. 前置假設

v1.3 系列（v1.3.0 ~ v1.3.7）與 `df-dev-v1.3-extended` 分支已分別上線, 並於 v1.4 啟動時把兩條工作分支合一為 `dev-v1.4`：

- v1.3 主線：開源 / 對外功能基線（多 Agent 對話、跨層記憶、Agentic Skill 工廠正式版等, 詳見 v1.3 propose）
- v1.3-extended：df 公司版本延伸（DF-SSO 整合、Coolify 部署管線、df 公司版本 feature gating）

合一動作見 commit `d02c693`（dev-v1.3 → df-dev-v1.3-extended）與 `adfa569`（dev-v1.4 → main）。v1.4 起**不再維護獨立的 df 公司版本分支**, 後續所有變更都在 `dev-v1.4` / `main` 上開發。

---

## 1. 版本目標

1. **分支策略統一**：把 `dev-v1.3` 與 `df-dev-v1.3-extended` 合併為 `dev-v1.4`, 移除「對外開源版 / df 公司版」雙線維護成本
2. **DF-SSO 整合落地**：接 OAuth2 / Azure AD 中央驗證, 與既有 local JWT 並存
3. **Coolify 部署管線正式化**：把 v1.3-extended 期間實戰累積的 Dockerfile、build-time flyway 烤 SQL、healthcheck 移除等修補納入主線
4. **拆除 df 公司版本 feature gating**：對話 / 專案 / Skill 建議全面解鎖（v1.4 起 API token 餘額隔離不再需要）

### 範圍內

- 中央 SSO 串接（authorize / token / userinfo / refresh / back-channel logout）
- SSO 與既有 local JWT 共存的策略（雙模式登入）
- Coolify 部署檔案集（root `docker-compose.yml`、`frontend/Dockerfile`、`migrations/Dockerfile`、frontend `.dockerignore`）
- 拆除 `BlockedFeatureMiddleware`、`CHAT_DOMAIN_ENABLED` flag、`PendingApprovalCard` / `usePendingApprovalDialog`
- 跨頁作者 chip util（`frontend/src/utils/search.ts`）統一 / `/skills`、`/scripts` UI 補齊
- `_KEPT` 死碼與 `pendingApproval` 標記從 `Sidebar.tsx`、`/skill-suggestions/page.tsx` 等檔清除

### 範圍外（延後）

- v1.5+：SSO 多 IdP 切換、SSO group claim → role mapping 自動化
- v1.5+：部署環境差異抽象（dev / stage / prod 走同一份 compose, 目前以 `.env` 與獨立 `docker-compose.yml` 區隔）

---

## 2. DF-SSO 整合（OAuth2 / Azure AD bridge）

> 起點：commit `0fd87ec`（基礎串接）+ `bd23b86`（refresh 接中央 /me + JWT 加 `auth_method` claim + SSO 24h TTL）+ `a69b581`（callback Suspense 修 build）。

### 2-1 雙模式登入策略

- **本地 JWT**：v1.x 既有方式維持運作, 適用內部測試 / 本機開發
- **DF-SSO**：經 Azure AD 取得 OAuth2 token 後, 向中央 SSO `/me` 換取 user info, bridge 為本地 JWT 簽發
- 兩種登入方式產出的本地 JWT 結構相同, 但加 `auth_method` claim 標示來源；refresh 時依 `auth_method` 走不同驗證路徑

### 2-2 SSO 票期 / refresh 設計

- SSO 簽發的本地 JWT 有效期 **24h**（vs local-only 的 7 天）, 因為 SSO refresh 必須回中央 `/me` 即時驗證
- refresh 流程：本地 JWT 過期 → 帶 SSO refresh_token → 打中央 `/userinfo` 重新換 → 失敗則使用者被即時登出
- back-channel logout：中央 SSO 主動推送 logout 事件至 `/api/auth/back-channel-logout`, 本地立即作廢該 user 的 session（涵蓋「Azure AD 帳號被停用」此類場景, 不能等到 7 天 JWT 自然過期）

### 2-3 環境變數

| 鍵 | 用途 |
| --- | --- |
| `SSO_URL` | 中央 SSO 服務 base URL |
| `SSO_APP_ID` | SSO 註冊的本應用 client_id |
| `SSO_APP_SECRET` | SSO client_secret |
| `APP_URL` | 本應用對外 URL（callback / back-channel logout 用） |

本機開發可保留空值；空值時 SSO 路由不啟用, 仍可走本地 JWT 流程。

### 2-4 涵蓋元件

| 層級 | 元件 |
| --- | --- |
| Backend client | `app/clients/sso_client.py`（向中央 SSO 換 token / userinfo / refresh） |
| Backend service | `app/services/sso_auth_service.py`（OAuth2 callback → bridge 本地 JWT） |
| Backend router | `app/api/v1/auth/router.py`（新增 SSO 啟動 / callback / logout endpoints） |
| Backend security | `app/core/security.py`（JWT 加 `auth_method` claim） |
| Frontend callback | `app/api/auth/callback/page.tsx`（OAuth2 redirect 落點） |
| Frontend logout | `app/api/auth/back-channel-logout/route.ts`（接中央推送的 logout 事件） |
| Frontend login | `app/(auth)/page.tsx`（新增 SSO 登入按鈕） |

---

## 3. Coolify 部署管線

> 起點：v1.3-extended 期間累積的 5 條 Coolify 修復（[v1.3/fixed.md §9](../v1.3/fixed.md), 以及 build / deploy 相關修補）。

### 3-1 Production 部署檔案集

- 根目錄新增 `docker-compose.yml`（生產用, 與 `docker-compose.dev.yml` 區隔）
- `frontend/Dockerfile` + `frontend/.dockerignore`（next.js standalone build, 排除 `.next` / `node_modules` / 開發檔）
- `migrations/Dockerfile`（自帶 SQL 以避開 Coolify volume mount 不穩）

### 3-2 Deploy 加速與穩定化（已驗證的設計取捨）

| 問題 | 設計取捨 |
| --- | --- |
| `flyway/flyway:latest` 每次 deploy re-pull | 釘版本 `flyway/flyway:10`, 並改 build-time 烤 SQL 進 image（不靠 runtime mount） |
| postgres / redis healthcheck `interval: 5s × retries: 10` 串接 backend / flyway 等待鏈過長 | 移除 healthcheck, 將 `condition: service_healthy` 改為 `service_started`, flyway 改靠 `FLYWAY_CONNECT_RETRIES: "30"` 自身重試 |
| Coolify deploy 卡 In progress | flyway 改 `restart: no`, 完成 migration 後立即退出, 避免被 Coolify healthcheck 視為仍在啟動 |
| frontend Coolify build TS check OOM | 砍 frontend Dockerfile / .dockerignore, 排除不必要檔, 讓 type check 在限制記憶體內可完成 |
| backend 啟動連 postgres / redis 失敗會 crash | 靠 `restart: unless-stopped` 重啟兜底, 首次部署 log 出現 1~2 次紅字屬正常 |

### 3-3 上傳目錄預建

- backend lifespan 啟動時 `_ensure_upload_dirs()` 預建 `SKILLS_UPLOAD_DIR` / `ATTACHMENTS_UPLOAD_DIR` / `scripts_dir`, 避免 Coolify volume 權限問題延後到第一次上傳才爆

---

## 4. 拆除 df 公司版本 feature gating

> 起點：commit `08a4a0c`（拆 gating）。原 gating 設計見 commit `84977d0`。

### 4-1 反向設計動機

v1.3-extended 階段, 因 df 公司版本「API Token 餘額尚未開通」, 把對話 / 專案 / Skill 建議三個領域以**整段隱藏**處理, 保留程式碼但前後端短路（前端鎖定卡, 後端 501）。

v1.4 起本功能開放, 不再需要差異化版本, **gating 屬冗餘風險**（兩條程式碼路徑會逐漸分歧, 解鎖時容易漏修）。一次性拆除。

### 4-2 拆除清單

| 層級 | 拆除項目 |
| --- | --- |
| Backend middleware | `BlockedFeatureMiddleware` 整支移除（含 `app/core/blocked_features.py`） |
| Backend `main.py` | 移除 middleware 註冊 |
| Frontend feature flag | 各頁 `CHAT_DOMAIN_ENABLED: boolean = false` 整段拿掉 |
| Frontend lock card 渲染 | `/sessions`、`/sessions/new`、`/sessions/[uid]`、`/projects`、`/projects/[uid]`、`/skill-suggestions` 還原原邏輯 |
| Frontend Sidebar | 還原 `ChatSection` 渲染、collapsed `+` 按鈕改 `Link → /sessions/new`、移除 `SidebarItem.pendingApproval` flag |
| Frontend dead code | 刪 `PendingApprovalCard.tsx`、`usePendingApprovalDialog.ts` |
| Frontend `_KEPT` 死碼 | `/skill-suggestions/page.tsx` 還原 `_SkillSuggestionsPage_KEPT` 為 default export |

### 4-3 後續守則

- v1.4 起若再有「需臨時關閉某領域功能」需求, **不**走 feature flag + 隱藏卡的模式, 改以正規的 access control（user role / permission）或 admin 設定處理
- 所有保留「以利日後解鎖」的死碼都應立即清除, 避免長期偏離主線

---

## 5. 跨頁作者 chip util 統一

> 起點：v1.3 二輪掃描補強 + v1.3-extended §2 / §5（已合併為 [v1.3/fixed.md §14, §17](../v1.3/fixed.md)）。

`frontend/src/utils/search.ts` 升級為共用工具：

- `matchByTextAndAuthor(name, description, author, parsed, selectedAuthors = [])` 多收 `selectedAuthors` 取聯集
- 新增 `toggleAuthorChip(selected, author)` 取代舊 `toggleAuthorInQuery`
- 移除 `toggleAuthorInQuery`
- 涵蓋四頁（dashboard / agents / skills / scripts）共用同規則

避免 username 含空格時 chip 篩選結果為空（v1.3 接 SSO display name 後浮現的 bug, 詳見 v1.3-extended §2）。

---

## 6. 範圍外 / 後續評估

| 項目 | 暫緩理由 |
| --- | --- |
| SSO 多 IdP 切換 | 目前僅一個 Azure AD tenant, 不需通用化 |
| SSO group claim → role mapping 自動化 | 需先確認 Azure AD group 設計與 SSO claim 內容, 留 v1.5 |
| dev / stage / prod compose 抽象成同一份 | 三環境差異目前以獨立檔處理已足夠, 抽象成本暫不划算 |
| 移除 v1.3 的「dev-v1.3-extended.md」獨立文件 | 內容已合併進 v1.3/fixed.md, 但 v1.4 期間保留以供追溯, v1.5 起再考慮歸檔 |

---

## 7. 上線前自我檢查

- [ ] DF-SSO 完整流程：登入 → 取 token → bridge 本地 JWT → refresh 走中央 → back-channel logout
- [ ] 對話 / 專案 / Skill 建議三領域在新使用者帳號下可正常進入（無 lock card / 無 501）
- [ ] Coolify 部署從零起來, flyway migration 全跑完, backend / frontend healthy
- [ ] 跨頁作者 chip 在 username 含空格 / 中文時可正確過濾
- [ ] `_KEPT` / `pendingApproval` / `BlockedFeatureMiddleware` 任一字串 grep 不到（避免漏拆殘留）
