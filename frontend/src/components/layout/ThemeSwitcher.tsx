"use client";

import React, { useCallback } from "react";
import { useTheme } from "@/hooks/useTheme";
import { useDialog } from "@/hooks/useDialog";
import { ThemeChooser } from "@/components/theme/ThemeChooser";

type Theme = "light" | "dark" | "cool" | "warm" | "purple";

export const ThemeSwitcher = React.memo(function ThemeSwitcher(): React.ReactNode {
  const { theme, revertTo } = useTheme();
  const { showContentDialog } = useDialog();

  const handleOpen = useCallback((): void => {
    const originalTheme: Theme = theme;
    showContentDialog({
      title: "選擇佈景主題",
      size: "lg",
      content: <ThemeChooser />,
      cancelLabel: "取消",
      onCancel: (): void => {
        revertTo(originalTheme);
      },
    });
  }, [theme, revertTo, showContentDialog]);

  return (
    <button
      type="button"
      onClick={handleOpen}
      className="flex min-h-11 min-w-11 items-center justify-center rounded-xl text-foreground transition-colors hover:cursor-pointer hover:bg-muted-bg"
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
  );
});
