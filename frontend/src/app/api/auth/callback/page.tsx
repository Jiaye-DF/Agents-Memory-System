"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { setAccessToken } from "@/lib/api/client";
import { Spinner } from "@/components/ui/Loading";

/**
 * DF-SSO 回呼頁。
 *
 * SSO Dashboard 的 redirect_uri 必須登記為 `${APP_URL}/auth/callback`。
 *
 * 流程：
 *   1. 從 query string 取出 code（中央 SSO 一次性 60 秒授權碼）
 *   2. POST 給 backend `/auth/sso/exchange`（backend 會做中央 exchange + /me + upsert local user）
 *   3. backend 透過 Set-Cookie 寫入 refresh_token，response body 帶 access_token
 *   4. 把 access_token 存進 in-memory client，導去 /dashboard
 *
 * 失敗則導回 `/?error=...`（登入頁顯示錯誤訊息，**不**自動 redirect 回 SSO，對應契約 #3）
 */
const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

function CallbackFallback(): React.ReactNode {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background p-4">
      <Spinner size="lg" />
      <p className="text-base text-muted">正在完成 SSO 登入...</p>
    </div>
  );
}

// useSearchParams() 必須包在 Suspense 內，否則 prerender 階段會 bail out
// （Next.js 16 build 規則：missing-suspense-with-csr-bailout）
export default function SsoCallbackPage(): React.ReactNode {
  return (
    <Suspense fallback={<CallbackFallback />}>
      <SsoCallbackInner />
    </Suspense>
  );
}

function SsoCallbackInner(): React.ReactNode {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  // StrictMode 下 effect 會跑兩次，code 是一次性的會直接被中央拒絕第二次
  const exchangedRef = useRef<boolean>(false);

  useEffect(() => {
    if (exchangedRef.current) return;
    exchangedRef.current = true;

    const code = searchParams.get("code");
    if (!code) {
      router.replace("/?error=no_code");
      return;
    }

    const exchange = async (): Promise<void> => {
      try {
        const response = await fetch(`${BASE_URL}/auth/sso/exchange`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code }),
        });
        const json = await response.json().catch(() => null);

        if (!response.ok || !json?.success || !json.data?.access_token) {
          const errCode =
            (json?.detail as string) ||
            (response.status === 401 ? "exchange_failed" : "exchange_error");
          router.replace(`/?error=${encodeURIComponent(errCode)}`);
          return;
        }

        setAccessToken(json.data.access_token as string);
        router.replace("/dashboard");
      } catch {
        setErrorMessage("無法連線到伺服器，請稍後再試");
        setTimeout(() => router.replace("/?error=exchange_error"), 1500);
      }
    };

    void exchange();
  }, [router, searchParams]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background p-4">
      <Spinner size="lg" />
      <p className="text-base text-muted">
        {errorMessage ?? "正在完成 SSO 登入..."}
      </p>
    </div>
  );
}
