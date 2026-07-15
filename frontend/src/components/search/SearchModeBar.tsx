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
  /** 是否顯示左側模式切換鈕；隱藏時等同純搜尋框（鎖定 keyword 行為由外部控制） */
  showModeSelect?: boolean;
}

// 搜尋框內建左側模式切換鈕（類早期搜尋引擎）：切換鈕 + input + AI 按鈕同一圓角容器
// 單一按鈕輪替：預設「關鍵字查詢」，點一下切成「AI 查詢」，再點切回
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
  const handleModeToggle = useCallback((): void => {
    onModeChange(mode === "ai" ? "keyword" : "ai");
  }, [mode, onModeChange]);

  return (
    <form
      onSubmit={onSubmit}
      className="flex min-h-11 w-full items-center rounded-xl border border-input-border bg-input-bg transition-colors focus-within:border-input-focus focus-within:ring-2 focus-within:ring-input-focus/20"
    >
      {showModeSelect && (
        <button
          type="button"
          onClick={handleModeToggle}
          aria-pressed={mode === "ai"}
          aria-label="切換搜尋模式"
          className={`shrink-0 self-stretch rounded-l-xl border-r border-input-border px-3 text-sm font-medium transition-colors hover:cursor-pointer ${
            mode === "ai"
              ? "bg-primary/10 text-primary"
              : "bg-transparent text-muted hover:text-foreground"
          }`}
        >
          {mode === "ai" ? "AI 查詢" : "關鍵字查詢"}
        </button>
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
          查詢
        </Button>
      )}
    </form>
  );
});
