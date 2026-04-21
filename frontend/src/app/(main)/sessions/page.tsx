"use client";

import React, { useCallback, useMemo } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { PageLoading } from "@/components/ui/Loading";
import { Pagination } from "@/components/ui/Pagination";
import { useAuth } from "@/hooks/useAuth";
import { useCursorPagination } from "@/hooks/useCursorPagination";
import { useConfirmMutation } from "@/hooks/useConfirmMutation";
import {
  useListOrphanChatSessionsQuery,
  useDeleteSessionMutation,
} from "@/store/chatApi";
import type { ChatSession } from "@/types";
import { formatDateTime } from "@/utils/datetime";

interface SessionRowProps {
  session: ChatSession;
  onDelete: (uid: string) => void;
}

const SessionRow = React.memo(function SessionRow({
  session,
  onDelete,
}: SessionRowProps): React.ReactNode {
  const handleDelete = useCallback((): void => {
    onDelete(session.chat_session_uid);
  }, [session.chat_session_uid, onDelete]);

  return (
    <div className="flex flex-col gap-3 px-4 py-4 transition-colors hover:bg-muted-bg/40 md:flex-row md:items-center md:gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={`/sessions/${session.chat_session_uid}`}
            className="min-w-0 hover:cursor-pointer"
          >
            <h3 className="truncate text-lg font-semibold text-foreground hover:text-primary">
              {session.title || "（未命名）"}
            </h3>
          </Link>
          <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
            {session.message_count} 則
          </span>
        </div>

        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
          {session.agent_name && <span>Agent：{session.agent_name}</span>}
          <span>
            最後訊息：
            {session.last_message_at
              ? formatDateTime(session.last_message_at)
              : "尚無"}
          </span>
          <span>建立於 {formatDateTime(session.created_at)}</span>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2 md:ml-auto">
        <Link href={`/sessions/${session.chat_session_uid}`}>
          <Button size="sm" variant="ghost">
            進入對話
          </Button>
        </Link>
        <Button size="sm" variant="destructive" onClick={handleDelete}>
          刪除
        </Button>
      </div>
    </div>
  );
});

export default function OrphanSessionsPage(): React.ReactNode {
  const { isLoading: authLoading } = useAuth();
  const {
    limit,
    cursor,
    hasPrev,
    handleNextPage,
    handlePrevPage,
    handleLimitChange,
  } = useCursorPagination(20);

  const { data, isLoading, isFetching } = useListOrphanChatSessionsQuery(
    { limit, cursor },
    { skip: authLoading },
  );

  const [deleteSession] = useDeleteSessionMutation();

  const sessions = useMemo((): ChatSession[] => data?.items ?? [], [data]);

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

  const handleNext = useCallback((): void => {
    handleNextPage(data?.next_cursor);
  }, [handleNextPage, data?.next_cursor]);

  if (authLoading) {
    return <PageLoading />;
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">最近對話</h1>
          <p className="mt-1 text-base text-muted">
            不屬於任何 Project 的游離對話；可在詳情頁把對話移入 Project。
          </p>
        </div>
        <Link href="/sessions/new">
          <Button>新對話</Button>
        </Link>
      </div>

      <div className="overflow-hidden rounded-xl bg-card-bg shadow-sm">
        {isLoading || isFetching ? (
          <PageLoading />
        ) : sessions.length === 0 ? (
          <div className="py-12 text-center text-muted">
            尚無游離對話，點擊右上角「新對話」開始。
          </div>
        ) : (
          <div className="divide-y divide-border">
            {sessions.map((session) => (
              <SessionRow
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
          hasNext={Boolean(data?.has_next)}
          hasPrev={hasPrev}
          limit={limit}
          onNextPage={handleNext}
          onPrevPage={handlePrevPage}
          onLimitChange={handleLimitChange}
        />
      </div>
    </div>
  );
}
