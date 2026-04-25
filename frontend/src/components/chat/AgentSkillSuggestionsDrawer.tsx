"use client";

/**
 * v1.3.6 Skill 推薦抽屜（多 Agent 對話頁的 Agent 切換器旁觸發）。
 *
 * 顯示該使用者對指定 Agent 的 active 推薦清單；
 * 接受 → 掛載到此 Agent；拒絕 → 樂觀更新移除卡片。
 *
 * 配色 / 規範：
 * - confidence 徽章：≥0.8 綠 / 0.6-0.8 黃 / <0.6 灰
 *   （本版僅顯示 ≥ recommender.min_confidence=0.75 的，即黃-綠範圍）
 * - 不顯示任何 uid（含 suggestion uid 與 source memory uid）
 */

import React, { useCallback } from "react";
import { Button } from "@/components/ui/Button";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { useDialog } from "@/hooks/useDialog";
import { useMutationWithDialog } from "@/hooks/useMutationWithDialog";
import {
  useAcceptAgentSkillSuggestionMutation,
  useListAgentSkillSuggestionsQuery,
  useRejectAgentSkillSuggestionMutation,
} from "@/store/agenticApi";
import type { RecommendSuggestionItem } from "@/types";

interface AgentSkillSuggestionsDrawerProps {
  agentUid: string;
  agentName: string | null;
  onClose: () => void;
}

export function AgentSkillSuggestionsDrawer({
  agentUid,
  agentName,
  onClose,
}: AgentSkillSuggestionsDrawerProps): React.ReactNode {
  const { data, isFetching } = useListAgentSkillSuggestionsQuery(
    { agentUid },
    { refetchOnMountOrArgChange: true },
  );
  const items = data?.items ?? [];

  const [acceptMutate, { isLoading: accepting }] =
    useAcceptAgentSkillSuggestionMutation();
  const [rejectMutate, { isLoading: rejecting }] =
    useRejectAgentSkillSuggestionMutation();
  const runAccept = useMutationWithDialog(acceptMutate);
  const runReject = useMutationWithDialog(rejectMutate);
  const { showDialog } = useDialog();

  const handleAccept = useCallback(
    (uid: string, suggestionName: string) => {
      void runAccept(
        { agentUid, suggestionUid: uid },
        {
          successTitle: "已建立 Skill 並掛載",
          successMessage: agentName
            ? `已建立 Skill「${suggestionName}」並掛載到「${agentName}」`
            : `已建立 Skill「${suggestionName}」`,
          errorMessage: "接受失敗，請稍後再試",
        },
      );
    },
    [runAccept, agentUid, agentName],
  );

  const handleReject = useCallback(
    (uid: string, suggestionName: string) => {
      showDialog({
        type: "warning",
        title: "拒絕此建議",
        message: `確定要拒絕「${suggestionName}」嗎？此後系統不會再針對此次模式推薦相同 Skill。`,
        onConfirm: () => {
          void runReject(
            { agentUid, suggestionUid: uid },
            {
              successTitle: "已拒絕",
              errorMessage: "拒絕失敗，請稍後再試",
            },
          );
        },
      });
    },
    [runReject, agentUid, showDialog],
  );

  const disabled = accepting || rejecting;

  return (
    <ModalDialog
      title={`Skill 建議${agentName ? `（${agentName}）` : ""}`}
      onClose={onClose}
      size="md"
    >
      <div className="flex flex-col gap-3">
        {isFetching ? (
          <div className="py-6 text-center text-sm text-muted">載入中…</div>
        ) : items.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted">
            目前沒有針對此 Agent 的 Skill 建議。
            <br />
            系統會在你跨 session / project 形成穩定使用習慣後自動推薦。
          </div>
        ) : (
          <ul className="flex flex-col gap-2">
            {items.map((item) => (
              <RecommendCard
                key={item.uid}
                item={item}
                disabled={disabled}
                onAccept={() => handleAccept(item.uid, item.name)}
                onReject={() => handleReject(item.uid, item.name)}
              />
            ))}
          </ul>
        )}
        <div className="flex items-center justify-end gap-2 border-t border-border pt-3">
          <Button variant="secondary" onClick={onClose}>
            關閉
          </Button>
        </div>
      </div>
    </ModalDialog>
  );
}


interface RecommendCardProps {
  item: RecommendSuggestionItem;
  disabled: boolean;
  onAccept: () => void;
  onReject: () => void;
}

function RecommendCard({
  item,
  disabled,
  onAccept,
  onReject,
}: RecommendCardProps): React.ReactNode {
  const confidencePct = Math.round(item.confidence * 100);
  // confidence 徽章配色：≥0.8 綠 / 0.6-0.8 黃 / <0.6 灰（本版只會顯示 ≥0.75）
  let confidenceClass = "bg-muted-bg text-muted";
  if (item.confidence >= 0.8) {
    confidenceClass =
      "bg-[color:var(--color-success-bg,#dcfce7)] text-[color:var(--color-success,#15803d)]";
  } else if (item.confidence >= 0.6) {
    confidenceClass =
      "bg-[color:var(--color-warning-bg,#fef9c3)] text-[color:var(--color-warning,#a16207)]";
  }
  // scope 徽章配色：藍/紫/金（與 v1.3.5 跨層記憶 UI 對齊）
  const scopeStyles: Record<typeof item.scope, string> = {
    session: "bg-blue-50 text-blue-700 border-blue-200",
    project:
      "bg-[color:var(--color-purple-bg,#f3e8ff)] text-[color:var(--color-purple,#7e22ce)] border-[color:var(--color-purple-border,#d8b4fe)]",
    user: "bg-amber-50 text-amber-700 border-amber-200",
  };
  const scopeLabels: Record<typeof item.scope, string> = {
    session: "Session",
    project: "Project",
    user: "User",
  };

  return (
    <li className="rounded-xl border border-border bg-input-bg p-3">
      <div className="mb-1 flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1 text-sm font-semibold text-foreground">
          {item.name || "（未命名建議）"}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <span
            className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${scopeStyles[item.scope]}`}
            title="此建議來源範圍"
          >
            {scopeLabels[item.scope]}
          </span>
          <span
            className={`rounded-xl px-2 py-0.5 text-xs font-medium ${confidenceClass}`}
            title="模型對此建議的信心分數"
          >
            {confidencePct}%
          </span>
        </div>
      </div>
      {item.description && (
        <p className="mb-2 text-xs text-muted">{item.description}</p>
      )}
      {item.source_memory_count > 0 && (
        <div className="mb-2 text-xs text-muted">
          來源 {item.source_memory_count} 則記憶
        </div>
      )}
      <div className="flex items-center gap-2">
        <Button onClick={onAccept} disabled={disabled} variant="primary">
          掛載到此 Agent
        </Button>
        <Button onClick={onReject} disabled={disabled} variant="secondary">
          拒絕
        </Button>
      </div>
    </li>
  );
}
