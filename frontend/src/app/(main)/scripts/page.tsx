"use client";

import React, { useState, useCallback, useMemo } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { PageLoading } from "@/components/ui/Loading";
import { FilterNav } from "@/components/social/FilterNav";
import { SocialMetrics } from "@/components/social/SocialMetrics";
import { FavoriteButton } from "@/components/social/FavoriteButton";
import { TombstoneCard } from "@/components/social/TombstoneCard";
import { useAuth } from "@/hooks/useAuth";
import { useDialog } from "@/hooks/useDialog";
import { useConfirmMutation } from "@/hooks/useConfirmMutation";
import {
  useListScriptsQuery,
  useDeleteScriptMutation,
} from "@/store/scriptsApi";
import {
  useListMyFavoritesQuery,
  useUnfavoriteResourceMutation,
} from "@/store/socialApi";
import type {
  Script,
  FilterScope,
  MyFavoriteItem,
  ResourceSnapshot,
} from "@/types";
import { parseSearch, matchByTextAndAuthor } from "@/utils/search";
import { formatDateTime } from "@/utils/datetime";
import { ScriptUploadDialog } from "./ScriptUploadDialog";
import { getAccessToken } from "@/lib/api/client";

type SortOrder = "newest" | "oldest";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

async function downloadScript(scriptUid: string): Promise<void> {
  const token = getAccessToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const response = await fetch(
    `${API_BASE_URL}/api/v1/scripts/${scriptUid}/download`,
    { method: "GET", headers, credentials: "include" }
  );
  if (!response.ok) {
    throw new Error("下載失敗");
  }
  const blob = await response.blob();
  const cd = response.headers.get("content-disposition");
  let filename = `${scriptUid}.zip`;
  if (cd) {
    const match = cd.match(/filename\*?=(?:UTF-8'')?["']?([^"';\n]+)/i);
    if (match && match[1]) {
      try {
        filename = decodeURIComponent(match[1]);
      } catch {
        filename = match[1];
      }
    }
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

interface ScriptRowProps {
  script: Script;
  isOwner: boolean;
  onDelete: (scriptUid: string) => void;
  onDownload: (scriptUid: string) => void;
}

const ScriptRow = React.memo(function ScriptRow({
  script,
  isOwner,
  onDelete,
  onDownload,
}: ScriptRowProps): React.ReactNode {
  const handleDelete = useCallback((): void => {
    onDelete(script.script_uid);
  }, [script.script_uid, onDelete]);

  const handleDownload = useCallback((): void => {
    onDownload(script.script_uid);
  }, [script.script_uid, onDownload]);

  return (
    <div className="flex flex-col gap-3 px-4 py-4 transition-colors hover:bg-muted-bg/40 md:flex-row md:items-center md:gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="truncate text-lg font-semibold text-foreground">
            {script.name}
          </h3>
          <span
            className={`shrink-0 rounded-xl px-2 py-0.5 text-sm font-medium ${
              script.visibility === "public"
                ? "bg-info-bg text-info"
                : "bg-muted-bg text-muted"
            }`}
          >
            {script.visibility === "public" ? "公開" : "私人"}
          </span>
          {script.owner_username && (
            <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
              @{script.owner_username}
            </span>
          )}
        </div>

        {script.description && (
          <p className="mt-1 line-clamp-1 text-base text-muted">
            {script.description}
          </p>
        )}

        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
          <span>{formatFileSize(script.file_size)}</span>
          <span className="truncate">{script.file_name}</span>
          <span>上傳於 {formatDateTime(script.created_at)}</span>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2 md:ml-auto">
        <SocialMetrics
          favoriteCount={script.favorite_count}
          downloadCount={script.download_count}
        />
        <FavoriteButton
          resourceType="script"
          resourceUid={script.script_uid}
          isFavorited={script.is_favorited}
        />
        <Button size="sm" variant="secondary" onClick={handleDownload}>
          下載
        </Button>
        {isOwner && (
          <Button size="sm" variant="destructive" onClick={handleDelete}>
            刪除
          </Button>
        )}
      </div>
    </div>
  );
});

interface SnapshotRowProps {
  resource: ResourceSnapshot;
  onDownload: (uid: string) => void;
}

const SnapshotRow = React.memo(function SnapshotRow({
  resource,
  onDownload,
}: SnapshotRowProps): React.ReactNode {
  const handleDownload = useCallback((): void => {
    onDownload(resource.uid);
  }, [resource.uid, onDownload]);

  return (
    <div className="flex flex-col gap-3 px-4 py-4 transition-colors hover:bg-muted-bg/40 md:flex-row md:items-center md:gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="truncate text-lg font-semibold text-foreground">
            {resource.name}
          </h3>
          {resource.owner_username && (
            <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
              @{resource.owner_username}
            </span>
          )}
        </div>
        {resource.description && (
          <p className="mt-1 line-clamp-1 text-base text-muted">
            {resource.description}
          </p>
        )}
        {resource.created_at && (
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
            <span>建立於 {formatDateTime(resource.created_at)}</span>
          </div>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2 md:ml-auto">
        <SocialMetrics
          favoriteCount={resource.favorite_count}
          downloadCount={resource.download_count}
        />
        <FavoriteButton
          resourceType="script"
          resourceUid={resource.uid}
          isFavorited
        />
        <Button size="sm" variant="secondary" onClick={handleDownload}>
          下載
        </Button>
      </div>
    </div>
  );
});

interface FilterChipProps {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}

const FilterChip = React.memo(function FilterChip({
  active,
  onClick,
  children,
}: FilterChipProps): React.ReactNode {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-xl px-3 py-1 text-sm font-medium transition-colors hover:cursor-pointer ${
        active
          ? "bg-primary text-white"
          : "bg-muted-bg text-muted hover:bg-border"
      }`}
    >
      {children}
    </button>
  );
});

export default function ScriptsListPage(): React.ReactNode {
  const { userUid, isLoading: authLoading } = useAuth();
  const { showDialog } = useDialog();

  const [scope, setScope] = useState<FilterScope>("mine");
  const [query, setQuery] = useState<string>("");
  const [sortOrder, setSortOrder] = useState<SortOrder>("newest");
  const [uploadOpen, setUploadOpen] = useState<boolean>(false);

  const { data, isLoading, isFetching } = useListScriptsQuery(
    { limit: 50, cursor: null },
    { skip: authLoading || scope === "favorites" }
  );
  const {
    data: favoritesData,
    isLoading: favLoading,
    isFetching: favFetching,
  } = useListMyFavoritesQuery(
    { type: "script", page: 1, size: 50 },
    { skip: authLoading || scope !== "favorites" }
  );

  const [deleteScript] = useDeleteScriptMutation();
  const [unfavorite, { isLoading: isUnfavoriting }] =
    useUnfavoriteResourceMutation();

  const scripts = useMemo((): Script[] => data?.items ?? [], [data]);

  const scopedScripts = useMemo((): Script[] => {
    if (scope === "mine") {
      return scripts.filter((s) => s.owner_user_uid === userUid);
    }
    return scripts;
  }, [scripts, scope, userUid]);

  const parsed = useMemo(() => parseSearch(query), [query]);

  const filteredScripts = useMemo((): Script[] => {
    const matched = scopedScripts.filter((s) =>
      matchByTextAndAuthor(
        s.name,
        s.description ?? "",
        s.owner_username,
        parsed
      )
    );
    const sorted = [...matched].sort((a, b) => {
      const diff = a.created_at.localeCompare(b.created_at);
      return sortOrder === "newest" ? -diff : diff;
    });
    return sorted;
  }, [scopedScripts, parsed, sortOrder]);

  const favoriteItems = useMemo(
    (): MyFavoriteItem[] => favoritesData?.items ?? [],
    [favoritesData]
  );

  const handleQueryChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setQuery(e.target.value);
    },
    []
  );

  const deleteOptions = useMemo(
    () => ({
      title: "刪除 Script",
      message: "確定要刪除此 Script 嗎？此操作無法復原。",
      successTitle: "刪除成功",
      successMessage: "Script 已成功刪除。",
      errorMessage: "刪除失敗，請稍後再試",
    }),
    []
  );
  const confirmDeleteScript = useConfirmMutation(deleteScript, deleteOptions);
  const handleDelete = useCallback(
    (scriptUid: string): void => {
      confirmDeleteScript(scriptUid);
    },
    [confirmDeleteScript]
  );

  const handleDownload = useCallback(
    async (scriptUid: string): Promise<void> => {
      try {
        await downloadScript(scriptUid);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "下載失敗，請稍後再試";
        showDialog({ type: "error", title: "下載失敗", message });
      }
    },
    [showDialog]
  );

  const handleDownloadSync = useCallback(
    (scriptUid: string): void => {
      void handleDownload(scriptUid);
    },
    [handleDownload]
  );

  const handleTombstoneRemove = useCallback(
    async (scriptUid: string): Promise<void> => {
      try {
        await unfavorite({
          resourceType: "script",
          resourceUid: scriptUid,
        }).unwrap();
      } catch (err: unknown) {
        const fallback = "從收藏移除失敗，請稍後再試";
        const message = typeof err === "string" ? err : fallback;
        showDialog({ type: "error", title: "操作失敗", message });
      }
    },
    [unfavorite, showDialog]
  );

  const handleTombstoneRemoveSync = useCallback(
    (scriptUid: string): void => {
      void handleTombstoneRemove(scriptUid);
    },
    [handleTombstoneRemove]
  );

  const handleScopeChange = useCallback((next: FilterScope): void => {
    setScope(next);
  }, []);

  const handleOpenUpload = useCallback((): void => {
    setUploadOpen(true);
  }, []);

  const handleCloseUpload = useCallback((): void => {
    setUploadOpen(false);
  }, []);

  if (authLoading) {
    return <PageLoading />;
  }

  const isFavoritesScope = scope === "favorites";
  const showLoading = isFavoritesScope
    ? favLoading || favFetching
    : isLoading || isFetching;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-3xl font-bold text-foreground">Scripts 管理</h1>
        <Button onClick={handleOpenUpload}>新增 Script</Button>
      </div>

      <div className="mb-4">
        <FilterNav value={scope} onChange={handleScopeChange} />
      </div>

      {!isFavoritesScope && (
        <div className="mb-4 flex flex-col gap-3">
          <Input
            placeholder="搜尋名稱、描述，或輸入 @作者 篩選（可多個）"
            value={query}
            onChange={handleQueryChange}
          />

          <div className="flex flex-wrap items-center gap-2">
            <span className="shrink-0 text-sm text-muted">排序：</span>
            <FilterChip
              active={sortOrder === "newest"}
              onClick={() => setSortOrder("newest")}
            >
              由新到舊
            </FilterChip>
            <FilterChip
              active={sortOrder === "oldest"}
              onClick={() => setSortOrder("oldest")}
            >
              由舊到新
            </FilterChip>
          </div>
        </div>
      )}

      <div className="overflow-hidden rounded-xl bg-card-bg shadow-sm">
        {showLoading ? (
          <PageLoading />
        ) : isFavoritesScope ? (
          favoriteItems.length === 0 ? (
            <div className="py-12 text-center text-muted">
              尚未收藏任何 Script。
            </div>
          ) : (
            <div className="divide-y divide-border">
              {favoriteItems.map((item) =>
                item.resource === null ? (
                  <TombstoneCard
                    key={item.user_favorite_uid}
                    resourceType="script"
                    resourceUid={item.resource_uid}
                    onRemove={handleTombstoneRemoveSync}
                    isRemoving={isUnfavoriting}
                  />
                ) : (
                  <SnapshotRow
                    key={item.user_favorite_uid}
                    resource={item.resource}
                    onDownload={handleDownloadSync}
                  />
                )
              )}
            </div>
          )
        ) : scopedScripts.length === 0 ? (
          <div className="py-12 text-center text-muted">
            尚無 Scripts，點擊右上角「新增 Script」上傳第一個。
          </div>
        ) : filteredScripts.length === 0 ? (
          <div className="py-12 text-center text-muted">
            沒有符合條件的 Scripts
          </div>
        ) : (
          <div className="divide-y divide-border">
            {filteredScripts.map((script) => (
              <ScriptRow
                key={script.script_uid}
                script={script}
                isOwner={script.owner_user_uid === userUid}
                onDelete={handleDelete}
                onDownload={handleDownloadSync}
              />
            ))}
          </div>
        )}
      </div>

      {uploadOpen && <ScriptUploadDialog onClose={handleCloseUpload} />}
    </div>
  );
}
