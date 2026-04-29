"use client";

import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Logo } from "@/components/layout/Logo";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Loading";
import { useDialog } from "@/hooks/useDialog";
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

  // 跨 app SSO auto-redirect（INTEGRATION.md 契約 #3 的放寬版）：
  // 沒登出 / 沒錯誤 / 沒指定本地登入時，直接跳中央 /authorize。中央有 session
  // 就無感簽回 dashboard，沒 session 就走 Azure AD 標準登入流程。
  // 三個 guard 守住「登出真有效」與「使用者主動選本地」的退路 —
  //   ?logged_out=1：剛登出, 不跳, 顯示登入頁讓使用者確認
  //   ?error=...：SSO 流程出錯回來, 不跳, 顯示錯誤訊息
  //   ?local=1：手動指定走本地帳密（書籤 / 內部後門）
  const redirectingRef = useRef<boolean>(false);
  const [redirecting, setRedirecting] = useState<boolean>(false);

  useEffect(() => {
    if (redirectingRef.current) return;
    if (!ssoAuthorizeUrl) return;
    if (loggedOut === "1" || ssoError || localOnly) return;
    redirectingRef.current = true;
    setRedirecting(true);
    window.location.href = ssoAuthorizeUrl;
  }, [ssoAuthorizeUrl, loggedOut, ssoError, localOnly]);

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

  // 如果預期會 auto-redirect，在 SSO authorize URL 還沒抓回來前先顯示 spinner，
  // 避免登入頁閃一下又被導走。SSO 沒設或有 guard 命中（logged_out / error / local）時直接渲染表單。
  const stillFetchingSsoConfig =
    !ssoConfigError &&
    !ssoAuthorizeUrl &&
    loggedOut !== "1" &&
    !ssoError &&
    !localOnly;

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
