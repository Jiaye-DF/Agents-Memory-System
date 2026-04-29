/**
 * `last_login_provider` hint — INTEGRATION.md「Mode B Portal 模式必須 provider-aware」要求。
 *
 * 用途：登入頁據此決定是否 auto-redirect 到 SSO。
 * - "sso" / null（首訪）→ auto-redirect（Portal 體驗）
 * - "local" → 顯示本地表單，不 auto-redirect（避免本地用戶被誤丟去 SSO）
 *
 * 為何用 localStorage 而非 sessionStorage：跨分頁 / 跨瀏覽器 session 都要記得使用者上次選什麼,
 * 否則「我已經改用本地帳號了，但開分頁還一直跳 SSO」這個 INTEGRATION.md 點名要避免的問題就會復現。
 *
 * 為何不是 httpOnly cookie：這個 hint **不是憑證**，洩漏無害, 純粹是 UI 顯示分流參考。
 * 設成 httpOnly 反而前端讀不到, 失去意義。
 */

const STORAGE_KEY = "last_login_provider";

export type LoginProvider = "sso" | "local";

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
}
