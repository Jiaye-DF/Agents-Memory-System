"use client";

import React, { useCallback, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { useDialog } from "@/hooks/useDialog";
import { useMutationWithDialog } from "@/hooks/useMutationWithDialog";
import { useListAgentsQuery } from "@/store/agentsApi";
import {
  useAddSessionAgentMutation,
  usePromoteSessionAgentMutation,
  useRemoveSessionAgentMutation,
} from "@/store/chatApi";
import type { SessionAgent } from "@/types";

const MAX_AGENTS_PER_SESSION = 5;

interface SessionAgentBarProps {
  sessionUid: string;
  agents: SessionAgent[];
}

/**
 * v1.3.3 多 Agent 顯示與操作列：
 * - badge 列出 primary / member（primary 標星號）
 * - 每個 badge 可移除（X）、設為 primary（☆）
 * - 「+ 新增 Agent」開 Modal 從可見 Agents 選擇；達 5 個 disable
 */
export function SessionAgentBar({
  sessionUid,
  agents,
}: SessionAgentBarProps): React.ReactNode {
  const [adderOpen, setAdderOpen] = useState<boolean>(false);
  const reachedLimit = agents.length >= MAX_AGENTS_PER_SESSION;

  const { showDialog } = useDialog();

  const [removeAgent, { isLoading: removing }] = useRemoveSessionAgentMutation();
  const runRemove = useMutationWithDialog(removeAgent);
  const [promoteAgent, { isLoading: promoting }] =
    usePromoteSessionAgentMutation();
  const runPromote = useMutationWithDialog(promoteAgent);

  const handleRemove = useCallback(
    (agent: SessionAgent): void => {
      if (agents.length <= 1) {
        showDialog({
          type: "warning",
          title: "無法移除",
          message: "Session 至少需保留一個 Agent。",
        });
        return;
      }
      showDialog({
        type: "warning",
        title: "移除 Agent",
        message: `確定要從此 Session 移除「${agent.agent_name ?? "Agent"}」嗎？`,
        onConfirm: () => {
          void runRemove(
            { sessionUid, agentUid: agent.agent_uid },
            {
              successTitle: "已移除",
              errorMessage: "移除失敗，請稍後再試",
            },
          );
        },
      });
    },
    [agents.length, runRemove, sessionUid, showDialog],
  );

  const handlePromote = useCallback(
    (agent: SessionAgent): void => {
      if (agent.role === "primary") return;
      void runPromote(
        { sessionUid, agentUid: agent.agent_uid },
        {
          successTitle: "已切換 primary",
          errorMessage: "切換 primary 失敗，請稍後再試",
        },
      );
    },
    [runPromote, sessionUid],
  );

  return (
    <div className="flex flex-wrap items-center gap-2">
      {agents.map((a) => (
        <AgentBadge
          key={a.session_agent_uid}
          agent={a}
          disabled={removing || promoting}
          onRemove={handleRemove}
          onPromote={handlePromote}
        />
      ))}
      <Button
        variant="secondary"
        onClick={() => setAdderOpen(true)}
        disabled={reachedLimit}
        title={
          reachedLimit
            ? `每個 Session 最多 ${MAX_AGENTS_PER_SESSION} 個 Agent`
            : "從可見 Agents 中加入"
        }
      >
        + 新增 Agent
        {reachedLimit && (
          <span className="ml-1 text-xs text-muted">
            （已達 {MAX_AGENTS_PER_SESSION}）
          </span>
        )}
      </Button>

      {adderOpen && (
        <AddAgentModal
          sessionUid={sessionUid}
          existingAgentUids={agents.map((a) => a.agent_uid)}
          onClose={() => setAdderOpen(false)}
        />
      )}
    </div>
  );
}

interface AgentBadgeProps {
  agent: SessionAgent;
  disabled: boolean;
  onRemove: (agent: SessionAgent) => void;
  onPromote: (agent: SessionAgent) => void;
}

function AgentBadge({
  agent,
  disabled,
  onRemove,
  onPromote,
}: AgentBadgeProps): React.ReactNode {
  const isPrimary = agent.role === "primary";
  return (
    <div
      className={`group flex items-center gap-1 rounded-full border px-2 py-1 text-sm transition-colors ${
        isPrimary
          ? "border-primary/40 bg-primary/10 text-primary"
          : "border-border bg-muted-bg text-foreground"
      }`}
      title={
        isPrimary
          ? "primary：未指定 mention 時由此 Agent 回覆"
          : "member：可被 @mention 指定回覆"
      }
    >
      <span className="truncate max-w-[160px]">
        {agent.agent_name ?? "Agent"}
      </span>
      {isPrimary && (
        <span aria-hidden="true" className="text-xs">
          ★
        </span>
      )}
      {!isPrimary && (
        <button
          type="button"
          onClick={() => onPromote(agent)}
          disabled={disabled}
          aria-label={`將 ${agent.agent_name ?? "Agent"} 設為 primary`}
          title="設為 primary"
          className="ml-1 hover:cursor-pointer text-muted hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
        >
          ☆
        </button>
      )}
      <button
        type="button"
        onClick={() => onRemove(agent)}
        disabled={disabled}
        aria-label={`從 Session 移除 ${agent.agent_name ?? "Agent"}`}
        title="移除"
        className="ml-1 hover:cursor-pointer text-muted hover:text-destructive disabled:cursor-not-allowed disabled:opacity-50"
      >
        ✕
      </button>
    </div>
  );
}

interface AddAgentModalProps {
  sessionUid: string;
  existingAgentUids: string[];
  onClose: () => void;
}

function AddAgentModal({
  sessionUid,
  existingAgentUids,
  onClose,
}: AddAgentModalProps): React.ReactNode {
  const { data: agentsPage, isLoading } = useListAgentsQuery({
    limit: 50,
    cursor: null,
  });
  const [selected, setSelected] = useState<string>("");

  const candidates = useMemo(() => {
    const items = agentsPage?.items ?? [];
    const existSet = new Set(existingAgentUids);
    return items.filter((a) => !existSet.has(a.agent_uid));
  }, [agentsPage, existingAgentUids]);

  const [addAgent, { isLoading: adding }] = useAddSessionAgentMutation();
  const runAdd = useMutationWithDialog(addAgent);

  const handleSubmit = useCallback((): void => {
    if (!selected) return;
    void runAdd(
      { sessionUid, agentUid: selected },
      {
        successTitle: "已加入",
        errorMessage: "加入失敗，請稍後再試",
        onSuccess: onClose,
      },
    );
  }, [selected, runAdd, sessionUid, onClose]);

  return (
    <ModalDialog title="新增 Agent 至 Session" onClose={onClose} size="md">
      <div className="flex flex-col gap-4">
        <p className="text-sm text-muted">
          從你可見的 Agents 中挑選一個加入此 Session（最多 5 個）。
        </p>
        <div>
          <label
            htmlFor="add-agent-select"
            className="mb-1.5 block text-base font-medium text-foreground"
          >
            Agent
          </label>
          <select
            id="add-agent-select"
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            disabled={isLoading || adding}
            className="min-h-11 w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground transition-colors focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <option value="">請選擇 Agent</option>
            {candidates.map((a) => (
              <option key={a.agent_uid} value={a.agent_uid}>
                {a.name}
                {a.visibility === "public" ? "（公開）" : ""}
              </option>
            ))}
          </select>
          {!isLoading && candidates.length === 0 && (
            <p className="mt-1 text-sm text-muted">
              你目前沒有可加入的 Agent，先到 /agents 建立或收藏一個。
            </p>
          )}
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-border pt-4">
          <Button variant="secondary" onClick={onClose}>
            取消
          </Button>
          <Button
            onClick={handleSubmit}
            loading={adding}
            disabled={!selected}
          >
            加入
          </Button>
        </div>
      </div>
    </ModalDialog>
  );
}
