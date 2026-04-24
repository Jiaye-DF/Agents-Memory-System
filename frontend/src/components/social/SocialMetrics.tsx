"use client";

import React from "react";

interface SocialMetricsProps {
  favoriteCount: number;
  downloadCount?: number;
  className?: string;
}

export const SocialMetrics = React.memo(function SocialMetrics({
  favoriteCount,
  downloadCount,
  className = "",
}: SocialMetricsProps): React.ReactNode {
  return (
    <div
      className={`inline-flex items-center gap-3 text-sm text-muted ${className}`}
    >
      <span className="inline-flex items-center gap-1" title="收藏數">
        <span aria-hidden>⭐</span>
        <span className="tabular-nums">{favoriteCount}</span>
      </span>
      {downloadCount !== undefined && (
        <span className="inline-flex items-center gap-1" title="下載數">
          <span aria-hidden>⬇</span>
          <span className="tabular-nums">{downloadCount}</span>
        </span>
      )}
    </div>
  );
});
