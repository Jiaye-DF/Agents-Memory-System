"use client";

import { useSyncExternalStore, useCallback } from "react";

type Theme = "light" | "dark" | "cool" | "warm" | "purple";

const THEME_KEY = "agents-platform-theme";
const VALID_THEMES: readonly Theme[] = ["light", "dark", "cool", "warm", "purple"];

let listeners: Array<() => void> = [];

function emitChange(): void {
  for (const listener of listeners) {
    listener();
  }
}

function subscribe(listener: () => void): () => void {
  listeners = [...listeners, listener];
  return (): void => {
    listeners = listeners.filter((l) => l !== listener);
  };
}

function getSnapshot(): Theme {
  const stored = localStorage.getItem(THEME_KEY);
  if (VALID_THEMES.includes(stored as Theme)) {
    return stored as Theme;
  }
  return "light";
}

function getServerSnapshot(): Theme {
  return "light";
}

function applyThemeToDOM(theme: Theme): void {
  const html = document.documentElement;
  html.classList.remove("dark");
  html.removeAttribute("data-theme");

  if (theme === "dark") {
    html.classList.add("dark");
  } else if (theme !== "light") {
    html.setAttribute("data-theme", theme);
  }
}

export function useTheme(): {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  themes: readonly Theme[];
} {
  const theme = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const setTheme = useCallback((newTheme: Theme): void => {
    localStorage.setItem(THEME_KEY, newTheme);
    applyThemeToDOM(newTheme);
    emitChange();
  }, []);

  return { theme, setTheme, themes: VALID_THEMES };
}
