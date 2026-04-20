"use client";

import React, { useState, useCallback, useMemo } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { PageLoading } from "@/components/ui/Loading";
import { useAuth } from "@/hooks/useAuth";
import { useMutationWithDialog } from "@/hooks/useMutationWithDialog";
import { useConfirmMutation } from "@/hooks/useConfirmMutation";
import {
  useListAgentsQuery,
  useDeleteAgentMutation,
  useToggleAgentVisibilityMutation,
} from "@/store/agentsApi";
import { useListAgentLanguagesQuery } from "@/store/agentLanguagesApi";
import type { Agent } from "@/types";
import {
  parseSearch,
  matchByTextAndAuthor,
  toggleAuthorInQuery,
} from "@/utils/search";
import { formatDateTime } from "@/utils/datetime";

type VisibilityFilter = "all" | "public" | "private";
type SortOrder = "newest" | "oldest";

interface AgentCardProps {
  agent: Agent;
  isOwner: boolean;
  languageLabel: string | null;
  onDelete: (agentUid: string) => void;
  onToggleVisibility: (agentUid: string, current: string) => void;
}

const AgentCard = React.memo(function AgentCard({
  agent,
  isOwner,
  languageLabel,
  onDelete,
  onToggleVisibility,
}: AgentCardProps): React.ReactNode {
  const handleDelete = useCallback((): void => {
    onDelete(agent.agent_uid);
  }, [agent.agent_uid, onDelete]);

  const handleToggle = useCallback((): void => {
    onToggleVisibility(agent.agent_uid, agent.visibility);
  }, [agent.agent_uid, agent.visibility, onToggleVisibility]);

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-card-bg p-4 shadow-sm transition-colors hover:shadow-md">
      <div className="flex items-start justify-between gap-2">
        <Link
          href={`/agents/${agent.agent_uid}`}
          className="min-w-0 flex-1 hover:cursor-pointer"
        >
          <h3 className="truncate text-xl font-semibold text-foreground">
            {agent.name}
          </h3>
        </Link>
        <span
          className={`shrink-0 rounded-xl px-2 py-0.5 text-sm font-medium ${
            agent.visibility === "public"
              ? "bg-info-bg text-info"
              : "bg-muted-bg text-muted"
          }`}
        >
          {agent.visibility === "public" ? "公開" : "私人"}
        </span>
      </div>

      {agent.owner_username && (
        <span className="inline-flex w-fit rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
          @{agent.owner_username}
        </span>
      )}

      {agent.description ? (
        <p className="line-clamp-2 text-base text-muted">{agent.description}</p>
      ) : (
        <p className="text-base text-muted italic">尚無描述</p>
      )}

      <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm text-muted">
        {languageLabel && <span>語言：{languageLabel}</span>}
        {agent.style && <span>風格：{agent.style}</span>}
        <span>建立於 {formatDateTime(agent.created_at)}</span>
      </div>

      <div className="mt-auto flex items-center gap-2 border-t border-border pt-3">
        <Link href={`/agents/${agent.agent_uid}`}>
          <Button variant="ghost" size="sm">
            檢視
          </Button>
        </Link>
        {isOwner && (
          <>
            <Link href={`/agents/${agent.agent_uid}/edit`}>
              <Button variant="ghost" size="sm">
                編輯
              </Button>
            </Link>
            <Button variant="secondary" size="sm" onClick={handleToggle}>
              {agent.visibility === "public" ? "設為私人" : "設為公開"}
            </Button>
            <Button variant="destructive" size="sm" onClick={handleDelete}>
              刪除
            </Button>
          </>
        )}
      </div>
    </div>
  );
});

interface FilterChipProps {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}

const FilterChip = React.memo(function FilterChip({
  active,
  onClick,
  children,
}: FilterChipProps): React.ReactNode {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-xl px-3 py-1 text-sm font-medium transition-colors hover:cursor-pointer ${
        active
          ? "bg-primary text-white"
          : "bg-muted-bg text-muted hover:bg-border"
      }`}
    >
      {children}
    </button>
  );
});

export default function AgentsPage(): React.ReactNode {
  const { userUid } = useAuth();

  const [query, setQuery] = useState<string>("");
  const [visibilityFilter, setVisibilityFilter] =
    useState<VisibilityFilter>("all");
  const [sortOrder, setSortOrder] = useState<SortOrder>("newest");

  const { data, isLoading, isFetching } = useListAgentsQuery({
    limit: 50,
    cursor: null,
  });
  const { data: languagesData } = useListAgentLanguagesQuery();
  const [deleteAgent] = useDeleteAgentMutation();
  const [toggleVisibility] = useToggleAgentVisibilityMutation();
  const runToggleVisibility = useMutationWithDialog(toggleVisibility);

  const languageNameMap = useMemo((): Map<string, string> => {
    const map = new Map<string, string>();
    for (const l of languagesData?.items ?? []) {
      map.set(l.code, l.name);
    }
    return map;
  }, [languagesData]);

  const resolveLanguage = useCallback(
    (code: string | null): string | null => {
      if (!code) return null;
      return languageNameMap.get(code) ?? code;
    },
    [languageNameMap]
  );

  const agents = useMemo((): Agent[] => data?.items ?? [], [data]);

  const parsed = useMemo(() => parseSearch(query), [query]);

  const filteredAgents = useMemo((): Agent[] => {
    const matched = agents.filter((a) => {
      if (visibilityFilter !== "all" && a.visibility !== visibilityFilter) {
        return false;
      }
      return matchByTextAndAuthor(
        a.name,
        a.description,
        a.owner_username,
        parsed
      );
    });
    const sorted = [...matched].sort((a, b) => {
      const diff = a.created_at.localeCompare(b.created_at);
      return sortOrder === "newest" ? -diff : diff;
    });
    return sorted;
  }, [agents, visibilityFilter, parsed, sortOrder]);

  const authorOptions = useMemo((): string[] => {
    const set = new Set<string>();
    for (const a of agents) {
      if (a.owner_username) set.add(a.owner_username);
    }
    return Array.from(set).sort();
  }, [agents]);

  const handleQueryChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setQuery(e.target.value);
    },
    []
  );

  const handleToggleAuthor = useCallback((author: string): void => {
    setQuery((prev) => toggleAuthorInQuery(prev, author));
  }, []);

  const deleteOptions = useMemo(
    () => ({
      title: "刪除 Agent",
      message: "確定要刪除此 Agent 嗎？此操作無法復原。",
      successTitle: "刪除成功",
      successMessage: "Agent 已成功刪除。",
      errorMessage: "刪除失敗，請稍後再試",
    }),
    []
  );
  const confirmDeleteAgent = useConfirmMutation(deleteAgent, deleteOptions);
  const handleDelete = useCallback(
    (agentUid: string): void => {
      confirmDeleteAgent(agentUid);
    },
    [confirmDeleteAgent]
  );

  const handleToggleVisibility = useCallback(
    (agentUid: string, current: string): void => {
      const newVisibility = current === "public" ? "private" : "public";
      void runToggleVisibility(
        {
          agentUid,
          body: { visibility: newVisibility as "public" | "private" },
        },
        { errorMessage: "切換可見性失敗，請稍後再試" }
      );
    },
    [runToggleVisibility]
  );

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-3xl font-bold text-foreground">Agent 管理</h1>
        <Link href="/agents/new">
          <Button>新增 Agent</Button>
        </Link>
      </div>

      <div className="mb-4 flex flex-col gap-3">
        <Input
          placeholder="搜尋名稱、描述，或輸入 @作者 篩選（可多個）"
          value={query}
          onChange={handleQueryChange}
        />

        <div className="flex flex-wrap items-center gap-2">
          <span className="shrink-0 text-sm text-muted">可見性：</span>
          <FilterChip
            active={visibilityFilter === "all"}
            onClick={() => setVisibilityFilter("all")}
          >
            全部
          </FilterChip>
          <FilterChip
            active={visibilityFilter === "public"}
            onClick={() => setVisibilityFilter("public")}
          >
            公開
          </FilterChip>
          <FilterChip
            active={visibilityFilter === "private"}
            onClick={() => setVisibilityFilter("private")}
          >
            私人
          </FilterChip>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="shrink-0 text-sm text-muted">排序：</span>
          <FilterChip
            active={sortOrder === "newest"}
            onClick={() => setSortOrder("newest")}
          >
            由新到舊
          </FilterChip>
          <FilterChip
            active={sortOrder === "oldest"}
            onClick={() => setSortOrder("oldest")}
          >
            由舊到新
          </FilterChip>
        </div>

        {authorOptions.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="shrink-0 text-sm text-muted">作者：</span>
            {authorOptions.map((author) => {
              const isSelected = parsed.authors.includes(author.toLowerCase());
              return (
                <FilterChip
                  key={author}
                  active={isSelected}
                  onClick={() => handleToggleAuthor(author)}
                >
                  @{author}
                </FilterChip>
              );
            })}
          </div>
        )}
      </div>

      <div className="rounded-xl bg-card-bg p-6 shadow-sm">
        {isLoading || isFetching ? (
          <PageLoading />
        ) : agents.length === 0 ? (
          <div className="py-12 text-center text-muted">
            尚未建立任何 Agent，點擊右上角新增。
          </div>
        ) : filteredAgents.length === 0 ? (
          <div className="py-12 text-center text-muted">
            沒有符合條件的 Agents
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filteredAgents.map((agent) => (
              <AgentCard
                key={agent.agent_uid}
                agent={agent}
                isOwner={agent.owner_uid === userUid}
                languageLabel={resolveLanguage(agent.language)}
                onDelete={handleDelete}
                onToggleVisibility={handleToggleVisibility}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
