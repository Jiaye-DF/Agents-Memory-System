"use client";

import React, { useCallback } from "react";
import Link from "next/link";
import { Logo } from "./Logo";
import { ThemeSwitcher } from "./ThemeSwitcher";

interface HeaderProps {
  onToggleSidebar: () => void;
  username?: string;
  onLogout?: () => void;
}

export const Header = React.memo(function Header({
  onToggleSidebar,
  username = "使用者",
  onLogout,
}: HeaderProps): React.ReactNode {
  const handleLogout = useCallback((): void => {
    onLogout?.();
  }, [onLogout]);

  return (
    <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center border-b border-border bg-header-bg px-4 shadow-[0_2px_8px_var(--color-shadow)]">
      <div className="flex flex-1 items-center gap-3">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-xl text-foreground transition-colors hover:cursor-pointer hover:bg-muted-bg"
          aria-label="切換側邊選單"
        >
          <svg
            width="22"
            height="22"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M3 5H17M3 10H17M3 15H17"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </button>
        <Link
          href="/dashboard"
          className="flex items-center gap-2 hover:cursor-pointer"
        >
          <Logo />
          <span className="hidden text-xl font-semibold text-foreground sm:inline">
            Agents-Platform
          </span>
        </Link>
      </div>
      <div className="flex items-center gap-3">
        <ThemeSwitcher />
        <span className="text-lg text-foreground">{username}</span>
        <button
          type="button"
          onClick={handleLogout}
          className="min-h-[44px] min-w-[44px] rounded-xl px-3 py-2 text-lg font-medium text-destructive transition-colors hover:cursor-pointer hover:bg-error-bg"
        >
          登出
        </button>
      </div>
    </header>
  );
});
