"use client";

/**
 * v1.3.6 Agentic Skill 建議列表頁。
 *
 * - 上方頁籤：待處理 / 已接受 / 已拒絕 / 已過期（依 status）
 * - 上方 chip：全部 / Session / Project / User（依 scope；單選平鋪）
 * - 卡片：name / description / confidence 徽章 / scope 徽章 / 來源記憶展開 / 接受 / 拒絕
 * - 「接受並掛到 Agent」展開可見 agents（useListAgentsQuery），單選後 accept
 * - 不顯示任何 uid（含 suggestion uid 與 source memory uid）
 */

import React, { useCallback, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { FilterChip } from "@/components/ui/FilterChip";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { PageLoading } from "@/components/ui/Loading";
import { useDialog } from "@/hooks/useDialog";
import { useMutationWithDialog } from "@/hooks/useMutationWithDialog";
import { useListAgentsQuery } from "@/store/agentsApi";
import {
  useAcceptSkillSuggestionMutation,
  useGetSkillSuggestionQuery,
  useListSkillSuggestionsQuery,
  useRejectSkillSuggestionMutation,
} from "@/store/agenticApi";
import type {
  AgenticSkillSuggestionItem,
  AgenticSuggestionScope,
  AgenticSuggestionStatus,
  Agent,
} from "@/types";
import { formatDateTime } from "@/utils/datetime";

type ScopeFilter = "all" | AgenticSuggestionScope;
type StatusFilter = AgenticSuggestionStatus;

const STATUS_TABS: { key: StatusFilter; label: string }[] = [
  { key: "pending", label: "待處理" },
  { key: "approved", label: "已接受" },
  { key: "rejected", label: "已拒絕" },
  { key: "expired", label: "已過期" },
];

const SCOPE_CHIPS: { key: ScopeFilter; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "session", label: "Session" },
  { key: "project", label: "Project" },
  { key: "user", label: "User" },
];

export default function SkillSuggestionsPage(): React.ReactNode {
  // df 公司版本：Skill 建議功能未開通，整頁改顯示「尚待審核」說明卡。
  // 原 Suggestion 列表 / 接受 / 拒絕等流程程式碼保留於本檔以利日後解鎖。
  return (
    <div>
      <div className="mb-4">
        <h1 className="text-3xl font-bold text-foreground">Skill 建議</h1>
        <p className="mt-1 text-sm text-muted">
          系統會在你跨 session / project / 跨主題形成穩定使用習慣後自動產出
          Skill 建議； 人工審核通過才會建立 Skill。
        </p>
      </div>
      <div className="rounded-xl bg-card-bg p-12 text-center shadow-sm">
        <h2 className="mb-2 text-lg font-semibold text-foreground">
          功能尚待審核
        </h2>
        <p className="text-base text-muted">
          此功能尚待審核，暫無 API Token 餘額。
        </p>
      </div>
    </div>
  );
}

// df 公司版本：以下為原始 Suggestion 列表 / 接受 / 拒絕流程，保留供日後解鎖。
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function _SkillSuggestionsPage_KEPT(): React.ReactNode {
  const [statusTab, setStatusTab] = useState<StatusFilter>("pending");
  const [scopeChip, setScopeChip] = useState<ScopeFilter>("all");

  // 各狀態頁籤計數（page=1, size=1 + total）
  const counts = useTabCounts();

  const { data, isLoading, isFetching } = useListSkillSuggestionsQuery({
    status: statusTab,
    scope: scopeChip === "all" ? undefined : scopeChip,
    page: 1,
    size: 50,
  });

  const items = data?.items ?? [];

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-3xl font-bold text-foreground">Skill 建議</h1>
        <p className="mt-1 text-sm text-muted">
          系統會在你跨 session / project / 跨主題形成穩定使用習慣後自動產出
          Skill 建議； 人工審核通過才會建立 Skill。
        </p>
      </div>

      {/* 狀態切換（FilterNav 風格 segmented button）*/}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {STATUS_TABS.map((tab) => {
          const active = tab.key === statusTab;
          const c = counts[tab.key];
          const label =
            typeof c === "number" ? `${tab.label} (${c})` : tab.label;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setStatusTab(tab.key)}
              aria-pressed={active}
              className={`rounded-xl px-4 py-2 text-base font-medium transition-colors hover:cursor-pointer ${
                active
                  ? "bg-primary text-white shadow-sm"
                  : "bg-muted-bg text-muted hover:bg-border"
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>

      {/* scope chip */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="shrink-0 text-sm text-muted">範疇：</span>
        {SCOPE_CHIPS.map((chip) => (
          <FilterChip
            key={chip.key}
            active={chip.key === scopeChip}
            onClick={() => setScopeChip(chip.key)}
          >
            {chip.label}
          </FilterChip>
        ))}
      </div>

      {/* 列表 */}
      <div className="overflow-hidden rounded-xl bg-card-bg shadow-sm">
        {isLoading ? (
          <PageLoading />
        ) : items.length === 0 ? (
          <div className="py-12 text-center text-muted">
            {statusTab === "pending"
              ? "目前沒有待處理的 Skill 建議。系統會在你形成穩定使用習慣後自動推薦。"
              : "此狀態下尚無 Skill 建議紀錄。"}
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {items.map((item) => (
              <SuggestionCard key={item.uid} item={item} />
            ))}
          </ul>
        )}
      </div>

      {isFetching && !isLoading && (
        <div className="mt-4 text-center text-sm text-muted">更新中…</div>
      )}
    </div>
  );
}

function useTabCounts(): Record<StatusFilter, number | undefined> {
  const pending = useListSkillSuggestionsQuery({
    status: "pending",
    page: 1,
    size: 1,
  });
  const approved = useListSkillSuggestionsQuery({
    status: "approved",
    page: 1,
    size: 1,
  });
  const rejected = useListSkillSuggestionsQuery({
    status: "rejected",
    page: 1,
    size: 1,
  });
  const expired = useListSkillSuggestionsQuery({
    status: "expired",
    page: 1,
    size: 1,
  });

  return {
    pending: pending.data?.total,
    approved: approved.data?.total,
    rejected: rejected.data?.total,
    expired: expired.data?.total,
  };
}

interface SuggestionCardProps {
  item: AgenticSkillSuggestionItem;
}

function SuggestionCard({ item }: SuggestionCardProps): React.ReactNode {
  const [sourceOpen, setSourceOpen] = useState<boolean>(false);
  const [agentPickerOpen, setAgentPickerOpen] = useState<boolean>(false);

  const [acceptMutate, { isLoading: accepting }] =
    useAcceptSkillSuggestionMutation();
  const [rejectMutate, { isLoading: rejecting }] =
    useRejectSkillSuggestionMutation();
  const runAccept = useMutationWithDialog(acceptMutate);
  const runReject = useMutationWithDialog(rejectMutate);
  const { showDialog } = useDialog();

  const handleAcceptOnly = useCallback(() => {
    void runAccept(
      { uid: item.uid, agentUid: null },
      {
        successTitle: "已建立 Skill",
        successMessage: `已建立 Skill「${item.name}」，可至 Skill 列表掛載到 Agent`,
        errorMessage: "接受失敗，請稍後再試",
      },
    );
  }, [runAccept, item.uid, item.name]);

  const handleAcceptWithAgent = useCallback(
    (agent: Agent) => {
      void runAccept(
        { uid: item.uid, agentUid: agent.agent_uid },
        {
          successTitle: "已建立 Skill 並掛載",
          successMessage: `已建立 Skill「${item.name}」並掛載到「${agent.name}」`,
          errorMessage: "接受失敗，請稍後再試",
          onSuccess: () => setAgentPickerOpen(false),
        },
      );
    },
    [runAccept, item.uid, item.name],
  );

  const handleReject = useCallback(() => {
    showDialog({
      type: "warning",
      title: "拒絕此建議",
      message: `確定要拒絕「${item.name}」嗎？`,
      onConfirm: () => {
        void runReject(
          { uid: item.uid },
          {
            successTitle: "已拒絕",
            errorMessage: "拒絕失敗，請稍後再試",
          },
        );
      },
    });
  }, [runReject, item.uid, item.name, showDialog]);

  const isPending = item.status === "pending";
  const disabled = accepting || rejecting;

  const confidencePct = Math.round(item.confidence * 100);
  let confidenceClass = "bg-muted-bg text-muted";
  if (item.confidence >= 0.8) {
    confidenceClass =
      "bg-[color:var(--color-success-bg)] text-[color:var(--color-success)]";
  } else if (item.confidence >= 0.6) {
    confidenceClass =
      "bg-[color:var(--color-warning-bg)] text-[color:var(--color-warning)]";
  }
  const scopeStyles: Record<AgenticSuggestionScope, string> = {
    session: "bg-blue-50 text-blue-700 border-blue-200",
    project:
      "bg-[color:var(--color-purple-bg)] text-[color:var(--color-purple)] border-[color:var(--color-purple-border)]",
    user: "bg-amber-50 text-amber-700 border-amber-200",
  };
  const scopeLabels: Record<AgenticSuggestionScope, string> = {
    session: "Session",
    project: "Project",
    user: "User",
  };

  return (
    <li className="px-4 py-4 transition-colors hover:bg-muted-bg/40">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-lg font-semibold text-foreground">{item.name}</h3>
          {item.description && (
            <p className="mt-1 text-sm text-muted">{item.description}</p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className={`rounded-xl px-2 py-0.5 text-sm font-medium ${scopeStyles[item.scope]}`}
          >
            {scopeLabels[item.scope]}
          </span>
          <span
            className={`rounded-xl px-2 py-0.5 text-sm font-medium ${confidenceClass}`}
            title="模型對此建議的信心分數"
          >
            {confidencePct}%
          </span>
        </div>
      </div>

      <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
        <span>建立時間：{formatDateTime(item.created_at)}</span>
        {item.source_memory_uids.length > 0 && (
          <button
            type="button"
            onClick={() => setSourceOpen((v) => !v)}
            className="hover:cursor-pointer text-primary hover:underline"
          >
            來源 {item.source_memory_uids.length} 則記憶{" "}
            {sourceOpen ? "▴" : "▾"}
          </button>
        )}
      </div>

      {sourceOpen && <SourceMemoryList suggestionUid={item.uid} />}

      {isPending && (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-3">
          <Button
            onClick={handleAcceptOnly}
            disabled={disabled}
            variant="primary"
          >
            接受
          </Button>
          <Button
            onClick={() => setAgentPickerOpen(true)}
            disabled={disabled}
            variant="secondary"
          >
            接受並掛到 Agent ▾
          </Button>
          <Button
            onClick={handleReject}
            disabled={disabled}
            variant="secondary"
          >
            拒絕
          </Button>
        </div>
      )}

      {!isPending && (
        <div className="mt-2 rounded-md bg-muted-bg px-2 py-1 text-xs text-muted">
          {item.status === "approved" && "已建立 Skill"}
          {item.status === "rejected" && "已拒絕"}
          {item.status === "expired" && "已過期"}
        </div>
      )}

      {agentPickerOpen && (
        <AgentPickerModal
          onClose={() => setAgentPickerOpen(false)}
          onPick={handleAcceptWithAgent}
          disabled={disabled}
        />
      )}
    </li>
  );
}

interface SourceMemoryListProps {
  suggestionUid: string;
}

function SourceMemoryList({
  suggestionUid,
}: SourceMemoryListProps): React.ReactNode {
  const { data, isLoading } = useGetSkillSuggestionQuery({
    uid: suggestionUid,
  });
  const memories = data?.source_memories ?? [];
  if (isLoading) {
    return (
      <div className="my-2 rounded-md bg-muted-bg px-3 py-2 text-xs text-muted">
        載入來源記憶…
      </div>
    );
  }
  if (memories.length === 0) {
    return (
      <div className="my-2 rounded-md bg-muted-bg px-3 py-2 text-xs text-muted">
        無對應的記憶摘要（可能已被清除）
      </div>
    );
  }
  return (
    <ul className="my-2 flex flex-col gap-1 rounded-md bg-muted-bg px-3 py-2 text-xs text-muted">
      {memories.map((m, idx) => (
        <li key={idx} className="leading-relaxed">
          <span className="font-medium text-foreground">
            {m.topic ?? "（無主題）"}
          </span>
          {m.keywords.length > 0 && (
            <span className="ml-2">關鍵字：{m.keywords.join("、")}</span>
          )}
        </li>
      ))}
    </ul>
  );
}

interface AgentPickerModalProps {
  onClose: () => void;
  onPick: (agent: Agent) => void;
  disabled: boolean;
}

function AgentPickerModal({
  onClose,
  onPick,
  disabled,
}: AgentPickerModalProps): React.ReactNode {
  const { data, isLoading } = useListAgentsQuery({ limit: 50 });
  const [selected, setSelected] = useState<string>("");
  const candidates = useMemo(() => data?.items ?? [], [data]);

  return (
    <ModalDialog title="選擇要掛載的 Agent" onClose={onClose} size="md">
      <div className="flex flex-col gap-4">
        <p className="text-sm text-muted">
          建立 Skill 後將同步加入所選 Agent 的 skill_uids。
        </p>
        {isLoading ? (
          <div className="py-6 text-center text-sm text-muted">載入中…</div>
        ) : candidates.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted">
            找不到可掛載的 Agent。請先到 /agents 建立或收藏一個。
          </div>
        ) : (
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            disabled={disabled}
            aria-label="選擇要掛載的 Agent"
            title="選擇要掛載的 Agent"
            className="min-h-11 w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <option value="">請選擇 Agent</option>
            {candidates.map((a) => (
              <option key={a.agent_uid} value={a.agent_uid}>
                {a.name}
                {a.visibility === "public" ? "（公開）" : ""}
              </option>
            ))}
          </select>
        )}
        <div className="flex items-center justify-end gap-2 border-t border-border pt-3">
          <Button variant="secondary" onClick={onClose} disabled={disabled}>
            取消
          </Button>
          <Button
            onClick={() => {
              const target = candidates.find((a) => a.agent_uid === selected);
              if (target) onPick(target);
            }}
            disabled={!selected || disabled}
          >
            接受並掛載
          </Button>
        </div>
      </div>
    </ModalDialog>
  );
}
