"use client";

import React, { useCallback } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { SidebarState } from "@/hooks/useSidebar";

interface SidebarItem {
  label: string;
  href: string;
  icon: React.ReactNode;
}

interface SidebarProps {
  state: SidebarState;
  isOverlay: boolean;
  onClose: () => void;
}

const SIDEBAR_ITEMS: SidebarItem[] = [
  {
    label: "Dashboard",
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
    label: "Agents",
    href: "/agents",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="7" r="3" stroke="currentColor" strokeWidth="1.5" />
        <path d="M4 17C4 13.6863 6.68629 11 10 11C13.3137 11 16 13.6863 16 17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    label: "Skills",
    href: "/skills",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M10 3L12.5 8H17L13.5 11.5L15 17L10 13.5L5 17L6.5 11.5L3 8H7.5L10 3Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    label: "Admin",
    href: "/admin/users",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M10 3C6.13401 3 3 6.13401 3 10C3 13.866 6.13401 17 10 17C13.866 17 17 13.866 17 10C17 6.13401 13.866 3 10 3Z" stroke="currentColor" strokeWidth="1.5" />
        <path d="M10 7V10L12 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
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
}: SidebarProps): React.ReactNode {
  const pathname = usePathname();

  const handleOverlayClick = useCallback((): void => {
    onClose();
  }, [onClose]);

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
        {SIDEBAR_ITEMS.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={isOverlay ? onClose : undefined}
              className={`flex min-h-[44px] items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors hover:cursor-pointer hover:bg-sidebar-hover ${
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
