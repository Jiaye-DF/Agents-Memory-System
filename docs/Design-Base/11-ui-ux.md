# UI / UX 規範

樣式、主題、共用元件的視覺與互動規則。

> 元件工程結構（目錄、命名）參閱 [10-frontend.md](10-frontend.md)

---

## 整體風格

- 全站統一 `rounded-xl`（卡片、按鈕、輸入框、Dialog 等）
- 可點選元素**必須**加 `hover:cursor-pointer`
- 間距一律使用 Tailwind spacing scale（`p-4`、`gap-6`），不用任意數值

---

## 佈景主題

### 架構：系列（Series） + 主題（Theme）

兩層結構（系列 + 成員），為多系列擴充與使用者自訂主題預留彈性。

```ts
interface ThemeColors {
  background: string;
  foreground: string;
  primary: string;
  accent: string;
  // 其他項依 globals.css 擴充
}

interface ThemeItem {
  id: string;                   // builtin 如 'light'，user 如 'custom-<uuid>'
  labelZh: string;              // 中文主標
  labelEn: string;              // 英文副標
  icon: string;                 // Unicode 符號或 SVG 路徑
  colors: ThemeColors;          // 宣告式配色（thumb 繪製與自訂注入共用）
  source: 'builtin' | 'user';
}

interface ThemeSeries {
  key: string;                  // 'atmosphere' / 'gemstone' / 'user-custom'
  label: string;
  labelEn: string;
  source: 'builtin' | 'user';
  themes: ThemeItem[];
}
```

**關鍵原則**：

- 主題 `id` 一旦發布**不得改名**（綁 localStorage 值與 CSS 選擇器）
- 顯示欄位（`labelZh` / `labelEn` / `icon`）可隨時調整
- `colors` 為宣告式真相，須與 `globals.css` 對齊；`source: 'user'` 改以動態注入 `<html>` inline style，不寫入 CSS 檔
- `source: 'user'` 卡片右上角顯示「編輯 / 刪除」，`builtin` 則無

### 首發系列：光影 Atmosphere（v1.2）

以「一日光影變化」為敘事軸，五個主題分別對應不同時刻氛圍：

| id | labelZh | labelEn | icon | 氛圍 |
| --- | --- | --- | --- | --- |
| light | 晨曦 | Dawn | ◐ | 清透白光 |
| cool | 霧境 | Nordic | ❅ | 清冷霧藍 |
| warm | 夕映 | Ember | ◉ | 暖陽餘暉 |
| purple | 暮霞 | Twilight | ✦ | 霞紫漸層 |
| dark | 深夜 | Midnight | ☾ | 靜謐黑墨 |

> `id` 沿用舊值以避免 localStorage 遷移；僅顯示名與 icon 為新命名。

### 擴充協議

- **同族擴充**：既有系列新增 `ThemeItem`
- **跨族擴充**：新增 `ThemeSeries`，Dialog 自動多一個分區
- **使用者自訂**（v1.2 不實作）：獨立系列 `user-custom`，`colors` 存 DB，套用時動態注入 `<html>` 的 CSS Variable，不污染 `globals.css`

### 實作方式

- 色彩一律走 `globals.css` 的 CSS Variables，元件內**禁止**寫死 hex 色碼
- 透過 `<html data-theme="<id>">` 切換（`light` = `:root`、`dark` = `.dark`、其餘 `[data-theme="<id>"]`）
- 偏好存 localStorage（key：`agents-platform-theme`），重新載入時自動套用
- **例外**：`app/global-error.tsx` 因 `globals.css` 未載入，允許 inline style + 中性色 hex（如 `#6b7280`）呈現純文字錯誤頁，不得含業務邏輯

```css
/* globals.css 範例（需與 ThemeItem.colors 對齊） */
:root {                    /* id: light，晨曦 Dawn */
  --color-background: #ffffff;
  --color-foreground: #171717;
  --color-primary: #2563eb;
  --color-accent: #3b82f6;
}

.dark {                    /* id: dark，深夜 Midnight */
  --color-background: #0a0a0a;
  --color-foreground: #ededed;
  --color-primary: #60a5fa;
  --color-accent: #93c5fd;
}

/* 其餘主題 (cool / warm / purple) 以 [data-theme="<id>"] 同模式宣告 */
```

### 主題選擇 UI（ThemeSwitcher）

- Header 主題按鈕開啟 **Content Dialog**，不用懸浮下拉（無法承載多系列擴充）
- Dialog 內以系列分區（垂直），各系列下為主題卡片 grid
- 卡片：色彩縮影 thumb（依 `colors` 動態繪製）+ `labelZh` / `labelEn`，選中以 `ring-primary` 標示
- **即時套用**：點擊即套用全頁
- **取消回復**：「取消」回復原主題；關閉（ESC / 遮罩 / X）**保留**當前選擇
- `source: 'user'` 卡片右上角顯示「編輯 / 刪除」

---

## Header

Header 為全站共用，固定於頂部，結構如下：

```text
┌──────────────────────────────────────────────────────────────────┐
│  [☰] [SVG 圖示] Agents-Platform          [🎨] {Username} [登出] │
└──────────────────────────────────────────────────────────────────┘
```

- **左側**：Sidebar 切換（☰）+ SVG 圖示 + 「Agents-Platform」文字（點擊回主頁）
- **右側**：主題切換（🎨）+ `{Username}` + 登出
- 主題按鈕行為見 [主題選擇 UI](#主題選擇-uithemeswitcher)
- Sidebar 按鈕循環三態：完整展開（圖示+文字）→ 收合（僅圖示）→ 完全隱藏
- `md` 以下 Sidebar 預設隱藏，點擊以 overlay 展開
- Header 高度固定，背景跟隨主題 CSS Variable
- `sm` 以下「Agents-Platform」文字隱藏，僅保留 SVG 圖示

---

## 頁面佈局

所有登入後頁面（`(main)` 群組）共用相同的 main section 佈局結構：

```text
Sidebar 展開：                          Sidebar 隱藏：
┌──────────────────────────────────┐    ┌──────────────────────────────┐
│             Header               │    │            Header            │
├────────┬─────────────────────────┤    ├──────────────────────────────┤
│        │       Page Title        │    │         Page Title           │
│Sidebar │ ┌─────────────────────┐ │    │ ┌──────────────────────────┐ │
│        │ │                     │ │    │ │                          │ │
│        │ │   Main Content      │ │    │ │      Main Content        │ │
│        │ │                     │ │    │ │                          │ │
│        │ └─────────────────────┘ │    │ └──────────────────────────┘ │
└────────┴─────────────────────────┘    └──────────────────────────────┘
```

- 每個頁面含 **Page Title** + **Main Content 卡片容器**（`rounded-xl` + 背景 + 陰影）
- 外層佈局由 `(main)/layout.tsx` 統一控制，**禁止**頁面自行定義

---

## Dialog 元件

- **禁止** `alert()` / `confirm()` / `prompt()`，一律走 Dialog 元件
- 透過共用 Hook / Store（如 `useDialog`）程式觸發，無須逐一引入元件
- 容器 `rounded-xl`

分兩族：**提示型**（Info / Warning / Error）承載訊息，**內容型**（Content）承載表單 / 選擇器。

### 提示型 Dialog

| 類型    | 用途           | 圖示/色調 | 預設按鈕    |
| ------- | -------------- | --------- | ----------- |
| Info    | 一般資訊告知   | 藍色      | 確認        |
| Warning | 需使用者注意   | 黃色      | 取消 / 確認 |
| Error   | 錯誤或失敗通知 | 紅色      | 確認        |

使用範例：

```typescript
const { showDialog } = useDialog();
showDialog({ type: "error", title: "操作失敗", message: "無法取得資料" });
```

### 內容型 Dialog（Content Dialog）

承載表單、選擇器、複雜流程：

- 結構：`title` + `children`（JSX slot）+ 動作列
- 尺寸 `sm` / `md` / `lg`（預設 `md`）
- 即時副作用場景：`onConfirm` 保留變更、`onDismiss` 回復（ESC / 遮罩 / X 皆觸發 `onDismiss`）
- `< sm` 自動轉底部滑出式（bottom sheet）

```typescript
const { showContentDialog } = useDialog();
showContentDialog({
  title: "選擇主題",
  size: "md",
  children: <ThemePicker />,
  onDismiss: () => revertToOriginalTheme(),  // 回復副作用
  onConfirm: () => persistThemeChoice(),     // 即時副作用場景可省
});
```

---

## 表單驗證回饋

- 欄位錯誤：即時顯示於欄位下方（紅色文字）
- 伺服器錯誤：以 Error Dialog 呈現
- 送出按鈕請求期間顯示 loading 並禁用

---

## 響應式設計（RWD）

**Mobile First**，採 Tailwind 預設斷點：

| 斷點 | 寬度      | 佈局變化                      |
| ---- | --------- | ----------------------------- |
| 預設 | < 640px   | 單欄、Sidebar 為漢堡選單      |
| `sm` | >= 640px  | 單欄、間距微調                |
| `md` | >= 768px  | Sidebar 展開、雙欄            |
| `lg` | >= 1024px | Main Content 加寬             |
| `xl` | >= 1280px | 最大寬度、置中                |

- `md` 以下 Sidebar 收為漢堡選單，點擊以 overlay 展開
- 表格於小螢幕可水平捲動或轉卡片式
- 觸控區域至少 44x44px（a11y）

---

## Loading 狀態

- 頁面級：全頁 Skeleton 或 Spinner
- 元件級：局部 Skeleton，避免整頁閃爍
- 按鈕：操作中顯 Spinner 並禁用
