"use client";

import React, { useState, useCallback, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { PageLoading } from "@/components/ui/Loading";
import { useDialog } from "@/hooks/useDialog";
import { useAuth } from "@/hooks/useAuth";
import {
  useGetSkillQuery,
  useGetFileTreeQuery,
  useGetFileContentQuery,
} from "@/store/skillsApi";
import { getAccessToken } from "@/lib/api/client";
import type { FileTreeNode } from "@/types";
import { formatDateTime } from "@/utils/datetime";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

interface TreeNodeProps {
  node: FileTreeNode;
  depth: number;
  parentPath: string;
  selectedPath: string | null;
  onSelect: (path: string) => void;
}

const TreeNode = React.memo(function TreeNode({
  node,
  depth,
  parentPath,
  selectedPath,
  onSelect,
}: TreeNodeProps): React.ReactNode {
  const [isExpanded, setIsExpanded] = useState<boolean>(depth < 2);

  const fullPath = useMemo(
    (): string => (parentPath ? `${parentPath}/${node.name}` : node.name),
    [parentPath, node.name]
  );

  const handleToggle = useCallback((): void => {
    setIsExpanded((prev) => !prev);
  }, []);

  const handleSelect = useCallback((): void => {
    onSelect(fullPath);
  }, [onSelect, fullPath]);

  const paddingLeft = useMemo((): string => `${depth * 20 + 8}px`, [depth]);

  if (node.type === "directory") {
    return (
      <div>
        <button
          type="button"
          onClick={handleToggle}
          className="flex w-full items-center gap-2 rounded-xl px-2 py-1.5 text-base text-foreground transition-colors hover:cursor-pointer hover:bg-muted-bg"
          style={{ paddingLeft }}
        >
          <span className="shrink-0 text-sm text-muted">
            {isExpanded ? "\u25BC" : "\u25B6"}
          </span>
          <span className="shrink-0">
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              className="text-warning"
            >
              <path
                d="M1.5 3C1.5 2.44772 1.94772 2 2.5 2H6.29289C6.55811 2 6.81246 2.10536 7 2.29289L8 3.29289C8.18754 3.48043 8.44189 3.58579 8.70711 3.58579H13.5C14.0523 3.58579 14.5 4.0335 14.5 4.58579V13C14.5 13.5523 14.0523 14 13.5 14H2.5C1.94772 14 1.5 13.5523 1.5 13V3Z"
                stroke="currentColor"
                strokeWidth="1.2"
              />
            </svg>
          </span>
          <span className="truncate font-medium">{node.name}</span>
        </button>
        {isExpanded && node.children && (
          <div>
            {node.children.map((child) => (
              <TreeNode
                key={`${node.name}-${child.name}`}
                node={child}
                depth={depth + 1}
                parentPath={fullPath}
                selectedPath={selectedPath}
                onSelect={onSelect}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  const isSelected = selectedPath === fullPath;

  return (
    <button
      type="button"
      onClick={handleSelect}
      className={`flex w-full items-center gap-2 rounded-xl px-2 py-1.5 text-base text-foreground transition-colors hover:cursor-pointer hover:bg-muted-bg ${
        isSelected ? "bg-primary/10 text-primary" : ""
      }`}
      style={{ paddingLeft }}
    >
      <span className="shrink-0 text-sm text-transparent">{"\u25B6"}</span>
      <span className="shrink-0">
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          className={isSelected ? "text-primary" : "text-muted"}
        >
          <rect
            x="2"
            y="1.5"
            width="12"
            height="13"
            rx="1.5"
            stroke="currentColor"
            strokeWidth="1.2"
          />
          <line
            x1="5"
            y1="5"
            x2="11"
            y2="5"
            stroke="currentColor"
            strokeWidth="1"
          />
          <line
            x1="5"
            y1="8"
            x2="11"
            y2="8"
            stroke="currentColor"
            strokeWidth="1"
          />
          <line
            x1="5"
            y1="11"
            x2="9"
            y2="11"
            stroke="currentColor"
            strokeWidth="1"
          />
        </svg>
      </span>
      <span className="truncate">{node.name}</span>
    </button>
  );
});

interface CodeViewerProps {
  skillUid: string;
  path: string;
}

function CodeViewer({ skillUid, path }: CodeViewerProps): React.ReactNode {
  const { data, isFetching, error } = useGetFileContentQuery({
    skillUid,
    path,
  });

  const lines = useMemo((): string[] => {
    if (!data || data.encoding !== "text" || data.too_large) return [];
    return data.content.split("\n");
  }, [data]);

  if (isFetching) {
    return <div className="p-6 text-center text-muted">載入中...</div>;
  }

  if (error || !data) {
    return (
      <div className="p-6 text-center text-danger">
        無法載入檔案內容。
      </div>
    );
  }

  if (data.too_large) {
    return (
      <div className="p-6 text-center text-muted">
        檔案過大（{formatFileSize(data.size)}），無法預覽。請下載後檢視。
      </div>
    );
  }

  if (data.encoding === "binary") {
    return (
      <div className="p-6 text-center text-muted">
        二進位檔案（{formatFileSize(data.size)}），無法顯示內容。
      </div>
    );
  }

  return (
    <div className="flex max-h-[70vh] overflow-auto font-mono text-sm">
      <div className="sticky left-0 select-none border-r border-border bg-muted-bg px-3 py-3 text-right text-muted">
        {lines.map((_, i) => (
          <div key={i} className="leading-6">
            {i + 1}
          </div>
        ))}
      </div>
      <pre className="flex-1 px-4 py-3 leading-6 text-foreground">
        <code>{data.content}</code>
      </pre>
    </div>
  );
}

export default function SkillDetailPage(): React.ReactNode {
  const params = useParams();
  const router = useRouter();
  const { showDialog } = useDialog();
  const { isLoading: authLoading } = useAuth();
  const uid = params.uid as string;

  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  const {
    data: skill,
    isLoading: skillLoading,
    error: skillError,
  } = useGetSkillQuery(uid, { skip: authLoading });

  const { data: treeData, isLoading: treeLoading } = useGetFileTreeQuery(uid, {
    skip: authLoading || !skill,
  });

  const handleSelect = useCallback((path: string): void => {
    setSelectedPath(path);
  }, []);

  const handleDownload = useCallback((): void => {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "";
    const token = getAccessToken();
    const url = `${baseUrl}/skills/${uid}/download`;

    const link = document.createElement("a");
    link.href = `${url}?token=${encodeURIComponent(token ?? "")}`;

    const anchor = document.createElement("a");
    anchor.style.display = "none";
    document.body.appendChild(anchor);

    const downloadAsync = async (): Promise<void> => {
      try {
        const response = await fetch(url, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          credentials: "include",
        });

        if (!response.ok) {
          throw new Error("下載失敗");
        }

        const blob = await response.blob();
        const blobUrl = URL.createObjectURL(blob);
        anchor.href = blobUrl;

        const contentDisposition = response.headers.get("content-disposition");
        let filename = "download.zip";
        if (contentDisposition) {
          const match = contentDisposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';\n]+)/i);
          if (match) {
            filename = decodeURIComponent(match[1]);
          }
        }
        anchor.download = filename;
        anchor.click();
        URL.revokeObjectURL(blobUrl);
      } catch {
        showDialog({
          type: "error",
          title: "下載失敗",
          message: "無法下載檔案，請稍後再試。",
        });
      } finally {
        document.body.removeChild(anchor);
      }
    };

    void downloadAsync();
  }, [uid, showDialog]);

  const handleBack = useCallback((): void => {
    router.push("/skills");
  }, [router]);

  if (authLoading || skillLoading) {
    return <PageLoading />;
  }

  if (skillError || !skill) {
    return (
      <div>
        <h1 className="mb-4 text-3xl font-bold text-foreground">
          Skill 詳情
        </h1>
        <div className="rounded-xl bg-card-bg p-6 text-center shadow-sm">
          <p className="text-muted">找不到指定的 Skill。</p>
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
        <h1 className="text-3xl font-bold text-foreground">Skill 詳情</h1>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={handleBack}>
            返回列表
          </Button>
          <Button onClick={handleDownload}>下載</Button>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <div className="rounded-xl bg-card-bg p-6 shadow-sm">
          <h2 className="mb-4 text-xl font-semibold text-foreground">
            基本資訊
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <span className="text-base text-muted">名稱</span>
              <p className="font-medium text-foreground">{skill.name}</p>
            </div>
            <div>
              <span className="text-base text-muted">可見性</span>
              <p>
                <span
                  className={`rounded-xl px-2 py-0.5 text-sm font-medium ${
                    skill.visibility === "public"
                      ? "bg-success/10 text-success"
                      : "bg-muted-bg text-muted"
                  }`}
                >
                  {skill.visibility === "public" ? "公開" : "私人"}
                </span>
              </p>
            </div>
            <div>
              <span className="text-base text-muted">檔案名稱</span>
              <p className="font-medium text-foreground">
                {skill.original_filename}
              </p>
            </div>
            <div>
              <span className="text-base text-muted">檔案大小</span>
              <p className="font-medium text-foreground">
                {formatFileSize(skill.file_size)}
              </p>
            </div>
            <div>
              <span className="text-base text-muted">上傳時間</span>
              <p className="font-medium text-foreground">
                {formatDateTime(skill.created_at)}
              </p>
            </div>
            <div>
              <span className="text-base text-muted">更新時間</span>
              <p className="font-medium text-foreground">
                {formatDateTime(skill.updated_at)}
              </p>
            </div>
            <div className="sm:col-span-2">
              <span className="text-base text-muted">描述</span>
              <p className="whitespace-pre-wrap text-foreground">
                {skill.description}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-xl bg-card-bg p-6 shadow-sm">
          <h2 className="mb-4 text-xl font-semibold text-foreground">
            檔案內容
          </h2>
          {treeLoading ? (
            <div className="py-8 text-center text-muted">載入中...</div>
          ) : treeData?.tree && treeData.tree.length > 0 ? (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(240px,300px)_1fr]">
              <div className="rounded-xl border border-border p-1 lg:max-h-[70vh] lg:overflow-auto">
                {treeData.tree.map((node) => (
                  <TreeNode
                    key={node.name}
                    node={node}
                    depth={0}
                    parentPath=""
                    selectedPath={selectedPath}
                    onSelect={handleSelect}
                  />
                ))}
              </div>
              <div className="overflow-hidden rounded-xl border border-border">
                {selectedPath ? (
                  <>
                    <div className="flex items-center justify-between border-b border-border bg-muted-bg px-4 py-2">
                      <span className="truncate font-mono text-sm text-foreground">
                        {selectedPath}
                      </span>
                    </div>
                    <CodeViewer skillUid={uid} path={selectedPath} />
                  </>
                ) : (
                  <div className="p-8 text-center text-muted">
                    請從左側點選檔案以查看內容。
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="py-8 text-center text-muted">
              無法取得檔案目錄結構。
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
