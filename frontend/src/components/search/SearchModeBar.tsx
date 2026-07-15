"use client";

import React, { useCallback } from "react";
import { Button } from "@/components/ui/Button";

export type SearchMode = "keyword" | "ai";

interface SearchModeBarProps {
  mode: SearchMode;
  onModeChange: (mode: SearchMode) => void;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
  isLoading?: boolean;
  placeholder?: string;
  /** 是否顯示左側模式選擇器；隱藏時等同純搜尋框（鎖定 keyword 行為由外部控制） */
  showModeSelect?: boolean;
}

// 搜尋框內建左側模式選擇器（類早期搜尋引擎）：select + input + AI 按鈕同一圓角容器
export const SearchModeBar = React.memo(function SearchModeBar({
  mode,
  onModeChange,
  value,
  onChange,
  onSubmit,
  isLoading = false,
  placeholder,
  showModeSelect = true,
}: SearchModeBarProps): React.ReactNode {
  const handleModeChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>): void => {
      onModeChange(e.target.value as SearchMode);
    },
    [onModeChange]
  );

  return (
    <form
      onSubmit={onSubmit}
      className="flex min-h-11 w-full items-center rounded-xl border border-input-border bg-input-bg transition-colors focus-within:border-input-focus focus-within:ring-2 focus-within:ring-input-focus/20"
    >
      {showModeSelect && (
        <div className="relative shrink-0 self-stretch border-r border-input-border">
          <select
            value={mode}
            onChange={handleModeChange}
            aria-label="搜尋模式"
            className="h-full w-28 appearance-none bg-transparent py-2 pl-3 pr-8 text-sm text-muted transition-colors hover:cursor-pointer hover:text-foreground focus:outline-none"
          >
            <option value="keyword">關鍵字</option>
            <option value="ai">AI 分析</option>
          </select>
          <svg
            className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted"
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            aria-hidden="true"
          >
            <path
              d="M6 8l4 4 4-4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      )}
      <input
        type="text"
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="min-w-0 flex-1 bg-transparent px-3 py-2 text-base text-foreground placeholder:text-muted focus:outline-none"
      />
      {mode === "ai" && (
        <Button
          type="submit"
          size="sm"
          loading={isLoading}
          disabled={value.trim().length === 0}
          className="mr-1 shrink-0"
        >
          AI 分析
        </Button>
      )}
    </form>
  );
});
