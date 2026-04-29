"use client";

import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Logo } from "@/components/layout/Logo";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Loading";
import { useDialog } from "@/hooks/useDialog";
import { getLastLoginProvider } from "@/lib/api/login-provider";
import {
  useLoginMutation,
  useSsoAuthorizeUrlQuery,
} from "@/store/authApi";
import { validateAccount, validatePassword } from "@/utils/validation";

interface FormErrors {
  account: string | null;
  password: string | null;
}

const SSO_ERROR_MESSAGES: Record<string, string> = {
  no_code: "SSO 回呼缺少授權碼，請重新登入",
  exchange_failed: "SSO 授權碼已失效或無效，請重新登入",
  exchange_error: "SSO 連線異常，請稍後再試",
  sso_unreachable: "無法連線到 SSO 伺服器，請稍後再試",
  sso_not_configured: "本系統尚未啟用 SSO，請聯繫管理員",
};

export default function LoginPage(): React.ReactNode {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { showDialog } = useDialog();
  const [login, { isLoading }] = useLoginMutation();
  // 取 SSO authorize URL（後端決定，沒設 SSO_URL 會回 503）
  const { data: ssoData, isError: ssoConfigError } = useSsoAuthorizeUrlQuery();
  const ssoAuthorizeUrl = ssoData?.message ?? null;

  const ssoError = searchParams.get("error");
  const loggedOut = searchParams.get("logged_out");
  const localOnly = searchParams.get("local") === "1";
  const ssoErrorMessage = useMemo<string | null>(() => {
    if (!ssoError) return null;
    return SSO_ERROR_MESSAGES[ssoError] ?? `登入失敗：${ssoError}`;
  }, [ssoError]);

  // 企業 Portal 模式 + Mode B provider-aware（INTEGRATION.md 契約 #3）：
  // 只有「上次明確走 SSO」的使用者才 auto-redirect, 其餘都顯示雙選項或表單。
  //
  // 決策表：
  //   ?logged_out=1 / ?error=... / ?local=1 → 顯示登入頁（Portal 例外 + 後門）
  //   last_login_provider === "sso" → auto-redirect 到中央 /authorize（Portal 行為）
  //   last_login_provider === "local" → 顯示本地表單, 不跳 SSO
  //   沒 hint（第一次訪問）→ 顯示雙選項, 不跳（spec 嚴格要求, 避免本地帳號使用者被誤丟）
  //
  // DF-SSO 不殺 AD 那層, 第一次訪客 auto-redirect 也只是 silent SSO 把人拉回, 意義不大,
  // 不如讓使用者主動選一次, 之後靠 hint 對應到「打開即進」UX。
  const redirectingRef = useRef<boolean>(false);
  const [redirecting, setRedirecting] = useState<boolean>(false);

  useEffect(() => {
    if (redirectingRef.current) return;
    if (!ssoAuthorizeUrl) return;
    if (loggedOut === "1" || ssoError || localOnly) return;
    if (getLastLoginProvider() !== "sso") return;
    redirectingRef.current = true;
    setRedirecting(true);
    window.location.href = ssoAuthorizeUrl;
  }, [ssoAuthorizeUrl, loggedOut, ssoError, localOnly]);

  useEffect(() => {
    // ?logged_out=1 是「過渡 flag」：用來阻止本次 mount 的 auto-redirect、顯示「您已登出」訊息。
    // 短暫顯示後就把 query 從 URL 清掉, 這樣使用者下次 refresh 拿到的是乾淨 URL, 走正常的
    // Portal 模式判斷（hint=sso → auto-redirect / 否則顯示雙選項）。useSearchParams 在
    // App Router 下不會因 history.replaceState 重觸發, 所以本次 mount 的訊息維持顯示,
    // 只有 URL 變乾淨。
    if (loggedOut !== "1") return;
    const timer = window.setTimeout(() => {
      window.history.replaceState(null, "", window.location.pathname);
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [loggedOut]);

  const [account, setAccount] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [errors, setErrors] = useState<FormErrors>({
    account: null,
    password: null,
  });

  const handleAccountChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setAccount(e.target.value);
      setErrors((prev) => ({ ...prev, account: null }));
    },
    []
  );

  const handlePasswordChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setPassword(e.target.value);
      setErrors((prev) => ({ ...prev, password: null }));
    },
    []
  );

  const handleAccountBlur = useCallback((): void => {
    if (account) {
      const error = validateAccount(account);
      setErrors((prev) => ({ ...prev, account: error }));
    }
  }, [account]);

  const handlePasswordBlur = useCallback((): void => {
    if (password) {
      const error = validatePassword(password);
      setErrors((prev) => ({ ...prev, password: error }));
    }
  }, [password]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
      e.preventDefault();

      const accountError = validateAccount(account);
      const passwordError = validatePassword(password);

      if (accountError || passwordError) {
        setErrors({ account: accountError, password: passwordError });
        return;
      }

      try {
        await login({ account, password }).unwrap();
        router.push("/dashboard");
      } catch (err: unknown) {
        const message =
          typeof err === "string" ? err : "登入失敗，請確認帳號或密碼是否正確";
        showDialog({
          type: "error",
          title: "登入失敗",
          message,
        });
      }
    },
    [account, password, login, router, showDialog]
  );

  // hint=sso 的使用者預期會 auto-redirect, 在 SSO authorize URL 還沒抓回來前先顯示 spinner,
  // 避免登入頁閃一下又被導走。其他使用者（hint=local / 無 hint / guard 命中）直接渲染表單。
  const willAutoRedirect =
    !ssoConfigError &&
    loggedOut !== "1" &&
    !ssoError &&
    !localOnly &&
    getLastLoginProvider() === "sso";
  const stillFetchingSsoConfig = willAutoRedirect && !ssoAuthorizeUrl;

  if (redirecting || stillFetchingSsoConfig) {
    return (
      <div className="flex flex-col items-center gap-4">
        <Spinner size="lg" />
        <p className="text-base text-muted">正在透過 DF-SSO 登入...</p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-md rounded-xl bg-card-bg p-8 shadow-lg">
      <div className="mb-6 flex flex-col items-center gap-2">
        <Logo className="h-12 w-12" />
        <h1 className="text-3xl font-bold text-foreground">Agents Platform</h1>
        <p className="text-base text-muted">請登入以繼續</p>
      </div>

      {/* SSO 提示訊息 */}
      {ssoErrorMessage && (
        <div className="mb-4 rounded-md border border-error/40 bg-error/10 px-3 py-2 text-sm text-error">
          {ssoErrorMessage}
        </div>
      )}
      {loggedOut === "1" && !ssoErrorMessage && (
        <div className="mb-4 rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-sm text-foreground">
          您已登出
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          label="帳號"
          placeholder="請輸入帳號"
          value={account}
          onChange={handleAccountChange}
          onBlur={handleAccountBlur}
          error={errors.account ?? undefined}
          required
        />
        <Input
          label="密碼"
          type="password"
          placeholder="請輸入密碼"
          value={password}
          onChange={handlePasswordChange}
          onBlur={handlePasswordBlur}
          error={errors.password ?? undefined}
          required
        />
        <Button type="submit" loading={isLoading} className="mt-2 w-full">
          登入
        </Button>
      </form>

      {/* SSO 登入按鈕（含 ?local=1 / ?logged_out=1 / ?error 的後備路徑） */}
      {ssoAuthorizeUrl && (
        <div className="mt-6 flex flex-col gap-3">
          <div className="flex items-center gap-3 text-xs text-muted">
            <span className="h-px flex-1 bg-border" />
            <span>或</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              window.location.href = ssoAuthorizeUrl;
            }}
            className="w-full"
          >
            透過 DF-SSO 登入
          </Button>
        </div>
      )}

      <div className="mt-4 flex items-center justify-between text-base">
        <Link
          href="/register"
          className="text-primary transition-colors hover:cursor-pointer hover:text-primary-hover"
        >
          註冊帳號
        </Link>
        <Link
          href="/reset-password"
          className="text-primary transition-colors hover:cursor-pointer hover:text-primary-hover"
        >
          忘記密碼
        </Link>
      </div>
      {/* 沒設 SSO 時的提示（dev 環境用） */}
      {ssoConfigError && (
        <p className="mt-3 text-center text-xs text-muted">
          SSO 尚未啟用（後端未設定 SSO_URL）
        </p>
      )}
    </div>
  );
}
