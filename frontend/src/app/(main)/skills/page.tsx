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
  useListSkillsQuery,
  useDeleteSkillMutation,
  useToggleSkillVisibilityMutation,
} from "@/store/skillsApi";
import type { Skill } from "@/types";
import { parseSearch, matchByTextAndAuthor } from "@/utils/search";
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

        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
          <span>{formatFileSize(skill.file_size)}</span>
          <span className="truncate">{skill.original_filename}</span>
          <span>上傳於 {formatDateTime(skill.created_at)}</span>
        </div>
      </div>

      {isOwner && (
        <div className="flex shrink-0 items-center gap-2 md:ml-auto">
          <Button size="sm" variant="secondary" onClick={handleToggle}>
            {skill.visibility === "public" ? "設為私人" : "設為公開"}
          </Button>
          <Button size="sm" variant="destructive" onClick={handleDelete}>
            刪除
          </Button>
        </div>
      )}
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

export default function SkillsListPage(): React.ReactNode {
  const { userUid, isLoading: authLoading } = useAuth();

  const [query, setQuery] = useState<string>("");
  const [visibilityFilter, setVisibilityFilter] =
    useState<VisibilityFilter>("all");
  const [sortOrder, setSortOrder] = useState<SortOrder>("newest");

  const { data, isLoading, isFetching } = useListSkillsQuery(
    { limit: 50, cursor: null },
    { skip: authLoading }
  );

  const [deleteSkill] = useDeleteSkillMutation();
  const [toggleVisibility] = useToggleSkillVisibilityMutation();
  const runToggleVisibility = useMutationWithDialog(toggleVisibility);

  const skills = useMemo((): Skill[] => data?.items ?? [], [data]);

  const parsed = useMemo(() => parseSearch(query), [query]);

  const filteredSkills = useMemo((): Skill[] => {
    const matched = skills.filter((s) => {
      if (visibilityFilter !== "all" && s.visibility !== visibilityFilter) {
        return false;
      }
      return matchByTextAndAuthor(
        s.name,
        s.description,
        s.owner_username,
        parsed
      );
    });
    const sorted = [...matched].sort((a, b) => {
      const diff = a.created_at.localeCompare(b.created_at);
      return sortOrder === "newest" ? -diff : diff;
    });
    return sorted;
  }, [skills, visibilityFilter, parsed, sortOrder]);

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

  if (authLoading) {
    return <PageLoading />;
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-3xl font-bold text-foreground">Skills 管理</h1>
        <Link href="/skills/upload">
          <Button>上傳 Skill</Button>
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

      </div>

      <div className="overflow-hidden rounded-xl bg-card-bg shadow-sm">
        {isLoading || isFetching ? (
          <PageLoading />
        ) : skills.length === 0 ? (
          <div className="py-12 text-center text-muted">
            尚無 Skills，點擊右上角上傳第一個 Skill。
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
                isOwner={skill.owner_uid === userUid}
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
