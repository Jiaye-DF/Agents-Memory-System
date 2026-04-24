# 掃描專案結構與分析潛在問題

掃描整個專案結構，依據 `docs/Design-Base/*` 所有規範逐項檢查，識別潛在問題並產出結構化報告。
**必須遵守 `CLAUDE.md` 與 `docs/Design-Base/*` 內部的所有規範**（繁體中文輸出、不主動新增檔案、保持簡潔等）。

## 執行前置

1. 讀取根目錄 `CLAUDE.md`，遵守基本原則、敏感資訊、Git 工作流程等規範。
2. **依序讀取 `docs/Design-Base/` 底下所有規範檔**（順序如下），作為掃描的權威規則來源：
   - `00-overview.md`
   - `10-frontend.md`
   - `11-ui-ux.md`
   - `20-backend.md`
   - `21-database.md`
   - `30-login.md`（若有內容）
   - `40-permission.md`（若有內容）
3. 讀取 `docs/Tasks/v*/Task-v*.md`（依版號分目錄），了解當前版本預期的交付範圍與 Definition of Done。
4. 所有輸出一律使用**繁體中文**。

## 執行步驟

### 1. 掃描專案結構

- 列出專案根目錄檔案與資料夾（排除 `node_modules/`、`.git/`、`dist/`、`build/`、`.next/`、`__pycache__/`、`.venv/` 等常見忽略目錄）。
- 針對主要目錄（`backend/`、`frontend/`、`migrations/`、`docs/`、`.claude/`、`scripts/`）展開一層內容。
- 統計：
  - 主要語言與檔案數量
  - 後端 / 前端 / 基礎設施（Docker、Migration）的檔案分布
  - 設定檔（`package.json`、`pyproject.toml`、`docker-compose.yml`、`Dockerfile`、`.env.example` 等）

### 2. 專案摘要分析

根據掃描結果與 Design-Base 內容整理：

- **專案目標**：從 `00-overview.md` 萃取核心目標。
- **技術棧對照**：將實際 `package.json` / `pyproject.toml` 與 `00-overview.md § 技術棧` 比對，標示「已採用 / 規劃中 / 未開始 / 版本不符」。
- **目錄結構對照**：與 `00-overview.md § Monorepo 目錄結構` 比對，標示缺漏或額外目錄。
- **完成度推估**：依據檔案存在情況與實作深度，估算各模組完成度（低 / 中 / 高）。
- **當前 Task 進度**：對照 `docs/Tasks/v*/Task-v*.md` 最新版本的 Definition of Done，檢查哪些項目已交付。

### 3. 規範逐項檢查

**不得擅自修復**，僅記錄問題位置與違反的規範章節。引用格式：`檔案路徑:行號 — 違反 <檔名> § <章節>`。

#### 3.1 `00-overview.md`（總覽）

- 技術棧版本是否與文件一致（Python、Node.js、FastAPI、Next.js、React、PostgreSQL、Redis、TailwindCSS 主要大版本）。
- Monorepo 目錄結構是否匹配；有無出現未登記的頂層目錄。
- 前端是否有直接呼叫第三方外部服務 API 的程式碼（**禁止**，須經由後端代理）。
- OpenRouter API Key、LINE / Telegram Token 是否僅存在於後端環境變數。

#### 3.2 `10-frontend.md`（前端）

- `app/error.tsx` 與 `app/global-error.tsx` 是否存在。
- 路由群組是否正確使用 `(auth)` 與 `(main)` 分組；首頁 `/` 是否為登入頁面。
- 是否有元件直接使用 `fetch` 或 `axios`（應透過 `lib/api/*` 或 RTK Query）。
- 客戶端是否誤用非 `NEXT_PUBLIC_` 前綴的環境變數。
- 全域狀態是否由 Redux Toolkit 管理；伺服器資料是否使用 RTK Query。
- TypeScript 函式是否明確標註參數型別與回傳型別；是否使用 `any`。
- React 元件 props 是否定義獨立 `interface`。
- 是否有可避免的不必要 re-render（缺少 `useCallback`、`useMemo`、`React.memo`；render 中建立物件/陣列字面值作為 props）。

#### 3.3 `11-ui-ux.md`（UI / UX）

- 全站是否統一使用圓角設計（`rounded-xl`）。
- 可點選元素是否皆有 `hover:cursor-pointer`。
- 是否有元件寫死 hex 色碼（應使用 CSS Variable / Tailwind class）。
- 佈景主題是否支援深淺色 + 三種自訂主題（冷色系 / 暖色系 / 粉紫色），是否透過 `data-theme` 切換。
- Header 結構：左側是否有 Sidebar 切換按鈕（☰）+ SVG 圖示 + 「Agents-Platform」文字；右側是否顯示 `{Username}` + 登出按鈕。
- Sidebar 是否支援三種狀態（完整展開 → 收合 → 完全隱藏）。
- 登入後頁面是否共用相同 main section 佈局（Page Title + Main Content 卡片容器）。
- 是否使用瀏覽器原生 `alert()` / `confirm()` / `prompt()`（**禁止**，須使用 Dialog 元件）。
- Dialog 是否區分 Info / Warning / Error 三種類型，是否提供共用觸發方法（`useDialog`）。
- 響應式：Sidebar 於 `md` 以下是否收合；互動元素觸控區域是否足夠。

#### 3.4 `20-backend.md`（後端）

- 所有 API 是否以 `/api/v1` 為前綴，路徑是否 kebab-case 複數。
- FastAPI `docs_url` 是否明確設為 `/api/docs`；**禁止** `/swagger`、`/docs`、`/openapi`。
- FastAPI 是否使用 `lifespan` context manager；是否仍使用已棄用的 `on_event`。
- 統一回應格式是否包含 `success`、`data`、`detail`、`response_code` 四個欄位。
- `data` 是否為 `null` 或 `dict`；是否有直接回傳 Array 的情況（**禁止**）。
- `response_code` 是否為 `int` 型別。
- 路由是否使用 `dict` 當 response type（**禁止**），**必須**使用 Pydantic 模型。
- `detail` 欄位是否洩漏 SQL、traceback、資料表結構、第三方原始錯誤、Token 等敏感資訊。
- 例外處理是否註冊 `AppError` / `RequestValidationError` / `Exception` 三個 handler。
- 分層是否正確：`api` → `services` → `repositories` → `models`，是否有跨層呼叫。
- `schemas/` 目錄結構是否對映 `api/v1/`。
- 第三方服務呼叫是否集中於 `clients/`（OpenRouter、LINE、Telegram）。
- Logging 是否使用 `logger.exception(...)` 紀錄 traceback；是否出現 Token 明文。
- CORS 設定：`allow_credentials=True`、origins 是否讀自 `CORS_ORIGINS`。
- 函式是否明確標註參數型別與回傳型別（PEP 484）；是否使用 `Any` 或 `typing.List` / `typing.Dict`。
- 測試是否 mock SQL 查詢（**禁止**）；外部服務是否使用 `respx` / `MockTransport`。

#### 3.5 `21-database.md`（資料庫）

- 每個業務表是否包含 `pid`、`{表}_uid`、`is_active`、`is_deleted`、`created_at`、`updated_at` 六個必備欄位。
- 對外識別是否使用 `{表}_uid`（UUID）；API path 是否使用 UID 而非 `pid`。
- 外部系統的 id 是否以獨立欄位儲存（如 `remote_*_id`），**禁止**作為本地 PK 或對外 UID。
- SQLAlchemy 查詢是否預設過濾 `is_deleted == False`。
- `updated_at` 是否由 `set_updated_at()` Trigger 維護。
- Migration 檔名是否符合 `V{版號}__{描述}.sql`；是否有修改既有已合併 Migration（**禁止**）。
- DB 連線是否使用連線池；是否每請求建立連線（**禁止**）。
- pgvector：向量欄位是否使用 `VECTOR(維度)` 型別；是否建立向量索引。
- Redis：Key 命名是否符合 `{模組}:{資源}:{識別碼}` 格式；是否皆設定 TTL。
- SQLAlchemy Model 是否繼承統一 `Base`；是否使用 `mapped_column` 語法。
- 資料表 / 欄位 / 索引命名是否符合命名慣例（單數 snake_case、`idx_`、`uq_`、`fk_`、`trg_`）。
- 每個欄位是否皆有 `COMMENT ON COLUMN` 中文說明；資料表是否有 `COMMENT ON TABLE`。

#### 3.6 `30-login.md`（登入）

- 若文件有內容，依其規範檢查登入相關實作。
- 登入頁面是否掛載於 `/`（首頁），**禁止**獨立 `/login` 路徑。
- 認證相關 API 是否位於 `backend/app/api/v1/auth/`。

#### 3.7 `40-permission.md`（權限）

- 若文件有內容，依其規範檢查權限相關實作。

#### 3.8 安全性（跨文件）

- `.env`、`credentials.json`、`*.key`、`*.pem` 是否被納入版控。
- 程式碼中是否出現疑似 Token、密碼、API Key 的字串。
- OpenRouter API Key、LINE / Telegram Token 是否僅透過環境變數注入。
- `.env.example` 是否存在；是否與 `.env` 的 key 集合一致（缺漏 / 多餘）。
- 程式碼中使用的環境變數是否全部登記於 `.env.example`。
- `.env`、credentials 等敏感檔案是否被 `.gitignore` 排除。

#### 3.9 命名慣例（跨文件）

- 前端：元件 PascalCase、Hook `use*`、路由目錄 kebab-case。
- 後端：模組 snake_case、類別 PascalCase、函式 snake_case、常數 SCREAMING_SNAKE。
- 資料庫：資料表單數 snake_case、API kebab-case 複數、環境變數 SCREAMING_SNAKE。
- Commit Message 是否使用繁體中文 `<類型>: <描述>` 格式；AI 產生的 commit 是否加 `(AI)` 前綴。

#### 3.10 程式碼品質（概略）

- 明顯的 `TODO` / `FIXME` / `XXX` 註解未處理。
- 疑似未使用的檔案或死程式碼。
- 不符合「不主動添加註解」原則的冗餘註解。

### 4. 輸出報告

**必須**將完整報告**寫入一個新檔案**（此為本指令唯一允許寫入的檔案種類）。檔名一律使用時間戳,每次掃描皆產生獨立檔案,**禁止**覆寫既有報告。

#### 4.1 檔案路徑規則

使用者呼叫 `/scan-project` 時可選擇性指定 Task 版本(例:`/scan-project v1.2`)。依是否指定決定輸出位置:

| 使用者輸入 | 輸出路徑 |
| --- | --- |
| 指定版本(如 `/scan-project v1.2`) | `docs/Tasks/v{版本}/Issue-Scan-Project-{YYMMDDHHMMSS}.md` |
| 未指定版本(如 `/scan-project`) | `docs/Tasks/scan-project/Issue-Scan-Project-{YYMMDDHHMMSS}.md` |

- `{YYMMDDHHMMSS}`:12 位時間戳,格式為「年末兩碼 + 月 + 日 + 時 + 分 + 秒」(例:`260424153012` 表示 2026-04-24 15:30:12),使用系統本地時間。
- 若指定版本對應的目錄(如 `docs/Tasks/v1.2/`)不存在,**停止執行**並回報「指定的版本目錄不存在」,不得擅自建立版本目錄。
- 若為未指定版本情境,`docs/Tasks/scan-project/` 目錄不存在時**可**直接建立。

#### 4.2 標題版本號

- **有指定版本**:標題 `# 專案掃描報告（v{版本} 後）`,版本號使用該目錄內最新子版本(例:`v1.2/` 下存在 `tasks-v1.2.2.md` → 標題寫 `v1.2.2 後`)。
- **未指定版本**:標題 `# 專案掃描報告（{YYYY-MM-DD}）`,使用掃描當日日期。

#### 4.3 報告模板(全部繁體中文)

```markdown
# 專案掃描報告（v{版本} 後）

> 初次掃描時點：YYYY-MM-DD；處理完成時點：YYYY-MM-DD（待回填）
> 對照 `docs/Design-Base/*` 與 `docs/Tasks/v{版本}/tasks-v*.md`。
>
> 每個項目以 `[x]` 代表「已處理」、`[ ]` 代表「仍未處理」。

---

## 處理摘要（YYYY-MM-DD）

- **高優先 N 項** ...（安全 / 敏感資訊外洩 / 必須規範違反）
- **中優先 N 項** ...（架構一致性 / 設定缺漏 / 應然建議）
- **低優先 N 項** ...（程式碼品質 / 可選建議）

（首次掃描此段可填「待處理後回填」）

---

## 一、專案摘要

- **專案目標**：萃取自 `00-overview.md § 核心目標`。
- **技術棧對照**（實際 vs `00-overview.md § 技術棧`）：

  | 分類 | 規範 | 實際 | 狀態 |
  | --- | --- | --- | --- |
  | ... | ... | ... | 已採用 / 規劃中 / 未開始 / 版本不符 |

- **目錄結構對照**：對照 `00-overview.md § Monorepo 目錄結構`，標示缺漏或額外目錄。
- **當前 Task 進度**：對照 `docs/Tasks/v*/tasks-v*.md` Definition of Done。
- **完成度推估**：依模組列出高 / 中 / 低。

---

## 二、規範違反清單

項目格式：`- [ ] 檔案路徑:行號 — 違反 <檔名> § <章節>：說明`

### 00-overview.md

- [ ] ...

### 10-frontend.md

- [ ] ...

### 11-ui-ux.md

- [ ] ...

### 20-backend.md

- [ ] ...

### 21-database.md

- [ ] ...

### 30-login.md

- [ ] ...

### 40-permission.md

- [ ] ...

### 安全性

- [ ] ...

### 命名慣例

- [ ] ...

### 程式碼品質

- [ ] ...

---

## 三、Design-Base 自身問題

（Design-Base 內部矛盾、缺漏，或規範與實作落差需調整規範的項目）

- [ ] ...

---

## 四、餘留事項

（經評估後明確延後或不處理的項目，須註明原因與優先級）

- [ ] ...

---

## 五、本輪新發現

（第二輪以後的掃描使用；首次掃描可省略此節）

- [ ] ...

---

## 六、後續版本建議

（非規範違反，但建議下一版本處理的優化項目，依序編號）

1. ...
2. ...
```

## 注意事項

- **僅允許寫入掃描報告檔**：本指令**只能**建立 `docs/Tasks/v{版本}/Issue-Scan-Project-{YYMMDDHHMMSS}.md` 或 `docs/Tasks/scan-project/Issue-Scan-Project-{YYMMDDHHMMSS}.md`（未指定版本時必要才建立 `scan-project/` 目錄）。**禁止**覆寫既有報告、修改、刪除任何其他檔案（程式碼、設定、規範文件皆不可動）。
- **禁止**擅自執行 `git` 寫入操作（`commit`、`push`、`merge` 等）。
- 若發現敏感資訊疑慮，立即在報告中標示為**高優先**，並提醒使用者自行處置。
- 引用檔案時使用 `檔案路徑:行號 — 違反 <檔名> § <章節>` 格式，方便定位與追溯規範來源。
- 若專案規模過大，先掃描根層結構，再針對每個主要模組遞迴展開，避免一次性讀取過多無關內容。
- 規範衝突時優先順序：**`docs/Tasks/v*/Task-v*.md`** > **`docs/Design-Base/*`** > **`CLAUDE.md`** > 其他。
- 掃描結果中若發現 Design-Base 本身有內部矛盾或缺漏，**應**在報告末段獨立區塊「Design-Base 自身問題」列出，提醒使用者補強規範。
