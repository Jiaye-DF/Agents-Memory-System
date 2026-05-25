"use client";

import React, { useCallback, useMemo, useRef, useState } from "react";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { Button } from "@/components/ui/Button";
import { FilterChip } from "@/components/ui/FilterChip";
import { Input } from "@/components/ui/Input";
import { TagInput } from "@/components/tags";
import { useDialog } from "@/hooks/useDialog";
import { useCreateScriptMutation } from "@/store/scriptsApi";
import { useSetEntityTagsMutation } from "@/store/tagsApi";
import type { TagSummary } from "@/types";

interface ScriptUploadDialogProps {
  onClose: () => void;
}

type UploadMode = "files" | "folder";

// 與後端預設值對齊（v1.2.3 §A-2）；超限最終以後端回應為準
const MAX_TOTAL_SIZE_MB = 50;
const MAX_TOTAL_SIZE_BYTES = MAX_TOTAL_SIZE_MB * 1024 * 1024;
const MAX_FILES = 200;
const ALLOWED_EXTS = [
  ".py",
  ".sh",
  ".js",
  ".ts",
  ".json",
  ".yaml",
  ".yml",
  ".md",
  ".txt",
  ".csv",
];

function getRelativePath(file: File): string {
  const rel = (file as File & { webkitRelativePath?: string })
    .webkitRelativePath;
  return rel && rel.length > 0 ? rel : file.name;
}

function getFileExtension(filename: string): string {
  const dotIndex = filename.lastIndexOf(".");
  return dotIndex >= 0 ? filename.slice(dotIndex).toLowerCase() : "";
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

export function ScriptUploadDialog({
  onClose,
}: ScriptUploadDialogProps): React.ReactNode {
  const { showDialog } = useDialog();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  const [mode, setMode] = useState<UploadMode>("files");
  const [name, setName] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [visibility, setVisibility] = useState<"public" | "private">("private");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [tags, setTags] = useState<TagSummary[]>([]);
  const [nameError, setNameError] = useState<string>("");
  const [descriptionError, setDescriptionError] = useState<string>("");
  const [fileError, setFileError] = useState<string>("");

  const [createScript, { isLoading }] = useCreateScriptMutation();
  const [setEntityTags, { isLoading: isSettingTags }] =
    useSetEntityTagsMutation();

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

  const validateFiles = useCallback(
    (files: File[]): boolean => {
      if (files.length === 0) {
        setFileError("請選擇檔案或資料夾");
        return false;
      }
      if (files.length > MAX_FILES) {
        setFileError(`檔案數量超過上限（${MAX_FILES}）`);
        return false;
      }

      for (const f of files) {
        const rel = getRelativePath(f);
        const ext = getFileExtension(rel);
        if (!ALLOWED_EXTS.includes(ext)) {
          setFileError(`不允許的副檔名 ${ext || "(無)"}：${rel}`);
          return false;
        }
      }

      const total = files.reduce((sum, f) => sum + f.size, 0);
      if (total > MAX_TOTAL_SIZE_BYTES) {
        setFileError(
          `總大小超過上限（${MAX_TOTAL_SIZE_MB} MB）。目前 ${formatFileSize(total)}`
        );
        return false;
      }
      if (total === 0) {
        setFileError("檔案內容為空");
        return false;
      }

      setFileError("");
      return true;
    },
    []
  );

  const handleFiles = useCallback(
    (files: File[]): void => {
      if (validateFiles(files)) {
        setSelectedFiles(files);
      } else {
        setSelectedFiles([]);
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

  const handleSelectFiles = useCallback((): void => {
    setMode("files");
    fileInputRef.current?.click();
  }, []);

  const handleSelectFolder = useCallback((): void => {
    setMode("folder");
    folderInputRef.current?.click();
  }, []);

  const handleClearSelection = useCallback((): void => {
    setSelectedFiles([]);
    setFileError("");
  }, []);

  const handleNameChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setName(e.target.value);
      setNameError("");
    },
    []
  );

  const handleDescriptionChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>): void => {
      setDescription(e.target.value);
      setDescriptionError("");
    },
    []
  );

  const handleModeSwitch = useCallback((next: UploadMode): void => {
    setMode(next);
    setSelectedFiles([]);
    setFileError("");
  }, []);

  const handleSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
      e.preventDefault();

      let hasError = false;
      if (!name.trim()) {
        setNameError("名稱為必填");
        hasError = true;
      }
      if (!description.trim()) {
        setDescriptionError("描述為必填");
        hasError = true;
      }
      if (selectedFiles.length === 0) {
        setFileError("請選擇檔案或資料夾");
        hasError = true;
      }
      if (hasError) return;

      try {
        const created = await createScript({
          name: name.trim(),
          description: description.trim(),
          visibility,
          files: selectedFiles,
          relativePaths: selectedFiles.map((f) => getRelativePath(f)),
        }).unwrap();

        let tagWarning: string | null = null;
        if (tags.length > 0) {
          try {
            await setEntityTags({
              entityType: "script",
              entityUid: created.script_uid,
              body: { names: tags.map((t) => t.name) },
            }).unwrap();
          } catch (err: unknown) {
            tagWarning =
              typeof err === "string"
                ? err
                : "Script 已上傳成功，但 tag 設定失敗，請至詳細頁手動補上。";
          }
        }

        if (tagWarning) {
          showDialog({
            type: "error",
            title: "Tag 設定失敗",
            message: tagWarning,
            onConfirm: () => {
              onClose();
            },
          });
        } else {
          showDialog({
            type: "info",
            title: "上傳成功",
            message: "Script 已成功上傳。",
            onConfirm: () => {
              onClose();
            },
          });
        }
      } catch (err: unknown) {
        const message =
          typeof err === "string" ? err : "上傳失敗，請稍後再試";
        showDialog({
          type: "error",
          title: "上傳失敗",
          message,
        });
      }
    },
    [
      name,
      description,
      visibility,
      selectedFiles,
      tags,
      createScript,
      setEntityTags,
      showDialog,
      onClose,
    ]
  );

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

  return (
    <ModalDialog title="新增 Script" onClose={onClose} size="md">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted">上傳模式：</span>
          <FilterChip
            active={mode === "files"}
            onClick={() => handleModeSwitch("files")}
          >
            選檔案
          </FilterChip>
          <FilterChip
            active={mode === "folder"}
            onClick={() => handleModeSwitch("folder")}
          >
            選資料夾
          </FilterChip>
        </div>

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

        <div className="flex min-h-32 flex-col items-center justify-center rounded-xl border-2 border-dashed border-border p-4">
          {selectedFiles.length > 0 ? (
            <div className="w-full text-center">
              <p className="text-base font-medium text-foreground">{summary}</p>
              {selectedFiles.length > 1 && (
                <div className="mx-auto mt-3 max-h-28 max-w-md overflow-auto rounded-xl border border-border bg-muted-bg/30 p-2 text-left font-mono text-sm text-muted">
                  {selectedFiles.slice(0, 20).map((f, i) => (
                    <div key={i} className="truncate">
                      {getRelativePath(f)}
                    </div>
                  ))}
                  {selectedFiles.length > 20 && (
                    <div className="text-primary">
                      ...還有 {selectedFiles.length - 20} 個檔案
                    </div>
                  )}
                </div>
              )}
              <div className="mt-3 flex justify-center gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={
                    mode === "folder" ? handleSelectFolder : handleSelectFiles
                  }
                >
                  重新選擇
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={handleClearSelection}
                >
                  清除
                </Button>
              </div>
            </div>
          ) : (
            <div className="text-center">
              <p className="text-base text-muted">
                {mode === "folder"
                  ? "選擇整個資料夾進行打包上傳"
                  : "選擇一個或多個檔案"}
              </p>
              <p className="mt-1 text-sm text-muted">
                允許副檔名：{ALLOWED_EXTS.join(" / ")}
              </p>
              <p className="text-sm text-muted">
                總大小上限 {MAX_TOTAL_SIZE_MB} MB、檔案數上限 {MAX_FILES}
              </p>
              <div className="mt-3">
                <Button
                  size="sm"
                  onClick={
                    mode === "folder" ? handleSelectFolder : handleSelectFiles
                  }
                >
                  {mode === "folder" ? "選擇資料夾" : "選擇檔案"}
                </Button>
              </div>
            </div>
          )}
        </div>
        {fileError && (
          <p className="text-base text-destructive">{fileError}</p>
        )}

        <Input
          label="名稱"
          required
          value={name}
          onChange={handleNameChange}
          error={nameError}
          placeholder="輸入 Script 名稱"
        />

        <div className="w-full">
          <label
            htmlFor="script-description"
            className="mb-1.5 block text-base font-medium text-foreground"
          >
            描述
            <span className="ml-0.5 text-destructive">*</span>
          </label>
          <textarea
            id="script-description"
            value={description}
            onChange={handleDescriptionChange}
            placeholder="輸入 Script 描述"
            rows={3}
            required
            aria-invalid={descriptionError ? true : undefined}
            className="min-h-16 w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
          />
          {descriptionError && (
            <p className="mt-1 text-base text-destructive">{descriptionError}</p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="shrink-0 text-base font-medium text-foreground">
            可見性：
          </span>
          <FilterChip
            active={visibility === "private"}
            onClick={() => setVisibility("private")}
          >
            私人
          </FilterChip>
          <FilterChip
            active={visibility === "public"}
            onClick={() => setVisibility("public")}
          >
            公開
          </FilterChip>
        </div>

        <div className="w-full">
          <label className="mb-1.5 block text-base font-medium text-foreground">
            標籤
          </label>
          <TagInput
            value={tags}
            onChange={setTags}
            disabled={isLoading || isSettingTags}
          />
          <p className="mt-1 text-sm text-muted">
            可自由輸入或從下拉建議中挑選，按 Enter 新增；標籤跨 Skill / Script / Agent 共用。
          </p>
        </div>

        <div className="mt-2 flex justify-end gap-3">
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            disabled={isLoading || isSettingTags}
          >
            取消
          </Button>
          <Button type="submit" loading={isLoading || isSettingTags}>
            上傳
          </Button>
        </div>
      </form>
    </ModalDialog>
  );
}
