"use client";

import React, { useCallback, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { useDispatch } from "react-redux";
import { Button } from "@/components/ui/Button";
import { PageLoading } from "@/components/ui/Loading";
import { SocialMetrics } from "@/components/social/SocialMetrics";
import { FavoriteButton } from "@/components/social/FavoriteButton";
import { TagsCard } from "@/components/tags";
import { useAuth } from "@/hooks/useAuth";
import { useDialog } from "@/hooks/useDialog";
import {
  useGetScriptQuery,
  useDeleteScriptMutation,
} from "@/store/scriptsApi";
import { baseApi } from "@/store/api";
import type { AppDispatch } from "@/store/store";
import {
  downloadBlob,
  extractFilename,
  triggerBrowserDownload,
} from "@/lib/api/download";
import { formatDateTime } from "@/utils/datetime";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

async function downloadScriptZip(scriptUid: string): Promise<void> {
  const result = await downloadBlob(`/scripts/${scriptUid}/download`);
  if (!result.ok || !result.blob) {
    throw new Error("下載失敗");
  }
  const filename = extractFilename(result.headers, `${scriptUid}.zip`);
  triggerBrowserDownload(result.blob, filename);
}

export default function ScriptDetailPage(): React.ReactNode {
  const params = useParams();
  const router = useRouter();
  const { showDialog } = useDialog();
  const { isLoading: authLoading, userUid } = useAuth();
  const dispatch = useDispatch<AppDispatch>();
  const uid = params.uid as string;

  const {
    data: script,
    isLoading: scriptLoading,
    error: scriptError,
  } = useGetScriptQuery(uid, { skip: authLoading });

  const [deleteScript] = useDeleteScriptMutation();

  const isOwner = useMemo((): boolean => {
    return !!script && !!userUid && script.owner_user_uid === userUid;
  }, [script, userUid]);

  const handleBack = useCallback((): void => {
    router.push("/scripts");
  }, [router]);

  const handleDownload = useCallback(async (): Promise<void> => {
    if (!script) return;
    try {
      await downloadScriptZip(script.script_uid);
      // 下載後讓列表 / 排行 / 收藏快照 refetch 取新 download_count
      dispatch(
        baseApi.util.invalidateTags(["Scripts", "Rankings", "Favorites"])
      );
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "下載失敗，請稍後再試";
      showDialog({ type: "error", title: "下載失敗", message });
    }
  }, [script, dispatch, showDialog]);

  const handleDelete = useCallback((): void => {
    if (!script) return;
    showDialog({
      type: "warning",
      title: "刪除 Script",
      message: "確定要刪除此 Script 嗎？此操作無法復原。",
      onConfirm: async () => {
        try {
          await deleteScript(script.script_uid).unwrap();
          router.push("/scripts");
        } catch (err: unknown) {
          const message =
            typeof err === "string" ? err : "刪除失敗，請稍後再試";
          showDialog({ type: "error", title: "刪除失敗", message });
        }
      },
      onCancel: () => {},
    });
  }, [script, showDialog, deleteScript, router]);

  if (authLoading || scriptLoading) {
    return <PageLoading />;
  }

  if (scriptError || !script) {
    return (
      <div>
        <h1 className="mb-4 text-3xl font-bold text-foreground">Script 詳情</h1>
        <div className="rounded-xl bg-card-bg p-6 text-center shadow-sm">
          <p className="text-muted">找不到指定的 Script。</p>
          <Button className="mt-4" variant="secondary" onClick={handleBack}>
            返回列表
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-3xl font-bold text-foreground">Script 詳情</h1>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={handleBack}>
            返回列表
          </Button>
          {isOwner && (
            <Button variant="destructive" onClick={handleDelete}>
              刪除
            </Button>
          )}
          <Button onClick={handleDownload}>下載</Button>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <div className="rounded-xl bg-card-bg p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xl font-semibold text-foreground">基本資訊</h2>
            <div className="flex items-center gap-2">
              <SocialMetrics
                favoriteCount={script.favorite_count}
                downloadCount={script.download_count}
              />
              <FavoriteButton
                resourceType="script"
                resourceUid={script.script_uid}
                isFavorited={script.is_favorited}
              />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <span className="text-base text-muted">名稱</span>
              <p className="font-medium text-foreground">{script.name}</p>
            </div>
            <div>
              <span className="text-base text-muted">擁有者</span>
              <p className="font-medium text-foreground">
                @{script.owner_username ?? "未知"}
              </p>
            </div>
            <div>
              <span className="text-base text-muted">可見性</span>
              <p>
                <span
                  className={`rounded-xl px-2 py-0.5 text-sm font-medium ${
                    script.visibility === "public"
                      ? "bg-info-bg text-info"
                      : "bg-muted-bg text-muted"
                  }`}
                >
                  {script.visibility === "public" ? "公開" : "私人"}
                </span>
              </p>
            </div>
            <div>
              <span className="text-base text-muted">檔案名稱</span>
              <p className="font-medium text-foreground">{script.file_name}</p>
            </div>
            <div>
              <span className="text-base text-muted">檔案大小</span>
              <p className="font-medium text-foreground">
                {formatFileSize(script.file_size)}
              </p>
            </div>
            <div>
              <span className="text-base text-muted">上傳時間</span>
              <p className="font-medium text-foreground">
                {formatDateTime(script.created_at)}
              </p>
            </div>
            <div className="sm:col-span-2">
              <span className="text-base text-muted">描述</span>
              <p className="whitespace-pre-wrap text-foreground">
                {script.description ?? <span className="italic text-muted">尚無描述</span>}
              </p>
            </div>
          </div>
        </div>

        <TagsCard
          entityType="script"
          entityUid={script.script_uid}
          initialTags={script.tags ?? []}
          canEdit={isOwner}
        />
      </div>
    </div>
  );
}
