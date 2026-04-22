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
import { useAuth } from "@/hooks/useAuth";
import { useChatStream } from "@/hooks/useChatStream";
import { useDialog } from "@/hooks/useDialog";
import { useMutationWithDialog } from "@/hooks/useMutationWithDialog";
import { useGetAgentQuery } from "@/store/agentsApi";
import {
  useGetSessionQuery,
  useListMessagesQuery,
  useListProjectsQuery,
  useListSessionMemoriesQuery,
  useMoveChatSessionMutation,
  useUpdateSessionMutation,
  chatApi,
} from "@/store/chatApi";
import type { AppDispatch } from "@/store/store";
import type { ChatMessage, ChatMessageRole } from "@/types";
import { formatDateTime } from "@/utils/datetime";

interface StreamingBubble {
  content: string;
}

interface MessageBubbleProps {
  role: ChatMessageRole;
  content: string;
  footer?: React.ReactNode;
}

const MessageBubble = React.memo(function MessageBubble({
  role,
  content,
  footer,
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
      className={`flex w-full ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[80%] rounded-xl px-4 py-3 shadow-sm ${
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
  return (
    <div className="flex flex-wrap gap-x-3">
      {message.model && <span>model: {message.model}</span>}
      {tokenText && <span>tokens: {tokenText}</span>}
      {message.cost_usd !== null && (
        <span>cost: {formatCost(message.cost_usd)}</span>
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

  const { data: agent } = useGetAgentQuery(session?.agent_uid ?? "", {
    skip: !session?.agent_uid,
  });

  const [input, setInput] = useState<string>("");
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [streaming, setStreaming] = useState<StreamingBubble | null>(null);
  const [memoryOpen, setMemoryOpen] = useState<boolean>(false);
  const [moveOpen, setMoveOpen] = useState<boolean>(false);
  const [titleDraft, setTitleDraft] = useState<string>("");
  const [titleEditing, setTitleEditing] = useState<boolean>(false);
  const titleInputRef = useRef<HTMLInputElement>(null);

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

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>): void => {
      setInput(e.target.value);
    },
    [],
  );

  const handleSend = useCallback((): void => {
    const content = input.trim();
    if (!content || isStreaming) return;

    setInput("");
    setPendingUser(content);
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
        // 串流完成後重抓歷史，取得完整 token / cost / uid
        void refetchMessages();
        // 同時 invalidate session 讓 message_count / last_message_at 更新
        dispatch(chatApi.util.invalidateTags(["ChatSessions"]));
        // 重抓記憶（非同步 worker 可能有新增）
        void refetchMemories();
        // 聚焦輸入框
        textareaRef.current?.focus();
      },
      (detail) => {
        setPendingUser(null);
        setStreaming(null);
        showDialog({
          type: "error",
          title: "對話失敗",
          message: detail,
        });
        textareaRef.current?.focus();
      },
    );
  }, [
    input,
    isStreaming,
    sendMessage,
    refetchMessages,
    refetchMemories,
    dispatch,
    showDialog,
  ]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>): void => {
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
            {session.agent_name && <span>Agent：{session.agent_name}</span>}
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
          <Button variant="secondary" onClick={handleOpenMove}>
            {session.chat_project_uid ? "更換專案" : "移至專案"}
          </Button>
          <Button variant="secondary" onClick={handleBack}>
            {session.chat_project_uid ? "返回專案" : "返回對話列表"}
          </Button>
        </div>
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
                    msg.model !== null);
                return (
                  <MessageBubble
                    key={msg.chat_message_uid}
                    role={msg.role}
                    content={msg.content}
                    footer={hasMeta ? buildAssistantFooter(msg) : undefined}
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

        <div className="shrink-0 border-t border-border p-3">
          <div className="flex items-end gap-2">
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
                  : "輸入訊息，Enter 送出，Shift+Enter 換行"
              }
              className="min-h-11 max-h-40 flex-1 resize-y rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20 disabled:cursor-not-allowed disabled:opacity-50"
            />
            <Button
              onClick={handleSend}
              loading={isStreaming}
              disabled={!input.trim() || isStreaming}
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
      </div>
    </div>
  );
}
