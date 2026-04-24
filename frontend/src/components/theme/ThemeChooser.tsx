"use client";

import React, { useCallback } from "react";
import { THEME_SERIES } from "@/theme/series";
import type { ThemeItem } from "@/theme/types";
import { useTheme } from "@/hooks/useTheme";

type Theme = "light" | "dark" | "cool" | "warm" | "purple";

interface ThemeCardProps {
  item: ThemeItem;
  selected: boolean;
  onSelect: (id: Theme) => void;
}

const ThemeCard = React.memo(function ThemeCard({
  item,
  selected,
  onSelect,
}: ThemeCardProps): React.ReactNode {
  const handleClick = useCallback((): void => {
    onSelect(item.id as Theme);
  }, [item.id, onSelect]);

  return (
    <button
      type="button"
      onClick={handleClick}
      className={`group flex flex-col gap-2 rounded-xl border p-3 text-left transition-all hover:cursor-pointer hover:border-primary ${
        selected ? "border-primary ring-2 ring-primary" : "border-border"
      }`}
      aria-pressed={selected}
    >
      <div
        className="relative h-16 w-full overflow-hidden rounded-xl border border-border"
        style={{ backgroundColor: item.colors.background }}
      >
        <div
          className="absolute inset-y-0 left-0 w-1/3"
          style={{ backgroundColor: item.colors.primary }}
        />
        <div
          className="absolute inset-y-0 left-1/3 w-1/4"
          style={{ backgroundColor: item.colors.accent }}
        />
        <div
          className="absolute bottom-1 right-2 text-2xl leading-none"
          style={{ color: item.colors.foreground }}
        >
          {item.icon}
        </div>
      </div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-base font-semibold text-foreground">
          {item.labelZh}
        </span>
        <span className="text-sm text-muted">{item.labelEn}</span>
      </div>
    </button>
  );
});

export const ThemeChooser = React.memo(function ThemeChooser(): React.ReactNode {
  const { theme, applyTheme } = useTheme();

  const handleSelect = useCallback(
    (id: Theme): void => {
      applyTheme(id);
    },
    [applyTheme]
  );

  return (
    <div className="flex flex-col gap-6">
      {THEME_SERIES.map((series) => (
        <div key={series.key} className="flex flex-col gap-3">
          <div className="flex items-baseline gap-2">
            <h4 className="text-base font-semibold text-foreground">
              {series.labelZh}
            </h4>
            <span className="text-sm text-muted">{series.labelEn}</span>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {series.items.map((item) => (
              <ThemeCard
                key={item.id}
                item={item}
                selected={item.id === theme}
                onSelect={handleSelect}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
});
