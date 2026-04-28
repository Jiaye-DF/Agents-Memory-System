"use client";

import React, { useCallback, useState } from "react";
import Link from "next/link";
import { useGetRankingsQuery } from "@/store/dashboardApi";
import { PageLoading } from "@/components/ui/Loading";
import { SocialMetrics } from "@/components/social/SocialMetrics";
import { FavoriteButton } from "@/components/social/FavoriteButton";
import type { RankingItem, RankingType, RankingTypeFilter } from "@/types";

const TYPE_TABS: {
  key: RankingTypeFilter;
  label: string;
}[] = [
  { key: "all", label: "全部" },
  { key: "agent", label: "Agents" },
  { key: "skill", label: "Skills" },
  { key: "script", label: "Scripts" },
];

const TYPE_LABEL: Record<RankingType, string> = {
  agent: "Agent",
  skill: "Skill",
  script: "Script",
};

const EMPTY_TYPE_LABEL: Record<RankingTypeFilter, string> = {
  all: "資源",
  agent: "Agent",
  skill: "Skill",
  script: "Script",
};

const TYPE_HREF: Record<RankingType, string> = {
  agent: "/agents",
  skill: "/skills",
  script: "/scripts",
};

function TypeIcon({ type }: { type: RankingType }): React.ReactNode {
  if (type === "agent") {
    return (
      <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden>
        <circle cx="10" cy="7" r="3" stroke="currentColor" strokeWidth="1.5" />
        <path
          d="M4 17C4 13.6863 6.68629 11 10 11C13.3137 11 16 13.6863 16 17"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
    );
  }
  if (type === "skill") {
    return (
      <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden>
        <path
          d="M10 3L12.5 8H17L13.5 11.5L15 17L10 13.5L5 17L6.5 11.5L3 8H7.5L10 3Z"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M6 4L2 10L6 16"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M14 4L18 10L14 16"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M12 3L8 17"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

interface RankingTypeTabsProps {
  value: RankingTypeFilter;
  onChange: (next: RankingTypeFilter) => void;
}

const RankingTypeTabs = React.memo(function RankingTypeTabs({
  value,
  onChange,
}: RankingTypeTabsProps): React.ReactNode {
  return (
    <div
      role="tablist"
      aria-label="排行榜類型"
      className="inline-flex flex-wrap items-center gap-2"
    >
      {TYPE_TABS.map((t) => {
        const active = value === t.key;
        return (
          <button
            key={t.key}
            type="button"
            role="tab"
            tabIndex={active ? 0 : -1}
            aria-selected={active}
            onClick={() => onChange(t.key)}
            className={`rounded-xl px-3 py-1.5 text-sm font-medium transition-colors hover:cursor-pointer ${
              active
                ? "bg-primary text-white shadow-sm"
                : "bg-muted-bg text-muted hover:bg-border"
            }`}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
});

interface RankingRowProps {
  item: RankingItem;
}

const RankingRow = React.memo(function RankingRow({
  item,
}: RankingRowProps): React.ReactNode {
  return (
    <div className="flex flex-col gap-2 px-4 py-3 transition-colors hover:bg-muted-bg/40 md:flex-row md:items-center md:gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span
            className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
            title={TYPE_LABEL[item.type]}
          >
            <TypeIcon type={item.type} />
          </span>
          <Link
            href={`${TYPE_HREF[item.type]}/${item.uid}`}
            className="min-w-0 truncate text-base font-semibold text-foreground hover:cursor-pointer hover:text-primary hover:underline"
          >
            {item.name}
          </Link>
          <span className="shrink-0 rounded-xl bg-muted-bg px-2 py-0.5 text-xs font-medium text-muted">
            {TYPE_LABEL[item.type]}
          </span>
        </div>
        {item.description && (
          <p className="mt-1 line-clamp-1 text-sm text-muted">
            {item.description}
          </p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2 md:ml-auto">
        <SocialMetrics
          favoriteCount={item.favorite_count}
          downloadCount={item.download_count}
        />
        <FavoriteButton
          resourceType={item.type}
          resourceUid={item.uid}
          isFavorited={item.is_favorited}
          size="sm"
        />
      </div>
    </div>
  );
});

export const RankingPanel = React.memo(
  function RankingPanel(): React.ReactNode {
    const [typeFilter, setTypeFilter] = useState<RankingTypeFilter>("all");

    const { data, isLoading, isFetching } = useGetRankingsQuery({
      type: typeFilter,
      orderBy: "download_count",
    });

    const handleTypeChange = useCallback((next: RankingTypeFilter): void => {
      setTypeFilter(next);
    }, []);

    const items = data?.items ?? [];
    const emptyLabel = EMPTY_TYPE_LABEL[typeFilter];

    return (
      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-foreground">最常使用</h2>
          <RankingTypeTabs value={typeFilter} onChange={handleTypeChange} />
        </div>

        <p className="text-sm text-muted">
          根據你擁有的資源統計；公開熱度／收藏排行將整合至公開
          Agents／Skills／Scripts 頁籤。
        </p>

        <div className="overflow-hidden rounded-xl bg-card-bg shadow-sm">
          {isLoading || (isFetching && items.length === 0) ? (
            <PageLoading />
          ) : items.length === 0 ? (
            <div className="px-6 py-10 text-center text-muted">
              你還沒有任何 {emptyLabel} — 去建立一個吧
            </div>
          ) : (
            <div className="divide-y divide-border">
              {items.map((item) => (
                <RankingRow
                  key={`${item.type}:${item.uid}`}
                  item={item}
                />
              ))}
            </div>
          )}
        </div>
      </section>
    );
  },
);
