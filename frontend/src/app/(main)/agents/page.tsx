"use client";

import React, { useState, useCallback, useMemo } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { FilterChip } from "@/components/ui/FilterChip";
import { PageLoading } from "@/components/ui/Loading";
import { FilterNav } from "@/components/social/FilterNav";
import { SocialMetrics } from "@/components/social/SocialMetrics";
import { FavoriteButton } from "@/components/social/FavoriteButton";
import { TombstoneCard } from "@/components/social/TombstoneCard";
import { useAuth } from "@/hooks/useAuth";
import { useDialog } from "@/hooks/useDialog";
import { useMutationWithDialog } from "@/hooks/useMutationWithDialog";
import { useConfirmMutation } from "@/hooks/useConfirmMutation";
import {
  useListAgentsQuery,
  useDeleteAgentMutation,
  useToggleAgentVisibilityMutation,
} from "@/store/agentsApi";
import {
  useListMyFavoritesQuery,
  useUnfavoriteResourceMutation,
} from "@/store/socialApi";
import { useListAgentLanguagesQuery } from "@/store/agentLanguagesApi";
import type {
  Agent,
  FilterScope,
  MyFavoriteItem,
  ResourceSnapshot,
} from "@/types";
import {
  parseSearch,
  matchByTextAndAuthor,
  toggleAuthorChip,
} from "@/utils/search";
import { formatDateTime } from "@/utils/datetime";

type VisibilityFilter = "all" | "public" | "private";
type SortOrder = "newest" | "oldest";

interface AgentRowProps {
  agent: Agent;
  isOwner: boolean;
  languageLabel: string | null;
  onDelete: (agentUid: string) => void;
  onToggleVisibility: (agentUid: string, current: string) => void;
}

const AgentRow = React.memo(function AgentRow({
  agent,
  isOwner,
  languageLabel,
  onDelete,
  onToggleVisibility,
}: AgentRowProps): React.ReactNode {
  const handleDelete = useCallback((): void => {
    onDelete(agent.agent_uid);
  }, [agent.agent_uid, onDelete]);

  const handleToggle = useCallback((): void => {
    onToggleVisibility(agent.agent_uid, agent.visibility);
  }, [agent.agent_uid, agent.visibility, onToggleVisibility]);

  return (
    <div className="flex flex-col gap-3 px-4 py-4 transition-colors hover:bg-muted-bg/40 md:flex-row md:items-center md:gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={`/agents/${agent.agent_uid}`}
            className="min-w-0 hover:cursor-pointer"
          >
            <h3 className="truncate text-lg font-semibold text-foreground hover:text-primary">
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
          {agent.owner_username && (
            <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
              @{agent.owner_username}
            </span>
          )}
        </div>

        {agent.description ? (
          <p className="mt-1 line-clamp-1 text-base text-muted">
            {agent.description}
          </p>
        ) : (
          <p className="mt-1 text-base text-muted italic">尚無描述</p>
        )}

        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
          {languageLabel && <span>語言：{languageLabel}</span>}
          {agent.style && <span>風格：{agent.style}</span>}
          <span>建立於 {formatDateTime(agent.created_at)}</span>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2 md:ml-auto">
        <SocialMetrics
          favoriteCount={agent.favorite_count}
          downloadCount={agent.download_count}
        />
        <FavoriteButton
          resourceType="agent"
          resourceUid={agent.agent_uid}
          isFavorited={agent.is_favorited}
        />
        {isOwner && (
          <>
            <Link href={`/agents/${agent.agent_uid}/edit`}>
              <Button size="sm" variant="ghost">
                編輯
              </Button>
            </Link>
            <Button size="sm" variant="secondary" onClick={handleToggle}>
              {agent.visibility === "public" ? "設為私人" : "設為公開"}
            </Button>
            <Button size="sm" variant="destructive" onClick={handleDelete}>
              刪除
            </Button>
          </>
        )}
      </div>
    </div>
  );
});

interface SnapshotRowProps {
  resource: ResourceSnapshot;
}

const SnapshotRow = React.memo(function SnapshotRow({
  resource,
}: SnapshotRowProps): React.ReactNode {
  return (
    <div className="flex flex-col gap-3 px-4 py-4 transition-colors hover:bg-muted-bg/40 md:flex-row md:items-center md:gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={`/agents/${resource.uid}`}
            className="min-w-0 hover:cursor-pointer"
          >
            <h3 className="truncate text-lg font-semibold text-foreground hover:text-primary">
              {resource.name}
            </h3>
          </Link>
          {resource.visibility && (
            <span
              className={`shrink-0 rounded-xl px-2 py-0.5 text-sm font-medium ${
                resource.visibility === "public"
                  ? "bg-info-bg text-info"
                  : "bg-muted-bg text-muted"
              }`}
            >
              {resource.visibility === "public" ? "公開" : "私人"}
            </span>
          )}
          {resource.owner_username && (
            <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
              @{resource.owner_username}
            </span>
          )}
        </div>
        {resource.description ? (
          <p className="mt-1 line-clamp-1 text-base text-muted">
            {resource.description}
          </p>
        ) : (
          <p className="mt-1 text-base text-muted italic">尚無描述</p>
        )}
        {resource.created_at && (
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
            <span>建立於 {formatDateTime(resource.created_at)}</span>
          </div>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2 md:ml-auto">
        <SocialMetrics
          favoriteCount={resource.favorite_count}
          downloadCount={resource.download_count}
        />
        <FavoriteButton
          resourceType="agent"
          resourceUid={resource.uid}
          isFavorited
        />
      </div>
    </div>
  );
});

export default function AgentsPage(): React.ReactNode {
  const { userUid } = useAuth();
  const { showDialog } = useDialog();

  const [scope, setScope] = useState<FilterScope>("mine");
  const [query, setQuery] = useState<string>("");
  const [selectedAuthors, setSelectedAuthors] = useState<string[]>([]);
  const [visibilityFilter, setVisibilityFilter] =
    useState<VisibilityFilter>("all");
  const [sortOrder, setSortOrder] = useState<SortOrder>("newest");

  const { data, isLoading, isFetching } = useListAgentsQuery(
    { limit: 50, cursor: null },
    { skip: scope === "favorites" }
  );
  const {
    data: favoritesData,
    isLoading: favLoading,
    isFetching: favFetching,
  } = useListMyFavoritesQuery(
    { type: "agent", page: 1, size: 50 },
    { skip: scope !== "favorites" }
  );
  const { data: languagesData } = useListAgentLanguagesQuery();
  const [deleteAgent] = useDeleteAgentMutation();
  const [toggleVisibility] = useToggleAgentVisibilityMutation();
  const [unfavorite, { isLoading: isUnfavoriting }] =
    useUnfavoriteResourceMutation();
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

  const scopedAgents = useMemo(
    (): Agent[] => agents.filter((a) => a.owner_uid === userUid),
    [agents, userUid]
  );

  const parsed = useMemo(() => parseSearch(query), [query]);

  const filteredAgents = useMemo((): Agent[] => {
    const matched = scopedAgents.filter((a) => {
      if (visibilityFilter !== "all" && a.visibility !== visibilityFilter) {
        return false;
      }
      return matchByTextAndAuthor(
        a.name,
        a.description,
        a.owner_username,
        parsed,
        selectedAuthors
      );
    });
    const sorted = [...matched].sort((a, b) => {
      const diff = a.created_at.localeCompare(b.created_at);
      return sortOrder === "newest" ? -diff : diff;
    });
    return sorted;
  }, [scopedAgents, visibilityFilter, parsed, selectedAuthors, sortOrder]);

  const favoriteItems = useMemo(
    (): MyFavoriteItem[] => favoritesData?.items ?? [],
    [favoritesData]
  );

  const authorOptions = useMemo((): string[] => {
    const set = new Set<string>();
    for (const a of scopedAgents) {
      if (a.owner_username) set.add(a.owner_username);
    }
    return Array.from(set).sort();
  }, [scopedAgents]);

  const handleQueryChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setQuery(e.target.value);
    },
    []
  );

  const handleToggleAuthor = useCallback((author: string): void => {
    setSelectedAuthors((prev) => toggleAuthorChip(prev, author));
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

  const handleTombstoneRemove = useCallback(
    async (agentUid: string): Promise<void> => {
      try {
        await unfavorite({
          resourceType: "agent",
          resourceUid: agentUid,
        }).unwrap();
      } catch (err: unknown) {
        const fallback = "從收藏移除失敗，請稍後再試";
        const message = typeof err === "string" ? err : fallback;
        showDialog({ type: "error", title: "操作失敗", message });
      }
    },
    [unfavorite, showDialog]
  );

  const handleTombstoneRemoveSync = useCallback(
    (agentUid: string): void => {
      void handleTombstoneRemove(agentUid);
    },
    [handleTombstoneRemove]
  );

  const handleScopeChange = useCallback((next: FilterScope): void => {
    setScope(next);
  }, []);

  const isFavoritesScope = scope === "favorites";
  const showLoading = isFavoritesScope
    ? favLoading || favFetching
    : isLoading || isFetching;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-3xl font-bold text-foreground">Agent 管理</h1>
        <Link href="/agents/new">
          <Button>新增 Agent</Button>
        </Link>
      </div>

      <div className="mb-4">
        <FilterNav value={scope} onChange={handleScopeChange} />
      </div>

      {!isFavoritesScope && (
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
            <span className="shrink-0 text-sm text-muted">按時間：</span>
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
                const lower = author.toLowerCase();
                const isSelected =
                  parsed.authors.includes(lower) ||
                  selectedAuthors.some((a) => a.toLowerCase() === lower);
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
      )}

      <div className="overflow-hidden rounded-xl bg-card-bg shadow-sm">
        {showLoading ? (
          <PageLoading />
        ) : isFavoritesScope ? (
          favoriteItems.length === 0 ? (
            <div className="py-12 text-center text-muted">
              尚未收藏任何 Agent。
            </div>
          ) : (
            <div className="divide-y divide-border">
              {favoriteItems.map((item) =>
                item.resource === null ? (
                  <TombstoneCard
                    key={item.user_favorite_uid}
                    resourceType="agent"
                    resourceUid={item.resource_uid}
                    onRemove={handleTombstoneRemoveSync}
                    isRemoving={isUnfavoriting}
                  />
                ) : (
                  <SnapshotRow
                    key={item.user_favorite_uid}
                    resource={item.resource}
                  />
                )
              )}
            </div>
          )
        ) : scopedAgents.length === 0 ? (
          <div className="py-12 text-center text-muted">
            {scope === "mine"
              ? "尚未建立任何 Agent，點擊右上角新增。"
              : "目前沒有可顯示的 Agent。"}
          </div>
        ) : filteredAgents.length === 0 ? (
          <div className="py-12 text-center text-muted">
            沒有符合條件的 Agents
          </div>
        ) : (
          <div className="divide-y divide-border">
            {filteredAgents.map((agent) => (
              <AgentRow
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
