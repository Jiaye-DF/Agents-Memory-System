"use client";

import React, { useState, useCallback, useMemo } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Pagination } from "@/components/ui/Pagination";
import { PageLoading, CardSkeleton } from "@/components/ui/Loading";
import { useDialog } from "@/hooks/useDialog";
import { useAuth } from "@/hooks/useAuth";
import {
  useListSkillsQuery,
  useDeleteSkillMutation,
  useToggleVisibilityMutation,
} from "@/store/skillsApi";
import type { Skill } from "@/types";

type TabType = "mine" | "public";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

interface SkillCardProps {
  skill: Skill;
  isOwner: boolean;
  onDelete: (skillUid: string) => void;
  onToggleVisibility: (skillUid: string, current: string) => void;
}

const SkillCard = React.memo(function SkillCard({
  skill,
  isOwner,
  onDelete,
  onToggleVisibility,
}: SkillCardProps): React.ReactNode {
  const handleDelete = useCallback((): void => {
    onDelete(skill.skill_uid);
  }, [skill.skill_uid, onDelete]);

  const handleToggle = useCallback((): void => {
    onToggleVisibility(skill.skill_uid, skill.visibility);
  }, [skill.skill_uid, skill.visibility, onToggleVisibility]);

  return (
    <div className="flex flex-col gap-3 rounded-xl bg-card-bg p-5 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between gap-2">
        <Link
          href={`/skills/${skill.skill_uid}`}
          className="min-w-0 flex-1 hover:cursor-pointer"
        >
          <h3 className="truncate text-lg font-semibold text-foreground hover:text-primary">
            {skill.name}
          </h3>
        </Link>
        <span
          className={`shrink-0 rounded-xl px-2 py-0.5 text-xs font-medium ${
            skill.visibility === "public"
              ? "bg-success/10 text-success"
              : "bg-muted-bg text-muted"
          }`}
        >
          {skill.visibility === "public" ? "公開" : "私人"}
        </span>
      </div>

      <p className="line-clamp-2 text-sm text-muted">{skill.description}</p>

      <div className="flex items-center gap-3 text-xs text-muted">
        <span>{formatFileSize(skill.file_size)}</span>
        <span>{skill.original_filename}</span>
      </div>

      {isOwner && (
        <div className="flex items-center gap-2 border-t border-border pt-3">
          <Button size="sm" variant="ghost" onClick={handleToggle}>
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

export default function SkillsListPage(): React.ReactNode {
  const { userUid, isLoading: authLoading } = useAuth();
  const { showDialog } = useDialog();

  const [activeTab, setActiveTab] = useState<TabType>("mine");
  const [limit, setLimit] = useState<number>(20);
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);

  const { data, isLoading, isFetching } = useListSkillsQuery(
    { limit, cursor },
    { skip: authLoading }
  );

  const [deleteSkill] = useDeleteSkillMutation();
  const [toggleVisibility] = useToggleVisibilityMutation();

  const filteredSkills = useMemo((): Skill[] => {
    if (!data?.items) return [];
    if (activeTab === "mine") {
      return data.items.filter((s) => s.owner_uid === userUid);
    }
    return data.items.filter((s) => s.visibility === "public");
  }, [data?.items, activeTab, userUid]);

  const handleDelete = useCallback(
    (skillUid: string): void => {
      showDialog({
        type: "warning",
        title: "刪除 Skill",
        message: "確定要刪除此 Skill 嗎？此操作無法復原。",
        onConfirm: async () => {
          try {
            await deleteSkill(skillUid).unwrap();
            showDialog({
              type: "info",
              title: "刪除成功",
              message: "Skill 已成功刪除。",
            });
          } catch (err: unknown) {
            const message =
              typeof err === "string" ? err : "刪除失敗，請稍後再試";
            showDialog({
              type: "error",
              title: "操作失敗",
              message,
            });
          }
        },
        onCancel: () => {},
      });
    },
    [showDialog, deleteSkill]
  );

  const handleToggleVisibility = useCallback(
    (skillUid: string, current: string): void => {
      const newVisibility = current === "public" ? "private" : "public";
      const toggleAsync = async (): Promise<void> => {
        try {
          await toggleVisibility({
            skillUid,
            body: { visibility: newVisibility },
          }).unwrap();
        } catch (err: unknown) {
          const message =
            typeof err === "string" ? err : "切換可見性失敗，請稍後再試";
          showDialog({
            type: "error",
            title: "操作失敗",
            message,
          });
        }
      };
      void toggleAsync();
    },
    [showDialog, toggleVisibility]
  );

  const handleTabChange = useCallback(
    (tab: TabType): void => {
      setActiveTab(tab);
    },
    []
  );

  const handleNextPage = useCallback((): void => {
    if (data?.next_cursor) {
      setCursorHistory((prev) => [...prev, cursor ?? ""]);
      setCursor(data.next_cursor);
    }
  }, [data?.next_cursor, cursor]);

  const handlePrevPage = useCallback((): void => {
    setCursorHistory((prev) => {
      const newHistory = [...prev];
      const prevCursor = newHistory.pop();
      setCursor(prevCursor || null);
      return newHistory;
    });
  }, []);

  const handleLimitChange = useCallback((newLimit: number): void => {
    setLimit(newLimit);
    setCursor(null);
    setCursorHistory([]);
  }, []);

  if (authLoading) {
    return <PageLoading />;
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-foreground">Skills 管理</h1>
        <Link href="/skills/upload">
          <Button>上傳 Skill</Button>
        </Link>
      </div>

      <div className="rounded-xl bg-card-bg p-6 shadow-sm">
        <div className="mb-4 flex gap-2">
          <button
            type="button"
            onClick={() => handleTabChange("mine")}
            className={`min-h-[44px] rounded-xl px-4 py-2 text-sm font-medium transition-colors hover:cursor-pointer ${
              activeTab === "mine"
                ? "bg-primary text-white"
                : "bg-muted-bg text-foreground hover:bg-border"
            }`}
          >
            我的 Skills
          </button>
          <button
            type="button"
            onClick={() => handleTabChange("public")}
            className={`min-h-[44px] rounded-xl px-4 py-2 text-sm font-medium transition-colors hover:cursor-pointer ${
              activeTab === "public"
                ? "bg-primary text-white"
                : "bg-muted-bg text-foreground hover:bg-border"
            }`}
          >
            公開 Skills
          </button>
        </div>

        {isLoading || isFetching ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        ) : filteredSkills.length === 0 ? (
          <div className="py-12 text-center text-muted">
            {activeTab === "mine"
              ? "尚無 Skills，點擊右上角上傳第一個 Skill。"
              : "目前沒有公開的 Skills。"}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {filteredSkills.map((skill) => (
                <SkillCard
                  key={skill.skill_uid}
                  skill={skill}
                  isOwner={skill.owner_uid === userUid}
                  onDelete={handleDelete}
                  onToggleVisibility={handleToggleVisibility}
                />
              ))}
            </div>
            <div className="mt-6">
              <Pagination
                hasNext={data?.has_next ?? false}
                hasPrev={cursorHistory.length > 0}
                limit={limit}
                onNextPage={handleNextPage}
                onPrevPage={handlePrevPage}
                onLimitChange={handleLimitChange}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
