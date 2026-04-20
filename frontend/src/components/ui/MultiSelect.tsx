"use client";

import React, { useCallback, useMemo, useState } from "react";

export interface MultiSelectOption {
  value: string;
  label: string;
  description?: string;
}

interface MultiSelectProps {
  options: MultiSelectOption[];
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
  maxSelected?: number;
  emptyMessage?: string;
  limitReachedMessage?: string;
}

export const MultiSelect = React.memo(function MultiSelect({
  options,
  value,
  onChange,
  placeholder = "搜尋...",
  disabled = false,
  maxSelected,
  emptyMessage = "沒有可選項目",
  limitReachedMessage,
}: MultiSelectProps): React.ReactNode {
  const [search, setSearch] = useState<string>("");

  const optionMap = useMemo((): Map<string, MultiSelectOption> => {
    const map = new Map<string, MultiSelectOption>();
    for (const opt of options) {
      map.set(opt.value, opt);
    }
    return map;
  }, [options]);

  const selectedSet = useMemo(
    (): Set<string> => new Set(value),
    [value]
  );

  const filteredOptions = useMemo((): MultiSelectOption[] => {
    const term = search.trim().toLowerCase();
    return options.filter((o) => {
      if (selectedSet.has(o.value)) return false;
      if (!term) return true;
      return (
        o.label.toLowerCase().includes(term) ||
        (o.description ?? "").toLowerCase().includes(term)
      );
    });
  }, [options, search, selectedSet]);

  const limitReached =
    typeof maxSelected === "number" && value.length >= maxSelected;

  const handleSearch = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setSearch(e.target.value);
    },
    []
  );

  const handleAdd = useCallback(
    (val: string): void => {
      if (limitReached) return;
      if (selectedSet.has(val)) return;
      onChange([...value, val]);
    },
    [limitReached, onChange, selectedSet, value]
  );

  const handleRemove = useCallback(
    (val: string): void => {
      onChange(value.filter((v) => v !== val));
    },
    [onChange, value]
  );

  return (
    <div className="flex flex-col gap-2">
      {value.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {value.map((v) => {
            const opt = optionMap.get(v);
            return (
              <span
                key={v}
                className="inline-flex items-center gap-1 rounded-xl bg-primary/10 px-3 py-1 text-sm font-medium text-primary"
              >
                <span>{opt?.label ?? v}</span>
                <button
                  type="button"
                  onClick={() => handleRemove(v)}
                  disabled={disabled}
                  className="inline-flex h-4 w-4 items-center justify-center rounded-full text-primary hover:cursor-pointer hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label={`移除 ${opt?.label ?? v}`}
                >
                  ×
                </button>
              </span>
            );
          })}
        </div>
      )}

      <input
        type="text"
        value={search}
        onChange={handleSearch}
        placeholder={placeholder}
        disabled={disabled}
        className="min-h-[44px] w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20 disabled:cursor-not-allowed disabled:opacity-50"
      />

      {limitReached && limitReachedMessage && (
        <p className="text-sm text-warning">{limitReachedMessage}</p>
      )}

      <div className="max-h-56 overflow-y-auto rounded-xl border border-input-border bg-input-bg">
        {filteredOptions.length === 0 ? (
          <div className="px-3 py-4 text-center text-sm text-muted">
            {emptyMessage}
          </div>
        ) : (
          <ul className="flex flex-col">
            {filteredOptions.map((opt) => (
              <li key={opt.value}>
                <button
                  type="button"
                  onClick={() => handleAdd(opt.value)}
                  disabled={disabled || limitReached}
                  className="flex w-full items-start gap-2 px-3 py-2 text-left text-base text-foreground transition-colors hover:cursor-pointer hover:bg-muted-bg disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{opt.label}</div>
                    {opt.description && (
                      <div className="line-clamp-1 text-sm text-muted">
                        {opt.description}
                      </div>
                    )}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
});
