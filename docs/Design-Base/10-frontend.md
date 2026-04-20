# 前端規範

> 技術棧與版本定義參閱 [00-overview.md § 前端](00-overview.md#前端)

---

## 目錄結構

```text
frontend/src/
├── app/                        # App Router 頁面與佈局
│   ├── layout.tsx              # 根佈局
│   ├── error.tsx               # 路由層錯誤邊界（必備）
│   ├── global-error.tsx        # 全域錯誤邊界（必備）
│   ├── (auth)/                 # 未登入狀態的路由群組
│   │   ├── layout.tsx          # Auth 佈局（無 Sidebar）
│   │   └── page.tsx            # "/" 首頁 = 登入頁面
│   └── (main)/                 # 登入後的主要功能路由群組
│       ├── layout.tsx          # Main 佈局（含 Header、Sidebar）
│       ├── dashboard/
│       │   └── page.tsx        # 儀表板
│       ├── agents/
│       │   └── page.tsx        # Agent 管理
│       ├── skills/
│       │   └── page.tsx        # Skills 管理
│       ├── memories/
│       │   └── page.tsx        # 記憶管理
│       └── conversations/
│           └── page.tsx        # 對話管理
├── components/                 # 共用 UI 元件
│   ├── ui/                     # 基礎元件（Button、Input、Dialog 等）
│   └── layout/                 # 佈局元件（Header、Sidebar 等）
├── lib/
│   └── api/                    # API Client（統一出口）
│       ├── client.ts           # 基礎 fetch 封裝
│       └── endpoints/          # 依資源分檔
├── store/                      # Redux Store
│   ├── store.ts                # Store 設定
│   ├── provider.tsx            # StoreProvider 元件
│   └── api.ts                  # RTK Query baseApi
├── hooks/                      # 自定義 Hook
├── types/                      # 共用型別定義
└── utils/                      # 工具函式
```

### 路由群組說明

- `(auth)` — 未登入狀態。`page.tsx` 掛載於 `/`，即首頁直接顯示登入表單，**不設獨立 `/login` 路徑**
- `(main)` — 登入後功能區。共用含 Header / Sidebar 的佈局，未登入時重導至 `/`
- 兩個群組使用 Next.js Route Group（括號目錄），不影響 URL 結構

---

## 錯誤處理

- `app/error.tsx` 與 `app/global-error.tsx` 為**必備檔案**，專案建立時即須建立
- `error.tsx` 處理路由層級的執行期錯誤，須為 Client Component（`"use client"`）
- `global-error.tsx` 處理根佈局層級的錯誤，作為最後防線

---

## API 呼叫

- 元件**禁止**直接使用 `fetch` 或 `axios`，所有 API 呼叫須透過 `lib/api/*` 或 RTK Query
- 伺服器資料（需快取、同步）使用 **RTK Query**
- 僅前端本地狀態使用 Redux Toolkit slice

---

## 狀態管理

- 全域狀態由 **Redux Toolkit** 管理
- 伺服器資料使用 **RTK Query**（基於 `createApi`），不自行管理 loading / error 狀態
- 元件本地狀態使用 `useState` / `useReducer`，不需提升至 Redux

---

## 共用邏輯（Hooks 與 UI 元件）

跨頁面出現**三次以上**的邏輯**必須**抽成共用方法，不得各頁重複實作。既有共用層請直接使用，不可另起爐灶。

### 必備共用 Hooks（`frontend/src/hooks/`）

| Hook | 用途 | 取代模式 |
| --- | --- | --- |
| `useAuth` | 取得登入狀態、`role`、`username`；自動解析 JWT | 手動解析 token |
| `useDialog` | 觸發全站 Dialog（`info` / `warning` / `error`） | `alert()` / `confirm()` |
| `useSidebar` | Sidebar 三態切換與 overlay 控制 | 各自管理 state |
| `useTheme` | 讀寫當前主題、持久化至 `localStorage` | 自行讀 `document` |
| `useAdminGuard` | admin 路由守衛；非 admin 自動導向 `/403` | `useEffect + router.replace("/403")` |
| `useCursorPagination` | Cursor-based 分頁 state + 上/下一頁 + 換 limit | 手寫 `cursor` / `cursorHistory` |
| `useFilteredList` | 列表依 `searchTerm` + `predicates` 過濾 | 各頁自寫 `useMemo` filter |
| `useMutationWithDialog` | RTK mutation + 成功 info / 失敗 error Dialog | 各頁 try/catch + showDialog |
| `useConfirmMutation` | Warning Dialog 確認後執行 mutation | 手寫 `showDialog({ type: "warning", onConfirm })` |

### 必備共用 UI 元件（`frontend/src/components/ui/`）

| 元件 | 用途 |
| --- | --- |
| `Button` / `Input` / `Toggle` / `Slider` / `MultiSelect` / `PasswordStrengthBar` | 基礎輸入元件 |
| `Dialog` | 由 `useDialog` 自動渲染；**禁止**直接 import |
| `ModalDialog` | 所有彈出式表單 / 選擇器的容器（自動處理 portal、overlay click 關閉、ESC 關閉、`body` scroll 鎖） |
| `Table` / `Pagination` / `Loading` | 列表頁標配元件 |

### 新增共用方法的時機

- 同一段邏輯即將被 **第三次** copy 時，**必須**先抽成共用方法再實作；只出現兩次時，可暫緩。
- 抽象時**必須**：放到對應目錄（hook 進 `hooks/`、純邏輯進 `utils/`、UI 進 `components/ui/`）；**必須**以 TypeScript `interface` 定義參數與回傳；**必須**在該模組開頭以一句 JSDoc 說明用途。
- **禁止**在頁面檔案內宣告名為 `FormDialog`、`XXXDialog` 等包含 overlay / ESC / portal 的自訂彈窗 — 一律以 `ModalDialog` 為外殼。

### 既有頁面遷移原則

- 新增功能若在列表頁、admin 管理頁、可彈窗的表單場景，**必須**使用上述 hooks 與元件；發現現行頁面未使用，應順手替換（不需獨立 commit）。
- 修改既有頁面時若撞見重複模式超過一頁，應一次改齊，避免半遷移狀態。

---

## 環境變數

- 客戶端可存取的環境變數**必須**使用 `NEXT_PUBLIC_` 前綴
- **禁止**在客戶端程式碼中引用無 `NEXT_PUBLIC_` 前綴的環境變數（編譯時為 `undefined`，且可能洩漏敏感資訊）
- 所有環境變數須登記於根目錄 `.env.example`

---

## 命名慣例

| 對象         | 慣例          | 範例                     |
| ------------ | ------------- | ------------------------ |
| 元件檔案     | PascalCase    | `AgentCard.tsx`          |
| 元件目錄     | PascalCase    | `AgentCard/index.tsx`    |
| Hook         | camelCase     | `useAgentList.ts`        |
| 工具函式     | camelCase     | `formatDate.ts`          |
| 型別/介面    | PascalCase    | `AgentConfig`            |
| CSS Variable | kebab-case    | `--color-background`     |
| 路由目錄     | kebab-case    | `app/agent-settings/`    |

---

## TypeScript 規則

- 所有函式**必須**明確標註參數型別與回傳型別，**禁止**依賴隱式推導
- **禁止**使用 `any`，若型別確實無法確定，使用 `unknown` 並搭配型別守衛收窄
- 優先使用 `interface` 定義物件結構；`type` 用於聯合型別、交集型別、工具型別等場景
- React 元件 props **必須**定義獨立的 `interface`，不使用行內匿名型別

```typescript
// 正確
interface AgentCardProps {
  name: string;
  isActive: boolean;
  onSelect: (uid: string) => void;
}

function AgentCard({ name, isActive, onSelect }: AgentCardProps): React.ReactNode {
  // ...
}

// 錯誤 — 缺少回傳型別、props 未定義 interface
function AgentCard({ name, isActive, onSelect }) {
  // ...
}
```

```typescript
// 正確
async function fetchAgents(page: number): Promise<AgentListResponse> {
  // ...
}

// 錯誤 — 參數與回傳型別皆未標註
async function fetchAgents(page) {
  // ...
}
```

---

## 渲染效能

避免不必要的 re-render，以下為必須遵守的規則：

- 傳入子元件的 **callback** 須以 `useCallback` 包裹，避免每次渲染產生新函式參考
- 計算成本較高的衍生資料須以 `useMemo` 快取，避免重複運算
- 清單項目元件若 props 未變更不應重新渲染，使用 `React.memo` 包裹
- **禁止**在 render 中建立物件或陣列字面值作為 props（每次渲染皆為新參考）

```typescript
// 正確
const handleSelect = useCallback((uid: string): void => {
  dispatch(selectAgent(uid));
}, [dispatch]);

<AgentList onSelect={handleSelect} />

// 錯誤 — 每次渲染建立新函式，導致 AgentList 不必要 re-render
<AgentList onSelect={(uid) => dispatch(selectAgent(uid))} />
```

```typescript
// 正確
const filterOptions = useMemo((): FilterOption[] => {
  return agents.filter((a) => a.isActive);
}, [agents]);

// 錯誤 — 每次渲染重新計算
const filterOptions = agents.filter((a) => a.isActive);
```

- 使用 React DevTools Profiler 檢查是否有非預期的重複渲染
- Redux selector 須精確選取所需欄位，避免整個 slice 變更觸發無關元件更新

---

## 日期時間顯示

- 後端回傳的時間欄位（`created_at`、`updated_at`、`locked_until` 等）已是 **UTC+8 的 wall-clock 值**（詳見 [21-database.md § 時區](21-database.md#時區重要)）
- **禁止**使用 `new Date().toLocaleString(...)` 或帶 `timeZone` 選項的 API 做轉換，瀏覽器會再偏移一次導致顯示錯誤
- 一律使用 `utils/datetime.ts` 的 `formatDateTime()`，該函式直接從 ISO 字串正規地抽出 `YYYY/MM/DD HH:mm:ss`，不經過 `Date` 物件

```typescript
// 正確
import { formatDateTime } from "@/utils/datetime";
<span>{formatDateTime(user.created_at)}</span>

// 錯誤 — 會觸發瀏覽器時區偏移
<span>{new Date(user.created_at).toLocaleString("zh-TW")}</span>
<span>{new Date(user.created_at).toLocaleString("zh-TW", { timeZone: "Asia/Taipei" })}</span>
```

---

## 其他注意事項

- 圖片、靜態資源放置於 `public/`，引用時使用絕對路徑（`/images/logo.png`）
- 第三方外部服務 API **禁止**從前端直接呼叫，須經由後端代理
- 頁面若需 SEO，優先使用 Server Component 搭配 `metadata` export
