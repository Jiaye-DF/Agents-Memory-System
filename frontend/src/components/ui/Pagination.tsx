"use client";

import React, { useCallback } from "react";
import { Button } from "./Button";

interface PaginationProps {
  hasNext: boolean;
  hasPrev: boolean;
  limit: number;
  onNextPage: () => void;
  onPrevPage: () => void;
  onLimitChange: (limit: number) => void;
}

const LIMIT_OPTIONS = [10, 20, 50] as const;

export const Pagination = React.memo(function Pagination({
  hasNext,
  hasPrev,
  limit,
  onNextPage,
  onPrevPage,
  onLimitChange,
}: PaginationProps): React.ReactNode {
  const handleLimitChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>): void => {
      onLimitChange(Number(e.target.value));
    },
    [onLimitChange]
  );

  return (
    <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
      <div className="flex items-center gap-2">
        <label
          htmlFor="page-limit"
          className="text-base text-muted"
        >
          每頁顯示
        </label>
        <select
          id="page-limit"
          value={limit}
          onChange={handleLimitChange}
          className="min-h-11 rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground hover:cursor-pointer focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
        >
          {LIMIT_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option} 筆
            </option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={!hasPrev}
          onClick={onPrevPage}
        >
          上一頁
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={!hasNext}
          onClick={onNextPage}
        >
          下一頁
        </Button>
      </div>
    </div>
  );
});
