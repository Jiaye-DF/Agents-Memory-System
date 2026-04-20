"use client";

import React, { useCallback } from "react";

export interface SliderMark {
  value: number;
  label: string;
}

interface SliderProps {
  min: number;
  max: number;
  step?: number;
  value: number;
  onChange: (value: number) => void;
  marks?: SliderMark[];
  disabled?: boolean;
  id?: string;
  className?: string;
  ariaLabel?: string;
}

export const Slider = React.memo(function Slider({
  min,
  max,
  step = 1,
  value,
  onChange,
  marks,
  disabled = false,
  id,
  className = "",
  ariaLabel,
}: SliderProps): React.ReactNode {
  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      const next = Number(e.target.value);
      if (!Number.isNaN(next)) {
        onChange(next);
      }
    },
    [onChange]
  );

  return (
    <div className={`w-full ${className}`}>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={handleChange}
        aria-label={ariaLabel}
        className="h-2 w-full cursor-pointer appearance-none rounded-xl bg-muted-bg accent-primary disabled:cursor-not-allowed disabled:opacity-50"
      />
      {marks && marks.length > 0 && (
        <div className="mt-2 flex justify-between text-sm text-muted">
          {marks.map((m) => (
            <span key={m.value}>{m.label}</span>
          ))}
        </div>
      )}
    </div>
  );
});
