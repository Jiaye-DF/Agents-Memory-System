"use client";

import React, { useCallback, useMemo, useRef, useState } from "react";

import { useListTagsQuery } from "@/store/tagsApi";
import type { TagSummary } from "@/types";
import { TagChip } from "./TagChip";

interface TagInputProps {
  value: TagSummary[];
  onChange: (next: TagSummary[]) => void;
  placeholder?: string;
  disabled?: boolean;
  /** 上限張數（前端 hint），預設 20 對齊後端 MAX_TAGS_PER_ENTITY。 */
  maxTags?: number;
}

/** Tag 輸入元件：autocomplete + Enter 新增 + Backspace 移除。

  注意：本元件不會自己呼叫 createTag，只負責收集 `TagSummary[]`，
  由 caller 在送出時透過 `useSetEntityTagsMutation` 帶 `{ names: [...] }`
  讓後端走 find-or-create。
*/
export const TagInput = React.memo(function TagInput({
  value,
  onChange,
  placeholder = "輸入 tag 後按 Enter，例：資料分析",
  disabled = false,
  maxTags = 20,
}: TagInputProps): React.ReactNode {
  const [input, setInput] = useState("");
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const { data } = useListTagsQuery({ q: input.trim() || undefined });

  const selectedNames = useMemo(
    (): Set<string> => new Set(value.map((t) => t.name.toLowerCase())),
    [value]
  );

  const suggestions = useMemo(() => {
    const items = data?.items ?? [];
    return items
      .filter((t) => !selectedNames.has(t.name.toLowerCase()))
      .slice(0, 8);
  }, [data, selectedNames]);

  const addByName = useCallback(
    (raw: string): void => {
      const name = raw.trim();
      if (!name) return;
      if (selectedNames.has(name.toLowerCase())) return;
      if (value.length >= maxTags) return;
      // 新加的 tag 暫用 name 當 placeholder uid（送出時由後端 find-or-create 回真 uid）
      onChange([...value, { tag_uid: `__new__:${name}`, name }]);
      setInput("");
    },
    [value, onChange, selectedNames, maxTags]
  );

  const addByExisting = useCallback(
    (t: { tag_uid: string; name: string }): void => {
      if (value.length >= maxTags) return;
      onChange([...value, { tag_uid: t.tag_uid, name: t.name }]);
      setInput("");
      inputRef.current?.focus();
    },
    [value, onChange, maxTags]
  );

  const handleRemove = useCallback(
    (tagUid: string): void => {
      onChange(value.filter((t) => t.tag_uid !== tagUid));
    },
    [value, onChange]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>): void => {
      if (e.key === "Enter") {
        e.preventDefault();
        if (input.trim()) {
          addByName(input);
        }
      } else if (e.key === "Backspace" && input === "" && value.length > 0) {
        e.preventDefault();
        onChange(value.slice(0, -1));
      }
    },
    [input, value, onChange, addByName]
  );

  return (
    <div className="relative">
      <div
        className={`flex flex-wrap items-center gap-1.5 rounded-xl border border-border bg-input-bg px-2 py-1.5 ${
          disabled ? "opacity-60" : ""
        }`}
        onClick={() => inputRef.current?.focus()}
      >
        {value.map((t) => (
          <TagChip
            key={t.tag_uid}
            name={t.name}
            onRemove={disabled ? undefined : () => handleRemove(t.tag_uid)}
          />
        ))}
        <input
          ref={inputRef}
          type="text"
          value={input}
          disabled={disabled || value.length >= maxTags}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setTimeout(() => setFocused(false), 150)}
          placeholder={value.length === 0 ? placeholder : ""}
          className="min-w-[10rem] flex-1 bg-transparent text-sm outline-none placeholder:text-muted disabled:cursor-not-allowed"
        />
      </div>

      {focused && (suggestions.length > 0 || input.trim()) && (
        <div className="absolute left-0 right-0 z-10 mt-1 max-h-60 overflow-auto rounded-xl border border-border bg-card-bg shadow-lg">
          {suggestions.map((t) => (
            <button
              key={t.tag_uid}
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                addByExisting(t);
              }}
              className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-muted-bg hover:cursor-pointer"
            >
              <span>{t.name}</span>
              <span className="text-xs text-muted">{t.usage_count} 次</span>
            </button>
          ))}
          {input.trim() &&
            !suggestions.some(
              (s) => s.name.toLowerCase() === input.trim().toLowerCase()
            ) && (
              <button
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                  addByName(input);
                }}
                className="flex w-full items-center gap-2 border-t border-border px-3 py-2 text-left text-sm text-primary hover:bg-muted-bg hover:cursor-pointer"
              >
                + 新增「{input.trim()}」
              </button>
            )}
        </div>
      )}

      {value.length >= maxTags && (
        <p className="mt-1 text-xs text-muted">
          已達上限 {maxTags} 個 tag
        </p>
      )}
    </div>
  );
});
