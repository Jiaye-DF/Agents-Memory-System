"use client";

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { Agent } from "@/types";

interface ClassifiedAgent {
  agent: Agent;
  tier: 0 | 1 | 2; // 0: 個人私人、1: 個人公開、2: 他人公開
  isOwn: boolean;
}

interface AgentSelectProps {
  agents: Agent[];
  value: string;
  onChange: (agentUid: string) => void;
  userUid: string | null;
  disabled?: boolean;
  placeholder?: string;
}

function classifyAgents(
  agents: Agent[],
  userUid: string | null,
): ClassifiedAgent[] {
  const classified = agents.map((a): ClassifiedAgent => {
    const isOwn = !!userUid && a.owner_uid === userUid;
    const isPublic = a.visibility === "public";
    let tier: 0 | 1 | 2;
    if (isOwn && !isPublic) tier = 0;
    else if (isOwn && isPublic) tier = 1;
    else tier = 2;
    return { agent: a, tier, isOwn };
  });
  classified.sort((a, b) => {
    if (a.tier !== b.tier) return a.tier - b.tier;
    return a.agent.name.localeCompare(b.agent.name);
  });
  return classified;
}

function VisibilityTag({ isPublic }: { isPublic: boolean }): React.ReactNode {
  return (
    <span
      className={`shrink-0 rounded-md px-1.5 py-0.5 text-xs font-medium ${
        isPublic
          ? "bg-success/10 text-success"
          : "bg-muted-bg text-muted"
      }`}
    >
      {isPublic ? "公開" : "私人"}
    </span>
  );
}

function AuthorTag({
  username,
  isOwn,
}: {
  username: string | null;
  isOwn: boolean;
}): React.ReactNode {
  if (!username) return null;
  return (
    <span
      className={`shrink-0 truncate rounded-md px-1.5 py-0.5 text-xs font-medium ${
        isOwn
          ? "bg-primary/15 text-primary"
          : "bg-info-bg text-info"
      }`}
      title={`@${username}`}
    >
      @{username}
    </span>
  );
}

export const AgentSelect = React.memo(function AgentSelect({
  agents,
  value,
  onChange,
  userUid,
  disabled = false,
  placeholder = "請選擇 Agent",
}: AgentSelectProps): React.ReactNode {
  const [open, setOpen] = useState<boolean>(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const classified = useMemo(
    () => classifyAgents(agents, userUid),
    [agents, userUid],
  );

  const selected = useMemo(
    () => classified.find((c) => c.agent.agent_uid === value) ?? null,
    [classified, value],
  );

  const handleToggle = useCallback((): void => {
    if (disabled) return;
    setOpen((v) => !v);
  }, [disabled]);

  const handlePick = useCallback(
    (agentUid: string): void => {
      onChange(agentUid);
      setOpen(false);
    },
    [onChange],
  );

  useEffect(() => {
    if (!open) return undefined;
    function handleClickOutside(e: MouseEvent): void {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function handleEscape(e: KeyboardEvent): void {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={handleToggle}
        disabled={disabled}
        className="flex min-h-11 w-full items-center justify-between gap-2 rounded-xl border border-input-border bg-input-bg px-3 py-2 text-left text-base text-foreground transition-colors hover:cursor-pointer focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <div className="flex min-w-0 flex-1 items-center gap-2">
          {selected ? (
            <>
              <VisibilityTag
                isPublic={selected.agent.visibility === "public"}
              />
              <AuthorTag
                username={selected.agent.owner_username}
                isOwn={selected.isOwn}
              />
              <span className="truncate text-foreground">
                {selected.agent.name}
              </span>
            </>
          ) : (
            <span className="text-muted">{placeholder}</span>
          )}
        </div>
        <svg
          className={`shrink-0 text-muted transition-transform ${open ? "rotate-180" : ""}`}
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M4 6L8 10L12 6"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {open && (
        <div className="absolute left-0 right-0 z-20 mt-1 max-h-72 overflow-y-auto rounded-xl border border-border bg-card-bg shadow-lg">
          {classified.length === 0 ? (
            <div className="px-3 py-4 text-center text-sm text-muted">
              尚無可用的 Agent
            </div>
          ) : (
            <ul className="py-1">
              {classified.map(({ agent, isOwn }) => {
                const isSelected = agent.agent_uid === value;
                return (
                  <li key={agent.agent_uid}>
                    <button
                      type="button"
                      onClick={() => handlePick(agent.agent_uid)}
                      className={`flex w-full items-center gap-2 px-3 py-2 text-left text-base transition-colors hover:cursor-pointer hover:bg-muted-bg/60 ${
                        isSelected ? "bg-primary/10" : ""
                      }`}
                    >
                      <VisibilityTag
                        isPublic={agent.visibility === "public"}
                      />
                      <AuthorTag
                        username={agent.owner_username}
                        isOwn={isOwn}
                      />
                      <span className="min-w-0 truncate text-foreground">
                        {agent.name}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
});
