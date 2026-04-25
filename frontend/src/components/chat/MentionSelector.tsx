"use client";

import React, {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import type { SessionAgent } from "@/types";

/**
 * v1.3.3 @mention selector：偵測輸入框 `@` 字元觸發浮層，
 * 列出該 session 已掛 Agent；鍵盤 ↑ / ↓ / Enter / Esc 操作。
 *
 * 確認後將 `@AgentName ` 插入文字，並呼叫 onSelect(agent_uid) 通知 parent
 * 以同步送出 payload 的 mentioned_agent_uid。
 *
 * 設計上以 controlled 方式吃 textarea ref + 目前文字；不支援多重 mention
 * （決策 #3：序列；一次只能 mention 一個）。當使用者刪除 mention 文字、
 * parent 應呼叫 clearMention() 讓 mentioned_agent_uid 同步清空。
 */

export interface MentionSelectorHandle {
  /** parent 在 textarea onKeyDown / onChange 時呼叫，攔截上下鍵與 Enter / Esc。
   *  回傳 true 代表事件已被 selector 處理（parent 應 preventDefault 後忽略）。 */
  handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>): boolean;
}

interface MentionSelectorProps {
  agents: SessionAgent[];
  value: string;
  onChange: (next: string) => void;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  /** 選中後 callback；agentUid=null 代表 mention 被清空。 */
  onSelect: (agentUid: string | null) => void;
}

interface MentionContext {
  trigger: number; // @ 在文字中的 index
  query: string; // @ 後到游標的字串
}

function findMentionContext(
  text: string,
  caret: number,
): MentionContext | null {
  // 從 caret 往前找最近的 '@'，且 '@' 前必須為空白 / 開頭。
  if (caret <= 0) return null;
  let i = caret - 1;
  while (i >= 0) {
    const ch = text[i];
    if (ch === "@") {
      const prev = i === 0 ? "" : text[i - 1];
      if (prev === "" || /\s/.test(prev)) {
        const query = text.slice(i + 1, caret);
        // 若 query 內含空白則視為已完結 mention，不再彈出
        if (/\s/.test(query)) return null;
        return { trigger: i, query };
      }
      return null;
    }
    if (/\s/.test(ch)) return null;
    i -= 1;
  }
  return null;
}

export const MentionSelector = forwardRef<
  MentionSelectorHandle,
  MentionSelectorProps
>(function MentionSelector(
  { agents, value, onChange, textareaRef, onSelect }: MentionSelectorProps,
  ref,
): React.ReactNode {
  const [open, setOpen] = useState<boolean>(false);
  const [activeIdx, setActiveIdx] = useState<number>(0);
  const [context, setContext] = useState<MentionContext | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // 過濾候選：不做模糊比對，採前綴 match（決策 #8）
  const candidates = useMemo((): SessionAgent[] => {
    if (!context) return [];
    const q = context.query.toLowerCase();
    if (q === "") return agents;
    return agents.filter((a) =>
      (a.agent_name ?? "").toLowerCase().startsWith(q),
    );
  }, [agents, context]);

  // 監聽 value / caret 變動更新 mention 狀態
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) {
      setOpen(false);
      setContext(null);
      return;
    }
    const caret = el.selectionStart ?? value.length;
    const ctx = findMentionContext(value, caret);
    if (ctx === null) {
      setOpen(false);
      setContext(null);
      return;
    }
    setContext(ctx);
    setOpen(candidates.length > 0 || ctx.query === "");
    setActiveIdx(0);
  }, [value, textareaRef, candidates.length]);

  const commitSelection = useCallback(
    (agent: SessionAgent): void => {
      if (!context) return;
      const before = value.slice(0, context.trigger);
      const after = value.slice(context.trigger + 1 + context.query.length);
      const insertion = `@${agent.agent_name ?? "Agent"} `;
      const next = `${before}${insertion}${after}`;
      onChange(next);
      onSelect(agent.agent_uid);
      setOpen(false);
      setContext(null);
      // 將 caret 移到 insertion 後
      setTimeout(() => {
        const el = textareaRef.current;
        if (!el) return;
        const pos = before.length + insertion.length;
        el.focus();
        el.setSelectionRange(pos, pos);
      }, 0);
    },
    [context, value, onChange, onSelect, textareaRef],
  );

  useImperativeHandle(
    ref,
    (): MentionSelectorHandle => ({
      handleKeyDown(event) {
        if (!open || candidates.length === 0) return false;
        if (event.key === "ArrowDown") {
          event.preventDefault();
          setActiveIdx((idx) => (idx + 1) % candidates.length);
          return true;
        }
        if (event.key === "ArrowUp") {
          event.preventDefault();
          setActiveIdx(
            (idx) => (idx - 1 + candidates.length) % candidates.length,
          );
          return true;
        }
        if (event.key === "Enter") {
          event.preventDefault();
          const target = candidates[activeIdx];
          if (target) commitSelection(target);
          return true;
        }
        if (event.key === "Escape") {
          event.preventDefault();
          setOpen(false);
          setContext(null);
          return true;
        }
        return false;
      },
    }),
    [open, candidates, activeIdx, commitSelection],
  );

  if (!open || candidates.length === 0) return null;

  return (
    <div
      ref={wrapperRef}
      className="absolute bottom-full left-0 z-30 mb-2 w-72 max-h-60 overflow-y-auto rounded-xl border border-border bg-card-bg shadow-lg"
      role="listbox"
      aria-label="選擇要 mention 的 Agent"
    >
      <div className="border-b border-border px-3 py-1 text-xs text-muted">
        選擇要指定回覆的 Agent
      </div>
      <ul className="py-1">
        {candidates.map((agent, idx) => {
          const isActive = idx === activeIdx;
          return (
            <li
              key={agent.session_agent_uid}
              role="option"
              aria-selected={isActive}
            >
              <button
                type="button"
                onMouseDown={(e) => {
                  // 用 mousedown 避免 textarea 失焦讓 caret 跑掉
                  e.preventDefault();
                  commitSelection(agent);
                }}
                onMouseEnter={() => setActiveIdx(idx)}
                className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm transition-colors hover:cursor-pointer ${
                  isActive
                    ? "bg-primary/10 text-foreground"
                    : "text-foreground hover:bg-muted-bg"
                }`}
              >
                <span className="truncate">@{agent.agent_name ?? "Agent"}</span>
                {agent.role === "primary" && (
                  <span className="ml-2 shrink-0 rounded-full bg-primary/15 px-2 py-0.5 text-xs text-primary">
                    primary
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
});
