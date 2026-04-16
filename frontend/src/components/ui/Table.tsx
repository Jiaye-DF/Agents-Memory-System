"use client";

import React from "react";

interface Column<T> {
  key: string;
  header: string;
  render?: (item: T) => React.ReactNode;
  className?: string;
}

interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (item: T) => string;
  cardRender?: (item: T) => React.ReactNode;
  emptyMessage?: string;
}

function TableInner<T>({
  columns,
  data,
  keyExtractor,
  cardRender,
  emptyMessage = "尚無資料",
}: TableProps<T>): React.ReactNode {
  if (data.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-muted">{emptyMessage}</div>
    );
  }

  return (
    <>
      {cardRender && (
        <div className="flex flex-col gap-4 md:hidden">
          {data.map((item) => (
            <div
              key={keyExtractor(item)}
              className="rounded-xl border border-border bg-card-bg p-4"
            >
              {cardRender(item)}
            </div>
          ))}
        </div>
      )}

      <div className={cardRender ? "hidden md:block" : "block"}>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border">
                {columns.map((col) => (
                  <th
                    key={col.key}
                    className={`px-4 py-3 text-left font-medium text-muted ${col.className ?? ""}`}
                  >
                    {col.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((item) => (
                <tr
                  key={keyExtractor(item)}
                  className="border-b border-border transition-colors hover:bg-muted-bg"
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`px-4 py-3 text-foreground ${col.className ?? ""}`}
                    >
                      {col.render
                        ? col.render(item)
                        : String((item as Record<string, unknown>)[col.key] ?? "")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

export const Table = React.memo(TableInner) as typeof TableInner;
