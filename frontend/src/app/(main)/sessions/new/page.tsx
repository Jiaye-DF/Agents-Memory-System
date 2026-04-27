"use client";

import React, { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AgentSelect } from "@/components/ui/AgentSelect";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { PageLoading } from "@/components/ui/Loading";
import { PendingApprovalCard } from "@/components/ui/PendingApprovalCard";
import { useAuth } from "@/hooks/useAuth";
import { useDialog } from "@/hooks/useDialog";
import { useCreateSessionMutation } from "@/store/chatApi";
import { useListAgentsQuery } from "@/store/agentsApi";

/**
 * df 公司版本 feature flag：對話領域整段隱藏。
 * `false` 時整頁渲染 PendingApprovalCard；下方建立對話表單保留供日後解鎖。
 */
const CHAT_DOMAIN_ENABLED: boolean = false;

export default function NewOrphanSessionPage(): React.ReactNode {
  if (!CHAT_DOMAIN_ENABLED) {
    return (
      <PendingApprovalCard
        title="新對話"
        description="建立一個不屬於任何專案的獨立對話。"
      />
    );
  }
  const router = useRouter();
  const { isLoading: authLoading, userUid } = useAuth();
  const { showDialog } = useDialog();

  const [agentUid, setAgentUid] = useState<string>("");
  const [title, setTitle] = useState<string>("");

  const { data: agentsData, isLoading: agentsLoading } = useListAgentsQuery(
    { limit: 50, cursor: null },
    { skip: authLoading },
  );
  const [createSession, { isLoading: creating }] = useCreateSessionMutation();

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
        建立一個不屬於任何專案的獨立對話；若要分類可稍後再移入專案。
      </p>

      <div className="flex flex-col gap-4 rounded-xl bg-card-bg p-6 shadow-sm">
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
            userUid={userUid}
            disabled={agentsLoading}
          />
          {!agentsLoading && agents.length === 0 && (
            <p className="mt-1 text-sm text-muted">
              尚無可用的 Agent，請先到「Agent 管理」建立或啟用公開。
            </p>
          )}
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
