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

---

## 3. 跨 App 共享：`SSO_COOKIE_DOMAIN` + 跨子網域 `last_login_provider` cookie 〔2026-04-29〕

**問題**：

- 從別的 SSO 接入 App（例：Coolify-API-Integration）登入後，切到本系統登入頁仍要顯示「兩個選項」、不會 auto-redirect → 預期的「Coolify 登入後本系統打開即進」Portal 體驗失效。
- 任一 App 登出後，本系統的 `sso_recent_logout` hint cookie 沒被讀到 → 401 路徑不回 `X-Recently-Logged-Out`、silent re-auth 又把人拉回 dashboard，主動登出視覺被抵消。

**根因**：兩個 hint 都活在 backend host 上，沒設 `Domain=.zerozero.tw`：

| Hint | 用途 | 問題 |
|---|---|---|
| `last_login_provider` | 登入頁 Mode B Portal 分流（"sso" → auto-redirect, "local" → 顯示表單） | 寫在 `localStorage`（per-domain），其他 App 永遠讀不到 |
| `sso_recent_logout` | 5 分鐘內任意 401 都回 `X-Recently-Logged-Out` 讓前端跳 `/?logged_out=1` | `Set-Cookie` 沒帶 `Domain`，cookie 鎖在自己 backend host，其他 App 看不到 |

`*.zerozero.tw` 子網域 cookie 共享是這類「跨 App 視覺同步」最低成本的方案 — 不用 Redis、不用前端 broadcast，靠瀏覽器 cookie jar 就能傳遞。前提：`Set-Cookie` 必須明確帶 `Domain=.zerozero.tw`。

**修正**：

| 檔案 | 變更摘要 |
|---|---|
| `backend/app/core/config.py` | 新增 `SSO_COOKIE_DOMAIN: str = ""` 設定欄位 |
| `backend/app/api/v1/auth/router.py` | 1. 新增 `COOKIE_DOMAIN` constant（讀 `settings.SSO_COOKIE_DOMAIN`，空字串 → `None` 退化 host-only）<br>2. `_set_recent_logout_cookie` / `_delete_recent_logout_cookie` 帶 `domain`<br>3. 新增 `LOGIN_PROVIDER_COOKIE_KEY = "last_login_provider"` 與 `_set_login_provider_cookie(response, provider)` / `_delete_login_provider_cookie(response)` helper（**非 httpOnly** 讓前端 JS 讀得到，30 天 TTL）<br>4. 本地 `/auth/login` → `_set_login_provider_cookie(response, "local")`<br>5. SSO `/auth/sso/exchange` → `_set_login_provider_cookie(response, "sso")`<br>6. `/auth/logout` 與 `/auth/sso/logout` → `_delete_login_provider_cookie(response)`<br>7. `refresh_token` 仍維持 host-only（憑證不能跨 App） |
| `frontend/src/lib/api/login-provider.ts` | `getLastLoginProvider()` 改為**先讀跨 App cookie**（`document.cookie` 讀 `last_login_provider`），fallback 到 localStorage。`setLastLoginProvider` / `clearLastLoginProvider` 仍寫 / 清 localStorage（SPA 即時更新用），跨 App cookie 由 backend Set-Cookie 控制 |
| `docker-compose.yml` / `docker-compose.dev.yml` | backend 新增 `SSO_COOKIE_DOMAIN: ${SSO_COOKIE_DOMAIN}` 注入 |
| `.env.example` | 新增 `SSO_COOKIE_DOMAIN=`（dev 留空，prod 部署時設 `.zerozero.tw`） |

**驗證流程**：

1. 跨 App silent 登入：使用者在 Coolify 完成 SSO 登入 → backend `Set-Cookie: last_login_provider=sso; Domain=.zerozero.tw` → 打開本系統登入頁 → `getLastLoginProvider()` 從 cookie 讀到 `"sso"` → useEffect auto-redirect → 中央 silent SSO → callback → 自動進 dashboard，全程零互動。
2. 跨 App 登出視覺一致性：使用者在任一 App 登出 → `Set-Cookie: sso_recent_logout=1; Max-Age=300; Domain=.zerozero.tw` 同時 `Set-Cookie: last_login_provider=; Max-Age=0; Domain=.zerozero.tw` → 5 分鐘內打開本系統 → `last_login_provider` 已被刪 → 不 auto-redirect；`/auth/refresh` 路徑撞 `sso_recent_logout=1` → 回 `X-Recently-Logged-Out: 1` → silent re-auth 攔截器跳 `/?logged_out=1` 顯示「您已登出」訊息。
3. 本機開發：`SSO_COOKIE_DOMAIN=` 為空 → cookie 退化成 host-only，`localhost:3000` / `localhost:3001` 兩個 origin 不互通（預期，本機沒有共同 parent domain）。

**影響檔案**：

- `backend/app/core/config.py`
- `backend/app/api/v1/auth/router.py`
- `frontend/src/lib/api/login-provider.ts`
- `docker-compose.yml`
- `docker-compose.dev.yml`
- `.env.example`

**配套需求（DF-SSO 中央端）**：

本修正只解決「**hint cookie 跨 App 共享**」這一層。Back-channel 推送通知是另一條獨立的伺服端通道，需在 DF-SSO Dashboard 把本系統與 Coolify-API-Integration 都加進 `sso_allowed_list`、設好各自的 `back_channel_logout_url`，否則中央根本不會推到對方、也不會撤銷對方的 Redis session。

兩條路並行：

- **Cookie hint**（本修正）→ 前端視覺一致性
- **Back-channel HMAC push**（中央 Dashboard 設定）→ 後端 session 撤銷

兩條缺一就會出現「視覺正確但 session 還活著」或「session 已死但視覺被 silent SSO 抵消」的不一致。
