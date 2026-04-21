"use client";

import React, { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { PageLoading } from "@/components/ui/Loading";
import { useAuth } from "@/hooks/useAuth";
import { useDialog } from "@/hooks/useDialog";
import { useCreateSessionMutation } from "@/store/chatApi";
import { useListAgentsQuery } from "@/store/agentsApi";

export default function NewOrphanSessionPage(): React.ReactNode {
  const router = useRouter();
  const { isLoading: authLoading } = useAuth();
  const { showDialog } = useDialog();

  const [agentUid, setAgentUid] = useState<string>("");
  const [title, setTitle] = useState<string>("");

  const { data: agentsData, isLoading: agentsLoading } = useListAgentsQuery(
    { limit: 100, cursor: null },
    { skip: authLoading },
  );
  const [createSession, { isLoading: creating }] = useCreateSessionMutation();

  const agents = useMemo(() => agentsData?.items ?? [], [agentsData]);

  const handleAgentChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>): void => {
      setAgentUid(e.target.value);
    },
    [],
  );

  const handleTitleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setTitle(e.target.value);
    },
    [],
  );

  const handleCancel = useCallback((): void => {
    router.back();
  }, [router]);

  const handleCreate = useCallback((): void => {
    if (!agentUid) return;
    void (async (): Promise<void> => {
      try {
        const result = await createSession({
          chat_project_uid: null,
          agent_uid: agentUid,
          title: title.trim() || null,
        }).unwrap();
        router.push(`/sessions/${result.chat_session_uid}`);
      } catch (err: unknown) {
        const message =
          typeof err === "string" ? err : "建立對話失敗，請稍後再試";
        showDialog({
          type: "error",
          title: "操作失敗",
          message,
        });
      }
    })();
  }, [agentUid, title, createSession, router, showDialog]);

  if (authLoading) {
    return <PageLoading />;
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-2 text-3xl font-bold text-foreground">新對話</h1>
      <p className="mb-6 text-base text-muted">
        建立一個不屬於任何 Project 的對話；若要分類可稍後再移入 Project。
      </p>

      <div className="flex flex-col gap-4 rounded-xl bg-card-bg p-6 shadow-sm">
        <div>
          <label
            htmlFor="session-agent"
            className="mb-1.5 block text-base font-medium text-foreground"
          >
            Agent<span className="ml-0.5 text-destructive">*</span>
          </label>
          <select
            id="session-agent"
            value={agentUid}
            onChange={handleAgentChange}
            disabled={agentsLoading}
            className="min-h-11 w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground transition-colors focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <option value="">請選擇 Agent</option>
            {agents.map((agent) => (
              <option key={agent.agent_uid} value={agent.agent_uid}>
                {agent.name}
                {agent.owner_username ? ` (@${agent.owner_username})` : ""}
              </option>
            ))}
          </select>
        </div>

        <Input
          label="標題（選填）"
          placeholder="未填則由首則訊息自動帶入"
          value={title}
          onChange={handleTitleChange}
        />

        <div className="flex items-center justify-end gap-2 border-t border-border pt-4">
          <Button variant="secondary" onClick={handleCancel}>
            取消
          </Button>
          <Button onClick={handleCreate} loading={creating} disabled={!agentUid}>
            建立並開始對話
          </Button>
        </div>
      </div>
    </div>
  );
}
