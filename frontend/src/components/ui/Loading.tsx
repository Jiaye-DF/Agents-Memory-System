"use client";

import React from "react";

interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
}

const SPINNER_SIZES: Record<string, string> = {
  sm: "h-4 w-4",
  md: "h-8 w-8",
  lg: "h-12 w-12",
};

export const Spinner = React.memo(function Spinner({
  size = "md",
  className = "",
}: SpinnerProps): React.ReactNode {
  return (
    <div
      className={`animate-spin rounded-full border-2 border-muted-bg border-t-primary ${SPINNER_SIZES[size]} ${className}`}
      role="status"
      aria-label="載入中"
    >
      <span className="sr-only">載入中...</span>
    </div>
  );
});

interface SkeletonProps {
  className?: string;
}

export const Skeleton = React.memo(function Skeleton({
  className = "",
}: SkeletonProps): React.ReactNode {
  return (
    <div
      className={`animate-pulse rounded-xl bg-muted-bg ${className}`}
      role="status"
      aria-label="載入中"
    />
  );
});

export function PageLoading(): React.ReactNode {
  return (
    <div className="flex h-full w-full items-center justify-center p-8">
      <Spinner size="lg" />
    </div>
  );
}

export function CardSkeleton(): React.ReactNode {
  return (
    <div className="rounded-xl bg-card-bg p-6 shadow-sm">
      <Skeleton className="mb-4 h-6 w-3/4" />
      <Skeleton className="mb-2 h-4 w-full" />
      <Skeleton className="mb-2 h-4 w-5/6" />
      <Skeleton className="h-4 w-2/3" />
    </div>
  );
}
