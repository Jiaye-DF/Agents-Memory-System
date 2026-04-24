# v1.2 Propose — 社群互動統計 + 腳本管理 + 儀錶板排行

> 本文件為 v1.2 的構想與討論紀錄。定稿後拆為 `tasks-v1.2.*.md` 規格文件再進行實作。
>
> 前置版本：[v1.1 propose](../v1.1/propose-v1.1.0.md)、[v1.1 extended](../v1.1/propose-v1.1-extended.md)

---

## 0. 前置假設

v1.1 + v1.1 延伸已完成並作為基線：

- Agents / Skills 管理頁面（列表、建立、編輯、刪除、上傳 zip）— 已具備
- Project / Session / Message / chat_memory 資料表與 Session scope RAG — 已具備
- 附件系統（圖片 vision + 文字檔）、Agentic Skill 工廠 PoC — 已具備
- Sidebar 框架既有，加項目即可
- Skills 目前以 zip（內含 md 檔）形式儲存；Scripts 將沿用同套機制但放寬副檔名

---

## 1. 版本目標

1. **收藏 / 下載統計**：Agents / Skills 擁有 `favorite_count` / `download_count`，作為後續熱度排行依據
2. **我的收藏 Nav**：Agents / Skills 管理頁內切換「全部 / 我的 / 我的收藏」
3. **腳本管理（Scripts）**：Sidebar 新增獨立頁面，layout 與 Agents / Skills 一致，支援上傳**檔案或整個資料夾**；亦具備收藏 / 下載統計
4. **儀錶板排行 filter**：首頁加「熱度（下載數） / 收藏數」排序 filter，跨類型（Agent / Skill / Script）呈現

### 範圍內

- DB：Agents / Skills 加計數欄位；新增 `scripts` 與 `user_favorite` 表
- 後端：收藏 / 取消收藏 API、下載計數原子遞增、列表支援 `order_by`、資料夾上傳保留相對路徑
- 前端：管理頁 filter nav、收藏按鈕、腳本管理新頁、儀錶板排行 filter、**Sidebar 分組調整（§2-5）**、**主題切換器系列化 + Dialog 化（§2-6）**
- 指標呈現：管理頁卡片 / 列表項顯示「⭐ N / ⬇ N」

### 範圍外（延後）

- **社群共享**：收藏別人的 Skill / 下載他人 Script 的權限與可見性 — 本版只處理**擁有者自己**的收藏 / 下載。跨使用者共享與公開 marketplace 留給 v1.4（公開 API 一起設計權限 scope）
- **排行榜時效窗**（「本週熱門」/「本月熱門」）— 本版僅 all-time 累積計數，時效窗待觀察使用行為後再加
- **Script 執行引擎** — 本版 Scripts 僅作「資源管理」（CRUD + 上傳 + 下載），不涉及執行環境
- **AI 語意查詢**（「跟 X 類似的 Skill」）— v1.4 處理

---

## 2. 待討論項目

### 2-1 收藏與下載統計（Agents / Skills / Scripts 共用）

#### 計數儲存策略：denormalized 欄位 + 寫入時即時更新

| 方案 | 讀取 | 寫入 | 結論 |
| --- | --- | --- | --- |
| 每次 `COUNT(*) FROM user_favorite` | 慢（排行 query 需 join + aggregate） | 單純 | ❌ |
| **denormalized `favorite_count` / `download_count` 欄位**（加在 agents / skills / scripts 表） | O(1) | 需事務保證原子 +/- | ✅ |

下載數：使用者 `GET /.../{uid}/download` 後端在同一 transaction 內 `UPDATE ... SET download_count = download_count + 1`。
收藏數：`POST / DELETE /favorite` 時，同 transaction 寫 `user_favorite` 並 `UPDATE ... SET favorite_count = favorite_count +/- 1`。

並發保護：直接依賴 DB 的 row lock（Postgres `UPDATE ... WHERE uid = ?` 自帶 row-level lock），不做快取層。

#### Schema 影響

```sql
-- V33__add_social_counters.sql
ALTER TABLE agent  ADD COLUMN favorite_count INT NOT NULL DEFAULT 0;
ALTER TABLE agent  ADD COLUMN download_count INT NOT NULL DEFAULT 0;
ALTER TABLE skill  ADD COLUMN favorite_count INT NOT NULL DEFAULT 0;
ALTER TABLE skill  ADD COLUMN download_count INT NOT NULL DEFAULT 0;
-- script 表見 §2-3 V35，直接在建表時加

CREATE INDEX idx_agent_favorite_count ON agent(favorite_count DESC);
CREATE INDEX idx_agent_download_count ON agent(download_count DESC);
CREATE INDEX idx_skill_favorite_count ON skill(favorite_count DESC);
CREATE INDEX idx_skill_download_count ON skill(download_count DESC);
```

```sql
-- V34__create_user_favorite.sql
CREATE TABLE user_favorite (
    pid                  BIGSERIAL     PRIMARY KEY,
    user_favorite_uid    UUID          NOT NULL DEFAULT gen_random_uuid(),
    owner_user_uid       UUID          NOT NULL,
    resource_type        VARCHAR(20)   NOT NULL,  -- 'agent' / 'skill' / 'script'
    resource_uid         UUID          NOT NULL,  -- 對應 agent/skill/script 的 <type>_uid，**不綁 DB FK**
    is_active            BOOLEAN       NOT NULL DEFAULT TRUE,
    is_deleted           BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW()
    -- uq_(owner_user_uid, resource_type, resource_uid) where is_deleted=false
    -- idx_(owner_user_uid, resource_type) for 「我的收藏」列表
);
```

採用 `resource_type` + `resource_uid` 泛型對應（**不綁 DB 層 FK**）而非三張中介表，理由：

1. 收藏操作在三類資源上行為一致；未來加 `dataset` / `workflow` 等新資源類型僅擴 enum 不動 schema
2. 被收藏的資源（agent / skill / script）可能被刪除（soft delete 或硬刪），此時使用者的收藏紀錄不應 cascade 連帶消失 — 前端需顯示 tombstone「⚠ 此 {Agent | Skill | Script} 已被移除」讓使用者知情後自行清除

「我的收藏」查詢行為：`user_favorite` LEFT JOIN 目標表 ON `resource_type` / `resource_uid` → 若目標不存在或 `is_deleted=TRUE`，API response 仍保留該 favorite 項但 `resource` 欄位為 `null`，並帶 `"tombstone_reason": "resource_removed"`；前端據此渲染「已被移除」卡片，並提供「從收藏移除」操作。

#### 「下載」的定義（避免計數灌水）

- 下載計數觸發的時機：`GET /api/v1/{skills|scripts}/{uid}/download` 真的回傳 `StreamingResponse` 之前（response 200 成立時）才 +1
- 不對 HEAD / 預覽 / 在前端直接展開 metadata 計數
- 同一 user 24 小時內重複下載只計 1 次：在 Redis `download:dedup:{resource_uid}:{user_uid}` 設 24h TTL key 做 idempotency

> **Redis 依賴**：本功能引入 Redis 做下載 dedup。若既有技術棧尚未部署 Redis，v1.2.1 需一併補上 compose 服務、連線 env 設定（`REDIS_HOST` / `REDIS_PORT` / `REDIS_DB`），以及後端 client 封裝。

#### API

```text
POST   /api/v1/{agents|skills|scripts}/{uid}/favorite
DELETE /api/v1/{agents|skills|scripts}/{uid}/favorite
GET    /api/v1/users/me/favorites?type=agent|skill|script&page=&size=
```

列表 API 擴 `order_by`：

```text
GET /api/v1/agents?order_by=download_count|favorite_count|created_at&order=desc
GET /api/v1/skills?order_by=download_count|favorite_count|created_at&order=desc
GET /api/v1/scripts?order_by=download_count|favorite_count|created_at&order=desc
```

#### 列表 Response 增補 `is_favorited`

三類資源的列表 API（`GET /api/v1/{agents|skills|scripts}`）、單筆 GET、以及儀錶板 ranking API 的每個 item，皆需回傳 `is_favorited: bool`，供前端決定收藏按鈕顯示「空心星」或「實心星」，避免前端需額外打 `/users/me/favorites` 做交集。

後端實作：LEFT JOIN `user_favorite` ON (`owner_user_uid = :current_user` AND `resource_type = :type` AND `resource_uid = <table>.<uid>` AND `is_deleted = FALSE`)，以 `EXISTS` 或 `IS NOT NULL` 折成 bool。

### 2-2 管理頁面的「我的收藏」Nav

Agents / Skills / Scripts 管理頁共用三段式 filter：

```text
[全部]  [我的]  [我的收藏]
```

- **全部**：自己擁有 + 公開可見（v1.2 暫等同「我的」，跨使用者可見性留 v1.4）
- **我的**：`owner_user_uid = 當前使用者`
- **我的收藏**：join `user_favorite` where `owner_user_uid = 當前使用者 and resource_type = ?`

每個卡片 / 列表項右上角固定顯示：

```text
⭐ 32   ⬇ 127   [收藏/已收藏]
```

「已收藏」icon（實心星）是為了降低使用者重複點擊造成的 delete→insert 抖動；點一次 toggle。

### 2-3 腳本管理（Scripts）

#### 定位

Scripts 是使用者上傳的「工具腳本資源」— 目錄結構 / 多檔案 / 混合副檔名都可能出現（`.py`、`.sh`、`.js`、`.ts`、`README.md`、`config.json` ...）。目的：讓使用者將常用腳本歸檔、收藏、分享（v1.4+）。

#### 與 Skill 的差異

| 面向 | Skill | Script |
| --- | --- | --- |
| 內容性質 | 規範 / 文件（md） | 可執行腳本 / 設定檔 |
| 上傳格式 | 單 zip（扁平 md 檔集合） | zip **或**「選資料夾」整批上傳（保留相對路徑） |
| 系統如何使用 | 對話時載入 `system_prompt` 用 | 僅作資源（v1.2 不執行） |
| 副檔名白名單 | `.md` / `.txt` | `.py` / `.sh` / `.js` / `.ts` / `.json` / `.yaml` / `.yml` / `.md` / `.txt` / `.csv`（可 `system_setting` 調整） |

#### 資料夾上傳的前端實作

HTML 原生支援：`<input type="file" webkitdirectory multiple>` — 瀏覽器回傳的 `File.webkitRelativePath` 就是使用者選取資料夾下的相對路徑。

前端組裝：

```ts
for (const file of files) {
  form.append("files", file);
  form.append("relative_paths", file.webkitRelativePath || file.name);
}
```

後端接 `files: list[UploadFile]` + `relative_paths: list[str]`（兩 list 位置對齊）。儲存時後端自行打包為 zip（保留目錄結構），統一以 zip 存進 `script.file_path`，跟 Skill 的儲存格式一致 → 下載 API 直接回 zip。

#### Schema

```sql
-- V35__create_script.sql
CREATE TABLE script (
    pid                  BIGSERIAL     PRIMARY KEY,
    script_uid           UUID          NOT NULL DEFAULT gen_random_uuid(),
    owner_user_uid       UUID          NOT NULL,
    name                 VARCHAR(255)  NOT NULL,
    description          TEXT,
    file_name            VARCHAR(255)  NOT NULL,   -- 原始檔 / 資料夾名
    file_path            VARCHAR(500)  NOT NULL,   -- 儲存後的 zip 路徑
    file_size            BIGINT        NOT NULL,
    favorite_count       INT           NOT NULL DEFAULT 0,
    download_count       INT           NOT NULL DEFAULT 0,
    is_active            BOOLEAN       NOT NULL DEFAULT TRUE,
    is_deleted           BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW()
    -- uq_(owner_user_uid, name) where is_deleted=false
    -- idx_(owner_user_uid), idx_(favorite_count DESC), idx_(download_count DESC)
);
```

#### API

沿用 Skill 的 REST 風格：

```text
GET    /api/v1/scripts?order_by=&page=&size=
POST   /api/v1/scripts                         # multipart: files[], relative_paths[], name, description
GET    /api/v1/scripts/{uid}
PATCH  /api/v1/scripts/{uid}                   # 改 name / description
DELETE /api/v1/scripts/{uid}                   # soft delete
GET    /api/v1/scripts/{uid}/download          # 下載 zip + download_count += 1
```

下載 API **豁免統一回應格式**（沿用 v1.1 附件下載的慣例，見 [Design-Base/20-backend.md](../../Design-Base/20-backend.md)），直接 StreamingResponse。

#### 設定

| system_setting key | 預設 | 最大 |
| --- | --- | --- |
| `script.max_total_size_mb` | 50 | 200 |
| `script.max_files_per_upload` | 200 | 1000 |
| `script.allowed_extensions` | `.py,.sh,.js,.ts,.json,.yaml,.yml,.md,.txt,.csv` | — |

安全：副檔名白名單 + 單檔 / 總大小上限 + zip bomb 檢測（解壓預估大小超過 `max_total_size_mb * 10` 就拒絕）。

### 2-4 儀錶板首頁排行 filter

#### UI 位置

儀錶板首頁目前卡片式呈現。新增一塊「排行榜」區塊，或改造既有「最近」清單成可切換排序：

```text
類型切換：  [全部]  [Agents]  [Skills]  [Scripts]
排序：      [最新]  [熱度 (下載)]  [收藏數]
```

兩切換相交叉，展示 top N（預設 10，可在 `system_setting` 調 `dashboard.ranking_size`）。

#### 後端：統一 ranking endpoint

單一 API 跨三類資源：

```text
GET /api/v1/dashboard/rankings?type=all|agent|skill|script
                             &order_by=download_count|favorite_count|created_at
                             &limit=10
```

回傳格式（混合類型時以統一 shape 回傳，所有欄位為必填，不可省略）：

```json
{
  "items": [
    {
      "type": "skill",
      "uid": "c6f9…",
      "name": "Kubernetes Debug Toolkit",
      "description": "常用 kubectl 指令集合",
      "favorite_count": 32,
      "download_count": 127,
      "is_favorited": true,
      "owner": {
        "user_uid": "a1b2…",
        "display_name": "Jiaye He"
      },
      "created_at": "2026-04-10T08:30:00Z",
      "updated_at": "2026-04-18T12:15:00Z"
    }
  ]
}
```

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `type` | `"agent"` / `"skill"` / `"script"` | 資源類型 |
| `uid` | UUID | 對應 `<type>_uid`（agent_uid / skill_uid / script_uid） |
| `name` | string | 顯示名稱 |
| `description` | string \| null | 描述（可為空） |
| `favorite_count` | int | 收藏數（denormalized） |
| `download_count` | int | 下載數（denormalized；agent 恆為 0，UI 可隱藏） |
| `is_favorited` | bool | 當前使用者是否已收藏此項 |
| `owner` | object | 擁有者資訊，shape 固定為 `{user_uid, display_name}` |
| `created_at` | ISO8601 TIMESTAMPTZ | 建立時間 |
| `updated_at` | ISO8601 TIMESTAMPTZ | 最後更新時間 |

實作：三類資源各自 query top N → 合併 → 依 `order_by` 統一重排 → 截 limit。資源數量小（單人量級）不用擔心成本。

#### 權限

本版僅顯示「使用者擁有的資源」— 因為公開可見性尚未導入（留 v1.4）。排行本質是**使用者自己的使用習慣排名**，不是全平台 marketplace。UI 文案需點明「你最常用的」避免期待錯位。

### 2-5 Sidebar 分組調整（UX 修補）

#### 問題

目前 `Sidebar.tsx` 的 `SIDEBAR_ITEMS` 是**單一平面列表**，admin 視角下 8 項全部同層堆疊：

```
儀表板 / Agent 管理 / Skill 管理 / 使用者管理 / LLM 模型管理 / 語言管理 / Agent 範本 / 系統設定
```

v1.2 再插入 Script 管理 → 變 9 項，且「個人資源管理」與「系統管理」混雜，視覺上不好辨識。

#### 調整方向：依功能分三組 + 分隔線 + group label

```text
── 概覽 ──
  儀表板

── 我的資源 ──
  Agent 管理
  Skill 管理
  Script 管理          ← v1.2 新增

── 系統管理（admin）──
  使用者管理
  LLM 模型管理
  語言管理
  Agent 範本
  系統設定
```

- 一般使用者僅看見「概覽」+「我的資源」兩組（系統管理整組隱藏）
- admin 看見三組完整；整組皆為 `adminOnly` 時，group label 一併隱藏
- Collapsed 狀態：分隔線仍顯示，group label 隱藏（保留視覺節奏）

#### 資料結構調整

`SIDEBAR_ITEMS` 由 `SidebarItem[]` 改為 `SidebarGroup[]`：

```ts
interface SidebarGroup {
  key: string;                // 'overview' / 'resources' / 'admin'
  label: string;              // 'admin' 群組的中文標籤
  adminOnly?: boolean;        // 整組僅 admin 可見
  items: SidebarItem[];
}
```

渲染邏輯：先依 `adminOnly` + 使用者 role 過濾整組；組內的 `item.adminOnly` 保留以支援混合群組（例 v1.2 內無此需求，但保留彈性）。

#### 權衡

- **純排序不加分組**：工程量最小，但「同類型擺在一起」仍屬視覺約定，未來再加項目又會回到「混雜」狀態
- **分組 + 分隔線 + label**：工程量略增（資料結構 + 渲染），但可長期吸收新功能 — 採此方案

#### Design-Base/11-ui-ux.md 異動清單

本版於 `11-ui-ux.md` Header 節後、頁面佈局節前**新增 §Sidebar 節**，規範內容如下：

| 子節 | 內容 |
| --- | --- |
| 三態循環 | 將既有行為（expanded `w-56` / collapsed `w-16` / hidden `w-0`）整理為規範表格；`md` 以下 overlay 模式 |
| 分組結構 | 新增 `SidebarGroup` + `SidebarItem` 資料結構（兩層） |
| 首發分組（v1.2） | 明列三組：`overview`（概覽，公開）/ `resources`（我的資源，公開）/ `admin`（系統管理，adminOnly） |
| 權限與顯示規則 | 整組 `adminOnly` 對非 admin 完全隱藏（含 label 與分隔線）；項目層級 `adminOnly` 僅隱藏該項；collapsed 狀態 label 隱藏、分隔線保留 |
| 擴充協議 | 加項目 / 開新組 / 權限隔離三情境規範 |

> 先前 `11-ui-ux.md` 無 Sidebar 節（僅於 §Header / §RWD 片段提及），本版獨立成節，補齊規範覆蓋面。

### 2-6 主題切換器重構（系列化 + Dialog 化）

> 配套規範已寫入 [Design-Base/11-ui-ux.md](../../Design-Base/11-ui-ux.md)；本節記錄動機、範圍邊界，並完整列出 Design-Base 本版異動，供後人讀此 propose 即可掌握 UI/UX 規範變動全貌。

#### 問題

目前主題切換器以**懸浮下拉**呈現 5 個扁平選項（淺色 / 深色 / 冷色系 / 暖色系 / 粉紫色），當未來擴充（新系列、使用者自訂主題）時，下拉列表會撐破 Header 附近版面、小螢幕易切邊界，也沒空間放色彩預覽。

#### 調整方向

1. **命名升級**：主題名稱改為有設計感的「光影」系列（晨曦 / 霧境 / 夕映 / 暮霞 / 深夜），主題 `id` 沿用舊值避免 localStorage 遷移
2. **結構化**：主題資料結構改為「系列（ThemeSeries） + 成員（ThemeItem）」兩層，帶 `source: 'builtin' | 'user'` 欄位為未來自訂主題預留擴充點
3. **UI 改為 Content Dialog**：Header 主題按鈕改為開啟 Content Dialog，系列分區排列、每張主題卡帶色彩縮影 thumb（CSS 色塊動態繪製），點擊即時套用、取消可回復
4. **Dialog 元件擴充**：既有 Dialog 僅支援提示型（Info/Warning/Error），需新增 Content Dialog 類型（自訂 children、`sm/md/lg` 尺寸、`onConfirm` 與 `onDismiss` 分離）

#### Design-Base/11-ui-ux.md 異動清單

本版對 UI/UX 規範的具體修訂如下（完整內容以 Design-Base 檔案為準）：

**§佈景主題 — 整節重寫**

| 變更 | Before | After |
| --- | --- | --- |
| 組織結構 | 單層列表（淺色 / 深色 / 冷 / 暖 / 紫） | 兩層：**ThemeSeries（系列）** + **ThemeItem（主題成員）** |
| 資料結構 | 無 TS interface，CSS Variable 為唯一真相 | 新增 `ThemeColors` / `ThemeItem` / `ThemeSeries` interface，並規範 `id` 不可改、`labelZh/labelEn/icon` 可調、`colors` 為宣告式真相、`source` 區分 builtin / user |
| 主題命名 | 淺色 / 深色 / 冷色系 / 暖色系 / 粉紫色 | 光影系列：晨曦 Dawn / 霧境 Nordic / 夕映 Ember / 暮霞 Twilight / 深夜 Midnight（id 不變） |
| 擴充協議 | 無規範 | 明定三種擴充路徑：同族新增 `ThemeItem` / 跨族新增 `ThemeSeries` / 使用者自訂主題（`source: 'user'`）採動態注入 inline style，不污染 `globals.css` |
| 主題選擇 UI 規範 | 無（散落在 Header 節） | 獨立子節「主題選擇 UI（ThemeSwitcher）」：Content Dialog 呈現、系列分區、卡片帶 thumb + 中英雙語、即時套用、取消回復、`source: 'user'` 卡右上顯示編輯 / 刪除 |

**§Header — 主題按鈕行為改寫**

- Before：「主題切換按鈕點擊後展開下拉選單，列出所有可用主題（淺色 / 深色 / 冷色系 / 暖色系 / 粉紫色）」
- After：指向「主題選擇 UI」節（Content Dialog 承載），並明定**不採用懸浮下拉**（理由：無法承載多系列擴充與使用者自訂）

**§Dialog 元件 — 擴充類型分族**

| 變更 | Before | After |
| --- | --- | --- |
| 分類 | 單一族「三類」（Info / Warning / Error） | 分**兩族**：提示型（Info / Warning / Error，保留原樣）+ 內容型（Content Dialog，新增） |
| 新增 Content Dialog | — | 結構 `title` + 自訂 `children` + 動作列；尺寸 `sm` / `md` / `lg`（預設 md）；`onConfirm` / `onDismiss` 分離以支援「即時副作用 + 取消可回復」；ESC / 遮罩 / X 均觸發 `onDismiss`；小螢幕（`< sm`）自動轉 bottom sheet |
| 使用範例 | 僅 `showDialog` 用法 | 新增 `showContentDialog` 用法，以主題選擇器為示範情境 |

#### v1.2 範圍邊界

**做**：
- 系列 + 主題資料結構（含 `source` / `colors` 欄位）
- Dialog 化切換器、主題卡 thumb 預覽（CSS 色塊，不做 build-time image）
- 光影系列 5 個內建主題的中英文命名、icon 更新
- Dialog 元件擴充出 Content Dialog 類型（此為通用基建，後續複雜表單亦可用）

**不做**（留給未來版本）：
- 使用者自訂主題的調色盤 UI、`user_theme` DB 表、儲存 API
- 主題分享 / 匯出 / 匯入
- 其他系列（礦石、無障礙等）的主題

#### 資料遷移

無。主題 `id` 不變，使用者 localStorage 內的 `agents-platform-theme` 舊值（`light` / `dark` / `cool` / `warm` / `purple`）直接對應新的光影系列 `ThemeItem.id`。

---

## 3. 子版本 Roadmap

| 子版本 | 主題 | 性質 | 時程估 | 前後相依 |
| --- | --- | --- | --- | --- |
| v1.2.1 | 計數欄位 + user_favorite + API（§2-1） | Schema + 後端 | 1-2 天 | 無，最底層 |
| v1.2.2 | 管理頁 filter nav + 收藏按鈕（§2-2） | 前端 | 1-2 天 | v1.2.1 |
| v1.2.3 | 腳本管理（§2-3）+ Sidebar 分組（§2-5）+ 主題切換器重構（§2-6） | 後端 + 前端新頁 + Sidebar 重構 + ThemeSwitcher Dialog 化 | 4-6 天 | v1.2.1 的 favorite / download 機制 |
| v1.2.4 | 儀錶板排行 filter（§2-4） | 後端 + 前端 | 1-2 天 | v1.2.1（資料）、v1.2.3（Script 資料來源） |

v1.2.1 是入口，其他三項都可在 v1.2.1 完成後平行開工（前端檔案衝突需協調，見 §5）。

---

## 4. 跟前後版本的銜接

### 與 v1.1 / v1.1 延伸

- Skill 的 zip 下載 API：v1.1 已存在 → v1.2.1 只需在該 handler 加一行 `download_count += 1`
- Agent 目前沒有「下載」語意（Agent 是 DB 記錄而非檔案），但仍保留 `download_count` 欄位 — 未來若支援「Agent export / import」會用到；v1.2 內該欄位始終 0，前端可暫不顯示

### 與新 v1.3（原 v1.2 內容）

- 多 Agent 對話仍與 v1.2 無交集 — Session ↔ Agent schema 不動
- Agentic Skill 工廠推薦的 Skill 被使用者 approve 後，計入 `skill.download_count`（使用者 approve 即視為「下載到自己的庫」）
- 跨層記憶 / classifier / 可觀察性完全獨立

### 與新 v1.4（原 v1.3 內容）

- v1.4 儀表板 AI 查詢是 v1.2.4 排行 filter 的**延伸**：v1.2 規則排序（量化） → v1.4 自然語言查詢（語意）
- v1.4 公開 API + 社群共享是**收藏 / 下載**真正跨使用者流動的舞台；v1.2 已備好 `user_favorite` schema，v1.4 只需放寬 `owner_user_uid` 篩選

---

## 5. 跨子版本衝突檢查

| 動到 | 1.2.1 | 1.2.2 | 1.2.3 | 1.2.4 |
| --- | --- | --- | --- | --- |
| `agent` / `skill` 表 | ✓（V33 加欄位） | ✗ | ✗ | ✗ |
| `user_favorite` 表 | ✓（V34 新表） | ✗ | ✗ | ✗ |
| `script` 表 | ✗ | ✗ | ✓（V35 新表） | ✗ |
| Redis 服務與 client | ✓（新增） | ✗ | ✗ | ✗ |
| Sidebar 元件 | ✗ | ✗ | ✓（加項目 + 分組重構，§2-5） | ✗ |
| ThemeSwitcher 元件 | ✗ | ✗ | ✓（重構為 Dialog，§2-6） | ✗ |
| Dialog 元件 | ✗ | ✗ | ✓（擴充 Content Dialog，§2-6） | ✗ |
| 管理頁 filter | ✗ | ✓ | ✓（同 UI pattern） | ✗ |
| 儀錶板首頁 | ✗ | ✗ | ✗ | ✓ |

**需協調**：
- Flyway 版號 V33（agent/skill 加欄位）→ V34（user_favorite）→ V35（script），v1.2.1 合入 V33 + V34，v1.2.3 合入 V35，避免 out-of-order
- 前端管理頁 filter nav 由 v1.2.2 定 pattern，v1.2.3 Scripts 頁沿用

---

## 6. 驗收（初稿）

### 基本功能
- [ ] Agents / Skills / Scripts 每筆卡片顯示 `⭐ favorite_count` `⬇ download_count`
- [ ] 收藏 / 取消收藏 即時反映計數變化（無頁面 reload）
- [ ] 同一使用者 24h 內重複下載同一 Skill / Script，`download_count` 只加 1
- [ ] 管理頁三段式 filter（全部 / 我的 / 我的收藏）正確篩選
- [ ] Scripts 上傳整個資料夾後，下載回來的 zip 保留相對路徑結構
- [ ] Scripts 副檔名白名單外的檔案被拒、zip bomb 被拒
- [ ] 儀錶板首頁排行 filter 能依熱度 / 收藏 / 最新切換，類型切換正確
- [ ] Skill 被 Agentic Skill 工廠 approve 時，該 Skill 的 `download_count` 合理累加（+1）

### 列表 / API 行為
- [ ] 列表 API response 每項帶 `is_favorited`，前端星號 UI 狀態與 `/users/me/favorites` 一致（無 stale UI）
- [ ] 列表 API `order_by` × `page` / `size` × 既有搜尋參數（`q` 等）可任意組合不崩
- [ ] Ranking API `type=all` 時能跨三類正確混排，`type=agent|skill|script` 時單類正確
- [ ] Ranking API 每個 item 欄位齊全（`type` / `uid` / `name` / `description` / `favorite_count` / `download_count` / `is_favorited` / `owner` / `created_at` / `updated_at`），`owner` shape 為 `{user_uid, display_name}`

### Sidebar 分組
- [ ] Sidebar 呈現三組「概覽 / 我的資源 / 系統管理」，組間有分隔線與 group label
- [ ] 一般使用者僅見「概覽」+「我的資源」兩組，`系統管理` 整組（含 label 與分隔線）隱藏
- [ ] admin 登入後看見三組完整，新加 `Script 管理` 位於「我的資源」組內，緊接在 `Skill 管理` 之後
- [ ] Sidebar collapsed 狀態下分隔線仍顯示、group label 隱藏，點擊仍可正確導航

### 主題切換器
- [ ] Header 主題按鈕點擊後開啟 Content Dialog，**不再**顯示懸浮下拉選單
- [ ] Dialog 內以「光影 Atmosphere」系列為分區標題，下方排列 5 張主題卡
- [ ] 每張主題卡含色彩縮影 thumb（反映 `background / foreground / primary / accent`）、中文主標、英文副標
- [ ] 當前選中主題卡以 `ring-primary` 標示
- [ ] 點擊主題卡即時套用全頁，不需按確認
- [ ] 按「取消」回復 Dialog 開啟前主題；按 ESC / 點遮罩 / X 保留當前選擇
- [ ] 小螢幕（`< sm`）Dialog 轉為底部滑出式（bottom sheet）
- [ ] 使用者原本的 localStorage 主題值（舊 `cool` / `warm` / `purple`）重新整理後仍正確映射到新命名主題，不會被重設為預設
- [ ] `ThemeItem` 資料結構含 `source` 與 `colors` 欄位，v1.2 內所有主題 `source = 'builtin'`

### 被刪除資源的 tombstone
- [ ] 使用者收藏的 Skill / Agent / Script 被擁有者刪除後，`GET /users/me/favorites` 該項仍保留，`resource = null`，帶 `tombstone_reason = "resource_removed"`
- [ ] 前端「我的收藏」對 tombstone 項呈現「⚠ 此資源已被移除」卡片，且提供「從收藏移除」按鈕

### 基礎建設
- [ ] Redis 服務於 docker-compose 啟動正常，後端 `REDIS_HOST / PORT / DB` env 連線成功
- [ ] Flyway 依序套用 V33 → V34（v1.2.1）→ V35（v1.2.3）無 out-of-order 錯誤
- [ ] 所有新增 API 皆於 `/api/docs` Swagger 可見，Request / Response Schema 正確

---

## 7. 下一步

1. 本 propose 定稿
2. 起手 `tasks-v1.2.1.md`（最底層，其他三個都依賴它）
3. v1.2.2 / v1.2.3 / v1.2.4 依需要擇優開工
4. 每子版本完成後**回填** `tasks-v1.2.X.md` 狀態標題（CLAUDE.md §任務文件回填）
