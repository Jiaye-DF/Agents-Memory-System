"use client";

import { useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { DialogProvider } from "@/hooks/useDialog";
import { useSidebar } from "@/hooks/useSidebar";
import { useAuth } from "@/hooks/useAuth";
import { isSsoUser } from "@/lib/api/silent-reauth";
import { PageLoading } from "@/components/ui/Loading";

interface MainLayoutProps {
  children: React.ReactNode;
}

export default function MainLayout({
  children,
}: MainLayoutProps): React.ReactNode {
  const router = useRouter();
  const { state, isOverlay, toggle, close } = useSidebar();
  const { isAuthenticated, isLoading, role, username, logout } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      // SSO 用戶 → 走登入頁 auto-redirect 流程；本地用戶帶 ?local=1 避免被誤丟去 SSO
      const target = isSsoUser() ? "/" : "/?local=1";
      router.replace(target);
    }
  }, [isAuthenticated, isLoading, router]);

  const handleToggleSidebar = useCallback((): void => {
    toggle();
  }, [toggle]);

  const handleCloseSidebar = useCallback((): void => {
    close();
  }, [close]);

  const handleLogout = useCallback(async (): Promise<void> => {
    await logout();
  }, [logout]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <PageLoading />
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <DialogProvider>
      <div className="flex h-screen flex-col">
        <Header
          onToggleSidebar={handleToggleSidebar}
          username={username ?? "使用者"}
          onLogout={handleLogout}
        />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar
            state={state}
            isOverlay={isOverlay}
            onClose={handleCloseSidebar}
            role={role}
          />
          <main className="flex-1 overflow-y-auto p-4 lg:p-6">
            {children}
          </main>
        </div>
      </div>
    </DialogProvider>
  );
}
