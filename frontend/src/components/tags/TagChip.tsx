"use client";

import React from "react";

interface TagChipProps {
  name: string;
  /** 不傳時不可點，僅顯示。 */
  onRemove?: () => void;
  /** 不傳時不可點，僅顯示。 */
  onClick?: () => void;
  size?: "sm" | "md";
  active?: boolean;
}

export const TagChip = React.memo(function TagChip({
  name,
  onRemove,
  onClick,
  size = "sm",
  active = false,
}: TagChipProps): React.ReactNode {
  const sizeCls =
    size === "md" ? "px-3 py-1 text-sm" : "px-2 py-0.5 text-xs";
  const interactive = onClick !== undefined;
  const colorCls = active
    ? "bg-primary text-white"
    : interactive
      ? "bg-muted-bg text-foreground hover:bg-border"
      : "bg-muted-bg text-muted";

  return (
    <span
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      onClick={onClick}
      onKeyDown={
        interactive
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick?.();
              }
            }
          : undefined
      }
      className={`inline-flex items-center gap-1 rounded-xl font-medium transition-colors ${sizeCls} ${colorCls} ${
        interactive ? "hover:cursor-pointer" : ""
      }`}
    >
      <span className="truncate max-w-[12rem]">{name}</span>
      {onRemove && (
        <button
          type="button"
          aria-label={`移除標籤 ${name}`}
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="-mr-0.5 ml-0.5 rounded-full px-1 text-muted hover:bg-border hover:text-foreground hover:cursor-pointer"
        >
          ×
        </button>
      )}
    </span>
  );
});


interface TagListProps {
  tags: { tag_uid: string; name: string }[];
  maxVisible?: number;
}

/** 列表 row 用：顯示前 N 個 + `+N` 摘要。 */
export const TagList = React.memo(function TagList({
  tags,
  maxVisible = 3,
}: TagListProps): React.ReactNode {
  if (tags.length === 0) return null;
  const visible = tags.slice(0, maxVisible);
  const extra = tags.length - visible.length;
  return (
    <div className="flex flex-wrap items-center gap-1">
      {visible.map((t) => (
        <TagChip key={t.tag_uid} name={t.name} />
      ))}
      {extra > 0 && (
        <span className="text-xs text-muted">+{extra}</span>
      )}
    </div>
  );
});
