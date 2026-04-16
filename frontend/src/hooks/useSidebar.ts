"use client";

import { useState, useCallback, useEffect } from "react";

export type SidebarState = "expanded" | "collapsed" | "hidden";

interface UseSidebarReturn {
  state: SidebarState;
  isOverlay: boolean;
  toggle: () => void;
  close: () => void;
}

const STATE_CYCLE: Record<SidebarState, SidebarState> = {
  expanded: "collapsed",
  collapsed: "hidden",
  hidden: "expanded",
};

export function useSidebar(): UseSidebarReturn {
  const [state, setState] = useState<SidebarState>("expanded");
  const [isMobile, setIsMobile] = useState<boolean>(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 767px)");

    const handleChange = (e: MediaQueryListEvent | MediaQueryList): void => {
      setIsMobile(e.matches);
      if (e.matches) {
        setState("hidden");
      }
    };

    handleChange(mediaQuery);
    mediaQuery.addEventListener("change", handleChange);
    return (): void => {
      mediaQuery.removeEventListener("change", handleChange);
    };
  }, []);

  const toggle = useCallback((): void => {
    if (isMobile) {
      setState((prev) => (prev === "hidden" ? "expanded" : "hidden"));
    } else {
      setState((prev) => STATE_CYCLE[prev]);
    }
  }, [isMobile]);

  const close = useCallback((): void => {
    setState("hidden");
  }, []);

  return {
    state,
    isOverlay: isMobile && state !== "hidden",
    toggle,
    close,
  };
}
