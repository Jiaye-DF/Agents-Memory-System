"use client";

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useParams, useRouter } from "next/navigation";
import { useDispatch } from "react-redux";
import { Button } from "@/components/ui/Button";
import { PageLoading, Spinner } from "@/components/ui/Loading";
import { ModalDialog } from "@/components/ui/ModalDialog";
import {
  MentionSelector,
  type MentionSelectorHandle,
} from "@/components/chat/MentionSelector";
import { SessionAgentBar } from "@/components/chat/SessionAgentBar";
import { useAuth } from "@/hooks/useAuth";
import { useChatStream } from "@/hooks/useChatStream";
import { useDialog } from "@/hooks/useDialog";
import { useMutationWithDialog } from "@/hooks/useMutationWithDialog";
import {
  useGetAgentQuery,
  useUpdateAgentMutation,
} from "@/store/agentsApi";
import {
  useApproveSkillSuggestionMutation,
  useGetAgentSkillSuggestionsQuery,
  useGetSessionQuery,
  useListMessagesQuery,
  useListProjectsQuery,
  useListSessionMemoriesQuery,
  useListSkillSuggestionsQuery,
  useMoveChatSessionMutation,
  useRejectSkillSuggestionMutation,
  useUpdateSessionMutation,
  useUploadAttachmentsMutation,
  chatApi,
} from "@/store/chatApi";
import type { AppDispatch } from "@/store/store";
import type {
  ChatAttachment,
  ChatMessage,
  ChatMessageRole,
  SessionAgent,
  SkillSuggestion,
} from "@/types";
import { formatDateTime } from "@/utils/datetime";

interface StreamingBubble {
  content: string;
}

// textarea auto-resize 上限（約 10 行，line-height 以目前 text-base 估算）
const TEXTAREA_MAX_PX = 240;
const IMAGE_MIME_PREFIX = "image/";
const ALLOWED_EXTENSIONS = [
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
  ".pdf",
  ".md",
  ".txt",
  ".json",
  ".csv",
];
const MAX_ATTACHMENTS_PER_MESSAGE = 5;
const MAX_ATTACHMENT_SIZE_MB = 10;

interface PendingAttachment {
  chat_attachment_uid: string;
  file_name: string;
  file_type: string;
  file_size: number;
  preview_url: string | null;
}

function isImageMime(mime: string | null | undefined): boolean {
  return !!mime && mime.toLowerCase().startsWith(IMAGE_MIME_PREFIX);
}

function isExtensionAllowed(name: string): boolean {
  const lower = name.toLowerCase();
  return ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function attachmentDownloadPath(attachmentUid: string): string {
  return `/chat/attachments/${attachmentUid}`;
}

interface AttachmentThumbProps {
  attachment: ChatAttachment;
  previewUrl?: string | null;
}

const AttachmentThumb = React.memo(function AttachmentThumb({
  attachment,
  previewUrl,
}: AttachmentThumbProps): React.ReactNode {
  const isImage = isImageMime(attachment.file_type);

  // 歷史訊息 render：沒有 previewUrl 時 img 直接打 API（fetch 會走 cookie + 401 refresh？
  // 這邊 API 其實只吃 Authorization header；歷史訊息的圖片在 v1.1.6 僅顯示檔名 chip，
  // 點擊後於新分頁開啟 inline 預覽（瀏覽器亦無 header）。
  // 為支援 auth 下的預覽縮圖，送出當下用 previewUrl；歷史訊息走檔名 chip + 新分頁。
  if (isImage && previewUrl) {
    return (
      <div className="relative h-20 w-20 overflow-hidden rounded-lg border border-border bg-muted-bg">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={previewUrl}
          alt={attachment.file_name}
          className="h-full w-full object-cover"
        />
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 rounded-lg border border-border bg-muted-bg px-2 py-1.5 text-sm">
      <span aria-hidden="true">{isImage ? "🖼️" : "📄"}</span>
      <span className="max-w-[140px] truncate">{attachment.file_name}</span>
      <span className="text-xs text-muted">
        {formatFileSize(attachment.file_size)}
      </span>
    </div>
  );
});

interface MessageBubbleProps {
  role: ChatMessageRole;
  content: string;
  footer?: React.ReactNode;
  copyable?: boolean;
  copied?: boolean;
  onCopy?: () => void;
  attachments?: ChatAttachment[] | null;
  /** v1.3.3：assistant 訊息附帶來源 Agent 名稱顯示在卡片左上 */
  respondingAgentName?: string | null;
  /** v1.3.3：Skill 推薦 placeholder 入口（assistant 訊息下方） */
  onSuggestSkill?: () => void;
}

const MessageBubble = React.memo(function MessageBubble({
  role,
  content,
  footer,
  copyable,
  copied,
  onCopy,
  attachments,
  respondingAgentName,
  onSuggestSkill,
}: MessageBubbleProps): React.ReactNode {
  const isUser = role === "user";
  const isSystem = role === "system" || role === "tool";

  if (isSystem) {
    return (
      <div className="my-2 flex justify-center">
        <div className="max-w-[80%] rounded-xl bg-muted-bg px-3 py-1 text-sm text-muted">
          {content}
        </div>
      </div>
    );
  }

  return (
    <div
      className={`flex w-full flex-col ${isUser ? "items-end" : "items-start"}`}
    >
      {!isUser && respondingAgentName && (
        <div className="mb-1 flex items-center gap-1 text-xs text-muted">
          <span aria-hidden="true">🤖</span>
          <span className="font-medium">{respondingAgentName}</span>
        </div>
      )}
      <div
        className={`group relative max-w-[80%] rounded-xl px-4 py-3 shadow-sm ${
          isUser
            ? "bg-primary text-white"
            : "border border-border bg-card-bg text-foreground"
        }`}
      >
        <pre
          className={`whitespace-pre-wrap break-words font-sans text-base ${
            isUser ? "text-white" : "text-foreground"
          }`}
        >
          {content}
        </pre>
        {copyable && onCopy && (
          <button
            type="button"
            onClick={onCopy}
            aria-label={copied ? "已複製" : "複製訊息"}
            title={copied ? "已複製" : "複製"}
            className="absolute right-2 top-2 rounded-xl border border-border bg-card-bg px-2 py-0.5 text-xs text-muted opacity-0 shadow-sm transition-opacity hover:cursor-pointer hover:text-foreground focus:opacity-100 focus:outline-none focus:ring-2 focus:ring-input-focus/30 group-hover:opacity-100"
          >
            {copied ? "✓ 已複製" : "複製"}
          </button>
        )}
        {attachments && attachments.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {attachments.map((a) => (
              <a
                key={a.chat_attachment_uid}
                href={`${process.env.NEXT_PUBLIC_API_URL ?? ""}${attachmentDownloadPath(a.chat_attachment_uid)}`}
                target="_blank"
                rel="noopener noreferrer"
                title={a.file_name}
                className="hover:cursor-pointer"
              >
                <AttachmentThumb attachment={a} />
              </a>
            ))}
          </div>
        )}
        {footer && (
          <div
            className={`mt-2 border-t pt-1 text-sm ${
              isUser
                ? "border-white/20 text-white/80"
                : "border-border text-muted"
            }`}
          >
            {footer}
          </div>
        )}
      </div>
      {!isUser && onSuggestSkill && (
        <button
          type="button"
          onClick={onSuggestSkill}
          className="mt-1 text-xs text-muted hover:cursor-pointer hover:text-primary"
          title="查看可掛載的推薦 Skill（v1.3.6 起亮起）"
        >
          💡 推薦 Skill
        </button>
      )}
    </div>
  );
});

interface MoveSessionModalProps {
  sessionUid: string;
  currentProjectUid: string | null;
  onClose: () => void;
}

function MoveSessionModal({
  sessionUid,
  currentProjectUid,
  onClose,
}: MoveSessionModalProps): React.ReactNode {
  const [target, setTarget] = useState<string>(currentProjectUid ?? "");

  const { data: projectsData, isLoading: projectsLoading } = useListProjectsQuery({
    limit: 50,
    cursor: null,
  });
  const projects = useMemo(() => projectsData?.items ?? [], [projectsData]);

  const [moveSession, { isLoading: moving }] = useMoveChatSessionMutation();
  const runMove = useMutationWithDialog(moveSession);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>): void => {
      setTarget(e.target.value);
    },
    [],
  );

  const handleSubmit = useCallback((): void => {
    const targetUid = target === "" ? null : target;
    void runMove(
      {
        sessionUid,
        body: { chat_project_uid: targetUid },
      },
      {
        successTitle: "移動成功",
        successMessage: targetUid
          ? "對話已移至指定專案。"
          : "對話已設為獨立。",
        errorMessage: "移動失敗，請稍後再試",
        onSuccess: onClose,
      },
    );
  }, [target, sessionUid, runMove, onClose]);

  const isSame = target === (currentProjectUid ?? "");

  return (
    <ModalDialog title="移動對話至專案" onClose={onClose} size="md">
      <div className="flex flex-col gap-4">
        <p className="text-sm text-muted">
          選擇要移入的專案，或選「（無，設為獨立對話）」把對話移出。
        </p>

        <div>
          <label
            htmlFor="move-target"
            className="mb-1.5 block text-base font-medium text-foreground"
          >
            目標
          </label>
          <select
            id="move-target"
            value={target}
            onChange={handleChange}
            disabled={projectsLoading || moving}
            className="min-h-11 w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground transition-colors focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <option value="">（無，設為獨立對話）</option>
            {projects.map((p) => (
              <option key={p.chat_project_uid} value={p.chat_project_uid}>
                {p.name}（{p.session_count} 則對話）
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border pt-4">
          <Button variant="secondary" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={moving} disabled={isSame}>
            確定移動
          </Button>
        </div>
      </div>
    </ModalDialog>
  );
}

function formatCost(cost: number | null): string {
  if (cost === null || cost === undefined) return "-";
  return `$${cost.toFixed(6)}`;
}

function buildAssistantFooter(message: ChatMessage): React.ReactNode {
  const tokenParts: string[] = [];
  if (message.token_in !== null) tokenParts.push(`in ${message.token_in}`);
  if (message.token_out !== null) tokenParts.push(`out ${message.token_out}`);
  const tokenText = tokenParts.length > 0 ? tokenParts.join(" / ") : null;
  const truncated = message.finish_reason === "length";
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {message.model && <span>model: {message.model}</span>}
      {tokenText && <span>tokens: {tokenText}</span>}
      {message.cost_usd !== null && (
        <span>cost: {formatCost(message.cost_usd)}</span>
      )}
      {truncated && (
        <span
          title="LLM 達到 max_tokens 上限。建議在 Agent 設定提高 max_tokens 或清空此欄位"
          className="inline-flex items-center gap-1 rounded-xl bg-warning-bg px-2 py-0.5 text-xs font-medium text-warning"
        >
          <span aria-hidden="true">⚠</span>
          <span>回覆被截斷</span>
        </span>
      )}
    </div>
  );
}

export default function SessionChatPage(): React.ReactNode {
  const params = useParams();
  const router = useRouter();
  const sessionUid = params.uid as string;
  const { isLoading: authLoading } = useAuth();
  const { showDialog } = useDialog();
  const dispatch = useDispatch<AppDispatch>();

  const {
    data: session,
    isLoading: sessionLoading,
    error: sessionError,
  } = useGetSessionQuery(sessionUid, { skip: authLoading });

  const {
    data: messagesData,
    isLoading: messagesLoading,
    refetch: refetchMessages,
  } = useListMessagesQuery(
    { sessionUid, limit: 100, cursor: null },
    { skip: authLoading || !session },
  );

  const messages = useMemo(
    (): ChatMessage[] => messagesData?.items ?? [],
    [messagesData],
  );

  // v1.3.3：session.agents 取代單 agent；primary 用於 greeting 與 Skill 推薦入口
  const sessionAgents = useMemo(
    (): SessionAgent[] => session?.agents ?? [],
    [session],
  );
  const primaryAgent = useMemo(
    (): SessionAgent | null =>
      sessionAgents.find((a) => a.role === "primary") ?? null,
    [sessionAgents],
  );
  const isMultiAgent = sessionAgents.length > 1;

  // 取 primary 的完整資料（v1.1.7 Skill 建議掛載流程仍需 skill_uids）
  const { data: agent } = useGetAgentQuery(primaryAgent?.agent_uid ?? "", {
    skip: !primaryAgent?.agent_uid,
  });

  const [input, setInput] = useState<string>("");
  // v1.3.3：@mention 對應的目標 agent_uid；MentionSelector 設定後送出時帶入
  const [mentionedAgentUid, setMentionedAgentUid] = useState<string | null>(
    null,
  );
  const [mentionTipDismissed, setMentionTipDismissed] =
    useState<boolean>(false);
  const mentionRef = useRef<MentionSelectorHandle>(null);
  // v1.3.3：Skill 推薦 placeholder 入口要顯示哪個 agent_uid 的占位提示
  const [skillSuggestAgentUid, setSkillSuggestAgentUid] = useState<
    string | null
  >(null);
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [pendingAttachments, setPendingAttachments] = useState<
    PendingAttachment[]
  >([]);
  const [streaming, setStreaming] = useState<StreamingBubble | null>(null);
  const [memoryOpen, setMemoryOpen] = useState<boolean>(false);
  const [suggestionsOpen, setSuggestionsOpen] = useState<boolean>(false);
  const [moveOpen, setMoveOpen] = useState<boolean>(false);
  const [titleDraft, setTitleDraft] = useState<string>("");
  const [titleEditing, setTitleEditing] = useState<boolean>(false);
  const [copiedUid, setCopiedUid] = useState<string | null>(null);
  const titleInputRef = useRef<HTMLInputElement>(null);
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [dragOver, setDragOver] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadAttachments] = useUploadAttachmentsMutation();

  const [updateSession] = useUpdateSessionMutation();
  const runUpdateSession = useMutationWithDialog(updateSession);

  const {
    data: memoriesData,
    isFetching: memoriesFetching,
    refetch: refetchMemories,
  } = useListSessionMemoriesQuery(
    { sessionUid },
    { skip: authLoading || !session },
  );
  const memories = useMemo(
    () => memoriesData?.items ?? [],
    [memoriesData],
  );

  useEffect(() => {
    if (memoryOpen) {
      void refetchMemories();
    }
  }, [memoryOpen, refetchMemories]);

  const {
    data: suggestionsData,
    isFetching: suggestionsFetching,
    refetch: refetchSuggestions,
  } = useListSkillSuggestionsQuery(
    { sessionUid },
    { skip: authLoading || !session },
  );
  const suggestions = useMemo(
    (): SkillSuggestion[] => suggestionsData?.items ?? [],
    [suggestionsData],
  );
  const pendingSuggestionCount = useMemo(
    (): number => suggestions.filter((s) => s.status === "pending").length,
    [suggestions],
  );

  useEffect(() => {
    if (suggestionsOpen) {
      void refetchSuggestions();
    }
  }, [suggestionsOpen, refetchSuggestions]);

  const [approveSuggestion, { isLoading: approvingSuggestion }] =
    useApproveSkillSuggestionMutation();
  const [rejectSuggestion, { isLoading: rejectingSuggestion }] =
    useRejectSkillSuggestionMutation();
  const [updateAgent] = useUpdateAgentMutation();
  const runUpdateAgent = useMutationWithDialog(updateAgent);
  const runApproveSuggestion = useMutationWithDialog(approveSuggestion);
  const runRejectSuggestion = useMutationWithDialog(rejectSuggestion);

  const handleApproveSuggestion = useCallback(
    (idx: number): void => {
      void (async () => {
        let approvedSkillUid: string | null = null;
        await runApproveSuggestion(
          { sessionUid, idx },
          {
            successTitle: "已建立 Skill",
            errorMessage: "建立 Skill 失敗，請稍後再試",
            onSuccess: () => {
              // noop；unwrap 會在下方取得 skill_uid
            },
          },
        );
        // 再抓一次最新狀態取 created_skill_uid（invalidatesTags 已觸發 refetch）
        try {
          const refreshed = await refetchSuggestions();
          const latest = refreshed.data?.items ?? [];
          const target = latest.find((s) => s.idx === idx);
          approvedSkillUid = target?.created_skill_uid ?? null;
        } catch {
          approvedSkillUid = null;
        }

        if (!approvedSkillUid || !session || !agent) return;

        showDialog({
          type: "warning",
          title: "建立完成",
          message: `已建立新的 Skill。要立即掛到目前 Agent「${
            agent.name
          }」嗎？`,
          onConfirm: () => {
            const currentUids = agent.skill_uids ?? [];
            if (currentUids.includes(approvedSkillUid!)) return;
            void runUpdateAgent(
              {
                agentUid: agent.agent_uid,
                body: { skill_uids: [...currentUids, approvedSkillUid!] },
              },
              {
                successTitle: "掛載成功",
                successMessage: "Skill 已掛到 Agent，下次對話生效。",
                errorMessage: "掛載失敗，稍後可到 Agent 設定頁手動加入。",
              },
            );
          },
        });
      })();
    },
    [
      runApproveSuggestion,
      sessionUid,
      refetchSuggestions,
      session,
      agent,
      showDialog,
      runUpdateAgent,
    ],
  );

  const handleRejectSuggestion = useCallback(
    (idx: number): void => {
      void runRejectSuggestion(
        { sessionUid, idx },
        {
          errorMessage: "拒絕失敗，請稍後再試",
        },
      );
    },
    [runRejectSuggestion, sessionUid],
  );

  const { isStreaming, sendMessage } = useChatStream(sessionUid);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback((): void => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, pendingUser, streaming, scrollToBottom]);

  const handleBack = useCallback((): void => {
    if (session?.chat_project_uid) {
      router.push(`/projects/${session.chat_project_uid}`);
    } else {
      router.push("/sessions");
    }
  }, [router, session]);

  const handleOpenMove = useCallback((): void => {
    setMoveOpen(true);
  }, []);

  const handleCloseMove = useCallback((): void => {
    setMoveOpen(false);
  }, []);

  const handleStartEditTitle = useCallback((): void => {
    if (!session) return;
    setTitleDraft(session.title ?? "");
    setTitleEditing(true);
    // 下一個 tick 才聚焦，避免 input 還沒 mount
    setTimeout(() => {
      titleInputRef.current?.focus();
      titleInputRef.current?.select();
    }, 0);
  }, [session]);

  const handleCancelEditTitle = useCallback((): void => {
    setTitleEditing(false);
    setTitleDraft("");
  }, []);

  const handleCommitTitle = useCallback((): void => {
    if (!session) {
      setTitleEditing(false);
      return;
    }
    const trimmed = titleDraft.trim();
    if (!trimmed || trimmed === (session.title ?? "")) {
      // 空白或未修改 → 直接退出不送 API
      setTitleEditing(false);
      setTitleDraft("");
      return;
    }
    void runUpdateSession(
      {
        sessionUid,
        body: { title: trimmed },
      },
      {
        errorMessage: "更名失敗，請稍後再試",
        onSuccess: () => {
          setTitleEditing(false);
          setTitleDraft("");
        },
      },
    );
  }, [session, titleDraft, runUpdateSession, sessionUid]);

  const handleTitleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>): void => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleCommitTitle();
      } else if (e.key === "Escape") {
        e.preventDefault();
        handleCancelEditTitle();
      }
    },
    [handleCommitTitle, handleCancelEditTitle],
  );

  const handleTitleDraftChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setTitleDraft(e.target.value);
    },
    [],
  );

  const resizeTextarea = useCallback((): void => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const next = Math.min(el.scrollHeight, TEXTAREA_MAX_PX);
    el.style.height = `${next}px`;
  }, []);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>): void => {
      setInput(e.target.value);
      resizeTextarea();
    },
    [resizeTextarea],
  );

  const handleCopyMessage = useCallback(
    (messageUid: string, content: string): void => {
      const writer =
        typeof navigator !== "undefined" &&
        navigator.clipboard &&
        typeof navigator.clipboard.writeText === "function"
          ? navigator.clipboard.writeText(content)
          : Promise.reject(new Error("clipboard unavailable"));

      void writer
        .then(() => {
          setCopiedUid(messageUid);
          if (copyTimerRef.current) {
            clearTimeout(copyTimerRef.current);
          }
          copyTimerRef.current = setTimeout(() => {
            setCopiedUid((prev) => (prev === messageUid ? null : prev));
            copyTimerRef.current = null;
          }, 2000);
        })
        .catch(() => {
          showDialog({
            type: "error",
            title: "複製失敗",
            message: "瀏覽器不支援自動複製，請手動框選內容。",
          });
        });
    },
    [showDialog],
  );

  useEffect(() => {
    return () => {
      if (copyTimerRef.current) {
        clearTimeout(copyTimerRef.current);
        copyTimerRef.current = null;
      }
    };
  }, []);

  const releasePendingPreviews = useCallback(
    (items: PendingAttachment[]): void => {
      items.forEach((a) => {
        if (a.preview_url) URL.revokeObjectURL(a.preview_url);
      });
    },
    [],
  );

  const pendingAttachmentsRef = useRef<PendingAttachment[]>([]);
  useEffect(() => {
    pendingAttachmentsRef.current = pendingAttachments;
  }, [pendingAttachments]);
  useEffect(() => {
    return () => {
      releasePendingPreviews(pendingAttachmentsRef.current);
    };
  }, [releasePendingPreviews]);

  const validateFiles = useCallback(
    (files: File[]): string | null => {
      const remaining = MAX_ATTACHMENTS_PER_MESSAGE - pendingAttachments.length;
      if (files.length === 0) return null;
      if (files.length > remaining) {
        return `單則訊息最多 ${MAX_ATTACHMENTS_PER_MESSAGE} 個附件（目前剩餘 ${remaining} 個）`;
      }
      for (const f of files) {
        if (!isExtensionAllowed(f.name)) {
          return `不允許的檔案類型：${f.name}（允許：${ALLOWED_EXTENSIONS.join(", ")}）`;
        }
        if (f.size > MAX_ATTACHMENT_SIZE_MB * 1024 * 1024) {
          return `檔案超過 ${MAX_ATTACHMENT_SIZE_MB} MB 上限：${f.name}`;
        }
      }
      return null;
    },
    [pendingAttachments.length],
  );

  const handleUploadFiles = useCallback(
    async (files: File[]): Promise<void> => {
      if (files.length === 0) return;
      const err = validateFiles(files);
      if (err) {
        showDialog({ type: "error", title: "附件錯誤", message: err });
        return;
      }

      setUploading(true);
      try {
        const resp = await uploadAttachments({
          sessionUid,
          files,
        }).unwrap();

        const items = resp.items ?? [];
        const previews: PendingAttachment[] = items.map((a, idx) => {
          const originalFile = files[idx];
          const url =
            originalFile && isImageMime(a.file_type)
              ? URL.createObjectURL(originalFile)
              : null;
          return {
            chat_attachment_uid: a.chat_attachment_uid,
            file_name: a.file_name,
            file_type: a.file_type,
            file_size: a.file_size,
            preview_url: url,
          };
        });
        setPendingAttachments((prev) => [...prev, ...previews]);
      } catch (e: unknown) {
        const message =
          typeof e === "string"
            ? e
            : e instanceof Error
              ? e.message
              : "附件上傳失敗";
        showDialog({ type: "error", title: "附件上傳失敗", message });
      } finally {
        setUploading(false);
      }
    },
    [sessionUid, uploadAttachments, validateFiles, showDialog],
  );

  const handlePickFiles = useCallback((): void => {
    fileInputRef.current?.click();
  }, []);

  const handleFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      const list = e.target.files;
      if (!list) return;
      const files = Array.from(list);
      e.target.value = "";
      void handleUploadFiles(files);
    },
    [handleUploadFiles],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>): void => {
      e.preventDefault();
      setDragOver(false);
      const files = Array.from(e.dataTransfer.files ?? []);
      if (files.length === 0) return;
      void handleUploadFiles(files);
    },
    [handleUploadFiles],
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent<HTMLDivElement>): void => {
      e.preventDefault();
      setDragOver(true);
    },
    [],
  );

  const handleDragLeave = useCallback(
    (e: React.DragEvent<HTMLDivElement>): void => {
      e.preventDefault();
      setDragOver(false);
    },
    [],
  );

  const handleRemovePending = useCallback(
    (uid: string): void => {
      setPendingAttachments((prev) => {
        const target = prev.find((a) => a.chat_attachment_uid === uid);
        if (target?.preview_url) {
          URL.revokeObjectURL(target.preview_url);
        }
        return prev.filter((a) => a.chat_attachment_uid !== uid);
      });
    },
    [],
  );

  const handleSend = useCallback((): void => {
    const content = input.trim();
    if (!content || isStreaming || uploading) return;

    const attachmentUids = pendingAttachments.map(
      (a) => a.chat_attachment_uid,
    );
    const snapshot = pendingAttachments;

    // v1.3.3：mention 解析在輸入時已寫入 mentionedAgentUid；
    // 若使用者後來把 @mention 文字刪掉、就不再帶入（檢查 input 內仍含 @AgentName）。
    let resolvedMention: string | null = mentionedAgentUid;
    if (resolvedMention) {
      const mentionedAgent = sessionAgents.find(
        (a) => a.agent_uid === resolvedMention,
      );
      if (
        !mentionedAgent ||
        !content.includes(`@${mentionedAgent.agent_name ?? ""}`)
      ) {
        resolvedMention = null;
      }
    }

    setInput("");
    setMentionedAgentUid(null);
    // 清空後把 textarea 高度重置，避免保持最後的大高度
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    setPendingUser(content);
    setPendingAttachments([]);
    setStreaming({ content: "" });

    void sendMessage(
      content,
      (chunk) => {
        setStreaming((prev) =>
          prev ? { content: prev.content + chunk } : { content: chunk },
        );
      },
      () => {
        setPendingUser(null);
        setStreaming(null);
        releasePendingPreviews(snapshot);
        // 串流完成後重抓歷史，取得完整 token / cost / uid
        void refetchMessages();
        // 同時 invalidate session 讓 message_count / last_message_at 更新
        dispatch(chatApi.util.invalidateTags(["ChatSessions"]));
        // 重抓記憶（非同步 worker 可能有新增）
        void refetchMemories();
        // v1.1.7：重抓 Skill 候選（skill_factory_worker 可能有新增）
        void refetchSuggestions();
        // 聚焦輸入框
        textareaRef.current?.focus();
      },
      (detail) => {
        setPendingUser(null);
        setStreaming(null);
        releasePendingPreviews(snapshot);
        showDialog({
          type: "error",
          title: "對話失敗",
          message: detail,
        });
        textareaRef.current?.focus();
      },
      attachmentUids.length > 0 || resolvedMention
        ? {
            attachmentUids:
              attachmentUids.length > 0 ? attachmentUids : undefined,
            mentionedAgentUid: resolvedMention,
          }
        : undefined,
    );
  }, [
    input,
    isStreaming,
    uploading,
    pendingAttachments,
    mentionedAgentUid,
    sessionAgents,
    sendMessage,
    refetchMessages,
    refetchMemories,
    refetchSuggestions,
    dispatch,
    showDialog,
    releasePendingPreviews,
  ]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>): void => {
      // v1.3.3：先讓 MentionSelector 處理上下鍵 / Enter / Esc
      if (mentionRef.current?.handleKeyDown(e)) return;
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  if (authLoading || sessionLoading) {
    return <PageLoading />;
  }

  if (sessionError || !session) {
    return (
      <div>
        <h1 className="mb-4 text-3xl font-bold text-foreground">對話</h1>
        <div className="rounded-xl bg-card-bg p-6 text-center shadow-sm">
          <p className="text-muted">找不到指定的對話。</p>
          <Button
            className="mt-4"
            variant="secondary"
            onClick={() => router.push("/sessions")}
          >
            返回對話列表
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      <div className="mb-3 flex shrink-0 items-start justify-between gap-2">
        <div className="min-w-0">
          {titleEditing ? (
            <input
              ref={titleInputRef}
              type="text"
              value={titleDraft}
              onChange={handleTitleDraftChange}
              onKeyDown={handleTitleKeyDown}
              onBlur={handleCommitTitle}
              maxLength={200}
              placeholder="輸入對話標題"
              className="w-full rounded-md border border-input-border bg-input-bg px-2 py-0.5 text-2xl font-bold text-foreground focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
            />
          ) : (
            <button
              type="button"
              onClick={handleStartEditTitle}
              className="group flex min-w-0 max-w-full items-center gap-2 rounded-md px-2 py-0.5 -mx-2 text-left transition-colors hover:cursor-pointer hover:bg-muted-bg/60"
              title="點擊以重新命名"
            >
              <span className="truncate text-2xl font-bold text-foreground">
                {session.title || "（未命名對話）"}
              </span>
              <svg
                className="shrink-0 text-muted opacity-0 transition-opacity group-hover:opacity-100"
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                aria-hidden="true"
              >
                <path
                  d="M11 2.5L13.5 5M2.5 13.5L3 11L11.5 2.5C12 2 12.5 2 13 2.5L13.5 3C14 3.5 14 4 13.5 4.5L5 13L2.5 13.5Z"
                  stroke="currentColor"
                  strokeWidth="1.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          )}
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-sm text-muted">
            <span>訊息數：{session.message_count}</span>
            {session.last_message_at && (
              <span>最後訊息：{formatDateTime(session.last_message_at)}</span>
            )}
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button
            variant="secondary"
            onClick={() => setMemoryOpen((v) => !v)}
          >
            記憶 {memories.length > 0 ? `(${memories.length})` : ""}
          </Button>
          <Button
            variant="secondary"
            onClick={() => setSuggestionsOpen((v) => !v)}
          >
            建議 Skill{" "}
            {pendingSuggestionCount > 0 ? `(${pendingSuggestionCount})` : ""}
          </Button>
          <Button variant="secondary" onClick={handleOpenMove}>
            {session.chat_project_uid ? "更換專案" : "移至專案"}
          </Button>
          <Button variant="secondary" onClick={handleBack}>
            {session.chat_project_uid ? "返回專案" : "返回對話列表"}
          </Button>
        </div>
      </div>

      {/* v1.3.3：多 Agent badge 列 + 加入按鈕 + 設 primary / 移除 */}
      <div className="mb-3 shrink-0">
        <SessionAgentBar
          sessionUid={sessionUid}
          agents={sessionAgents}
        />
        {isMultiAgent && !mentionTipDismissed && (
          <div className="mt-2 flex items-start justify-between gap-2 rounded-md border border-border bg-muted-bg px-3 py-2 text-xs text-muted">
            <span>
              這是多 Agent 對話：輸入 <code className="font-mono">@</code>{" "}
              即可指定 Agent；不指定時由 primary（標星號）回覆。
            </span>
            <button
              type="button"
              onClick={() => setMentionTipDismissed(true)}
              className="shrink-0 hover:cursor-pointer text-muted hover:text-foreground"
              aria-label="關閉提示"
            >
              ✕
            </button>
          </div>
        )}
      </div>

      {moveOpen && (
        <MoveSessionModal
          sessionUid={sessionUid}
          currentProjectUid={session.chat_project_uid}
          onClose={handleCloseMove}
        />
      )}

      <div className="flex min-h-0 flex-1 gap-3">
       <div className="flex min-h-0 flex-1 flex-col rounded-xl bg-card-bg shadow-sm">
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-4"
        >
          {messagesLoading ? (
            <PageLoading />
          ) : (
            <div className="flex flex-col gap-3">
              {messages.length === 0 && !pendingUser && agent?.greeting && (
                <MessageBubble role="assistant" content={agent.greeting} />
              )}
              {messages.length === 0 &&
                !pendingUser &&
                !agent?.greeting && (
                  <div className="py-12 text-center text-muted">
                    尚無對話，試著輸入第一則訊息。
                  </div>
                )}

              {messages.map((msg) => {
                const hasMeta =
                  msg.role === "assistant" &&
                  (msg.token_in !== null ||
                    msg.token_out !== null ||
                    msg.cost_usd !== null ||
                    msg.model !== null ||
                    msg.finish_reason === "length");
                const isAssistant = msg.role === "assistant";
                const respondingAgentName =
                  msg.responding_agent?.name ?? null;
                const respondingAgentUid =
                  msg.responding_agent_uid ?? null;
                return (
                  <MessageBubble
                    key={msg.chat_message_uid}
                    role={msg.role}
                    content={msg.content}
                    footer={hasMeta ? buildAssistantFooter(msg) : undefined}
                    copyable={isAssistant}
                    copied={copiedUid === msg.chat_message_uid}
                    onCopy={
                      isAssistant
                        ? () =>
                            handleCopyMessage(
                              msg.chat_message_uid,
                              msg.content,
                            )
                        : undefined
                    }
                    attachments={msg.attachments}
                    respondingAgentName={respondingAgentName}
                    onSuggestSkill={
                      isAssistant && respondingAgentUid
                        ? () => setSkillSuggestAgentUid(respondingAgentUid)
                        : undefined
                    }
                  />
                );
              })}

              {pendingUser && (
                <MessageBubble role="user" content={pendingUser} />
              )}

              {streaming && (
                <MessageBubble
                  role="assistant"
                  content={streaming.content || "…"}
                  footer={
                    <div className="flex items-center gap-2">
                      <Spinner size="sm" />
                      <span>回應中…</span>
                    </div>
                  }
                />
              )}
            </div>
          )}
        </div>

        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className={`shrink-0 border-t border-border p-3 transition-colors ${
            dragOver ? "bg-primary/5" : ""
          }`}
        >
          {pendingAttachments.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-2">
              {pendingAttachments.map((a) => (
                <div
                  key={a.chat_attachment_uid}
                  className="relative"
                  title={a.file_name}
                >
                  {a.preview_url ? (
                    <div className="relative h-16 w-16 overflow-hidden rounded-lg border border-border bg-muted-bg">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={a.preview_url}
                        alt={a.file_name}
                        className="h-full w-full object-cover"
                      />
                    </div>
                  ) : (
                    <div className="flex h-16 max-w-[180px] items-center gap-2 rounded-lg border border-border bg-muted-bg px-2 py-1 text-sm">
                      <span aria-hidden="true">📄</span>
                      <div className="flex flex-col overflow-hidden">
                        <span className="truncate">{a.file_name}</span>
                        <span className="text-xs text-muted">
                          {formatFileSize(a.file_size)}
                        </span>
                      </div>
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => handleRemovePending(a.chat_attachment_uid)}
                    className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-border bg-card-bg text-xs text-foreground shadow-sm hover:cursor-pointer hover:bg-muted-bg"
                    aria-label={`移除附件 ${a.file_name}`}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-end gap-2">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={ALLOWED_EXTENSIONS.join(",")}
              className="hidden"
              onChange={handleFileInputChange}
              aria-label="附件檔案選擇"
              title="附件檔案選擇"
            />
            <button
              type="button"
              onClick={handlePickFiles}
              disabled={isStreaming || uploading}
              className="flex min-h-11 min-w-11 items-center justify-center rounded-xl border border-border bg-card-bg text-lg text-foreground transition-colors hover:cursor-pointer hover:bg-muted-bg disabled:cursor-not-allowed disabled:opacity-50"
              aria-label="加入附件"
              title="加入附件（圖片 / 文字檔）"
            >
              {uploading ? <Spinner size="sm" /> : "📎"}
            </button>
            <div className="relative flex-1">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                disabled={isStreaming}
                rows={2}
                placeholder={
                  isStreaming
                    ? "回應生成中…"
                    : dragOver
                      ? "放開以加入附件…"
                      : isMultiAgent
                        ? "輸入訊息（@ 指定 Agent）；Enter 送出"
                        : "輸入訊息，Enter 送出，Shift+Enter 換行"
                }
                className="min-h-11 max-h-60 w-full resize-none overflow-y-auto rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20 disabled:cursor-not-allowed disabled:opacity-50"
              />
              {isMultiAgent && (
                <MentionSelector
                  ref={mentionRef}
                  agents={sessionAgents}
                  value={input}
                  onChange={(next) => setInput(next)}
                  textareaRef={textareaRef}
                  onSelect={(uid) => setMentionedAgentUid(uid)}
                />
              )}
            </div>
            <Button
              onClick={handleSend}
              loading={isStreaming}
              disabled={!input.trim() || isStreaming || uploading}
            >
              送出
            </Button>
          </div>
        </div>
       </div>

        {memoryOpen && (
          <aside className="flex w-72 shrink-0 flex-col rounded-xl bg-card-bg shadow-sm">
            <div className="flex shrink-0 items-center justify-between border-b border-border p-3">
              <h2 className="text-base font-semibold text-foreground">記憶</h2>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => void refetchMemories()}
                  disabled={memoriesFetching}
                  className="text-sm text-muted hover:cursor-pointer hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label="重新整理記憶"
                  title="重新整理"
                >
                  {memoriesFetching ? "⟳" : "🔄"}
                </button>
                <button
                  type="button"
                  onClick={() => setMemoryOpen(false)}
                  className="text-sm text-muted hover:cursor-pointer hover:text-foreground"
                  aria-label="關閉記憶抽屜"
                >
                  ✕
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-3">
              {memoriesFetching && memories.length === 0 ? (
                <div className="py-8 text-center text-sm text-muted">
                  載入中…
                </div>
              ) : memories.length === 0 ? (
                <div className="py-8 text-center text-sm text-muted">
                  尚無記憶，對話持續一段時間後會自動建立。
                </div>
              ) : (
                <ul className="flex flex-col gap-3">
                  {memories.map((mem) => (
                    <li
                      key={mem.chat_memory_uid}
                      className="rounded-lg border border-border bg-input-bg p-3"
                    >
                      <div className="mb-2 text-sm font-semibold text-foreground">
                        {mem.topic || "（未命名主題）"}
                      </div>
                      {mem.keywords.length > 0 && (
                        <div className="mb-1 flex flex-wrap gap-1">
                          {mem.keywords.map((kw, idx) => (
                            <span
                              key={`kw-${mem.chat_memory_uid}-${idx}`}
                              className="rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary"
                            >
                              {kw}
                            </span>
                          ))}
                        </div>
                      )}
                      {mem.entities.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {mem.entities.map((ent, idx) => (
                            <span
                              key={`ent-${mem.chat_memory_uid}-${idx}`}
                              className="rounded-full bg-muted-bg px-2 py-0.5 text-xs text-muted"
                            >
                              {ent}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="mt-2 text-xs text-muted">
                        {formatDateTime(mem.created_at)}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </aside>
        )}

        {suggestionsOpen && (
          <aside className="flex w-80 shrink-0 flex-col rounded-xl bg-card-bg shadow-sm">
            <div className="flex shrink-0 items-center justify-between border-b border-border p-3">
              <h2 className="text-base font-semibold text-foreground">
                建議 Skill
              </h2>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => void refetchSuggestions()}
                  disabled={suggestionsFetching}
                  className="text-sm text-muted hover:cursor-pointer hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label="重新整理建議 Skill"
                  title="重新整理"
                >
                  {suggestionsFetching ? "⟳" : "🔄"}
                </button>
                <button
                  type="button"
                  onClick={() => setSuggestionsOpen(false)}
                  className="text-sm text-muted hover:cursor-pointer hover:text-foreground"
                  aria-label="關閉建議 Skill 抽屜"
                >
                  ✕
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-3">
              {suggestionsFetching && suggestions.length === 0 ? (
                <div className="py-8 text-center text-sm text-muted">
                  載入中…
                </div>
              ) : suggestions.length === 0 ? (
                <div className="py-8 text-center text-sm text-muted">
                  對話累積一段時間後會出現建議的 Skills。
                  <div className="mt-2">
                    現有 {memories.length} 則記憶（達到約 10 則且主題聚焦即可觸發）。
                  </div>
                </div>
              ) : (
                <ul className="flex flex-col gap-3">
                  {suggestions.map((item) => (
                    <SkillSuggestionCard
                      key={`suggestion-${item.idx}`}
                      item={item}
                      disabled={approvingSuggestion || rejectingSuggestion}
                      onApprove={handleApproveSuggestion}
                      onReject={handleRejectSuggestion}
                    />
                  ))}
                </ul>
              )}
            </div>
          </aside>
        )}
      </div>

      {/* v1.3.3：Skill 推薦 placeholder（v1.3.6 接真實邏輯） */}
      {skillSuggestAgentUid && (
        <SkillSuggestPlaceholderModal
          agentUid={skillSuggestAgentUid}
          sessionUid={sessionUid}
          onClose={() => setSkillSuggestAgentUid(null)}
        />
      )}
    </div>
  );
}

interface SkillSuggestPlaceholderModalProps {
  agentUid: string;
  sessionUid: string;
  onClose: () => void;
}

function SkillSuggestPlaceholderModal({
  agentUid,
  sessionUid,
  onClose,
}: SkillSuggestPlaceholderModalProps): React.ReactNode {
  const { data, isFetching } = useGetAgentSkillSuggestionsQuery(
    { agentUid, scope: "session", scopeUid: sessionUid },
    { refetchOnMountOrArgChange: true },
  );
  const items = data?.items ?? [];
  return (
    <ModalDialog title="推薦 Skill" onClose={onClose} size="md">
      <div className="flex flex-col gap-3">
        {isFetching ? (
          <div className="py-6 text-center text-sm text-muted">
            載入中…
          </div>
        ) : items.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted">
            目前沒有可推薦的 Skill。
          </div>
        ) : (
          <ul className="flex flex-col gap-2">
            {items.map((item, idx) => (
              <li
                key={`suggest-${idx}`}
                className="rounded-lg border border-border bg-input-bg p-3 text-sm text-foreground"
              >
                {/* v1.3.6 接真實邏輯後此處渲染推薦項目 */}
                {JSON.stringify(item)}
              </li>
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

interface SkillSuggestionCardProps {
  item: SkillSuggestion;
  disabled: boolean;
  onApprove: (idx: number) => void;
  onReject: (idx: number) => void;
}

function SkillSuggestionCard({
  item,
  disabled,
  onApprove,
  onReject,
}: SkillSuggestionCardProps): React.ReactNode {
  const confidencePct = Math.round(item.confidence * 100);
  // confidence 徽章色：以 CSS variable 對應的 Tailwind class 呈現，
  // 切換規則：0.8+ 綠（success）、0.6-0.8 黃（warning）、< 0.6 灰（muted）
  let badgeClass = "bg-muted-bg text-muted";
  if (item.confidence >= 0.8) {
    badgeClass = "bg-[color:var(--color-success-bg,#dcfce7)] text-[color:var(--color-success,#15803d)]";
  } else if (item.confidence >= 0.6) {
    badgeClass = "bg-[color:var(--color-warning-bg,#fef9c3)] text-[color:var(--color-warning,#a16207)]";
  }

  const isHandled = item.status !== "pending";

  return (
    <li className="rounded-xl border border-border bg-input-bg p-3">
      <div className="mb-1 flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1 text-sm font-semibold text-foreground">
          {item.name || "（未命名建議）"}
        </div>
        <span
          className={`shrink-0 rounded-xl px-2 py-0.5 text-xs font-medium ${badgeClass}`}
          title="模型對此建議的信心分數"
        >
          {confidencePct}%
        </span>
      </div>
      {item.description && (
        <p className="mb-2 text-xs text-muted">{item.description}</p>
      )}
      {item.source_memory_uids.length > 0 && (
        <div className="mb-2 text-xs text-muted">
          參考 {item.source_memory_uids.length} 則記憶
        </div>
      )}
      {item.status === "approved" && (
        <div className="mb-2 rounded-md bg-muted-bg px-2 py-1 text-xs text-muted">
          已建立 Skill
        </div>
      )}
      {item.status === "rejected" && (
        <div className="mb-2 rounded-md bg-muted-bg px-2 py-1 text-xs text-muted">
          已拒絕
        </div>
      )}
      {!isHandled && (
        <div className="flex items-center justify-end gap-2 border-t border-border pt-2">
          <button
            type="button"
            onClick={() => onReject(item.idx)}
            disabled={disabled}
            className="rounded-xl border border-border bg-card-bg px-3 py-1 text-xs text-foreground transition-colors hover:cursor-pointer hover:bg-muted-bg disabled:cursor-not-allowed disabled:opacity-50"
          >
            拒絕
          </button>
          <button
            type="button"
            onClick={() => onApprove(item.idx)}
            disabled={disabled}
            className="rounded-xl bg-primary px-3 py-1 text-xs text-white transition-colors hover:cursor-pointer hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            建立
          </button>
        </div>
      )}
    </li>
  );
}
