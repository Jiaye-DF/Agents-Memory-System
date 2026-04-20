"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";

interface UseAdminGuardResult {
  role: string | null;
  authLoading: boolean;
  isAdmin: boolean;
  /** `true` 時頁面應回傳 PageLoading；`false` 時可進入正文 */
  shouldBlockRender: boolean;
}

/**
 * 非 admin 登入者自動導向 /403；頁面應依 `shouldBlockRender` 決定是否渲染 loading。
 */
export function useAdminGuard(): UseAdminGuardResult {
  const router = useRouter();
  const { role, isLoading: authLoading } = useAuth();

  useEffect(() => {
    if (!authLoading && role !== "admin") {
      router.replace("/403");
    }
  }, [role, authLoading, router]);

  const isAdmin = role === "admin";
  return {
    role,
    authLoading,
    isAdmin,
    shouldBlockRender: authLoading || !isAdmin,
  };
}
