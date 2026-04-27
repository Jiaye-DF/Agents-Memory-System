"use client";

import React, { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { PageLoading } from "@/components/ui/Loading";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { Pagination } from "@/components/ui/Pagination";
import { PendingApprovalCard } from "@/components/ui/PendingApprovalCard";
import { useAuth } from "@/hooks/useAuth";
import { useCursorPagination } from "@/hooks/useCursorPagination";
import { useMutationWithDialog } from "@/hooks/useMutationWithDialog";
import { useConfirmMutation } from "@/hooks/useConfirmMutation";
import { usePendingApprovalDialog } from "@/hooks/usePendingApprovalDialog";

/**
 * df 公司版本 feature flag：對話領域整段隱藏。
 * `false` 時整頁渲染 PendingApprovalCard；下方 CreateProjectModal / 列表 / 分頁邏輯保留供日後解鎖。
 */
const CHAT_DOMAIN_ENABLED: boolean = false;
import {
  useListProjectsQuery,
  useCreateProjectMutation,
  useDeleteProjectMutation,
} from "@/store/chatApi";
import type { ChatProject } from "@/types";
import { formatDateTime } from "@/utils/datetime";

interface ProjectCardProps {
  project: ChatProject;
  onDelete: (uid: string) => void;
}

const ProjectCard = React.memo(function ProjectCard({
  project,
  onDelete,
}: ProjectCardProps): React.ReactNode {
  const handleDelete = useCallback((): void => {
    onDelete(project.chat_project_uid);
  }, [project.chat_project_uid, onDelete]);

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-card-bg p-4 shadow-sm transition-colors hover:shadow-md">
      <div className="flex items-start justify-between gap-2">
        <Link
          href={`/projects/${project.chat_project_uid}`}
          className="min-w-0 flex-1 hover:cursor-pointer"
        >
          <h3 className="truncate text-xl font-semibold text-foreground hover:text-primary">
            {project.name}
          </h3>
        </Link>
        <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
          {project.session_count} 則對話
        </span>
      </div>

      {project.description ? (
        <p className="line-clamp-2 text-base text-muted">
          {project.description}
        </p>
      ) : (
        <p className="text-base text-muted italic">尚無描述</p>
      )}

      <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm text-muted">
        <span>建立於 {formatDateTime(project.created_at)}</span>
      </div>

      <div className="mt-auto flex items-center gap-2 border-t border-border pt-3">
        <Link href={`/projects/${project.chat_project_uid}`}>
          <Button variant="ghost" size="sm">
            進入
          </Button>
        </Link>
        <Button variant="destructive" size="sm" onClick={handleDelete}>
          刪除
        </Button>
      </div>
    </div>
  );
});

interface CreateProjectModalProps {
  onClose: () => void;
}

function CreateProjectModal({
  onClose,
}: CreateProjectModalProps): React.ReactNode {
  const [name, setName] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [createProject, { isLoading }] = useCreateProjectMutation();
  const runCreate = useMutationWithDialog(createProject);

  const handleNameChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setName(e.target.value);
    },
    [],
  );

  const handleDescChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>): void => {
      setDescription(e.target.value);
    },
    [],
  );

  const handleSubmit = useCallback((): void => {
    const trimmed = name.trim();
    if (!trimmed) return;
    void runCreate(
      {
        name: trimmed,
        description: description.trim() || null,
      },
      {
        errorMessage: "建立專案失敗，請稍後再試",
        onSuccess: onClose,
      },
    );
  }, [name, description, runCreate, onClose]);

  return (
    <ModalDialog title="新增專案" onClose={onClose} size="md">
      <div className="flex flex-col gap-4">
        <Input
          label="名稱"
          required
          placeholder="例如：客服對話"
          value={name}
          onChange={handleNameChange}
        />
        <div>
          <label
            htmlFor="project-description"
            className="mb-1.5 block text-base font-medium text-foreground"
          >
            描述
          </label>
          <textarea
            id="project-description"
            placeholder="選填"
            value={description}
            onChange={handleDescChange}
            rows={3}
            className="min-h-20 w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
          />
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border pt-4">
          <Button variant="secondary" onClick={onClose}>
            取消
          </Button>
          <Button
            onClick={handleSubmit}
            loading={isLoading}
            disabled={!name.trim()}
          >
            建立
          </Button>
        </div>
      </div>
    </ModalDialog>
  );
}

export default function ProjectsPage(): React.ReactNode {
  if (!CHAT_DOMAIN_ENABLED) {
    return <PendingApprovalCard title="專案管理" />;
  }
  const { isLoading: authLoading } = useAuth();
  // df 公司版本：新增專案功能未開通；點選按鈕只跳 pending dialog，
  // 不開啟下方 CreateProjectModal（modal 程式碼保留以利日後解鎖）。
  const showPendingApproval = usePendingApprovalDialog();
  const {
    limit,
    cursor,
    hasPrev,
    handleNextPage,
    handlePrevPage,
    handleLimitChange,
  } = useCursorPagination(20);

  const [showCreate, setShowCreate] = useState<boolean>(false);

  const { data, isLoading, isFetching } = useListProjectsQuery(
    { limit, cursor },
    { skip: authLoading },
  );

  const [deleteProject] = useDeleteProjectMutation();

  const projects = useMemo((): ChatProject[] => data?.items ?? [], [data]);

  const deleteOptions = useMemo(
    () => ({
      title: "刪除專案",
      message: "確定要刪除此專案嗎？其下所有對話也會一併停用。",
      successTitle: "刪除成功",
      successMessage: "專案已成功刪除。",
      errorMessage: "刪除失敗，請稍後再試",
    }),
    [],
  );
  const confirmDeleteProject = useConfirmMutation(deleteProject, deleteOptions);

  const handleDelete = useCallback(
    (projectUid: string): void => {
      confirmDeleteProject(projectUid);
    },
    [confirmDeleteProject],
  );

  // df 公司版本：原 handleOpenCreate（setShowCreate(true)）改為 pending dialog；
  // 保留 setShowCreate 以兼容下方 modal 渲染（永遠不會觸發）。
  void setShowCreate;
  const handleOpenCreate = showPendingApproval;

  const handleCloseCreate = useCallback((): void => {
    setShowCreate(false);
  }, []);

  const handleNext = useCallback((): void => {
    handleNextPage(data?.next_cursor);
  }, [handleNextPage, data?.next_cursor]);

  if (authLoading) {
    return <PageLoading />;
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-3xl font-bold text-foreground">專案管理</h1>
        <Button onClick={handleOpenCreate}>新增專案</Button>
      </div>

      <div className="rounded-xl bg-card-bg p-6 shadow-sm">
        {isLoading || isFetching ? (
          <PageLoading />
        ) : projects.length === 0 ? (
          <div className="py-12 text-center text-muted">
            尚未建立任何專案，點擊右上角新增。
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <ProjectCard
                key={project.chat_project_uid}
                project={project}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </div>

      <div className="mt-4">
        <Pagination
          hasNext={Boolean(data?.has_next)}
          hasPrev={hasPrev}
          limit={limit}
          onNextPage={handleNext}
          onPrevPage={handlePrevPage}
          onLimitChange={handleLimitChange}
        />
      </div>

      {showCreate && <CreateProjectModal onClose={handleCloseCreate} />}
    </div>
  );
}
