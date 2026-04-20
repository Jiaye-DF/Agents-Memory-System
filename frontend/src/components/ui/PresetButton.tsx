"use client";

import React from "react";

interface PresetButtonProps {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  disabled?: boolean;
}

export const PresetButton = React.memo(function PresetButton({
  active,
  onClick,
  children,
  disabled = false,
}: PresetButtonProps): React.ReactNode {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`rounded-xl border px-3 py-1.5 text-sm font-medium transition-colors hover:cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 ${
        active
          ? "border-primary bg-primary text-white"
          : "border-border bg-muted-bg text-foreground hover:bg-border"
      }`}
    >
      {children}
    </button>
  );
});
