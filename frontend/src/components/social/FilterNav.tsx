"use client";

import React, { useCallback } from "react";
import type { FilterScope } from "@/types";

interface FilterNavProps {
  value: FilterScope;
  onChange: (scope: FilterScope) => void;
  labels?: Partial<Record<FilterScope, string>>;
}

const DEFAULT_LABELS: Record<FilterScope, string> = {
  all: "全部",
  mine: "我的",
  favorites: "我的收藏",
};

const ORDER: FilterScope[] = ["all", "mine", "favorites"];

interface TabProps {
  scope: FilterScope;
  label: string;
  active: boolean;
  onSelect: (scope: FilterScope) => void;
}

const Tab = React.memo(function Tab({
  scope,
  label,
  active,
  onSelect,
}: TabProps): React.ReactNode {
  const handleClick = useCallback((): void => {
    onSelect(scope);
  }, [scope, onSelect]);

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-pressed={active}
      className={`rounded-xl px-4 py-2 text-base font-medium transition-colors hover:cursor-pointer ${
        active
          ? "bg-primary text-white shadow-sm"
          : "bg-muted-bg text-muted hover:bg-border"
      }`}
    >
      {label}
    </button>
  );
});

export const FilterNav = React.memo(function FilterNav({
  value,
  onChange,
  labels,
}: FilterNavProps): React.ReactNode {
  return (
    <div
      role="tablist"
      aria-label="資源範圍"
      className="inline-flex items-center gap-2"
    >
      {ORDER.map((scope) => (
        <Tab
          key={scope}
          scope={scope}
          label={labels?.[scope] ?? DEFAULT_LABELS[scope]}
          active={value === scope}
          onSelect={onChange}
        />
      ))}
    </div>
  );
});
