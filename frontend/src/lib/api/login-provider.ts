/**
 * `last_login_provider` hint — INTEGRATION.md「Mode B Portal 模式必須 provider-aware」要求。
 *
 * 用途：登入頁據此決定是否 auto-redirect 到 SSO。
 * - "sso"   → auto-redirect（Portal 體驗）
 * - "local" → 顯示本地表單，不 auto-redirect
 * - null（首訪）→ 顯示雙選項
 *
 * 雙來源策略：
 * 1. **跨 App cookie**（`.zerozero.tw` 共享）— 由 backend 在登入 / 登出時 set / clear。
 *    這是「Coolify 登入後本系統打開即 silent SSO」的關鍵 hint, 必須優先讀取。
 * 2. localStorage（per-domain）— 早期實作, 保留為 fallback, 也讓 SPA-only 流程能即時更新。
 *
 * 為何不是 httpOnly：這個 hint 不是憑證，洩漏無害, 純粹是 UI 顯示分流參考。
 * 設成 httpOnly 反而前端讀不到, 失去意義。
 */

const STORAGE_KEY = "last_login_provider";
const COOKIE_KEY = "last_login_provider";

export type LoginProvider = "sso" | "local";

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length));
    }
  }
  return null;
}

export function setLastLoginProvider(provider: LoginProvider): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, provider);
  } catch {
    // localStorage 不可用（隱私模式 / 配額爆掉）→ 退化成「沒 hint」, 不影響核心功能
  }
}

export function getLastLoginProvider(): LoginProvider | null {
  if (typeof window === "undefined") return null;
  // 優先讀跨 App cookie：Coolify 等其他 SSO 接入 App 登入後寫的 .zerozero.tw cookie 在這裡命中,
  // 觸發 auto-redirect 完成「他處登入 → 本系統 silent SSO」的 Portal 體驗。
  const fromCookie = readCookie(COOKIE_KEY);
  if (fromCookie === "sso" || fromCookie === "local") return fromCookie;
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value === "sso" || value === "local" ? value : null;
  } catch {
    return null;
  }
}

export function clearLastLoginProvider(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // 同上, 失敗也不抛
  }
  // 跨 App cookie 由 backend 端清（登出時的 Set-Cookie Max-Age=0）, 前端只清 localStorage 即可。
}
