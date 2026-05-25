"use client";

import React, { useState, useCallback, useRef, useMemo } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { TagInput } from "@/components/tags";
import { useDialog } from "@/hooks/useDialog";
import { useUploadSkillMutation } from "@/store/skillsApi";
import { useSetEntityTagsMutation } from "@/store/tagsApi";
import type { TagSummary } from "@/types";

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

export default function SkillsUploadPage(): React.ReactNode {
  const router = useRouter();
  const { showDialog } = useDialog();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  const [name, setName] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [tags, setTags] = useState<TagSummary[]>([]);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const [nameError, setNameError] = useState<string>("");
  const [descriptionError, setDescriptionError] = useState<string>("");
  const [fileError, setFileError] = useState<string>("");

  const [uploadSkill, { isLoading }] = useUploadSkillMutation();
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
      if (dropped.length > 0) {
        handleFiles(dropped);
      }
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
        const created = await uploadSkill({
          name: name.trim(),
          description: description.trim(),
          files: selectedFiles,
        }).unwrap();

        let tagWarning: string | null = null;
        if (tags.length > 0) {
          try {
            await setEntityTags({
              entityType: "skill",
              entityUid: created.skill_uid,
              body: { names: tags.map((t) => t.name) },
            }).unwrap();
          } catch (err: unknown) {
            tagWarning =
              typeof err === "string"
                ? err
                : "Skill 已上傳成功，但標籤設定失敗，請至詳細頁手動補上。";
          }
        }

        if (tagWarning) {
          showDialog({
            type: "error",
            title: "標籤設定失敗",
            message: tagWarning,
            onConfirm: () => {
              router.push("/skills");
            },
          });
        } else {
          showDialog({
            type: "info",
            title: "上傳成功",
            message: "Skill 已成功上傳。",
            onConfirm: () => {
              router.push("/skills");
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
      selectedFiles,
      tags,
      uploadSkill,
      setEntityTags,
      showDialog,
      router,
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
    <div>
      <h1 className="mb-4 text-3xl font-bold text-foreground">上傳 Skill</h1>

      <div className="rounded-xl bg-card-bg p-6 shadow-sm">
        <form onSubmit={handleSubmit} className="flex flex-col gap-6">
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            className={`flex min-h-45 flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 transition-colors ${
              isDragOver
                ? "border-primary bg-primary/5"
                : "border-border"
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
                {selectedFiles.length > 1 && (
                  <div className="mx-auto mt-3 max-h-32 max-w-md overflow-auto rounded-xl border border-border bg-muted-bg/30 p-2 text-left font-mono text-sm text-muted">
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
                    onClick={handleSelectFiles}
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
                <svg
                  className="mx-auto mb-2 h-10 w-10 text-muted"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
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
                  >
                    選擇資料夾
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={handleSelectFiles}
                  >
                    選擇檔案
                  </Button>
                </div>
              </div>
            )}
          </div>
          {fileError && (
            <p className="-mt-4 text-base text-destructive">{fileError}</p>
          )}

          <Input
            label="名稱"
            required
            value={name}
            onChange={handleNameChange}
            error={nameError}
            placeholder="輸入 Skill 名稱"
          />

          <div className="w-full">
            <label
              htmlFor="skill-description"
              className="mb-1.5 block text-base font-medium text-foreground"
            >
              描述<span className="ml-0.5 text-destructive">*</span>
            </label>
            <textarea
              id="skill-description"
              value={description}
              onChange={handleDescriptionChange}
              placeholder="輸入 Skill 描述"
              rows={4}
              className={`min-h-22 w-full rounded-xl border bg-input-bg px-3 py-2 text-base text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20 ${
                descriptionError
                  ? "border-destructive"
                  : "border-input-border"
              }`}
            />
            {descriptionError && (
              <p className="mt-1 text-base text-destructive">
                {descriptionError}
              </p>
            )}
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

          <div className="flex justify-end gap-3">
            <Button
              variant="secondary"
              onClick={() => router.push("/skills")}
              disabled={isLoading || isSettingTags}
            >
              取消
            </Button>
            <Button type="submit" loading={isLoading || isSettingTags}>
              上傳
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
