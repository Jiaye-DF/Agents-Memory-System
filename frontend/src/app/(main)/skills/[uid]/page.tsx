"use client";

import React, {
  useState,
  useCallback,
  useMemo,
  useRef,
} from "react";
import { useParams, useRouter } from "next/navigation";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import {
  oneLight,
  vscDarkPlus,
} from "react-syntax-highlighter/dist/esm/styles/prism";
import { Button } from "@/components/ui/Button";
import { PageLoading } from "@/components/ui/Loading";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { useDialog } from "@/hooks/useDialog";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";
import {
  useGetSkillQuery,
  useGetFileTreeQuery,
  useGetFileContentQuery,
  useGetSkillUsageQuery,
  useReuploadSkillMutation,
  useUpdateSkillFileMutation,
} from "@/store/skillsApi";
import {
  downloadBlob,
  extractFilename,
  triggerBrowserDownload,
} from "@/lib/api/download";
import type { FileTreeNode, SkillUsageResponse } from "@/types";
import { formatDateTime } from "@/utils/datetime";
import { detectLanguage } from "@/utils/language";
import {
  isEditable,
  FILE_EDIT_MAX_BYTES,
} from "@/utils/editableExtensions";

const MAX_TOTAL_SIZE = 50 * 1024 * 1024;
const BLOCKED_EXTENSIONS = [".exe"];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function getRelativePath(file: File): string {
  const rel = (file as File & { webkitRelativePath?: string })
    .webkitRelativePath;
  return rel && rel.length > 0 ? rel : file.name;
}

function getFileExtension(filename: string): string {
  const dotIndex = filename.lastIndexOf(".");
  return dotIndex >= 0 ? filename.slice(dotIndex).toLowerCase() : "";
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
        isSelected ? "bg-sidebar-active font-semibold" : ""
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
          className={isSelected ? "text-foreground" : "text-muted"}
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
  isOwner: boolean;
  skillUpdatedAt: string;
  onRequestEdit: (path: string, currentContent: string) => void;
}

function CodeViewer({
  skillUid,
  path,
  isOwner,
  skillUpdatedAt,
  onRequestEdit,
}: CodeViewerProps): React.ReactNode {
  const { theme } = useTheme();
  const { data, isFetching, error } = useGetFileContentQuery({
    skillUid,
    path,
  });

  const language = useMemo((): string => detectLanguage(path), [path]);
  const highlightStyle = theme === "dark" ? vscDarkPlus : oneLight;

  const canEdit = useMemo((): boolean => {
    if (!isOwner || !data) return false;
    if (data.too_large) return false;
    if (data.encoding !== "text") return false;
    if (!isEditable(path)) return false;
    if (data.size > FILE_EDIT_MAX_BYTES) return false;
    return true;
  }, [isOwner, data, path]);

  const handleEditClick = useCallback((): void => {
    if (data) onRequestEdit(path, data.content);
  }, [data, path, onRequestEdit]);

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
    <div>
      {canEdit && (
        <div className="flex items-center justify-end border-b border-border bg-muted-bg/50 px-3 py-1.5">
          <Button size="sm" variant="secondary" onClick={handleEditClick}>
            編輯
          </Button>
          {/* skillUpdatedAt is captured by parent on open */}
          <span className="hidden">{skillUpdatedAt}</span>
        </div>
      )}
      <div className="max-h-[65vh] overflow-auto">
        <SyntaxHighlighter
          language={language}
          style={highlightStyle}
          showLineNumbers
          wrapLongLines={false}
          customStyle={{
            margin: 0,
            padding: "0.75rem 1rem",
            background: "transparent",
            fontSize: "0.875rem",
            lineHeight: 1.6,
          }}
          lineNumberStyle={{
            minWidth: "2.5em",
            paddingRight: "1em",
            textAlign: "right",
            userSelect: "none",
            opacity: 0.5,
          }}
          codeTagProps={{
            style: { fontFamily: "var(--font-mono, monospace)" },
          }}
        >
          {data.content}
        </SyntaxHighlighter>
      </div>
    </div>
  );
}

interface CodeEditorProps {
  initialContent: string;
  saving: boolean;
  onSave: (content: string) => Promise<void>;
  onCancel: () => void;
}

function CodeEditor({
  initialContent,
  saving,
  onSave,
  onCancel,
}: CodeEditorProps): React.ReactNode {
  const [content, setContent] = useState<string>(initialContent);

  const byteLength = useMemo(
    (): number => new TextEncoder().encode(content).length,
    [content]
  );
  const overLimit = byteLength > FILE_EDIT_MAX_BYTES;

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>): void => {
      setContent(e.target.value);
    },
    []
  );

  const handleSave = useCallback((): void => {
    if (overLimit) return;
    void onSave(content);
  }, [content, onSave, overLimit]);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-muted-bg/50 px-3 py-1.5">
        <span className="text-sm text-muted">
          編輯中 · {formatFileSize(byteLength)}
          {overLimit && (
            <span className="ml-2 text-destructive">
              已超過 {FILE_EDIT_MAX_BYTES / 1024} KB 上限
            </span>
          )}
        </span>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="secondary"
            onClick={onCancel}
            disabled={saving}
          >
            取消
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            loading={saving}
            disabled={overLimit}
          >
            儲存
          </Button>
        </div>
      </div>
      <textarea
        value={content}
        onChange={handleChange}
        spellCheck={false}
        className="block max-h-[65vh] min-h-[40vh] w-full resize-y bg-card-bg p-3 font-mono text-sm leading-relaxed text-foreground focus:outline-none"
      />
    </div>
  );
}

interface UsageDialogProps {
  title: string;
  confirmLabel: string;
  usage: SkillUsageResponse | undefined;
  usageLoading: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

function UsageDialog({
  title,
  confirmLabel,
  usage,
  usageLoading,
  onConfirm,
  onClose,
}: UsageDialogProps): React.ReactNode {
  return (
    <ModalDialog title={title} onClose={onClose}>
      <div className="flex flex-col gap-4">
        {usageLoading || !usage ? (
          <p className="text-base text-muted">載入使用情況中...</p>
        ) : (
          <>
            <p className="text-base text-foreground">
              目前有 <span className="font-semibold">{usage.count}</span>{" "}
              個 Agent 使用此 Skill，更新後會立即套用。
            </p>
            {usage.count > 0 && (
              <div className="max-h-60 overflow-auto rounded-xl border border-border bg-muted-bg/30 p-2">
                {usage.items.map((a) => (
                  <div
                    key={a.agent_uid}
                    className="flex items-center justify-between gap-2 px-2 py-1.5 text-sm"
                  >
                    <span className="truncate font-medium text-foreground">
                      {a.agent_name}
                    </span>
                    <span className="shrink-0 text-muted">
                      {a.owner_username ?? "-"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
        <div className="mt-2 flex justify-end gap-3">
          <button
            type="button"
            className="min-h-11 min-w-11 rounded-xl border border-border px-4 py-2 text-base font-medium text-foreground hover:cursor-pointer hover:bg-muted-bg"
            onClick={onClose}
          >
            取消
          </button>
          <Button onClick={onConfirm} disabled={usageLoading}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </ModalDialog>
  );
}

interface ReuploadDialogProps {
  skillUid: string;
  expectedUpdatedAt: string;
  submitting: boolean;
  onSubmit: (files: File[]) => Promise<void>;
  onClose: () => void;
}

function ReuploadDialog({
  submitting,
  onSubmit,
  onClose,
}: ReuploadDialogProps): React.ReactNode {
  const { showDialog } = useDialog();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const [fileError, setFileError] = useState<string>("");

  const totalSize = useMemo(
    (): number => selectedFiles.reduce((sum, f) => sum + f.size, 0),
    [selectedFiles]
  );

  const topFolder = useMemo((): string | null => {
    if (selectedFiles.length === 0) return null;
    const first = getRelativePath(selectedFiles[0]);
    if (!first.includes("/")) return null;
    const top = first.split("/", 1)[0];
    const allMatch = selectedFiles.every((f) => {
      const p = getRelativePath(f);
      return p === top || p.startsWith(`${top}/`);
    });
    return allMatch ? top : null;
  }, [selectedFiles]);

  const summary = useMemo((): string => {
    if (selectedFiles.length === 0) return "";
    if (selectedFiles.length === 1 && !topFolder) {
      return `${selectedFiles[0].name}（${formatFileSize(totalSize)}）`;
    }
    if (topFolder) {
      return `資料夾：${topFolder}／共 ${selectedFiles.length} 個檔案（${formatFileSize(totalSize)}）`;
    }
    return `共 ${selectedFiles.length} 個檔案（${formatFileSize(totalSize)}）`;
  }, [selectedFiles, topFolder, totalSize]);

  const validateFiles = useCallback(
    (files: File[]): boolean => {
      if (files.length === 0) {
        setFileError("請選擇檔案或資料夾");
        return false;
      }
      for (const f of files) {
        const ext = getFileExtension(f.name);
        if (BLOCKED_EXTENSIONS.includes(ext)) {
          showDialog({
            type: "error",
            title: "不允許的檔案類型",
            message: `不允許上傳 ${ext} 檔案：${getRelativePath(f)}`,
          });
          return false;
        }
      }
      const total = files.reduce((sum, f) => sum + f.size, 0);
      if (total > MAX_TOTAL_SIZE) {
        showDialog({
          type: "error",
          title: "檔案過大",
          message: `總大小超過上限（50 MB）。目前總大小：${formatFileSize(total)}`,
        });
        return false;
      }
      if (total === 0) {
        setFileError("檔案內容為空");
        return false;
      }
      return true;
    },
    [showDialog]
  );

  const handleFiles = useCallback(
    (files: File[]): void => {
      setFileError("");
      if (validateFiles(files)) {
        setSelectedFiles(files);
      }
    },
    [validateFiles]
  );

  const handleFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      const list = e.target.files;
      if (!list) return;
      handleFiles(Array.from(list));
      e.target.value = "";
    },
    [handleFiles]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>): void => {
      e.preventDefault();
      setIsDragOver(false);
      const dropped = Array.from(e.dataTransfer.files ?? []);
      if (dropped.length > 0) handleFiles(dropped);
    },
    [handleFiles]
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent<HTMLDivElement>): void => {
      e.preventDefault();
      setIsDragOver(true);
    },
    []
  );

  const handleDragLeave = useCallback(
    (e: React.DragEvent<HTMLDivElement>): void => {
      e.preventDefault();
      setIsDragOver(false);
    },
    []
  );

  const handleSelectFiles = useCallback((): void => {
    fileInputRef.current?.click();
  }, []);

  const handleSelectFolder = useCallback((): void => {
    folderInputRef.current?.click();
  }, []);

  const handleClear = useCallback((): void => {
    setSelectedFiles([]);
    setFileError("");
  }, []);

  const handleSubmit = useCallback((): void => {
    if (selectedFiles.length === 0) {
      setFileError("請選擇檔案或資料夾");
      return;
    }
    void onSubmit(selectedFiles);
  }, [selectedFiles, onSubmit]);

  return (
    <ModalDialog title="重新上傳 Skill" onClose={onClose} size="md">
      <div className="flex flex-col gap-4">
        <p className="text-sm text-muted">
          重新上傳後將完整覆蓋原有檔案內容，且已使用此 Skill 的 Agent 會立即套用新內容。
        </p>
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className={`flex min-h-40 flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 transition-colors ${
            isDragOver ? "border-primary bg-primary/5" : "border-border"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            aria-label="選擇檔案"
            title="選擇檔案"
            onChange={handleFileInputChange}
            className="hidden"
          />
          <input
            ref={folderInputRef}
            type="file"
            aria-label="選擇資料夾"
            title="選擇資料夾"
            onChange={handleFileInputChange}
            className="hidden"
            {...({
              webkitdirectory: "",
              directory: "",
            } as React.InputHTMLAttributes<HTMLInputElement>)}
          />
          {selectedFiles.length > 0 ? (
            <div className="w-full text-center">
              <p className="text-base font-medium text-foreground">
                {summary}
              </p>
              <div className="mt-3 flex justify-center gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={handleSelectFiles}
                  disabled={submitting}
                >
                  重新選擇
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={handleClear}
                  disabled={submitting}
                >
                  清除
                </Button>
              </div>
            </div>
          ) : (
            <div className="text-center">
              <p className="text-base text-muted">
                拖曳 .zip 或多個檔案至此處
              </p>
              <p className="mt-1 text-sm text-muted">
                總大小上限 50 MB，禁止上傳 .exe
              </p>
              <div className="mt-4 flex justify-center gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={handleSelectFolder}
                  disabled={submitting}
                >
                  選擇資料夾
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={handleSelectFiles}
                  disabled={submitting}
                >
                  選擇檔案
                </Button>
              </div>
            </div>
          )}
        </div>
        {fileError && (
          <p className="text-base text-destructive">{fileError}</p>
        )}
        <div className="mt-2 flex justify-end gap-3">
          <button
            type="button"
            className="min-h-11 min-w-11 rounded-xl border border-border px-4 py-2 text-base font-medium text-foreground hover:cursor-pointer hover:bg-muted-bg"
            onClick={onClose}
            disabled={submitting}
          >
            取消
          </button>
          <Button
            onClick={handleSubmit}
            loading={submitting}
            disabled={selectedFiles.length === 0}
          >
            上傳
          </Button>
        </div>
      </div>
    </ModalDialog>
  );
}

type PendingAction =
  | { type: "reupload" }
  | { type: "edit"; path: string; content: string };

export default function SkillDetailPage(): React.ReactNode {
  const params = useParams();
  const router = useRouter();
  const { showDialog } = useDialog();
  const { isLoading: authLoading, userUid } = useAuth();
  const uid = params.uid as string;

  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [editingPath, setEditingPath] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState<string>("");
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(
    null
  );
  const [showReupload, setShowReupload] = useState<boolean>(false);

  const {
    data: skill,
    isLoading: skillLoading,
    error: skillError,
  } = useGetSkillQuery(uid, { skip: authLoading });

  const { data: treeData, isLoading: treeLoading } = useGetFileTreeQuery(uid, {
    skip: authLoading || !skill,
  });

  const { data: usage, isFetching: usageFetching } = useGetSkillUsageQuery(
    uid,
    { skip: authLoading || !skill || !pendingAction }
  );

  const [reuploadSkill, { isLoading: reuploading }] =
    useReuploadSkillMutation();
  const [updateSkillFile, { isLoading: savingFile }] =
    useUpdateSkillFileMutation();

  const isOwner = useMemo((): boolean => {
    return !!skill && !!userUid && skill.owner_uid === userUid;
  }, [skill, userUid]);

  const handleSelect = useCallback((path: string): void => {
    setSelectedPath(path);
    setEditingPath(null);
  }, []);

  const handleRequestEdit = useCallback(
    (path: string, currentContent: string): void => {
      setPendingAction({ type: "edit", path, content: currentContent });
    },
    []
  );

  const handleRequestReupload = useCallback((): void => {
    setPendingAction({ type: "reupload" });
  }, []);

  const handleCancelUsage = useCallback((): void => {
    setPendingAction(null);
  }, []);

  const handleConfirmUsage = useCallback((): void => {
    if (!pendingAction) return;
    if (pendingAction.type === "edit") {
      setEditingPath(pendingAction.path);
      setEditingContent(pendingAction.content);
      setPendingAction(null);
    } else {
      setShowReupload(true);
      setPendingAction(null);
    }
  }, [pendingAction]);

  const handleCancelEdit = useCallback((): void => {
    setEditingPath(null);
  }, []);

  const handleSaveFile = useCallback(
    async (content: string): Promise<void> => {
      if (!skill || !editingPath) return;
      try {
        await updateSkillFile({
          skillUid: uid,
          path: editingPath,
          body: {
            content,
            expected_updated_at: skill.updated_at,
          },
        }).unwrap();
        setEditingPath(null);
        showDialog({
          type: "info",
          title: "已儲存",
          message: "檔案內容已更新。",
        });
      } catch (err: unknown) {
        const msg = typeof err === "string" ? err : "儲存失敗，請稍後再試";
        const isConflict = typeof err === "string" && err.includes("已被更新");
        showDialog({
          type: "error",
          title: isConflict ? "檔案已被更新" : "儲存失敗",
          message: msg,
        });
      }
    },
    [skill, editingPath, uid, updateSkillFile, showDialog]
  );

  const handleSubmitReupload = useCallback(
    async (files: File[]): Promise<void> => {
      if (!skill) return;
      try {
        await reuploadSkill({
          skillUid: uid,
          files,
          expectedUpdatedAt: skill.updated_at,
        }).unwrap();
        setShowReupload(false);
        setSelectedPath(null);
        setEditingPath(null);
        showDialog({
          type: "info",
          title: "上傳成功",
          message: "Skill 已重新上傳，內容已更新。",
        });
      } catch (err: unknown) {
        const msg = typeof err === "string" ? err : "上傳失敗，請稍後再試";
        const isConflict = typeof err === "string" && err.includes("已被更新");
        showDialog({
          type: "error",
          title: isConflict ? "檔案已被更新" : "上傳失敗",
          message: msg,
        });
      }
    },
    [skill, uid, reuploadSkill, showDialog]
  );

  const handleCloseReupload = useCallback((): void => {
    setShowReupload(false);
  }, []);

  const handleDownload = useCallback((): void => {
    const downloadAsync = async (): Promise<void> => {
      try {
        const result = await downloadBlob(`/skills/${uid}/download`);
        if (!result.ok || !result.blob) {
          throw new Error("下載失敗");
        }
        const filename = extractFilename(result.headers, "download.zip");
        triggerBrowserDownload(result.blob, filename);
      } catch {
        showDialog({
          type: "error",
          title: "下載失敗",
          message: "無法下載檔案，請稍後再試。",
        });
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
          {isOwner && (
            <Button variant="secondary" onClick={handleRequestReupload}>
              重新上傳
            </Button>
          )}
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
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(240px,300px)_minmax(0,1fr)]">
              <div className="min-w-0 rounded-xl border border-border p-1 lg:max-h-[70vh] lg:overflow-auto">
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
              <div className="min-w-0 overflow-hidden rounded-xl border border-border">
                {selectedPath ? (
                  <>
                    <div className="flex items-center justify-between border-b border-border bg-muted-bg px-4 py-2">
                      <span className="truncate font-mono text-sm text-foreground">
                        {selectedPath}
                      </span>
                    </div>
                    {editingPath === selectedPath ? (
                      <CodeEditor
                        key={selectedPath}
                        initialContent={editingContent}
                        saving={savingFile}
                        onSave={handleSaveFile}
                        onCancel={handleCancelEdit}
                      />
                    ) : (
                      <CodeViewer
                        skillUid={uid}
                        path={selectedPath}
                        isOwner={isOwner}
                        skillUpdatedAt={skill.updated_at}
                        onRequestEdit={handleRequestEdit}
                      />
                    )}
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

      {pendingAction && (
        <UsageDialog
          title={
            pendingAction.type === "edit" ? "確認編輯檔案" : "確認重新上傳"
          }
          confirmLabel={
            pendingAction.type === "edit" ? "繼續編輯" : "繼續上傳"
          }
          usage={usage}
          usageLoading={usageFetching}
          onConfirm={handleConfirmUsage}
          onClose={handleCancelUsage}
        />
      )}

      {showReupload && (
        <ReuploadDialog
          skillUid={uid}
          expectedUpdatedAt={skill.updated_at}
          submitting={reuploading}
          onSubmit={handleSubmitReupload}
          onClose={handleCloseReupload}
        />
      )}
    </div>
  );
}
