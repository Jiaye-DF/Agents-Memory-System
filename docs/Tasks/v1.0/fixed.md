# v1.0 修正記錄

## 1. RTK Query endpoint 名稱衝突

**問題**：`agentsApi` 與 `skillsApi` 都定義了 `toggleVisibility` endpoint，注入同一個 `baseApi` 時發生名稱衝突，Console 報錯 `called injectEndpoints to override already-existing endpointName toggleVisibility`。

**修正**：

- `agentsApi.ts`：`toggleVisibility` → `toggleAgentVisibility`，hook 改為 `useToggleAgentVisibilityMutation`
- `skillsApi.ts`：`toggleVisibility` → `toggleSkillVisibility`，hook 改為 `useToggleSkillVisibilityMutation`
- 同步更新 `agents/page.tsx`、`skills/page.tsx` 的 import

**影響檔案**：

- `frontend/src/store/agentsApi.ts`
- `frontend/src/store/skillsApi.ts`
- `frontend/src/app/(main)/agents/page.tsx`
- `frontend/src/app/(main)/skills/page.tsx`

---

## 2. Agents / Skills 頁面移除公開 Tab

**問題**：Agents 和 Skills 頁面有「我的」和「公開」兩個 Tab，但需求調整為只顯示自己的項目。

**修正**：

- 移除 `TabValue` / `TabType` 型別與 `activeTab` state
- 移除 Tab 按鈕 UI 區塊
- 直接使用 `data.items` 渲染列表，不再做前端 filter
- 移除未使用的 `useMemo` import

**影響檔案**：

- `frontend/src/app/(main)/agents/page.tsx`
- `frontend/src/app/(main)/skills/page.tsx`

---

## 3. Dashboard 新增快捷按鈕

**問題**：Dashboard 頁面只有一行預留文字，缺乏導航至 Agents / Skills 的入口。

**修正**：

- 新增兩個卡片式按鈕：「我的 Agents」、「我的 Skills」
- 點擊分別導航至 `/agents` 和 `/skills`
- 卡片包含圖示、標題、描述，響應式雙欄排列

**影響檔案**：

- `frontend/src/app/(main)/dashboard/page.tsx`

---

## 4. 冷色系主題背景對比度不足

**問題**：冷色系（cool）主題的 background 與 card-bg 色差太小，視覺上難以區分。

**修正**：

- `--color-background`：`#f0f4f8` → `#e2eaf3`（加深）
- `--color-card-bg`：`#e0f2fe` → `#f0f7ff`（提亮，拉開與背景差距）
- `--color-header-bg`：`#e0f2fe` → `#ccdcef`
- `--color-sidebar-bg`：`#e0f2fe` → `#d4e3f3`
- `--color-muted-bg`：`#e2e8f0` → `#cbd5e1`
- `--color-border`：`#bae6fd` → `#93c5fd`（加深）
- `--color-primary`：`#0ea5e9` → `#0284c7`（更深，增加可讀性）

**影響檔案**：

- `frontend/src/app/globals.css`

---

## 5. Agent 建立表單補充欄位

**問題**：新增 Agent 表單欄位太少，缺乏模型參數與開場白設定。

**新增欄位**：

| 欄位 | 型別 | 說明 |
| ---- | ---- | ---- |
| `model` | `VARCHAR(100)` | 使用的 LLM 模型（下拉選單） |
| `temperature` | `DOUBLE PRECISION` | 生成溫度，0 ~ 2 |
| `max_tokens` | `INTEGER` | 最大 Token 數，1 ~ 200000 |
| `greeting` | `TEXT` | Agent 開場白 |

**修正範圍**：

- **Migration**：`V8__add_agent_extended_fields.sql` — 新增 4 個欄位
- **後端 Model**：`backend/app/models/agent.py` — 新增 4 個 mapped_column
- **後端 Schema**：`backend/app/schemas/agents/schemas.py` — Create / Update / Response 三個 schema 同步新增
- **前端 Type**：`frontend/src/types/agents.ts` — Agent / AgentCreateRequest / AgentUpdateRequest 同步新增
- **前端表單**：`frontend/src/app/(main)/agents/new/page.tsx` — 新增模型下拉選單、溫度、Token 數、開場白欄位，含驗證邏輯
