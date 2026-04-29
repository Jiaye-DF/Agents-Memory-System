# v1.4 修正記錄

> v1.4 開發 / 驗收期間發現的 bug 與修正紀錄。

---

## 1. 跨 app SSO 不會自動登入，使用者卡在 `/auth/refresh` 401（既存自 v1.3-extended）  〔2026-04-29 10:48:33〕

**問題**：使用者已在 App B 用 DF-SSO 登入（中央 Redis 有 session），開啟本系統 App A 的 `/` 後，預期應無感登入，實際卻看到登入頁。Network tab 顯示一次 `POST /api/v1/auth/refresh` 回 `401 Unauthorized`，登入頁顯示後仍要使用者手動點 SSO 按鈕才會進到 dashboard。

```text
Request URL: https://df-it-agents-platform-api.it.zerozero.tw/api/v1/auth/refresh
Request Method: POST
Status Code: 401 Unauthorized
```

根因：v1.3-extended 接 SSO 時嚴格遵守 INTEGRATION.md 契約 #3（「登入頁 401 時顯示按鈕，不可自動 redirect 到 `/authorize`」），所以 `(auth)/page.tsx` mount 時不對中央 `/authorize` 做任何嘗試 — 使用者沒按鈕點，本系統就完全不知道中央有沒有 session。「跨 app SSO 應無感登入」的核心訴求沒有被滿足。契約 #3 設計動機是怕 logout 後又被自動拉回，但這個風險可以用 query param guard 守住，不必整段封死。

**修正**：放寬契約 #3 — `(auth)/page.tsx` mount 後若三個 guard 都不命中就自動 `window.location.href = ssoAuthorizeUrl`，三個 guard 守住「不該自動跳」的情境：

1. `?logged_out=1`：剛登出回來，不跳，顯示「您已登出」訊息
2. `?error=...`：SSO 流程失敗回來，不跳，顯示錯誤訊息
3. `?local=1`：手動指定走本地帳密（書籤 / 內部後門 / 不想被 SSO 蓋掉的情境）

連帶調整：

- `useAuth.logout()` 改 navigate `/?logged_out=1`（原本是 `/`，會被 auto-redirect 立刻拉回去）
- `(main)/layout.tsx` 把 unauth user 踢出時依 `isSsoUser()` 決定 `/`（SSO）或 `/?local=1`（本地），避免本地用戶被誤丟去 SSO
- 加 `redirecting` state + `stillFetchingSsoConfig` gating，等 SSO authorize URL 抓回來再跳，避免登入頁閃一下又被導走

**影響檔案**：

- `frontend/src/app/(auth)/page.tsx`
- `frontend/src/hooks/useAuth.ts`
- `frontend/src/app/(main)/layout.tsx`

---

## 2. 中文 username 讓 JWT decode 失敗，整個 auth flow 卡 `/auth/refresh` loop（既存自 v1.3-extended）  〔2026-04-29 10:48:33〕

**問題**：SSO 使用者 `name` 為中文（例：王小明）時，登入後進 `/dashboard` 會被打回登入頁，且 network tab 看到 `/auth/refresh` 反覆被打。本地用 ASCII 帳號測試正常，沒有人在意這個 case。

```text
useAuth.initAuth → decodeTokenPayload(access_token) → InvalidCharacterError → null
→ 落到 refreshMutation → /auth/refresh → 200 + 新 token
→ decode 又 fail → setTokenPayload(null) → !isAuthenticated → redirect /
→ (auth)/layout → useAuth → decode 又 fail → /auth/refresh ...
```

根因：[`useAuth.ts:18-27`](../../../frontend/src/hooks/useAuth.ts) 的 `decodeTokenPayload` 用 `JSON.parse(atob(parts[1]))` 解 JWT payload。`atob` 只認標準 base64（`+ /` 配 padding），但 JWT 用 base64url（`- _` 不配 padding）。中文 username 的 UTF-8 byte 在某些 offset 會編出 `-` 或 `_`，碰到的瞬間 `atob` 拋 `InvalidCharacterError`，`decodeTokenPayload` return null → useAuth 進 fallthrough refresh 的分支 → /refresh 成功但拿到的新 token 也是同一個壞掉的 username → 永遠 decode fail。即使 v1.3-extended `bd23b86` 修了 SSO refresh 路徑，前端 decode 這一層的 base64url 與 UTF-8 解碼一直被忽略。

同類追蹤：[v1.3/fixed.md §17 跨頁作者 chip 對含空格 username 過濾失敗](../v1.3/fixed.md) — 都是「不單純 ASCII 的 username 引爆 SSO 流程」，前後端各踩一次。

**修正**：`decodeTokenPayload` 補 base64url → base64 + padding + UTF-8 還原：

```ts
let base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
while (base64.length % 4) base64 += "=";
const binary = atob(base64);
const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
const utf8 = new TextDecoder("utf-8").decode(bytes);
return JSON.parse(utf8) as TokenPayload;
```

**影響檔案**：

- `frontend/src/hooks/useAuth.ts`

**驗證方式**：用中文 SSO display name 完成登入後直接進 dashboard，network tab 不再出現 `/auth/refresh` 重複呼叫；`username` 顯示在 Header 為原始中文。
