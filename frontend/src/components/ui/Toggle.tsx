"use client";

import React from "react";

interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  disabled?: boolean;
  className?: string;
}

export const Toggle = React.memo(function Toggle({
  checked,
  onChange,
  label,
  disabled = false,
  className = "",
}: ToggleProps): React.ReactNode {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    onChange(e.target.checked);
  };

  return (
    <label
      className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center ${
        disabled ? "cursor-not-allowed opacity-50" : ""
      } ${className}`}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={handleChange}
        disabled={disabled}
        aria-label={label}
        className="peer sr-only"
      />
      <span className="absolute inset-0 rounded-full bg-muted-bg transition-colors peer-checked:bg-primary" />
      <span className="relative inline-block h-4 w-4 translate-x-1 transform rounded-full bg-white transition-transform peer-checked:translate-x-6" />
    </label>
  );
});
