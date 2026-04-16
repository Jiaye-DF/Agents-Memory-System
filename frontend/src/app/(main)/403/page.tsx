"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";

export default function ForbiddenPage(): React.ReactNode {
  const router = useRouter();

  const handleBack = useCallback((): void => {
    router.push("/dashboard");
  }, [router]);

  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold text-foreground">權限不足</h1>
      <div className="rounded-xl bg-card-bg p-6 shadow-sm">
        <div className="flex flex-col items-center gap-6 py-8">
          <div className="rounded-xl bg-error-bg p-4">
            <svg
              width="48"
              height="48"
              viewBox="0 0 48 48"
              fill="none"
              className="text-destructive"
            >
              <circle
                cx="24"
                cy="24"
                r="20"
                stroke="currentColor"
                strokeWidth="2"
              />
              <path
                d="M16 24H32"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </div>
          <div className="text-center">
            <h2 className="text-xl font-semibold text-foreground">403 Forbidden</h2>
            <p className="mt-2 text-sm text-muted">
              您沒有權限存取此頁面，請聯繫管理員取得相應權限。
            </p>
          </div>
          <Button onClick={handleBack}>返回 Dashboard</Button>
        </div>
      </div>
    </div>
  );
}
