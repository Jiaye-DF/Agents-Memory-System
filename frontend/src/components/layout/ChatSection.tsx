"use client";

import React, { useMemo } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  useListOrphanChatSessionsQuery,
  useListProjectsQuery,
} from "@/store/chatApi";
import type { ChatProject, ChatSession } from "@/types";

const RECENT_LIMIT = 5;
const PROJECT_LIMIT = 8;

interface ChatSectionProps {
  onNavigate?: () => void;
}

export const ChatSection = React.memo(function ChatSection({
  onNavigate,
}: ChatSectionProps): React.ReactNode {
  const pathname = usePathname();

  const { data: orphanData } = useListOrphanChatSessionsQuery({
    limit: RECENT_LIMIT,
    cursor: null,
  });
  const { data: projectData } = useListProjectsQuery({
    limit: PROJECT_LIMIT,
    cursor: null,
  });

  const orphanSessions = useMemo(
    (): ChatSession[] => orphanData?.items ?? [],
    [orphanData],
  );
  const projects = useMemo(
    (): ChatProject[] => projectData?.items ?? [],
    [projectData],
  );

  const isActiveSession = (uid: string): boolean =>
    pathname === `/sessions/${uid}`;
  const isActiveProject = (uid: string): boolean =>
    pathname.startsWith(`/projects/${uid}`);

  return (
    <div className="flex flex-col gap-1">
      <Link
        href="/sessions/new"
        onClick={onNavigate}
        className="flex min-h-11 items-center justify-center gap-2 rounded-xl bg-primary px-3 py-2 text-base font-medium text-white transition-colors hover:cursor-pointer hover:opacity-90"
      >
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
          <path
            d="M10 4V16M4 10H16"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
        新對話
      </Link>

      <section className="mt-3">
        <div className="flex items-center justify-between px-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">
            最近對話
          </h3>
          <Link
            href="/sessions"
            onClick={onNavigate}
            className="text-sm text-muted hover:cursor-pointer hover:text-primary"
          >
            查看全部
          </Link>
        </div>
        <div className="mt-1 flex flex-col gap-0.5">
          {orphanSessions.length === 0 ? (
            <p className="px-3 py-2 text-sm text-muted italic">尚無游離對話</p>
          ) : (
            orphanSessions.map((s) => (
              <Link
                key={s.chat_session_uid}
                href={`/sessions/${s.chat_session_uid}`}
                onClick={onNavigate}
                className={`flex min-h-9 items-center truncate rounded-xl px-3 py-1.5 text-sm transition-colors hover:cursor-pointer hover:bg-sidebar-hover ${
                  isActiveSession(s.chat_session_uid)
                    ? "bg-sidebar-active text-primary"
                    : "text-foreground"
                }`}
                title={s.title}
              >
                <span className="truncate">{s.title}</span>
              </Link>
            ))
          )}
        </div>
      </section>

      <section className="mt-4">
        <div className="flex items-center justify-between px-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">
            Projects
          </h3>
          <Link
            href="/projects"
            onClick={onNavigate}
            className="text-sm text-muted hover:cursor-pointer hover:text-primary"
          >
            管理
          </Link>
        </div>
        <div className="mt-1 flex flex-col gap-0.5">
          {projects.length === 0 ? (
            <p className="px-3 py-2 text-sm text-muted italic">尚無 Project</p>
          ) : (
            projects.map((p) => (
              <Link
                key={p.chat_project_uid}
                href={`/projects/${p.chat_project_uid}`}
                onClick={onNavigate}
                className={`flex min-h-9 items-center justify-between gap-2 truncate rounded-xl px-3 py-1.5 text-sm transition-colors hover:cursor-pointer hover:bg-sidebar-hover ${
                  isActiveProject(p.chat_project_uid)
                    ? "bg-sidebar-active text-primary"
                    : "text-foreground"
                }`}
                title={p.name}
              >
                <span className="truncate">{p.name}</span>
                <span className="shrink-0 rounded-xl bg-muted-bg px-1.5 py-0.5 text-xs text-muted">
                  {p.session_count}
                </span>
              </Link>
            ))
          )}
        </div>
      </section>
    </div>
  );
});
