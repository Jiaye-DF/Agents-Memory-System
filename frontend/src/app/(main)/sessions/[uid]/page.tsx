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
import { useAuth } from "@/hooks/useAuth";
import { useChatStream } from "@/hooks/useChatStream";
import { useDialog } from "@/hooks/useDialog";
import {
  useGetSessionQuery,
  useListMessagesQuery,
  useListSessionMemoriesQuery,
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

  const [input, setInput] = useState<string>("");
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [streaming, setStreaming] = useState<StreamingBubble | null>(null);
  const [memoryOpen, setMemoryOpen] = useState<boolean>(false);

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
    if (session) {
      router.push(`/projects/${session.chat_project_uid}`);
    } else {
      router.push("/projects");
    }
  }, [router, session]);

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
          <p className="text-muted">找不到指定的 Session。</p>
          <Button
            className="mt-4"
            variant="secondary"
            onClick={() => router.push("/projects")}
          >
            返回列表
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      <div className="mb-3 flex shrink-0 items-start justify-between gap-2">
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-bold text-foreground">
            {session.title || "（未命名對話）"}
          </h1>
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
          <Button variant="secondary" onClick={handleBack}>
            返回 Project
          </Button>
        </div>
      </div>

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
              {messages.length === 0 && !pendingUser && (
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
              <button
                type="button"
                onClick={() => setMemoryOpen(false)}
                className="text-sm text-muted hover:text-foreground"
                aria-label="關閉記憶抽屜"
              >
                ✕
              </button>
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
