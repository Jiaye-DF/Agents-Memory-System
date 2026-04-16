"use client";

import { useCallback } from "react";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { DialogProvider } from "@/hooks/useDialog";
import { useSidebar } from "@/hooks/useSidebar";

interface MainLayoutProps {
  children: React.ReactNode;
}

export default function MainLayout({
  children,
}: MainLayoutProps): React.ReactNode {
  const { state, isOverlay, toggle, close } = useSidebar();

  const handleToggleSidebar = useCallback((): void => {
    toggle();
  }, [toggle]);

  const handleCloseSidebar = useCallback((): void => {
    close();
  }, [close]);

  return (
    <DialogProvider>
      <div className="flex h-screen flex-col">
        <Header onToggleSidebar={handleToggleSidebar} />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar
            state={state}
            isOverlay={isOverlay}
            onClose={handleCloseSidebar}
          />
          <main className="flex-1 overflow-y-auto p-4 lg:p-6 xl:mx-auto xl:max-w-screen-xl">
            {children}
          </main>
        </div>
      </div>
    </DialogProvider>
  );
}
