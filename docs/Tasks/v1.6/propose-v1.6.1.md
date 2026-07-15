# v1.6.1 Propose — Dashboard 公開市集加入「AI 分析」語意檢索

> 本文件為 v1.6.1 的構想與討論紀錄。定稿後於 [tasks-v1.6.1.md](tasks-v1.6.1.md) 進行實作。
>
> 前置版本：[propose-v1.6.0.md](propose-v1.6.0.md)（Skills RAG 基礎設施，本版直接複用）

---

## 0. 前置假設

- v1.6.0 已完成：`skill.embedding`（V56/V57）、`POST /api/v1/skills/search`（cosine 檢索 + LLM 推薦理由）、`/skills` 管理頁「AI 分析」模式
- v1.6.0 檢索可見性固定為「自己的 OR public」（對齊 `stmt_visible_to_user`），無參數可調
- Dashboard（[`dashboard/page.tsx`](../../../frontend/src/app/(main)/dashboard/page.tsx)）為公開市集：四頁籤（Skills / Agents / Scripts / 最常使用），前端 filter `visibility === "public"`，共用一個關鍵字搜尋 Input（純前端 `matchByTextAndAuthor` 過濾）

---

## 1. 版本目標

把 v1.6.0 的「AI 分析」語意檢索帶進 dashboard 的 **公開 Skills 頁籤**，並確保檢索範圍符合公開市集語意（**只回 public，不混入自己的私有 Skill**）。

### 範圍內

- 後端：`SkillSearchRequest` 加選配 `scope` 參數（`"visible"`（預設，v1.6.0 行為不變）/ `"public"`）；`skill_repository.search_similar` 依 scope 切換可見性條件
- 前端：`skillsApi` mutation 加 `scope` 參數；dashboard 公開 Skills 頁籤加「關鍵字 / AI 分析」模式切換與結果渲染（徽章 + 相似度 + 理由），互動與 `/skills` 管理頁一致
- 測試：scope 條件的 SQL 條款驗證、schema validation

### 範圍外（延後）

- Agents / Scripts 頁籤的語意檢索（無 embedding，屬 v1.6.x 後續）
- 「最常使用」頁籤（RankingPanel）不動
- 其餘 v1.6.0 範圍外項目維持不變

---

## 2. 設計

### 2-1 為什麼加 `scope` 而非前端過濾

| 方案 | 評估 |
| --- | --- |
| 前端拿 v1.6.0 結果後過濾 `visibility === "public"` | top_k 名額被私有結果吃掉、AI 理由浪費在會被丟棄的項目上；結果數不穩定 |
| **後端 `scope` 參數** ✅ | SQL 層直接換條件，top_k / min_score / AI 分析都作用在正確集合；預設值保證 v1.6.0 呼叫端零改動 |

### 2-2 API 變更（向下相容）

`POST /api/v1/skills/search`：

```python
class SkillSearchRequest(BaseModel):
    query: str
    top_k: int | None = None
    scope: Literal["visible", "public"] = "visible"   # 新增
```

- `visible`（預設）：`owner_user_uid = :user_uid OR visibility = 'public'`（v1.6.0 原行為）
- `public`：`visibility = 'public'`（含自己的 public，不含任何 private）
- `search_similar` 簽名加 `scope: str = "visible"`，SQL 依 scope 組可見性條款；其餘（embedding IS NOT NULL / min_score / ORDER / LIMIT）不變

### 2-3 前端（dashboard）

- 僅 **公開 Skills 頁籤** 顯示「搜尋模式」chip（`關鍵字` / `AI 分析`），與 `/skills` 管理頁同視覺；切到其他頁籤自動回 keyword 行為（AI 狀態不套用）
- AI 模式：placeholder「用一句話描述你要找的 Skill…」、Enter / 按鈕觸發、`scope: "public"`、loading `<PageLoading />`、空結果「找不到語意相近的 Skill」
- 結果渲染沿用 dashboard 既有 `SkillRow`（加選配 `score` / `aiReason` props，不破壞既有呼叫點）：「AI 分析」徽章、`相似度 NN%`、理由淺色文字
- AI 模式下隱藏作者 / 標籤 / 排序 chips（後端已排序過濾）；關鍵字模式完全不變

---

## 3. Migration / 部署

無 DB 變更、無新 system_setting、無新環境變數。純程式碼版本，部署即生效。

---

## 4. 風險與決策

| # | 風險 / 議題 | 應對 |
| --- | --- | --- |
| 1 | scope 參數破壞 v1.6.0 呼叫端 | 預設 `visible`，`/skills` 管理頁零改動 |
| 2 | scope 傳入非法值 | Pydantic `Literal` 驗證，400 |
| 3 | dashboard 搜尋 Input 跨頁籤共用，AI 狀態殘留 | 切離 Skills 頁籤時 AI 結果不渲染；模式 state 僅作用於 Skills 頁籤 |
| 4 | 成本 | 與 v1.6.0 同策略：獨立模式、主動觸發才呼叫 |

---

## 5. 驗收標準

- [ ] `POST /skills/search {scope: "public"}` 不回他人與自己的 private Skill；不帶 scope 行為與 v1.6.0 一致
- [ ] Dashboard 公開 Skills 頁籤可切「AI 分析」，結果帶徽章 + 相似度 + 理由
- [ ] Agents / Scripts / 最常使用頁籤行為不變；`/skills` 管理頁行為不變
- [ ] `pytest backend/tests -v` 全綠；前端 type check 全綠
