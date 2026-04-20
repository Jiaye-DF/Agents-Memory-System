"use client";

import { useCallback, useState } from "react";

interface UseCursorPaginationResult {
  limit: number;
  cursor: string | null;
  cursorHistory: string[];
  hasPrev: boolean;
  setLimit: (limit: number) => void;
  handleNextPage: (nextCursor: string | null | undefined) => void;
  handlePrevPage: () => void;
  handleLimitChange: (newLimit: number) => void;
  reset: () => void;
}

export function useCursorPagination(
  initialLimit: number = 20
): UseCursorPaginationResult {
  const [limit, setLimitState] = useState<number>(initialLimit);
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);

  const handleNextPage = useCallback(
    (nextCursor: string | null | undefined): void => {
      if (!nextCursor) return;
      setCursorHistory((prev) => [...prev, cursor ?? ""]);
      setCursor(nextCursor);
    },
    [cursor]
  );

  const handlePrevPage = useCallback((): void => {
    setCursorHistory((prev) => {
      const newHistory = [...prev];
      const prevCursor = newHistory.pop();
      setCursor(prevCursor || null);
      return newHistory;
    });
  }, []);

  const handleLimitChange = useCallback((newLimit: number): void => {
    setLimitState(newLimit);
    setCursor(null);
    setCursorHistory([]);
  }, []);

  const setLimit = useCallback((newLimit: number): void => {
    setLimitState(newLimit);
  }, []);

  const reset = useCallback((): void => {
    setCursor(null);
    setCursorHistory([]);
  }, []);

  return {
    limit,
    cursor,
    cursorHistory,
    hasPrev: cursorHistory.length > 0,
    setLimit,
    handleNextPage,
    handlePrevPage,
    handleLimitChange,
    reset,
  };
}
