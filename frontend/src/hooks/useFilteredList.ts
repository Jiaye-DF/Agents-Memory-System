"use client";

import { useMemo } from "react";

type FieldAccessor<T> = (item: T) => string | null | undefined;

interface UseFilteredListOptions<T> {
  items: T[];
  searchTerm: string;
  searchFields: ReadonlyArray<keyof T | FieldAccessor<T>>;
  /** 額外過濾條件；全部為 true 才保留項目 */
  predicates?: ReadonlyArray<(item: T) => boolean>;
}

function readField<T>(
  item: T,
  field: keyof T | FieldAccessor<T>
): string {
  const raw =
    typeof field === "function"
      ? field(item)
      : (item[field] as unknown);
  if (raw === null || raw === undefined) return "";
  return String(raw).toLowerCase();
}

export function useFilteredList<T>({
  items,
  searchTerm,
  searchFields,
  predicates,
}: UseFilteredListOptions<T>): T[] {
  return useMemo((): T[] => {
    const term = searchTerm.trim().toLowerCase();
    return items.filter((item) => {
      if (predicates && !predicates.every((p) => p(item))) {
        return false;
      }
      if (!term) return true;
      return searchFields.some((field) =>
        readField(item, field).includes(term)
      );
    });
  }, [items, searchTerm, searchFields, predicates]);
}
