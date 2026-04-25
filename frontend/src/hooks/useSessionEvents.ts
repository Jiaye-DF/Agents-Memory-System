"use client";

/**
 * v1.3.2：訂閱 backend SSE endpoint `/chat/sessions/{uid}/events`
 *
 * 設計重點：
 * - 連線生命週期跟著 hook caller（Session 頁面）的 mount / unmount
 * - 連線成功（收到 `ready`）→ stop polling fallback
 * - SSE error → 5 秒後重連 + 啟動 30 秒 polling fallback
 * - 連續錯誤超過 MAX_SSE_FAILURES 後退化為僅 polling，避免無謂連線風暴
 * - 收到 `memory_updated` → invalidate `{type:"ChatMessages", id:"memories-${sessionUid}"}` tag
 *   觸發 `useListMemoriesQuery` refetch；`memory_failed` 僅 log（本版不顯示 UI badge）
 */

import { useEffect, useRef } from "react";
import { useDispatch } from "react-redux";
import { getAccessToken } from "@/lib/api/client";
import { chatApi } from "@/store/chatApi";
import { setSessionRecommendations } from "@/store/skillSuggestionSlice";
import type { AppDispatch } from "@/store/store";
import type { RecommendSuggestionItem } from "@/types";

export type SessionEventName =
  | "memory_updated"
  | "memory_failed"
  | "session_archived"
  | "skill_recommendation"
  | "ready";

const POLLING_INTERVAL_MS = 30 * 1000;
const RECONNECT_DELAY_MS = 5 * 1000;
const MAX_SSE_FAILURES = 5;

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

function buildEventsUrl(sessionUid: string, token: string): string {
  return `${API_BASE_URL}/chat/sessions/${sessionUid}/events?token=${encodeURIComponent(token)}`;
}

export function useSessionEvents(
  sessionUid: string | null | undefined,
): void {
  const dispatch = useDispatch<AppDispatch>();
  // 使用 ref 維護所有副作用資源，避免 effect deps 帶入 dispatch / token 變動造成爆量重連
  const esRef = useRef<EventSource | null>(null);
  const pollingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const failureCountRef = useRef<number>(0);
  // unmount 時將 abort 設為 true，避免 reconnect timer 觸發後仍嘗試建立 EventSource
  const abortedRef = useRef<boolean>(false);

  useEffect(() => {
    if (!sessionUid) {
      return;
    }

    abortedRef.current = false;
    failureCountRef.current = 0;

    const invalidateMemories = (): void => {
      dispatch(
        chatApi.util.invalidateTags([
          { type: "ChatMessages", id: `memories-${sessionUid}` },
        ]),
      );
    };

    const stopPolling = (): void => {
      if (pollingTimerRef.current !== null) {
        clearInterval(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
    };

    const startPolling = (): void => {
      if (pollingTimerRef.current !== null) return;
      pollingTimerRef.current = setInterval(() => {
        invalidateMemories();
      }, POLLING_INTERVAL_MS);
    };

    const closeEventSource = (): void => {
      if (esRef.current !== null) {
        try {
          esRef.current.close();
        } catch {
          // ignore
        }
        esRef.current = null;
      }
    };

    const scheduleReconnect = (): void => {
      if (reconnectTimerRef.current !== null) return;
      if (failureCountRef.current >= MAX_SSE_FAILURES) {
        // 超過閾值後退化為僅 polling，不再嘗試 SSE
        return;
      }
      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimerRef.current = null;
        if (abortedRef.current) return;
        connect();
      }, RECONNECT_DELAY_MS);
    };

    const connect = (): void => {
      if (abortedRef.current) return;

      const token = getAccessToken();
      if (!token) {
        // 沒有 token 不建連；由 polling 暫代（雖大多數情境也不會有資料）
        startPolling();
        return;
      }

      closeEventSource();

      let es: EventSource;
      try {
        es = new EventSource(buildEventsUrl(sessionUid, token));
      } catch (err) {
        console.warn("[useSessionEvents] 建立 EventSource 失敗", err);
        failureCountRef.current += 1;
        startPolling();
        scheduleReconnect();
        return;
      }
      esRef.current = es;

      es.addEventListener("ready", () => {
        // 連線成功握手 → 重置失敗計數、停掉 polling fallback
        failureCountRef.current = 0;
        stopPolling();
      });

      es.addEventListener("memory_updated", (event: MessageEvent) => {
        try {
          // payload 目前僅作 log，本版只需 invalidate tag 觸發 refetch
          JSON.parse(event.data);
        } catch {
          // ignore parse error
        }
        invalidateMemories();
      });

      es.addEventListener("memory_failed", (event: MessageEvent) => {
        // 本版不顯示 UI badge，僅 log；保留 listener 給後續 UI 接入
        try {
          const payload = JSON.parse(event.data);
          console.warn("[useSessionEvents] memory_failed", payload);
        } catch {
          console.warn("[useSessionEvents] memory_failed (unparsable)", event.data);
        }
      });

      // v1.3.6：Skill 推薦事件 → 暫存到 redux slice，由 UI 抽屜顯示
      es.addEventListener("skill_recommendation", (event: MessageEvent) => {
        try {
          const payload = JSON.parse(event.data) as {
            items?: RecommendSuggestionItem[];
          };
          const items = Array.isArray(payload?.items) ? payload.items : [];
          dispatch(
            setSessionRecommendations({
              sessionUid,
              items,
            }),
          );
        } catch (err) {
          console.warn("[useSessionEvents] skill_recommendation parse 失敗", err);
        }
      });

      es.onerror = (): void => {
        // EventSource 規格：onerror 會被頻繁觸發；這裡採保守策略 — 直接 close + reconnect
        failureCountRef.current += 1;
        closeEventSource();
        startPolling();
        scheduleReconnect();
      };
    };

    connect();

    return () => {
      abortedRef.current = true;
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      stopPolling();
      closeEventSource();
    };
    // 故意僅依賴 sessionUid：token 變動由內部 closure 於 connect 時即時讀取，
    // 避免 token refresh 觸發 effect re-run 而造成爆量重連
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionUid]);
}
