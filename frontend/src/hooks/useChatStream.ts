"use client";

import { useCallback, useState } from "react";
import { openStream } from "@/lib/api/stream";

interface SendMessageOptions {
  attachmentUids?: string[];
  /** v1.3.3 多 Agent：使用者於前端 @mention 後對應的 agent_uid。 */
  mentionedAgentUid?: string | null;
}

interface UseChatStreamResult {
  isStreaming: boolean;
  sendMessage: (
    content: string,
    onDelta: (chunk: string) => void,
    onDone: (finalUid: string) => void,
    onError: (detail: string) => void,
    options?: SendMessageOptions,
  ) => Promise<void>;
}

interface ParsedEvent {
  event: string;
  data: string;
}

function parseSseBlock(block: string): ParsedEvent | null {
  const lines = block.split("\n");
  let eventName = "message";
  const dataParts: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataParts.push(line.slice(5).trim());
    }
  }
  if (dataParts.length === 0) return null;
  return { event: eventName, data: dataParts.join("\n") };
}

export function useChatStream(sessionUid: string): UseChatStreamResult {
  const [isStreaming, setIsStreaming] = useState<boolean>(false);

  const sendMessage = useCallback(
    async (
      content: string,
      onDelta: (chunk: string) => void,
      onDone: (finalUid: string) => void,
      onError: (detail: string) => void,
      options?: SendMessageOptions,
    ): Promise<void> => {
      setIsStreaming(true);

      try {
        const body: Record<string, unknown> = { content };
        if (options?.attachmentUids && options.attachmentUids.length > 0) {
          body.attachment_uids = options.attachmentUids;
        }
        if (options?.mentionedAgentUid) {
          body.mentioned_agent_uid = options.mentionedAgentUid;
        }
        const resp = await openStream(
          `/chat/sessions/${sessionUid}/messages`,
          { method: "POST", body },
        );

        if (!resp.ok || !resp.body) {
          onError(`請求失敗（${resp.status}）`);
          return;
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let finished = false;

        while (!finished) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // SSE 事件以雙換行分隔
          let idx: number;
          while ((idx = buffer.indexOf("\n\n")) !== -1) {
            const block = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);
            const parsed = parseSseBlock(block);
            if (!parsed) continue;

            try {
              const payload = JSON.parse(parsed.data) as Record<string, unknown>;
              if (parsed.event === "delta") {
                const chunk = typeof payload.content === "string"
                  ? payload.content
                  : "";
                if (chunk) onDelta(chunk);
              } else if (parsed.event === "done") {
                const uid = typeof payload.message_uid === "string"
                  ? payload.message_uid
                  : "";
                onDone(uid);
                finished = true;
                break;
              } else if (parsed.event === "error") {
                const detail = typeof payload.detail === "string"
                  ? payload.detail
                  : "串流發生錯誤";
                onError(detail);
                finished = true;
                break;
              }
            } catch {
              // JSON 解析失敗忽略該區塊
            }
          }
        }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "串流連線異常";
        onError(message);
      } finally {
        setIsStreaming(false);
      }
    },
    [sessionUid],
  );

  return { isStreaming, sendMessage };
}
