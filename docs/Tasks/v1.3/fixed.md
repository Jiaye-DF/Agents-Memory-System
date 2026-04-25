# v1.3 fixed.md

> 本檔記錄 v1.3 系列上線後 / 開發過程中發現並修復的問題。
> 條目格式遵循 [docs/Design-Base/90-code-fixed.md](../../Design-Base/90-code-fixed.md)。

---

## 1. RTK Query 重複註冊 listSkillSuggestions / rejectSkillSuggestion endpoint warning〔2026-04-25 23:50:00〕

**問題**

前端啟動 / 切換 session 頁面時 console 出現：

```
called `injectEndpoints` to override already-existing endpointName listSkillSuggestions without specifying `overrideExisting: true`
```

`rejectSkillSuggestion` 同樣 warning。

**根因**

`chatApi.ts`（v1.1.7 PoC，session 範疇）與 `agenticApi.ts`（v1.3.6 正版，跨三 scope）皆 `injectEndpoints` 到同一個 `baseApi`，且註冊了**相同的 endpoint 名稱** — 後注入會覆蓋前注入，導致 hook 行為不可預期（呼叫端拿到的是 v1.3.6 介面，但傳入的是 v1.1.7 的 `{ sessionUid }`，造成執行期錯誤）。

兩者目的不同：v1.1.7 撈該 session 的 suggestions，v1.3.6 撈該 user 全部 scope 的 suggestions，**不能合併**。

**修正**

`chatApi.ts` 的 v1.1.7 三個 endpoint 全部加 `Session` 前綴，避開命名衝突；`agenticApi.ts` 維持原名作為主路徑。session 頁面改用新 hook 名稱：

- `listSkillSuggestions` → `listSessionSkillSuggestions`
- `approveSkillSuggestion` → `approveSessionSkillSuggestion`
- `rejectSkillSuggestion` → `rejectSessionSkillSuggestion`

過渡期 7 天並存（v1.3.6 規格規劃，2026-05-02 後可移除 v1.1.7 路徑）。

**影響檔案**

- [frontend/src/store/chatApi.ts](../../../frontend/src/store/chatApi.ts)
- [frontend/src/app/(main)/sessions/[uid]/page.tsx](../../../frontend/src/app/(main)/sessions/[uid]/page.tsx)

> 對應 commit：`c509a24`

---

## 2. MentionSelector 下拉行為失準（dropdown 未隨 caret 移動更新 / 關閉後反覆彈出）〔2026-04-25 23:55:00〕

**問題**

多 Agent 對話頁輸入 `@` 觸發 mention 下拉時：

- 移動 caret（方向鍵 / 點擊）後下拉內容不更新
- ESC 或選擇後關閉，但下一次輸入又立刻彈出（即使 query 還沒重新觸發）
- 在某些瀏覽器組合鍵情境下下拉「卡住」不消失

**根因**

原實作以 `useEffect([value, candidates.length])` 監聽變化計算 `open` / `context`，但：

- `value` 變化只反映輸入內容，**不反映 caret 移動**（方向鍵、點擊 textarea 不觸發 re-render）
- `setOpen` 與 `setContext` 雙 state 同步管理導致閉合 race（state 更新非同步，可能某次 keystroke 後 open=true 但 context 已被 reset）
- 沒有「使用者已關閉但 query 不變」的 dismiss 記憶，造成關閉後同 query 又彈出

**修正**

- 改以 textarea 的 `input` / `keyup` / `click` / `select` DOM 事件直接更新 `context`，確保 caret 移動即時反映
- 移除 `open` state，改為 `derived` 從 `context` + `dismissedKey` + `candidates.length` 算出（避免 state race）
- 新增 `dismissedKey`（`${value}:${trigger}:${query}` 雜湊）：使用者主動 dismiss 後，同 query 不再彈出，直到 query 變動才重置

**影響檔案**

- [frontend/src/components/chat/MentionSelector.tsx](../../../frontend/src/components/chat/MentionSelector.tsx)

---

## 3. AgentTemplate 編輯送出含 template_key 等不應更新欄位〔2026-04-25 23:56:00〕

**問題**

Admin 編輯 Agent Template 時，前端 `AgentTemplateUpdateRequest` body 透過 `const { template_key: _discard, ...rest } = base` 解構排除 `template_key`，再 `{ ...rest, is_active }` 重組。

此寫法依賴 `base` 物件結構**正好**等於 `AgentTemplateUpdateRequest`（去掉 `template_key`），但 `base` 來自 form state，可能含其他不該送出的欄位（如未來新增 form-only 計算欄位），導致：

- 後端可能收到未定義欄位 → 422 或意外覆寫
- TypeScript 沒有靜態保證 `rest` 結構與 `AgentTemplateUpdateRequest` 一致

**根因**

destructure-spread pattern 把欄位範圍交給「`base` 當下長什麼樣」決定，缺乏 schema-explicit 的契約；新增 form 欄位時會悄悄洩漏到 API 請求。

**修正**

改為**逐欄位顯式列出** `AgentTemplateUpdateRequest`：

```ts
const update: AgentTemplateUpdateRequest = {
  label: base.label,
  description: base.description,
  name: base.name,
  identity: base.identity,
  language: base.language,
  style: base.style,
  role_prompt: base.role_prompt,
  greeting: base.greeting,
  temperature: base.temperature,
  max_tokens: base.max_tokens,
  response_format: base.response_format,
  response_format_example: base.response_format_example,
  sort_order: base.sort_order,
  is_active: values.is_active,
};
```

未來 form 欄位增減時 TypeScript 會直接報錯，避免靜默洩漏。

**影響檔案**

- [frontend/src/app/(main)/admin/agent-templates/page.tsx](../../../frontend/src/app/(main)/admin/agent-templates/page.tsx)
