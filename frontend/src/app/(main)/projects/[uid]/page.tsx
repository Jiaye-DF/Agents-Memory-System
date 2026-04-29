"use client";

import React, { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { AgentSelect } from "@/components/ui/AgentSelect";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { PageLoading } from "@/components/ui/Loading";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { Pagination } from "@/components/ui/Pagination";
import { useAuth } from "@/hooks/useAuth";
import { useCursorPagination } from "@/hooks/useCursorPagination";
import { useDialog } from "@/hooks/useDialog";
import { useConfirmMutation } from "@/hooks/useConfirmMutation";
import {
  useGetProjectQuery,
  useListSessionsQuery,
  useCreateSessionMutation,
  useDeleteSessionMutation,
} from "@/store/chatApi";
import { useListAgentsQuery } from "@/store/agentsApi";
import type { ChatSession } from "@/types";
import { formatDateTime } from "@/utils/datetime";

interface SessionCardProps {
  session: ChatSession;
  onDelete: (uid: string) => void;
}

const SessionCard = React.memo(function SessionCard({
  session,
  onDelete,
}: SessionCardProps): React.ReactNode {
  const handleDelete = useCallback((): void => {
    onDelete(session.chat_session_uid);
  }, [session.chat_session_uid, onDelete]);

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-card-bg p-4 shadow-sm transition-colors hover:shadow-md">
      <div className="flex items-start justify-between gap-2">
        <Link
          href={`/sessions/${session.chat_session_uid}`}
          className="min-w-0 flex-1 hover:cursor-pointer"
        >
          <h3 className="truncate text-lg font-semibold text-foreground hover:text-primary">
            {session.title || "（未命名）"}
          </h3>
        </Link>
        <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
          {session.message_count} 則訊息
        </span>
      </div>

      <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm text-muted">
        {session.agent_name && <span>Agent：{session.agent_name}</span>}
        <span>
          最後訊息：
          {session.last_message_at
            ? formatDateTime(session.last_message_at)
            : "尚無"}
        </span>
        <span>建立於 {formatDateTime(session.created_at)}</span>
      </div>

      <div className="mt-auto flex items-center gap-2 border-t border-border pt-3">
        <Link href={`/sessions/${session.chat_session_uid}`}>
          <Button variant="ghost" size="sm">
            進入對話
          </Button>
        </Link>
        <Button variant="destructive" size="sm" onClick={handleDelete}>
          刪除
        </Button>
      </div>
    </div>
  );
});

interface CreateSessionModalProps {
  projectUid: string;
  onClose: () => void;
  onCreated: (sessionUid: string) => void;
}

function CreateSessionModal({
  projectUid,
  onClose,
  onCreated,
}: CreateSessionModalProps): React.ReactNode {
  const [agentUid, setAgentUid] = useState<string>("");
  const [title, setTitle] = useState<string>("");

  const { userUid } = useAuth();
  const { data: agentsData, isLoading: agentsLoading } = useListAgentsQuery({
    limit: 50,
    cursor: null,
  });

  const [createSession, { isLoading }] = useCreateSessionMutation();
  const { showDialog } = useDialog();

  const agents = useMemo(() => agentsData?.items ?? [], [agentsData]);

  const handleAgentChange = useCallback((next: string): void => {
    setAgentUid(next);
  }, []);

  const handleTitleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setTitle(e.target.value);
    },
    [],
  );

  const handleSubmit = useCallback((): void => {
    if (!agentUid) return;
    void (async (): Promise<void> => {
      try {
        const result = await createSession({
          chat_project_uid: projectUid,
          agent_uid: agentUid,
          title: title.trim() || null,
        }).unwrap();
        onCreated(result.chat_session_uid);
      } catch (err: unknown) {
        const message = typeof err === "string" ? err : "建立對話失敗，請稍後再試";
        showDialog({
          type: "error",
          title: "操作失敗",
          message,
        });
      }
    })();
  }, [agentUid, title, projectUid, createSession, onCreated, showDialog]);

  return (
    <ModalDialog title="新增對話" onClose={onClose} size="md">
      <div className="flex flex-col gap-4">
        <div>
          <label
            htmlFor="session-agent"
            className="mb-1.5 block text-base font-medium text-foreground"
          >
            Agent<span className="ml-0.5 text-destructive">*</span>
          </label>
          <AgentSelect
            agents={agents}
            value={agentUid}
            onChange={handleAgentChange}
            userUid={userUid ?? null}
            disabled={agentsLoading}
          />
          {!agentsLoading && agents.length === 0 && (
            <p className="mt-1 text-sm text-muted">
              尚無可用的 Agent，請先到「Agent 管理」建立或啟用公開。
            </p>
          )}
        </div>

        <Input
          label="對話標題（選填）"
          placeholder="未填則由首則訊息自動帶入"
          value={title}
          onChange={handleTitleChange}
        />

        <div className="flex items-center justify-end gap-2 border-t border-border pt-4">
          <Button variant="secondary" onClick={onClose}>
            取消
          </Button>
          <Button
            onClick={handleSubmit}
            loading={isLoading}
            disabled={!agentUid}
          >
            建立
          </Button>
        </div>
      </div>
    </ModalDialog>
  );
}

export default function ProjectDetailPage(): React.ReactNode {
  const params = useParams();
  const router = useRouter();
  const projectUid = params.uid as string;
  const { isLoading: authLoading } = useAuth();

  const {
    limit,
    cursor,
    hasPrev,
    handleNextPage,
    handlePrevPage,
    handleLimitChange,
  } = useCursorPagination(20);

  const [showCreate, setShowCreate] = useState<boolean>(false);

  const {
    data: project,
    isLoading: projectLoading,
    error: projectError,
  } = useGetProjectQuery(projectUid, { skip: authLoading });

  const { data: sessionsData, isLoading: sessionsLoading } =
    useListSessionsQuery(
      { projectUid, limit, cursor },
      { skip: authLoading || !project },
    );

  const [deleteSession] = useDeleteSessionMutation();

  const sessions = useMemo(
    (): ChatSession[] => sessionsData?.items ?? [],
    [sessionsData],
  );

  const deleteOptions = useMemo(
    () => ({
      title: "刪除對話",
      message: "確定要刪除此對話嗎？訊息歷史會保留但不可再進入。",
      successTitle: "刪除成功",
      successMessage: "對話已成功刪除。",
      errorMessage: "刪除失敗，請稍後再試",
    }),
    [],
  );
  const confirmDeleteSession = useConfirmMutation(deleteSession, deleteOptions);

  const handleDelete = useCallback(
    (uid: string): void => {
      confirmDeleteSession(uid);
    },
    [confirmDeleteSession],
  );

  const handleOpenCreate = useCallback((): void => {
    setShowCreate(true);
  }, []);

  const handleCloseCreate = useCallback((): void => {
    setShowCreate(false);
  }, []);

  const handleCreated = useCallback(
    (sessionUid: string): void => {
      setShowCreate(false);
      router.push(`/sessions/${sessionUid}`);
    },
    [router],
  );

  const handleBack = useCallback((): void => {
    router.push("/projects");
  }, [router]);

  const handleNext = useCallback((): void => {
    handleNextPage(sessionsData?.next_cursor);
  }, [handleNextPage, sessionsData?.next_cursor]);

  if (authLoading || projectLoading) {
    return <PageLoading />;
  }

  if (projectError || !project) {
    return (
      <div>
        <h1 className="mb-4 text-3xl font-bold text-foreground">專案詳情</h1>
        <div className="rounded-xl bg-card-bg p-6 text-center shadow-sm">
          <p className="text-muted">找不到指定的專案。</p>
          <Button className="mt-4" variant="secondary" onClick={handleBack}>
            返回列表
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div className="min-w-0">
          <h1 className="truncate text-3xl font-bold text-foreground">
            {project.name}
          </h1>
          {project.description && (
            <p className="mt-1 text-base text-muted">{project.description}</p>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="secondary" onClick={handleBack}>
            返回列表
          </Button>
          <Button onClick={handleOpenCreate}>新增對話</Button>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted">
        <span>對話總數：{project.session_count}</span>
        <span>建立於 {formatDateTime(project.created_at)}</span>
        <span>更新於 {formatDateTime(project.updated_at)}</span>
      </div>

      <div className="rounded-xl bg-card-bg p-6 shadow-sm">
        {sessionsLoading ? (
          <PageLoading />
        ) : sessions.length === 0 ? (
          <div className="py-12 text-center text-muted">
            尚未建立任何對話，點擊右上角新增。
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {sessions.map((session) => (
              <SessionCard
                key={session.chat_session_uid}
                session={session}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </div>

      <div className="mt-4">
        <Pagination
          hasNext={Boolean(sessionsData?.has_next)}
          hasPrev={hasPrev}
          limit={limit}
          onNextPage={handleNext}
          onPrevPage={handlePrevPage}
          onLimitChange={handleLimitChange}
        />
      </div>

      {showCreate && (
        <CreateSessionModal
          projectUid={projectUid}
          onClose={handleCloseCreate}
          onCreated={handleCreated}
        />
      )}
    </div>
  );
}
