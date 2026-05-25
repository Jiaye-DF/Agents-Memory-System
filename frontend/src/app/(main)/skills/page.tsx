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
import { TagFilterBar, TagList } from "@/components/tags";
import { useAuth } from "@/hooks/useAuth";
import { useDialog } from "@/hooks/useDialog";
import { useMutationWithDialog } from "@/hooks/useMutationWithDialog";
import { useConfirmMutation } from "@/hooks/useConfirmMutation";
import {
  useListSkillsQuery,
  useDeleteSkillMutation,
  useToggleSkillVisibilityMutation,
} from "@/store/skillsApi";
import {
  useListMyFavoritesQuery,
  useUnfavoriteResourceMutation,
} from "@/store/socialApi";
import type {
  Skill,
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

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

interface SkillRowProps {
  skill: Skill;
  isOwner: boolean;
  onDelete: (skillUid: string) => void;
  onToggleVisibility: (skillUid: string, current: string) => void;
}

const SkillRow = React.memo(function SkillRow({
  skill,
  isOwner,
  onDelete,
  onToggleVisibility,
}: SkillRowProps): React.ReactNode {
  const handleDelete = useCallback((): void => {
    onDelete(skill.skill_uid);
  }, [skill.skill_uid, onDelete]);

  const handleToggle = useCallback((): void => {
    onToggleVisibility(skill.skill_uid, skill.visibility);
  }, [skill.skill_uid, skill.visibility, onToggleVisibility]);

  return (
    <div className="flex flex-col gap-3 px-4 py-4 transition-colors hover:bg-muted-bg/40 md:flex-row md:items-center md:gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <Link
            href={`/skills/${skill.skill_uid}`}
            className="min-w-0 hover:cursor-pointer"
          >
            <h3 className="truncate text-lg font-semibold text-foreground hover:text-primary">
              {skill.name}
            </h3>
          </Link>
          <span
            className={`shrink-0 rounded-xl px-2 py-0.5 text-sm font-medium ${
              skill.visibility === "public"
                ? "bg-success/10 text-success"
                : "bg-muted-bg text-muted"
            }`}
          >
            {skill.visibility === "public" ? "公開" : "私人"}
          </span>
          {skill.owner_username && (
            <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
              @{skill.owner_username}
            </span>
          )}
        </div>

        {skill.description && (
          <p className="mt-1 line-clamp-1 text-base text-muted">
            {skill.description}
          </p>
        )}

        {skill.tags && skill.tags.length > 0 && (
          <div className="mt-1">
            <TagList tags={skill.tags} />
          </div>
        )}

        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
          <span>{formatFileSize(skill.file_size)}</span>
          <span className="truncate">{skill.original_filename}</span>
          <span>上傳於 {formatDateTime(skill.created_at)}</span>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2 md:ml-auto">
        <SocialMetrics
          favoriteCount={skill.favorite_count}
          downloadCount={skill.download_count}
        />
        <FavoriteButton
          resourceType="skill"
          resourceUid={skill.skill_uid}
          isFavorited={skill.is_favorited}
        />
        {isOwner && (
          <>
            <Button size="sm" variant="secondary" onClick={handleToggle}>
              {skill.visibility === "public" ? "設為私人" : "設為公開"}
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
            href={`/skills/${resource.uid}`}
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
                  ? "bg-success/10 text-success"
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
        {resource.description && (
          <p className="mt-1 line-clamp-1 text-base text-muted">
            {resource.description}
          </p>
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
          resourceType="skill"
          resourceUid={resource.uid}
          isFavorited
        />
      </div>
    </div>
  );
});

export default function SkillsListPage(): React.ReactNode {
  const { userUid, isLoading: authLoading } = useAuth();
  const { showDialog } = useDialog();

  const [scope, setScope] = useState<FilterScope>("mine");
  const [query, setQuery] = useState<string>("");
  const [selectedAuthors, setSelectedAuthors] = useState<string[]>([]);
  const [visibilityFilter, setVisibilityFilter] =
    useState<VisibilityFilter>("all");
  const [sortOrder, setSortOrder] = useState<SortOrder>("newest");
  const [tagUids, setTagUids] = useState<string[]>([]);

  const { data, isLoading, isFetching } = useListSkillsQuery(
    { limit: 50, cursor: null, tagUids: tagUids.length > 0 ? tagUids : undefined },
    { skip: authLoading || scope === "favorites" }
  );
  const {
    data: favoritesData,
    isLoading: favLoading,
    isFetching: favFetching,
  } = useListMyFavoritesQuery(
    { type: "skill", page: 1, size: 50 },
    { skip: authLoading || scope !== "favorites" }
  );

  const [deleteSkill] = useDeleteSkillMutation();
  const [toggleVisibility] = useToggleSkillVisibilityMutation();
  const [unfavorite, { isLoading: isUnfavoriting }] =
    useUnfavoriteResourceMutation();
  const runToggleVisibility = useMutationWithDialog(toggleVisibility);

  const skills = useMemo((): Skill[] => data?.items ?? [], [data]);

  const scopedSkills = useMemo(
    (): Skill[] => skills.filter((s) => s.owner_user_uid === userUid),
    [skills, userUid]
  );

  const parsed = useMemo(() => parseSearch(query), [query]);

  const filteredSkills = useMemo((): Skill[] => {
    const matched = scopedSkills.filter((s) => {
      if (visibilityFilter !== "all" && s.visibility !== visibilityFilter) {
        return false;
      }
      return matchByTextAndAuthor(
        s.name,
        s.description,
        s.owner_username,
        parsed,
        selectedAuthors
      );
    });
    const sorted = [...matched].sort((a, b) => {
      const diff = a.created_at.localeCompare(b.created_at);
      return sortOrder === "newest" ? -diff : diff;
    });
    return sorted;
  }, [scopedSkills, visibilityFilter, parsed, selectedAuthors, sortOrder]);

  const authorOptions = useMemo((): string[] => {
    const set = new Set<string>();
    for (const s of scopedSkills) {
      if (s.owner_username) set.add(s.owner_username);
    }
    return Array.from(set).sort();
  }, [scopedSkills]);

  const handleToggleAuthor = useCallback((author: string): void => {
    setSelectedAuthors((prev) => toggleAuthorChip(prev, author));
  }, []);

  const favoriteItems = useMemo(
    (): MyFavoriteItem[] => favoritesData?.items ?? [],
    [favoritesData]
  );

  const handleQueryChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setQuery(e.target.value);
    },
    []
  );

  const deleteOptions = useMemo(
    () => ({
      title: "刪除 Skill",
      message: "確定要刪除此 Skill 嗎？此操作無法復原。",
      successTitle: "刪除成功",
      successMessage: "Skill 已成功刪除。",
      errorMessage: "刪除失敗，請稍後再試",
    }),
    []
  );
  const confirmDeleteSkill = useConfirmMutation(deleteSkill, deleteOptions);
  const handleDelete = useCallback(
    (skillUid: string): void => {
      confirmDeleteSkill(skillUid);
    },
    [confirmDeleteSkill]
  );

  const handleToggleVisibility = useCallback(
    (skillUid: string, current: string): void => {
      const newVisibility = current === "public" ? "private" : "public";
      void runToggleVisibility(
        {
          skillUid,
          body: { visibility: newVisibility },
        },
        { errorMessage: "切換可見性失敗，請稍後再試" }
      );
    },
    [runToggleVisibility]
  );

  const handleTombstoneRemove = useCallback(
    async (skillUid: string): Promise<void> => {
      try {
        await unfavorite({
          resourceType: "skill",
          resourceUid: skillUid,
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
    (skillUid: string): void => {
      void handleTombstoneRemove(skillUid);
    },
    [handleTombstoneRemove]
  );

  const handleScopeChange = useCallback((next: FilterScope): void => {
    setScope(next);
  }, []);

  if (authLoading) {
    return <PageLoading />;
  }

  const isFavoritesScope = scope === "favorites";
  const showLoading = isFavoritesScope
    ? favLoading || favFetching
    : isLoading || isFetching;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-3xl font-bold text-foreground">Skills 管理</h1>
        <Link href="/skills/upload">
          <Button>上傳 Skill</Button>
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

          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
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

          <TagFilterBar selectedUids={tagUids} onChange={setTagUids} />
        </div>
      )}

      <div className="overflow-hidden rounded-xl bg-card-bg shadow-sm">
        {showLoading ? (
          <PageLoading />
        ) : isFavoritesScope ? (
          favoriteItems.length === 0 ? (
            <div className="py-12 text-center text-muted">
              尚未收藏任何 Skill。
            </div>
          ) : (
            <div className="divide-y divide-border">
              {favoriteItems.map((item) =>
                item.resource === null ? (
                  <TombstoneCard
                    key={item.user_favorite_uid}
                    resourceType="skill"
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
        ) : scopedSkills.length === 0 ? (
          <div className="py-12 text-center text-muted">
            {scope === "mine"
              ? "尚無 Skills，點擊右上角上傳第一個 Skill。"
              : "目前沒有可顯示的 Skill。"}
          </div>
        ) : filteredSkills.length === 0 ? (
          <div className="py-12 text-center text-muted">
            沒有符合條件的 Skills
          </div>
        ) : (
          <div className="divide-y divide-border">
            {filteredSkills.map((skill) => (
              <SkillRow
                key={skill.skill_uid}
                skill={skill}
                isOwner={skill.owner_user_uid === userUid}
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
