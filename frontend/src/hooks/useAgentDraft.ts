"use client";

import { useCallback, useEffect, useRef } from "react";

const DRAFT_KEY = "agent-draft";
const THROTTLE_MS = 2000;

export interface UseAgentDraftReturn<T> {
  loadDraft: () => T | null;
  saveDraft: (data: T) => void;
  clearDraft: () => void;
}

/**
 * 在 localStorage 管理單一 Agent 新增草稿。
 * - key 固定為 `agent-draft`（每位使用者僅一份）
 * - saveDraft 以 2 秒節流寫入，避免頻繁 I/O
 * - 僅在瀏覽器端執行，SSR 安全
 */
export function useAgentDraft<T>(): UseAgentDraftReturn<T> {
  const lastSaveRef = useRef<number>(0);
  const pendingRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestDataRef = useRef<T | null>(null);

  const flush = useCallback((): void => {
    if (typeof window === "undefined") return;
    if (latestDataRef.current === null) return;
    try {
      window.localStorage.setItem(
        DRAFT_KEY,
        JSON.stringify(latestDataRef.current)
      );
      lastSaveRef.current = Date.now();
    } catch {
      // localStorage 可能被停用或容量不足，忽略
    }
  }, []);

  const saveDraft = useCallback(
    (data: T): void => {
      if (typeof window === "undefined") return;
      latestDataRef.current = data;
      const now = Date.now();
      const elapsed = now - lastSaveRef.current;

      if (pendingRef.current) {
        clearTimeout(pendingRef.current);
        pendingRef.current = null;
      }

      if (elapsed >= THROTTLE_MS) {
        flush();
      } else {
        pendingRef.current = setTimeout(() => {
          pendingRef.current = null;
          flush();
        }, THROTTLE_MS - elapsed);
      }
    },
    [flush]
  );

  const loadDraft = useCallback((): T | null => {
    if (typeof window === "undefined") return null;
    try {
      const raw = window.localStorage.getItem(DRAFT_KEY);
      if (!raw) return null;
      return JSON.parse(raw) as T;
    } catch {
      return null;
    }
  }, []);

  const clearDraft = useCallback((): void => {
    if (typeof window === "undefined") return;
    if (pendingRef.current) {
      clearTimeout(pendingRef.current);
      pendingRef.current = null;
    }
    latestDataRef.current = null;
    try {
      window.localStorage.removeItem(DRAFT_KEY);
    } catch {
      // 忽略
    }
  }, []);

  useEffect(() => {
    return (): void => {
      if (pendingRef.current) {
        clearTimeout(pendingRef.current);
        pendingRef.current = null;
      }
    };
  }, []);

  return { loadDraft, saveDraft, clearDraft };
}
