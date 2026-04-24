"use client";

import React from "react";

interface FilterChipProps {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}

export const FilterChip = React.memo(function FilterChip({
  active,
  onClick,
  children,
}: FilterChipProps): React.ReactNode {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-xl px-3 py-1 text-sm font-medium transition-colors hover:cursor-pointer ${
        active
          ? "bg-primary text-white"
          : "bg-muted-bg text-muted hover:bg-border"
      }`}
    >
      {children}
    </button>
  );
});
