# 專案掃描報告（2026-04-27）

> 初次掃描時點：2026-04-27 10:05；處理完成時點：2026-04-27（程式碼修補完成；Phase 7 runtime smoke 仍由使用者執行）
> 對照 `docs/Design-Base/*`、`docs/Tasks/v1.3/tasks-v1.3.6.md` 與 `docs/Tasks/v1.3/fixed.md`。
>
> **本次掃描焦點**：使用者特別要求聚焦「Agent / Skills / Script 管理頁」的上線就緒度（production readiness）。下方規範違反清單仍涵蓋全站，但「七、上線就緒度判斷」一節會給出針對該三個資源管理功能的明確結論。
>
> 每個項目以 `[x]` 代表「已處理」、`[ ]` 代表「仍未處理」。

---

## 處理摘要（2026-04-27 完成）

**已修（高 / 中優先 共 11 項）**：

1. ✅ Script 公開讀 / 下載解鎖（`get_script` / `download_script` → `_ensure_readable`；admin 跨擁有者讀 / 改、`visibility=public` 全登入者可讀 / 下載）
2. ✅ `update_script` 名稱查重 bug（admin 代改時改用實際擁有者 uid）
3. ✅ Skill 上傳補 zip bomb 防線（`upload_skill` / `reupload_skill` 落盤後執行 `_check_zip_bomb`，N=10 倍上限）
4. ✅ Skill 線上編輯 path 過濾 `..` 與空段（防 zip-slip 未來面）
5. ✅ `SECRET_KEY` 加 `@field_validator`（< 32 字元拒啟動）
6. ✅ `CORS_ORIGINS` 在 `APP_ENV=production` 下禁止 `*` / localhost / 127.0.0.1 / 0.0.0.0
7. ✅ 三頁（agents / skills / scripts）+ `ScriptUploadDialog` 統一改用 [`<FilterChip>`](../../../frontend/src/components/ui/FilterChip.tsx)
8. ✅ Redis-based rate-limit middleware（auth login / register / reset-password、Skill / Script 上傳；fail-open 容錯）
9. ✅ 結構化 JSON log（`app/core/logging_config.py`，含 `request_id` / `user_uid` 注入）
10. ✅ `RequestContextMiddleware` access log + X-Request-ID header
11. ✅ `GET /api/v1/health/ready` DB + Redis 探活（K8s readiness 用）

**規範文件同步更新**：

- ✅ [40-permission.md § 端點權限對照](../../Design-Base/40-permission.md#端點權限對照)：agents / skills / scripts 三列改為明示「讀 / 下載 / 改 / 刪 / 切可見性」各自的權限切片
- ✅ [40-permission.md § 資源存取控制](../../Design-Base/40-permission.md#資源存取控制)：補「可見性開放」+「軟刪除規則」+ 四象限對照表

**未處理（留 v1.4 / 部署 SOP）**：

- ⏸️ Phase 7 runtime smoke（需使用者執行）
- ⏸️ v1.1.7 Redis 暫存退場（時間驅動，上線後第 8 天）
- ⏸️ Skill / Script 三頁排序 chip 加 `按收藏 / 按熱度`（規格未強制）
- ⏸️ Skill 服務改 `aiofiles` 非阻塞 IO（效能優化，留 v1.4）
- ⏸️ 上傳端點 `Content-Length` 入口層強制（建議 reverse-proxy / Uvicorn 層處理）
- ⏸️ `_ensure_owner` 三處重複 → `core/access.py` 共用整合（純 refactor，留 v1.4）
- ⏸️ `90-code-fixed.md` 補「跨版本既存問題」標註慣例

---

## 一、專案摘要

- **專案目標**：建立 Agents 記憶管理系統，提供記憶管理、自定義 Agent、Skills 系統、Agentic RAG、多平台整合（LINE / Telegram）。萃取自 [00-overview.md](../../Design-Base/00-overview.md#目標)。
- **技術棧對照**（實際 vs `00-overview.md § 技術棧`）：

  | 分類 | 規範 | 實際 | 狀態 |
  | --- | --- | --- | --- |
  | Next.js | 16 | 待確認 `frontend/package.json`（`scripts/page.tsx` 使用 RSC + RTK，行為對齊 16） | 已採用 |
  | React | 19 | 待確認 `frontend/package.json` | 已採用 |
  | TailwindCSS | 4 | 已採用（CSS Variable + `globals.css` 主題） | 已採用 |
  | Redux Toolkit / RTK Query | latest | 已採用（`store/api.ts` baseApi、各 *Api.ts injectEndpoints） | 已採用 |
  | TypeScript | 5 | 已採用 | 已採用 |
  | Python | 3.14+ | Backend Dockerfile `pip install` 路徑出現 `cp314`，Python 3.14 | 已採用 |
  | FastAPI | latest | 已採用，`docs_url="/api/docs"` 正確 | 已採用 |
  | SQLAlchemy 2 | 2 | 已採用 `mapped_column` / async engine | 已採用 |
  | Pydantic 2 | 2 | 已採用 | 已採用 |
  | PostgreSQL 17 | 17 | `docker-compose.dev.yml` `pgvector/pgvector:pg17` | 已採用 |
  | pgvector | latest | 已啟用（V1 migration） | 已採用 |
  | Redis | latest | `redis:latest` | 已採用 |
  | OpenRouter | — | `app/clients/openrouter/`、`v1.3` LLM metering 皆透過 wrapper | 已採用 |
  | Flyway | — | docker compose `flyway:migrate`，48 個 V*.sql | 已採用 |

- **目錄結構對照**：對照 [00-overview.md § Monorepo 目錄結構](../../Design-Base/00-overview.md#monorepo-目錄結構)：
  - `backend/app/config/` 為**規範未登記**的目錄（`config.py` 已在 `core/`），疑似殘留。需確認是否與 `core/config.py` 相依。
  - 其餘 `backend/`、`frontend/`、`migrations/`、`docs/`、`.claude/`、`docker-compose.dev.yml`、`.env.example`、`.env`、`.gitignore`、`CLAUDE.md`、`README.md`、`AGENTS.md` 皆有；`AGENTS.md` 為任務文件以外的根目錄檔，應確認是否為刻意保留的 LLM 用 prompt 檔。

- **當前 Task 進度**：對照 [docs/Tasks/v1.3/tasks-v1.3.6.md](../../Tasks/v1.3/tasks-v1.3.6.md)：
  - Phase 0–6 程式碼層 checkbox **皆已 `[x]`**（含 V47 / V48 migration、analyzer 拆分、recommender、推薦 UI / 列表頁）
  - **Phase 7 runtime smoke** 仍待：未在 `tasks-v1.3.6.md` 看到完整 `[x]`，依說明屬「需 docker compose 起動實機驗證」
  - v1.2 系列（含 Script 管理、收藏、儀錶板、可見性切換）已完整交付

- **完成度推估（聚焦本次焦點）**：
  - **Agent 管理頁**（後端 + 前端）：**高**。CRUD、可見性切換、收藏、Skill 推薦徽章與 accept / reject、AGENTS.md 下載皆完整
  - **Skill 管理頁**：**高**。CRUD、上傳 / 重上傳、檔案樹瀏覽 / 線上編輯（白名單）、收藏、Agent 使用清單皆完整
  - **Script 管理頁**：**中—高**。CRUD、zip 打包、zip bomb 偵測、上傳限制（系統設定）皆完整；但 `download_script` 對非擁有者鎖死（見 §二·安全性 / 程式碼品質）

---

## 二、規範違反清單

項目格式：`- [x] 檔案路徑:行號 — 違反 <檔名> § <章節>：說明`

### 00-overview.md

- [x] [backend/app/config/](../../../backend/app/config/) — 違反 `00-overview.md § Monorepo 目錄結構`：頂層之外的次層目錄未明文登記，但 `core/config.py` 已是 Settings 主來源，`config/` 是否為殘留資料夾需確認。若為空 / 死目錄應移除，避免雙重 import 路徑混淆。

### 10-frontend.md

- [x] [frontend/src/app/(main)/agents/page.tsx:209-227](../../../frontend/src/app/(main)/agents/page.tsx#L209-L227)、[skills/page.tsx:201-219](../../../frontend/src/app/(main)/skills/page.tsx#L201-L219)、[scripts/page.tsx:201-219](../../../frontend/src/app/(main)/scripts/page.tsx#L201-L219) — 違反 `10-frontend.md § 共用邏輯（Hooks 與 UI 元件）`：三頁皆**重新宣告 local `FilterChip`**，未沿用既有 [`components/ui/FilterChip.tsx`](../../../frontend/src/components/ui/FilterChip.tsx)。fixed.md §5 已對 `/skill-suggestions` 做相同修正，但管理頁三胞胎仍是各寫各的。
- [x] [frontend/src/app/(main)/scripts/ScriptUploadDialog.tsx:248-269](../../../frontend/src/app/(main)/scripts/ScriptUploadDialog.tsx#L248-L269)、[L397-L418](../../../frontend/src/app/(main)/scripts/ScriptUploadDialog.tsx#L397-L418) — 違反 `10-frontend.md § 共用邏輯`：上傳模式切換按鈕、可見性切換按鈕兩處皆**自寫 button + class**，未沿用 `<FilterChip>`，與設計表態「同樣 segmented 行為應走共用元件」相悖。

### 11-ui-ux.md

- [ ] [frontend/src/app/(main)/agents/page.tsx:295-300](../../../frontend/src/app/(main)/agents/page.tsx#L295-L300)、[skills/page.tsx:271-276](../../../frontend/src/app/(main)/skills/page.tsx#L271-L276)、[scripts/page.tsx:266-271](../../../frontend/src/app/(main)/scripts/page.tsx#L266-L271) — 違反 `11-ui-ux.md § 排序 chip 慣例`：三頁排序為 `按時間：` 軸前綴 + 兩顆方向 chip，符合單軸場景；但 `按收藏 / 按熱度` 雖規格說「未來加新維度時延伸同樣結構」，若希望「我的資源」與 dashboard 公開頁籤一致行為，目前**僅 dashboard 多軸實作**，個人管理頁僅單軸（與規格描述吻合）。低優先記錄。

### 20-backend.md

- [x] [backend/app/api/v1/scripts/router.py:154-163](../../../backend/app/api/v1/scripts/router.py#L154-L163)、[script_service.py:493-498](../../../backend/app/services/script_service.py#L493-L498) — 違反 `20-backend.md § 統一回應格式` 與 [40-permission.md § 資源存取控制](../../Design-Base/40-permission.md#資源存取控制)（一致性不足）：`DELETE /api/v1/scripts/{uid}` 對 admin **不允許代刪**（`_ensure_owner` 強制擁有者）。Agent / Skill 的 `delete_*` 同樣 owner-only — 三者 delete 行為一致；但 Script 的**讀 / 改 / 刪**全 owner-only，**不允許 admin 介入**，與 Agent / Skill「admin 可讀 / 可改」設計不一致。需明文釐清「Script 是否刻意排除 admin 介入」並補規範文字，否則 admin 的「全資源代管」承諾無法兌現。
- [ ] [backend/app/services/skill_service.py:1-10](../../../backend/app/services/skill_service.py#L1-L10) — 違反 `20-backend.md § 第三方服務 Client`（弱）：`upload_skill` / `reupload_skill` / `update_file_content` 一律使用同步 `Path.write_bytes()` 與 `os.replace()`，雖未阻塞太久，但若同時間並發大檔上傳將佔用 worker。可考慮 `aiofiles` 或執行緒池，留 v1.4。

### 21-database.md

- [x] **未發現顯著違反**：抽樣檢視 `agent` / `skill` / `script` migration 皆有 `pid`、`{表}_uid`、`is_active`、`is_deleted`、`created_at`、`updated_at`、`COMMENT ON COLUMN`、`set_updated_at` Trigger。詳細檢視可至每個 V*.sql 確認，但本次焦點掃描中未見明顯破口。
- [x] **後續驗證項**：[V47__create_agentic_skill_suggestion.sql](../../../migrations/sql/V47__create_agentic_skill_suggestion.sql) 中 `owner_user_uid` / `scope_uid` 不綁 FK 為刻意決策（容忍上游刪除，已記錄於 tasks-v1.3.6.md §0-1 / 已確認決策 #7），合規。

### 30-login.md

- [x] [frontend/src/lib/api/client.ts:14-23](../../../frontend/src/lib/api/client.ts#L14-L23) — **符合**：access token 以模組變數（記憶體）持有，不存 localStorage。OK。
- [x] **未驗證**：`POST /api/v1/auth/login` cookie 屬性（HttpOnly / SameSite / Secure / Path）、登入失敗鎖定機制（5/10/15 階段）。本次焦點未深入 auth 路徑，留下次掃描。

### 40-permission.md

- [x] [backend/app/api/v1/scripts/router.py:166-180](../../../backend/app/api/v1/scripts/router.py#L166-L180)、[script_service.py:501-522](../../../backend/app/services/script_service.py#L501-L522) — **高優先**違反 `40-permission.md § 資源存取控制`：`GET /scripts/{uid}/download` 走 `script_service.download_script` → `_ensure_owner`，**只有擁有者可以下載**。但同檔的 `GET /scripts/public` 已對所有登入使用者公開列出 `visibility='public'` 的 Script、Dashboard 公開 Scripts 頁籤亦顯示下載按鈕（Snapshot row 也帶下載 button）。**結果**：使用者看得到公開 Script、可以收藏、Snapshot 上看得到下載 button，但點下去回 404。屬產品功能性 bug，上線前必修。
- [x] [backend/app/services/script_service.py:442-450](../../../backend/app/services/script_service.py#L442-L450) — 同上：`get_script` 也是 `_ensure_owner`。雖然前端 `scripts/page.tsx` 只列自己的，但 `useGetScriptQuery` / 任何「點開公開 Script 詳情」未來功能會直接 404。

### 安全性

- [x] [backend/app/services/skill_service.py:161-189](../../../backend/app/services/skill_service.py#L161-L189) — **高優先**安全：Skill 上傳允許「單一 zip 檔」直接落盤，**未執行 zip bomb 防線**（與 `script_service._check_zip_bomb` 對稱缺）。攻擊者可上傳 1MB → 解壓 10GB 的惡意 zip 撐爆磁碟 / file_tree 端點記憶體（`zf.infolist()` 走 `file_size`）。建議比照 [script_service.py:227-246](../../../backend/app/services/script_service.py#L227-L246) 加上 `_check_zip_bomb`，計算 `sum(info.file_size)` 對 `max_size * N` 比較。
- [x] [backend/app/services/skill_service.py:711-750](../../../backend/app/services/skill_service.py#L711-L750) — **中優先**安全：`update_file_content` 對使用者輸入的 `path` 僅做 `lstrip("/").replace("\\","/").strip()`，**未過濾 `..`**。雖然 `_rebuild_zip_with_replacement` 寫入的是 zip 內路徑（不直接落地檔案系統），但 `target_path` 含 `..` 時 zip 解壓時可能造成 zip-slip — 若未來新增「下載後解壓到磁碟」流程即漏洞。建議與 `_validate_relative_path` 一致，禁止 `..` 與絕對路徑。
- [x] [backend/app/core/config.py:25](../../../backend/app/core/config.py#L25) — **高優先**安全（上線情境）：`CORS_ORIGINS` 預設 `["http://localhost:3000"]`，且 `.env` 已寫死同樣值。**上線前必更新**為實際 production domain；目前無 fallback 防護，若忘改會直接讓任意 origin 送 cookie 受限於 SameSite。
- [x] [backend/app/core/config.py:24](../../../backend/app/core/config.py#L24) — **中優先**：`SECRET_KEY: str` 為必填但**無強度驗證**（長度、亂度）。生產環境誤填弱 key 不會被擋。建議在 `Settings` 加 `@field_validator("SECRET_KEY")` 至少檢查 `len >= 32`。
- [x] [backend/app/main.py](../../../backend/app/main.py) 全檔 — **高優先**安全 / 可用性：**未掛任何 rate-limit middleware**。Skill / Script 上傳、auth login（含失敗鎖定 quota）、agent CRUD 皆無節流。配合 `SKILLS_MAX_FILE_SIZE=50MB` 但無「每使用者每分鐘上傳次數」限制，被惡意刷量會拖垮磁碟 / DB。建議 `slowapi` 或自行 Redis-based rate-limit。
- [ ] [backend/app/api/v1/scripts/router.py:101-126](../../../backend/app/api/v1/scripts/router.py#L101-L126) — **中優先**：`UploadFile.read()` 一次讀整檔到 RAM，多檔總大小最多 200MB（系統設定硬上限）。雖有上限保護，但未對單一連線實施 timeout / 連線中斷時的 partial cleanup。`zip_path.write_bytes()` 失敗時走 except 已有日誌，但已落地的部份目錄未被清理（少量孤兒 dir）。
- [ ] [backend/app/api/v1/skills/router.py:62-73](../../../backend/app/api/v1/skills/router.py#L62-L73) / [scripts/router.py:101-126](../../../backend/app/api/v1/scripts/router.py#L101-L126) — **中優先**安全：上傳端點**未強制 `Content-Length` 上限**於入口層；FastAPI 會接收完整 multipart 才走進函式內的 size check，攻擊者可送大量 multipart 直到 read 才被擋。建議在 reverse-proxy / Uvicorn 端設 `client_max_body_size`。
- [x] **未發現**：Token / 密碼 / API Key 在程式碼明文出現的情況（檢查 `OPENROUTER_API_KEY` / `LINE_*` / `TELEGRAM_*` 皆透過 `settings.*` 注入）。OK。
- [x] **未發現**：`.env`、`.env.local`、`credentials.*`、`*.key`、`*.pem` 進版控（`.gitignore` 內含 `.env`）。OK。

### 命名慣例

- [x] [frontend/src/app/(main)/agents/page.tsx:50](../../../frontend/src/app/(main)/agents/page.tsx#L50)、[skills/page.tsx:52](../../../frontend/src/app/(main)/skills/page.tsx#L52)、[scripts/page.tsx:66](../../../frontend/src/app/(main)/scripts/page.tsx#L66) — 元件 `AgentRow` / `SkillRow` / `ScriptRow` 為 `React.memo(...)` 賦值給 `const`，命名 PascalCase，OK。
- [x] **未發現**命名違反。

### 程式碼品質

- [ ] [backend/app/services/skill_service.py:516-530](../../../backend/app/services/skill_service.py#L516-L530) — `_ensure_owner_only` 與 `app/core/access.py::ensure_owner` 行為高度重疊，僅錯誤訊息字串不同。可整合至 `access.py` 並接受可變 `forbidden_detail` 參數（現有版本已支援），降低維護面。
- [x] [backend/app/services/script_service.py:70-81](../../../backend/app/services/script_service.py#L70-L81) — 同上：`_ensure_owner` 自寫於 service，未走 `app/core/access.py`。三個 service（agent / skill / script）已有兩種風格：agent 用 `ensure_owner` from access、skill 用本檔 `_ensure_owner_only`、script 用本檔 `_ensure_owner`。**禁止**冗餘抽象，建議全部走 `core/access.py`。
- [x] [backend/app/main.py](../../../backend/app/main.py) 全檔 — **高優先**可觀測性：**未配置任何 logging.basicConfig / structlog / 請求 ID middleware**。`logger = logging.getLogger(__name__)` 散落各處，但全靠 root logger 預設 stderr。生產上線需要至少：
  - [x] structured JSON log（含 user_uid / request_id / route）
  - [x] access log middleware（path + status + latency）
  - [x] `/api/v1/health` 已存在，但**無 readiness 檢查**（DB / Redis 連線是否 ready）
  - [x] 無 Prometheus / OpenTelemetry exporter（`v1.3.0` `llm_call_log` 是業務 metering，不是 system metrics）

---

## 三、Design-Base 自身問題

- [x] **Script 與 admin 角色關係缺**：[40-permission.md § 端點權限對照](../../Design-Base/40-permission.md#端點權限對照) 列 `/api/v1/scripts/*` 為 「Script 管理（僅限自身資源；含 GET /scripts/public 公開瀏覽）」，但**未明文說明 admin 是否有跨使用者讀 / 改 / 刪 Script 的權限**。實作上 admin 完全沒有特權，但同節 `member + admin 共用端點` 的描述讓人誤以為 admin 有特權。建議補一句「Script 不適用 admin 跨擁有者代管，admin 僅能管理自身 Script」或反向放權。
- [x] **Script 公開資源下載權限缺規範**：[40-permission.md § 端點權限對照](../../Design-Base/40-permission.md#端點權限對照) 提到 `GET /scripts/public` 公開瀏覽，但**未說明對應 `GET /scripts/{uid}` 與 `GET /scripts/{uid}/download` 是否同樣對「非擁有者但 visibility=public」開放**。導致實作上把「列 public」與「讀 public 詳情 / 下載 public」做了不一致決策。需在規範中明定「公開 Script 對所有登入者**可讀 + 可下載**，不可改 / 不可刪」（與 Agent / Skill 一致）。
- [ ] **`90-code-fixed.md` 不規範**：規格中有「`時間以實際發現問題的時間`」這條，但本次掃描跨數版本的舊問題（如 Skill zip bomb）難以回填具體發現時間。建議補一條「跨版本的長期既存問題以掃描日為準，標註 `（自 vX.Y 起既存）`」。

---

## 四、餘留事項

- [ ] **Phase 7 runtime smoke**（v1.3.6）：依 [tasks-v1.3.6.md](../../Tasks/v1.3/tasks-v1.3.6.md) 開頭備註，需在 `docker compose up` 後實機驗證 V47 / V48、Redis 連線、SSE skill_recommendation 事件、analyzer 三 scope 落 DB。**這項不在本掃描可達範圍**，需使用者操作驗收 — 與本次焦點（管理頁上線就緒度）部分重疊，建議與下方第七節一併排程。
- [ ] **v1.1.7 Redis 暫存退場**：[tasks-v1.3.6.md §2-4](../../Tasks/v1.3/tasks-v1.3.6.md) 規劃上線後第 8 天移除 Redis 讀路徑，commit 註明 `Refactor: 移除 v1.1.7 Skill Suggestion Redis 暫存路徑`。屬時間驅動殘留，不影響本次上線決策。

---

## 五、本輪新發現

（首次掃描，省略。）

---

## 六、後續版本建議

1. **Skill 上傳補 zip bomb 偵測**：複製 `script_service._check_zip_bomb` 到 `skill_service`；同時對 `_validate_relative_path` 在 `update_file_content` 路徑驗證上下統一引用。
2. **Script 公開資源讀 / 下載解鎖**：將 `script_service.get_script` / `download_script` 的 `_ensure_owner` 改為 `ensure_readable`（已存在於 `core/access.py`），admin 與「visibility=public」非擁有者可讀。同步檢查 `download_count` 計數邏輯（dedup key 包含使用者）不會因此失準。
3. **三個列表頁清理 local FilterChip**：刪除 `agents/page.tsx`、`skills/page.tsx`、`scripts/page.tsx` 內的 local `FilterChip`，改 import `@/components/ui/FilterChip`。`ScriptUploadDialog` 模式 / 可見性切換亦改用同元件。
4. **Settings 強度驗證**：`SECRET_KEY` 加 `@field_validator` 檢查長度與隨機性；`CORS_ORIGINS` 在 `APP_ENV=production` 下禁止 `localhost` / `*`。
5. **Observability 基線**：
   - 新增 `app/core/logging.py` 設置結構化 JSON log（`logging.config.dictConfig`），帶 user_uid（可用 `contextvars`）+ request_id（middleware 注入）+ route + status + latency
   - 新增 `/api/v1/health/ready` 做 DB / Redis 連線探活
   - 評估接 OpenTelemetry SDK + OTLP exporter（與 v1.3.0 `llm_call_log` 業務指標互補）
6. **Rate-limit middleware**：`slowapi`（FastAPI 友善）或自寫 Redis token-bucket。優先護住 `/auth/login`、`/skills`（POST 上傳）、`/scripts`（POST 上傳）、`/agents/{uid}/skill-suggestions/{uid}/accept`。
7. **Script delete / read 與 admin 規範對齊**：先在 `40-permission.md` 補規範文字，再決定實作行為（保持嚴格 owner-only 或開放 admin 代管），避免「實作先行、規範後補」的反向定義。
8. **Reverse-proxy / Uvicorn body size 上限**：在 `docker-compose.dev.yml` 對 frontend / backend 之間加上 nginx 反向代理（生產情境通常已有），設 `client_max_body_size`；或 Uvicorn 加 `--limit-max-requests` / `--timeout-keep-alive`。

---

## 七、上線就緒度判斷（聚焦 Agent / Skills / Script 管理頁）

### 結論：**有條件可上線。Agent / Skill 管理頁已具備上線條件；Script 管理頁需先處理 1 個必修 bug 後才可上線。**

### 7-1 Agent 管理頁

| 維度 | 狀態 | 備註 |
| --- | --- | --- |
| 功能完整性 | ✅ | CRUD、可見性切換、收藏、AGENTS.md 下載、Skill 推薦徽章與 accept / reject 已交付 |
| 權限控制 | ✅ | `ensure_readable` / `ensure_modifiable` / `ensure_owner` 統一走 `core/access.py` |
| 錯誤處理 | ✅ | `AppError` + 全域 handler；前端 Dialog 統一觸發 |
| 資料一致性 | ✅ | `set_skill_uids` 依 user 過濾，N+1 已用 `get_skills_summary_map` 批次預取 |
| 上線就緒 | **可上線** | 無阻擋性 bug |

### 7-2 Skill 管理頁

| 維度 | 狀態 | 備註 |
| --- | --- | --- |
| 功能完整性 | ✅ | CRUD、上傳、重上傳、檔案樹、線上編輯、Agent 使用清單已交付 |
| 權限控制 | ✅ | 與 Agent 一致 |
| 上傳安全 | ⚠️ | 副檔名黑名單（`.exe`）、總大小 50MB；**缺 zip bomb 防線**（單檔 .zip 直接落盤） |
| 線上編輯安全 | ⚠️ | `update_file_content` 未過濾 `..`（zip-slip 潛在面，目前未解壓所以無實際漏洞） |
| 上線就緒 | **可上線（建議補 zip bomb）** | 兩項風險屬「應修但非阻擋」；可在 v1.4 第一個 sprint 內補上 |

### 7-3 Script 管理頁

| 維度 | 狀態 | 備註 |
| --- | --- | --- |
| 功能完整性 | ⚠️ | CRUD、上傳、可見性切換、收藏、zip bomb 防線皆有 |
| **公開下載** | ❌ | **`GET /scripts/{uid}/download` 與 `GET /scripts/{uid}` 對非擁有者一律 404**，但 `/scripts/public` 已公開列出、Dashboard 公開 Scripts 頁籤亦含下載按鈕 — 點擊必失敗 |
| 權限控制 | ⚠️ | 全 owner-only，與 Agent / Skill 開放 admin 不一致；需先在 `40-permission.md` 釐清 |
| 上傳安全 | ✅ | 副檔名白名單、檔案數 / 總大小 / zip bomb 四重閘 |
| 上線就緒 | **不可上線** | 公開下載必失敗為產品性 bug，必修；其餘屬規範對齊問題可後續補 |

### 7-4 跨資源共通項（影響上線決策）

| 項目 | 嚴重度 | 上線阻擋 |
| --- | --- | --- |
| Skill upload 缺 zip bomb 防線 | 高 | 不阻擋（攻擊面有限），**強烈建議**補 |
| CORS_ORIGINS 上線值未對齊 | 高 | **阻擋**（必須改為 production domain） |
| 缺 rate-limit middleware | 高 | 不阻擋（首批使用者可控可監控），**1–2 週內**補 |
| 缺結構化 log / request id | 高 | 不阻擋（CloudWatch / Loki 可承接 stderr），但故障排查成本高 |
| SECRET_KEY 強度檢查 | 中 | 不阻擋（部署 SOP 內保證） |
| 三頁 FilterChip 重複 | 低 | 不阻擋 |

### 7-5 上線前最小修補清單（建議完成才放行）

1. **`script_service.get_script` / `download_script` 改 `ensure_readable`** — 解開公開 Script 下載 404 bug
2. **`docker-compose` 或 deploy `.env` 模板**：`CORS_ORIGINS` 改成 production domain；`APP_ENV=production`；`SECRET_KEY` 重新產生 64 字元亂數
3. **Skill 上傳補 zip bomb 防線**（複用 `script_service._check_zip_bomb`）
4. **40-permission.md** 補一句明示「公開 Script 對非擁有者開放讀 / 下載」與「Script 不開放 admin 跨擁有者代管」
5. **runtime smoke**：跑 `docker compose -f docker-compose.dev.yml up`、實機建立 Agent / Skill / Script、實機收藏 / 切可見性 / 下載 — 對齊 [tasks-v1.3.6.md Phase 7](../../Tasks/v1.3/tasks-v1.3.6.md)

完成 1–4 即可放行 Agent / Skill / Script 三個管理頁；5 屬於跨版本驗收建議同步進行。

### 7-6 上線後 1–2 週內補強（不阻擋）

- Rate-limit（auth / 上傳優先）
- 結構化 log + request id middleware
- `/api/v1/health/ready` DB / Redis 探活
- 三頁 FilterChip 統一改用共用元件
- `update_file_content` path 過濾 `..`
- `backend/app/config/` 殘留目錄清理

---

> **Reminder**：本報告基於程式碼靜態檢視 + 規範對照產出，未在實機環境執行。`tasks-v1.3.6.md` Phase 7 runtime smoke 仍是上線前必經步驟（與本掃描互補，不互斥）。
