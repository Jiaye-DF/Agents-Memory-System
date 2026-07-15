# v1.6.1 任務規格：Dashboard 公開市集加入「AI 分析」語意檢索

> **狀態：進行中（Phase 1-3 code 實作完成、pytest / tsc 全綠；剩 Phase 4 手動 smoke 待人工執行）**
>
> 前置：[propose-v1.6.1.md](propose-v1.6.1.md)

## 版本目標

把 v1.6.0 的「AI 分析」語意檢索帶進 dashboard 公開 Skills 頁籤，檢索範圍限 public（不混入私有）。

### 範圍內

- 後端：`SkillSearchRequest.scope`（`"visible"` 預設 / `"public"`）+ `search_similar` 依 scope 切換可見性條款
- 前端：`skillsApi` mutation 加 `scope`；dashboard 公開 Skills 頁籤加模式切換 + 結果渲染
- 測試：scope SQL 條款 + schema 驗證

### 範圍外

- Agents / Scripts 頁籤語意檢索、RankingPanel、其餘 v1.6.0 範圍外項目

---

## 前置現況

- v1.6.0 已完成（commit `7c9efc6`）：`POST /skills/search`、[`search_similar`](../../../backend/app/repositories/skill_repository.py)（可見性寫死 owner OR public）、[`semantic_search`](../../../backend/app/services/skill_service.py)、前端 [`skillsApi.ts`](../../../frontend/src/store/skillsApi.ts) `semanticSearchSkills` mutation、[`skills/page.tsx`](../../../frontend/src/app/(main)/skills/page.tsx) AI 模式（沿用其視覺範式）
- Dashboard：[`dashboard/page.tsx`](../../../frontend/src/app/(main)/dashboard/page.tsx)（四頁籤、共用 Input 純前端過濾、`SkillRow` 為 dashboard 內部元件）
- 既有測試：[`test_skill_repository.py`](../../../backend/tests/repositories/test_skill_repository.py)（SQL 條款驗證範式）、[`test_skill_semantic_search.py`](../../../backend/tests/services/test_skill_semantic_search.py)

## 已確認決策

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | 公開市集檢索範圍 | 後端 `scope` 參數（非前端過濾），`public` = `visibility='public'`（含自己的 public） |
| 2 | 向下相容 | `scope` 預設 `"visible"`，v1.6.0 呼叫端零改動 |
| 3 | 適用頁籤 | 僅公開 Skills；Agents / Scripts 無 embedding 不做 |
| 4 | UI 範式 | 完全對齊 `/skills` 管理頁 v1.6.0 模式切換 |

---

## Phase 1：後端 scope 參數

- [x] [`schemas/skills/schemas.py`](../../../backend/app/schemas/skills/schemas.py) `SkillSearchRequest` 加 `scope: Literal["visible", "public"] = "visible"`
- [x] [`skill_repository.search_similar`](../../../backend/app/repositories/skill_repository.py) 簽名加 `scope: str = "visible"`；SQL 可見性條款依 scope 切換（`public` → `visibility = 'public'`；`visible` → 原條款；未知值防呆落回 `visible`）
- [x] [`skill_service.semantic_search`](../../../backend/app/services/skill_service.py) 簽名加 `scope` 並透傳
- [x] [`skills/router.py`](../../../backend/app/api/v1/skills/router.py) `POST /search` 透傳 `body.scope`
- [x] Swagger schema 自動同步確認（欄位繁中說明：`scope` 以 `Field(description=...)` 標註）

## Phase 2：前端 dashboard

- [x] [`skillsApi.ts`](../../../frontend/src/store/skillsApi.ts) `semanticSearchSkills` 參數加 `scope?: "visible" | "public"`（未給不送，後端預設）
- [x] [`dashboard/page.tsx`](../../../frontend/src/app/(main)/dashboard/page.tsx)：
  - [x] 公開 Skills 頁籤加「搜尋模式」chip（`關鍵字` / `AI 分析`），僅該頁籤顯示 —（已改為搜尋框內建左側模式選擇器 `SearchModeBar`，v1.6 UI 調整）
  - [x] AI 模式：placeholder「用一句話描述你要找的 Skill…」、Enter（form onSubmit）/ 按鈕觸發、`scope: "public"`
  - [x] 結果渲染：dashboard `SkillRow` 加選配 `score` / `aiReason` props（徽章 + `相似度 NN%` + 理由淺色文字），既有呼叫點不破壞
  - [x] loading `<PageLoading />`；空結果「找不到語意相近的 Skill」；AI 模式隱藏作者 / 標籤 / 排序 chips
  - [x] 切換頁籤或切回關鍵字：清 AI 結果，keyword 行為不變

## Phase 3：測試

- [x] [`test_skill_repository.py`](../../../backend/tests/repositories/test_skill_repository.py) 加：`scope="public"` SQL 條款不含 owner 條件、`scope="visible"` 維持原條款（預設值行為，含未知 scope 防呆落回 visible）
- [x] [`test_skill_semantic_search.py`](../../../backend/tests/services/test_skill_semantic_search.py) 加：scope 透傳驗證
- [x] schema：scope 非法值 → validation error（無獨立 schema 測試慣例，併入 `test_skill_semantic_search.py`，含未帶 scope 預設 visible）

## Phase 4：驗證與部署

- [x] `pytest backend/tests -v` 全綠（48 passed, 1 skipped）
- [x] 前端 `tsc --noEmit` 全綠
- [ ] 手動 smoke：dashboard 切 AI 分析 → 只回 public；`/skills` 管理頁行為不變
- [ ] 無 DB / migration / env 變更，部署即生效
