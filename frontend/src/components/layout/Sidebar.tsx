"use client";

import React, { useCallback, useMemo } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { SidebarState } from "@/hooks/useSidebar";
import { usePendingApprovalDialog } from "@/hooks/usePendingApprovalDialog";
import { useListSkillSuggestionsQuery } from "@/store/agenticApi";
import { ChatSection } from "./ChatSection";

/**
 * df 公司版本 feature flag：對話領域（新對話 / 最近對話 / 最近專案 / 收合 + 鈕）整段隱藏。
 * 設為 `false` 時下方原始 ChatSection 渲染與收合 + 按鈕皆不執行；程式碼保留以利日後解鎖。
 */
const CHAT_DOMAIN_ENABLED: boolean = false;

interface SidebarItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  adminOnly?: boolean;
  /** v1.3.6：可選的右側計數徽章 key（由 Sidebar 元件解析後渲染） */
  badgeKey?: "skill-suggestions";
  /** df 公司版本：點擊時改顯示「功能審核中」dialog，不導航 */
  pendingApproval?: boolean;
}

interface SidebarGroup {
  key: string;
  label: string;
  adminOnly?: boolean;
  items: SidebarItem[];
}

interface SidebarProps {
  state: SidebarState;
  isOverlay: boolean;
  onClose: () => void;
  role?: string | null;
}

const SIDEBAR_GROUPS: SidebarGroup[] = [
  {
    key: "overview",
    label: "概覽",
    items: [
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
    ],
  },
  {
    key: "resources",
    label: "我的資源",
    items: [
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
        label: "Script 管理",
        href: "/scripts",
        icon: (
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M6 4L2 10L6 16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M14 4L18 10L14 16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M12 3L8 17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        ),
      },
      {
        label: "Skill 建議",
        href: "/skill-suggestions",
        badgeKey: "skill-suggestions",
        pendingApproval: true,
        icon: (
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M10 3L12.5 7L17 7.5L13.5 11L14.5 16L10 13.5L5.5 16L6.5 11L3 7.5L7.5 7L10 3Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
            <circle cx="15.5" cy="14.5" r="2" fill="currentColor" />
          </svg>
        ),
      },
    ],
  },
  {
    key: "admin",
    label: "系統管理",
    adminOnly: true,
    items: [
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
        label: "Agent 範本",
        href: "/admin/agent-templates",
        adminOnly: true,
        icon: (
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <rect x="3" y="4" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" />
            <path d="M6 8H14M6 11H12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
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
    ],
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
  const showPendingApproval = usePendingApprovalDialog();

  const handleOverlayClick = useCallback((): void => {
    onClose();
  }, [onClose]);

  const visibleGroups = useMemo((): SidebarGroup[] => {
    return SIDEBAR_GROUPS.map((group) => {
      if (group.adminOnly && role !== "admin") return null;
      const items = group.items.filter(
        (item) => !(item.adminOnly && role !== "admin")
      );
      if (items.length === 0) return null;
      return { ...group, items };
    }).filter((g): g is SidebarGroup => g !== null);
  }, [role]);

  if (state === "hidden" && !isOverlay) {
    return null;
  }

  const showChatSection = state === "expanded" || isOverlay;
  const handleChatSectionNavigate = isOverlay ? onClose : undefined;
  const showGroupLabel = state === "expanded" || isOverlay;

  const sidebarContent = (
    <nav
      className={`flex h-full flex-col border-r border-border bg-sidebar-bg transition-all duration-200 ${
        isOverlay ? "w-56" : WIDTH_CLASSES[state]
      }`}
    >
      <div className="flex flex-1 flex-col gap-1 overflow-y-auto p-2">
        {/* df 公司版本：CHAT_DOMAIN_ENABLED=false 時整段不渲染；程式碼保留以利解鎖 */}
        {CHAT_DOMAIN_ENABLED &&
          (showChatSection ? (
            <>
              <ChatSection onNavigate={handleChatSectionNavigate} />
              <div className="my-3 border-t border-border" />
            </>
          ) : (
            <button
              type="button"
              onClick={showPendingApproval}
              className="flex min-h-11 items-center justify-center rounded-xl bg-primary py-2 text-white transition-colors hover:cursor-pointer hover:opacity-90"
              title="新對話"
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path
                  d="M10 4V16M4 10H16"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          ))}

        {visibleGroups.map((group, groupIndex) => (
          <div key={group.key} className="flex flex-col gap-1">
            {groupIndex > 0 && (
              <hr className="my-2 border-t border-border" />
            )}
            {showGroupLabel && (
              <div className="px-3 pt-1 pb-0.5 text-xs font-semibold uppercase tracking-wider text-muted">
                {group.label}
              </div>
            )}
            {group.items.map((item) => {
              const isActive = pathname.startsWith(item.href);
              const showLabel = state === "expanded" || isOverlay;
              const className = `flex min-h-11 items-center gap-3 rounded-xl px-3 py-2 text-base font-medium transition-colors hover:cursor-pointer hover:bg-sidebar-hover ${
                isActive
                  ? "bg-sidebar-active text-primary"
                  : "text-foreground"
              } ${state === "collapsed" && !isOverlay ? "justify-center" : ""}`;
              const title =
                state === "collapsed" && !isOverlay ? item.label : undefined;
              const inner = (
                <>
                  <span className="shrink-0">{item.icon}</span>
                  {showLabel && (
                    <span className="truncate flex-1">{item.label}</span>
                  )}
                  {showLabel && item.badgeKey === "skill-suggestions" && (
                    <SkillSuggestionsPendingBadge />
                  )}
                </>
              );

              if (item.pendingApproval) {
                return (
                  <button
                    key={item.href}
                    type="button"
                    onClick={() => {
                      showPendingApproval();
                      if (isOverlay) onClose();
                    }}
                    className={`${className} w-full text-left`}
                    title={title}
                  >
                    {inner}
                  </button>
                );
              }

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={isOverlay ? onClose : undefined}
                  className={className}
                  title={title}
                >
                  {inner}
                </Link>
              );
            })}
          </div>
        ))}
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


/**
 * v1.3.6：sidebar Skill 建議入口的 pending 計數徽章。
 * 抽成獨立元件，避免在 Sidebar 主迴圈內每個 item 都觸發 query。
 */
function SkillSuggestionsPendingBadge(): React.ReactNode {
  const { data } = useListSkillSuggestionsQuery({
    status: "pending",
    page: 1,
    size: 1,
  });
  const count = data?.total ?? 0;
  if (count === 0) return null;
  return (
    <span
      className="ml-auto inline-flex min-w-6 items-center justify-center rounded-full bg-primary px-1.5 py-0.5 text-xs font-medium text-white"
      title={`${count} 則待處理建議`}
    >
      {count > 99 ? "99+" : count}
    </span>
  );
}
