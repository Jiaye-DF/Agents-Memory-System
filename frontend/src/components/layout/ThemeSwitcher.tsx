"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { useTheme } from "@/hooks/useTheme";

const THEME_LABELS: Record<string, string> = {
  light: "淺色",
  dark: "深色",
  cool: "冷色系",
  warm: "暖色系",
  purple: "粉紫色",
};

const THEME_ICONS: Record<string, string> = {
  light: "☀️",
  dark: "🌙",
  cool: "❄️",
  warm: "🔥",
  purple: "💜",
};

export const ThemeSwitcher = React.memo(function ThemeSwitcher(): React.ReactNode {
  const { theme, setTheme, themes } = useTheme();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent): void {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleToggle = useCallback((): void => {
    setOpen((prev) => !prev);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={handleToggle}
        className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-xl text-foreground transition-colors hover:cursor-pointer hover:bg-muted-bg"
        aria-label="切換主題"
        title="切換主題"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="2" />
          <path
            d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      </button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 w-36 overflow-hidden rounded-xl border border-border bg-card-bg shadow-lg">
          {themes.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => {
                setTheme(t);
                setOpen(false);
              }}
              className={`flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm transition-colors hover:cursor-pointer hover:bg-muted-bg ${
                theme === t ? "font-semibold text-primary" : "text-foreground"
              }`}
            >
              <span>{THEME_ICONS[t]}</span>
              <span>{THEME_LABELS[t]}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
});
