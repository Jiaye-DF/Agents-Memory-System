/**
 * DF-SSO Silent Re-Auth Pattern（對應 INTEGRATION.md「Silent Re-Auth Pattern」段落）。
 *
 * 觸發時機：使用者工作中, API 回 401 且本地 refresh 也失敗 → 不直接踢回登入頁,
 * 而是保留現場後 redirect 到中央 /authorize；中央仍有 session 即可無感再簽,
 * 中央也已被清才會回登入頁。
 *
 * 兩條防護：
 * 1. `reauth_attempts`（sessionStorage, 上限 2）— 防 callback 失敗造成無限迴圈
 * 2. `sso_login_marker`（sessionStorage）— 僅 SSO 登入用戶才走此路徑;
 *    本地帳密用戶 401 仍維持「踢回登入頁」舊行為。
 *
 * 復原現場：把當前 path + query 寫進 `post_reauth_url`,
 * 由 callback 頁面在 exchange 成功後讀回並 navigate。
 */

const ATTEMPTS_KEY = "sso_reauth_attempts";
const POST_URL_KEY = "sso_post_reauth_url";
const SSO_MARKER_KEY = "sso_login_marker";
const MAX_ATTEMPTS = 2;

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

let cachedAuthorizeUrl: string | null = null;

export function markSsoLogin(): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(SSO_MARKER_KEY, "1");
}

export function clearSsoLogin(): void {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(SSO_MARKER_KEY);
  sessionStorage.removeItem(ATTEMPTS_KEY);
  sessionStorage.removeItem(POST_URL_KEY);
}

export function isSsoUser(): boolean {
  if (typeof window === "undefined") return false;
  return sessionStorage.getItem(SSO_MARKER_KEY) === "1";
}

export function consumePostReAuthUrl(): string | null {
  if (typeof window === "undefined") return null;
  const url = sessionStorage.getItem(POST_URL_KEY);
  if (url) {
    sessionStorage.removeItem(POST_URL_KEY);
    sessionStorage.removeItem(ATTEMPTS_KEY);
  }
  return url;
}

async function fetchAuthorizeUrl(): Promise<string | null> {
  if (cachedAuthorizeUrl) return cachedAuthorizeUrl;
  try {
    const res = await fetch(`${BASE_URL}/auth/sso/authorize-url`, {
      method: "GET",
      cache: "no-store",
      credentials: "include",
    });
    if (!res.ok) return null;
    const json = (await res.json()) as {
      success?: boolean;
      data?: { message?: string };
    };
    const url = json?.data?.message;
    if (typeof url === "string" && url) {
      cachedAuthorizeUrl = url;
      return url;
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * 觸發 silent re-auth；成功則 redirect 到中央 /authorize, 不會 resolve（navigation 已發生）。
 *
 * 失敗（沒設 SSO / 重試上限 / 抓不到 authorize URL）→ resolve, 呼叫端應 fallback 到舊 401 行為。
 */
export async function triggerSilentReAuth(): Promise<void> {
  if (typeof window === "undefined") return;

  const attempts = Number(sessionStorage.getItem(ATTEMPTS_KEY) ?? "0");
  if (attempts >= MAX_ATTEMPTS) {
    sessionStorage.removeItem(ATTEMPTS_KEY);
    sessionStorage.removeItem(POST_URL_KEY);
    window.location.href = "/?error=reauth_failed";
    return new Promise<void>(() => {});
  }

  const authorizeUrl = await fetchAuthorizeUrl();
  if (!authorizeUrl) {
    // SSO 未啟用或後端不可達 → fallback 給呼叫端維持舊 401 行為
    return;
  }

  sessionStorage.setItem(ATTEMPTS_KEY, String(attempts + 1));
  sessionStorage.setItem(
    POST_URL_KEY,
    window.location.pathname + window.location.search
  );

  window.location.href = authorizeUrl;
  // navigation 進行中, 永不 resolve, 防止呼叫端在 navigate 後又 retry 打 API
  return new Promise<void>(() => {});
}
