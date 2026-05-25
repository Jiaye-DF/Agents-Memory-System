"use client";

import React, { useCallback } from "react";

import { useListTagsQuery } from "@/store/tagsApi";
import { TagChip } from "./TagChip";

interface TagFilterBarProps {
  selectedUids: string[];
  onChange: (next: string[]) => void;
  /** 預設 20，超過顯示「展開全部」。 */
  initialVisible?: number;
}

export const TagFilterBar = React.memo(function TagFilterBar({
  selectedUids,
  onChange,
  initialVisible = 20,
}: TagFilterBarProps): React.ReactNode {
  const { data, isLoading } = useListTagsQuery();
  const [showAll, setShowAll] = React.useState(false);

  const items = data?.items ?? [];
  const visibleItems = showAll ? items : items.slice(0, initialVisible);
  const extra = items.length - visibleItems.length;

  const handleToggle = useCallback(
    (tagUid: string): void => {
      if (selectedUids.includes(tagUid)) {
        onChange(selectedUids.filter((u) => u !== tagUid));
      } else {
        onChange([...selectedUids, tagUid]);
      }
    },
    [selectedUids, onChange]
  );

  const handleClear = useCallback((): void => {
    onChange([]);
  }, [onChange]);

  if (!isLoading && items.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="shrink-0 text-sm text-muted">Tag：</span>
      {visibleItems.map((t) => {
        const active = selectedUids.includes(t.tag_uid);
        return (
          <TagChip
            key={t.tag_uid}
            name={`${t.name}${t.usage_count > 0 ? ` (${t.usage_count})` : ""}`}
            active={active}
            onClick={() => handleToggle(t.tag_uid)}
            size="sm"
          />
        );
      })}
      {!showAll && extra > 0 && (
        <button
          type="button"
          onClick={() => setShowAll(true)}
          className="text-xs text-primary hover:cursor-pointer hover:underline"
        >
          展開全部（+{extra}）
        </button>
      )}
      {selectedUids.length > 0 && (
        <button
          type="button"
          onClick={handleClear}
          className="ml-1 text-xs text-muted hover:cursor-pointer hover:text-foreground hover:underline"
        >
          清除
        </button>
      )}
      {selectedUids.length > 1 && (
        <span className="text-xs text-muted">（AND 過濾）</span>
      )}
    </div>
  );
});
