"use client";

import React, { useCallback } from "react";
import { useDialog } from "@/hooks/useDialog";
import {
  useFavoriteResourceMutation,
  useUnfavoriteResourceMutation,
} from "@/store/socialApi";
import type { ResourceType } from "@/types";

interface FavoriteButtonProps {
  resourceType: ResourceType;
  resourceUid: string;
  isFavorited: boolean;
  onToggled?: (nextFavorited: boolean) => void;
  size?: "sm" | "md";
  className?: string;
}

const SIZE_CLASSES: Record<"sm" | "md", string> = {
  sm: "h-8 w-8 text-lg",
  md: "h-9 w-9 text-xl",
};

export const FavoriteButton = React.memo(function FavoriteButton({
  resourceType,
  resourceUid,
  isFavorited,
  onToggled,
  size = "md",
  className = "",
}: FavoriteButtonProps): React.ReactNode {
  const { showDialog } = useDialog();
  const [favorite, { isLoading: favoriting }] =
    useFavoriteResourceMutation();
  const [unfavorite, { isLoading: unfavoriting }] =
    useUnfavoriteResourceMutation();

  const disabled = favoriting || unfavoriting;

  const handleClick = useCallback(async (): Promise<void> => {
    if (disabled) return;
    const next = !isFavorited;
    try {
      if (next) {
        await favorite({ resourceType, resourceUid }).unwrap();
      } else {
        await unfavorite({ resourceType, resourceUid }).unwrap();
      }
      onToggled?.(next);
    } catch (err: unknown) {
      const fallback = next
        ? "收藏失敗，請稍後再試"
        : "取消收藏失敗，請稍後再試";
      const message = typeof err === "string" ? err : fallback;
      showDialog({
        type: "error",
        title: next ? "收藏失敗" : "取消收藏失敗",
        message,
      });
    }
  }, [
    disabled,
    isFavorited,
    favorite,
    unfavorite,
    resourceType,
    resourceUid,
    onToggled,
    showDialog,
  ]);

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled}
      aria-pressed={isFavorited}
      aria-label={isFavorited ? "取消收藏" : "收藏"}
      title={isFavorited ? "取消收藏" : "收藏"}
      className={`inline-flex shrink-0 items-center justify-center rounded-xl transition-colors hover:cursor-pointer hover:bg-muted-bg disabled:cursor-not-allowed disabled:opacity-50 ${SIZE_CLASSES[size]} ${className}`}
    >
      <span
        aria-hidden
        className={`transition-colors ${
          isFavorited ? "text-warning" : "text-muted"
        }`}
      >
        {isFavorited ? "★" : "☆"}
      </span>
    </button>
  );
});
