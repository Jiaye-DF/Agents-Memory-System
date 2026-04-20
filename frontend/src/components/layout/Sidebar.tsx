"use client";

import React, { useCallback, useMemo } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { SidebarState } from "@/hooks/useSidebar";

interface SidebarItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  adminOnly?: boolean;
}

interface SidebarProps {
  state: SidebarState;
  isOverlay: boolean;
  onClose: () => void;
  role?: string | null;
}

const SIDEBAR_ITEMS: SidebarItem[] = [
  {
    label: "儀表板",
    href: "/dashboard",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <rect x="3" y="3" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
        <rect x="11" y="3" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
        <rect x="3" y="11" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
        <rect x="11" y="11" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    ),
  },
  {
    label: "Agent 管理",
    href: "/agents",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="7" r="3" stroke="currentColor" strokeWidth="1.5" />
        <path d="M4 17C4 13.6863 6.68629 11 10 11C13.3137 11 16 13.6863 16 17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    label: "Skill 管理",
    href: "/skills",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M10 3L12.5 8H17L13.5 11.5L15 17L10 13.5L5 17L6.5 11.5L3 8H7.5L10 3Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    label: "使用者管理",
    href: "/admin/users",
    adminOnly: true,
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M13 7C13 8.65685 11.6569 10 10 10C8.34315 10 7 8.65685 7 7C7 5.34315 8.34315 4 10 4C11.6569 4 13 5.34315 13 7Z" stroke="currentColor" strokeWidth="1.5" />
        <path d="M5 16C5 13.2386 7.23858 11 10 11C12.7614 11 15 13.2386 15 16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M15 4L17 6L15 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M17 6H14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    label: "LLM 模型管理",
    href: "/admin/models",
    adminOnly: true,
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <rect x="4" y="4" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" />
        <rect x="7.5" y="7.5" width="5" height="5" rx="0.5" stroke="currentColor" strokeWidth="1.5" />
        <path d="M4 8H2M4 12H2M18 8H16M18 12H16M8 4V2M12 4V2M8 18V16M12 18V16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    label: "語言管理",
    href: "/admin/agent-languages",
    adminOnly: true,
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.5" />
        <path d="M3 10H17" stroke="currentColor" strokeWidth="1.5" />
        <path d="M10 3C12 5.5 13 7.5 13 10C13 12.5 12 14.5 10 17C8 14.5 7 12.5 7 10C7 7.5 8 5.5 10 3Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    label: "系統設定",
    href: "/admin/settings",
    adminOnly: true,
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="2.5" stroke="currentColor" strokeWidth="1.5" />
        <path d="M10 2V4M10 16V18M2 10H4M16 10H18M4.2 4.2L5.6 5.6M14.4 14.4L15.8 15.8M4.2 15.8L5.6 14.4M14.4 5.6L15.8 4.2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
];

const WIDTH_CLASSES: Record<SidebarState, string> = {
  expanded: "w-56",
  collapsed: "w-16",
  hidden: "w-0",
};

export const Sidebar = React.memo(function Sidebar({
  state,
  isOverlay,
  onClose,
  role,
}: SidebarProps): React.ReactNode {
  const pathname = usePathname();

  const handleOverlayClick = useCallback((): void => {
    onClose();
  }, [onClose]);

  const visibleItems = useMemo(
    (): SidebarItem[] =>
      SIDEBAR_ITEMS.filter((item) => {
        if (item.adminOnly && role !== "admin") return false;
        return true;
      }),
    [role]
  );

  if (state === "hidden" && !isOverlay) {
    return null;
  }

  const sidebarContent = (
    <nav
      className={`flex h-full flex-col border-r border-border bg-sidebar-bg transition-all duration-200 ${
        isOverlay ? "w-56" : WIDTH_CLASSES[state]
      }`}
    >
      <div className="flex flex-1 flex-col gap-1 overflow-y-auto p-2">
        {visibleItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={isOverlay ? onClose : undefined}
              className={`flex min-h-11 items-center gap-3 rounded-xl px-3 py-2 text-base font-medium transition-colors hover:cursor-pointer hover:bg-sidebar-hover ${
                isActive
                  ? "bg-sidebar-active text-primary"
                  : "text-foreground"
              } ${state === "collapsed" && !isOverlay ? "justify-center" : ""}`}
              title={state === "collapsed" && !isOverlay ? item.label : undefined}
            >
              <span className="shrink-0">{item.icon}</span>
              {(state === "expanded" || isOverlay) && (
                <span className="truncate">{item.label}</span>
              )}
            </Link>
          );
        })}
      </div>
    </nav>
  );

  if (isOverlay) {
    return (
      <>
        <div
          className="fixed inset-0 z-30 bg-overlay"
          onClick={handleOverlayClick}
        />
        <div className="fixed inset-y-0 left-0 z-30 mt-14">
          {sidebarContent}
        </div>
      </>
    );
  }

  return sidebarContent;
});
