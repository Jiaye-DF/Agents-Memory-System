"use client";

import React, { useState, useCallback } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Pagination } from "@/components/ui/Pagination";
import { PageLoading } from "@/components/ui/Loading";
import { useDialog } from "@/hooks/useDialog";
import { useAuth } from "@/hooks/useAuth";
import {
  useListAgentsQuery,
  useDeleteAgentMutation,
  useToggleAgentVisibilityMutation,
} from "@/store/agentsApi";

interface AgentCardProps {
  agent: Agent;
  isOwner: boolean;
  onDelete: (agentUid: string) => void;
  onToggleVisibility: (agentUid: string, current: string) => void;
}

const AgentCard = React.memo(function AgentCard({
  agent,
  isOwner,
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
          <h3 className="truncate text-lg font-semibold text-foreground">
            {agent.name}
          </h3>
        </Link>
        <span
          className={`shrink-0 rounded-xl px-2 py-0.5 text-xs font-medium ${
            agent.visibility === "public"
              ? "bg-info-bg text-info"
              : "bg-muted-bg text-muted"
          }`}
        >
          {agent.visibility === "public" ? "公開" : "私人"}
        </span>
      </div>

      {agent.description && (
        <p className="line-clamp-2 text-sm text-muted">{agent.description}</p>
      )}

      {!agent.description && (
        <p className="text-sm text-muted italic">尚無描述</p>
      )}

      <div className="flex flex-wrap gap-2 text-xs text-muted">
        {agent.language && <span>語言：{agent.language}</span>}
        {agent.style && <span>風格：{agent.style}</span>}
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
            <Button variant="ghost" size="sm" onClick={handleToggle}>
              {agent.visibility === "public" ? "設為私人" : "設為公開"}
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDelete}
            >
              刪除
            </Button>
          </>
        )}
      </div>
    </div>
  );
});

export default function AgentsPage(): React.ReactNode {
  const { userUid } = useAuth();
  const { showDialog } = useDialog();

  const [limit, setLimit] = useState<number>(20);
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);

  const { data, isLoading, isFetching } = useListAgentsQuery({ limit, cursor });
  const [deleteAgent] = useDeleteAgentMutation();
  const [toggleVisibility] = useToggleAgentVisibilityMutation();

  const agents = data?.items ?? [];

  const handleDelete = useCallback(
    (agentUid: string): void => {
      showDialog({
        type: "warning",
        title: "刪除 Agent",
        message: "確定要刪除此 Agent 嗎？此操作無法復原。",
        onConfirm: async () => {
          try {
            await deleteAgent(agentUid).unwrap();
            showDialog({
              type: "info",
              title: "刪除成功",
              message: "Agent 已成功刪除。",
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
    [showDialog, deleteAgent]
  );

  const handleToggleVisibility = useCallback(
    (agentUid: string, current: string): void => {
      const newVisibility = current === "public" ? "private" : "public";
      const toggleAsync = async (): Promise<void> => {
        try {
          await toggleVisibility({
            agentUid,
            body: { visibility: newVisibility as "public" | "private" },
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

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-foreground">Agent 管理</h1>
        <Link href="/agents/new">
          <Button>新增 Agent</Button>
        </Link>
      </div>

      <div className="rounded-xl bg-card-bg p-6 shadow-sm">
        {isLoading || isFetching ? (
          <PageLoading />
        ) : (
          <>
            {agents.length === 0 ? (
              <div className="py-12 text-center text-muted">
                尚未建立任何 Agent，點擊右上角新增。
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                {agents.map((agent) => (
                  <AgentCard
                    key={agent.agent_uid}
                    agent={agent}
                    isOwner={agent.owner_uid === userUid}
                    onDelete={handleDelete}
                    onToggleVisibility={handleToggleVisibility}
                  />
                ))}
              </div>
            )}
            <div className="mt-4">
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
