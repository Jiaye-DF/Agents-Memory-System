"use client";

import React, { useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useDialog } from "@/hooks/useDialog";
import { useUploadSkillMutation } from "@/store/skillsApi";

const MAX_FILE_SIZE = 50 * 1024 * 1024;
const BLOCKED_EXTENSIONS = [".exe"];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function getFileExtension(filename: string): string {
  const dotIndex = filename.lastIndexOf(".");
  return dotIndex >= 0 ? filename.slice(dotIndex).toLowerCase() : "";
}

export default function SkillsUploadPage(): React.ReactNode {
  const router = useRouter();
  const { showDialog } = useDialog();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [name, setName] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const [nameError, setNameError] = useState<string>("");
  const [descriptionError, setDescriptionError] = useState<string>("");
  const [fileError, setFileError] = useState<string>("");

  const [uploadSkill, { isLoading }] = useUploadSkillMutation();

  const validateFile = useCallback(
    (file: File): boolean => {
      const ext = getFileExtension(file.name);

      if (BLOCKED_EXTENSIONS.includes(ext)) {
        showDialog({
          type: "error",
          title: "不允許的檔案類型",
          message: "不允許上傳 .exe 檔案。",
        });
        return false;
      }

      if (file.size > MAX_FILE_SIZE) {
        showDialog({
          type: "error",
          title: "檔案過大",
          message: `檔案大小超過上限（50 MB）。目前大小：${formatFileSize(file.size)}`,
        });
        return false;
      }

      if (file.size === 0) {
        setFileError("檔案內容為空");
        return false;
      }

      return true;
    },
    [showDialog]
  );

  const handleFileSelect = useCallback(
    (file: File): void => {
      setFileError("");
      if (validateFile(file)) {
        setSelectedFile(file);
      }
    },
    [validateFile]
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      const file = e.target.files?.[0];
      if (file) {
        handleFileSelect(file);
      }
    },
    [handleFileSelect]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>): void => {
      e.preventDefault();
      setIsDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) {
        handleFileSelect(file);
      }
    },
    [handleFileSelect]
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

  const handleDropZoneClick = useCallback((): void => {
    fileInputRef.current?.click();
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

      if (!selectedFile) {
        setFileError("請選擇檔案");
        hasError = true;
      }

      if (hasError || !selectedFile) return;

      try {
        await uploadSkill({
          name: name.trim(),
          description: description.trim(),
          file: selectedFile,
        }).unwrap();

        showDialog({
          type: "info",
          title: "上傳成功",
          message: "Skill 已成功上傳。",
          onConfirm: () => {
            router.push("/skills");
          },
        });
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
    [name, description, selectedFile, uploadSkill, showDialog, router]
  );

  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold text-foreground">上傳 Skill</h1>

      <div className="rounded-xl bg-card-bg p-6 shadow-sm">
        <form onSubmit={handleSubmit} className="flex flex-col gap-6">
          <div
            onClick={handleDropZoneClick}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            className={`flex min-h-[160px] flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 transition-colors hover:cursor-pointer ${
              isDragOver
                ? "border-primary bg-primary/5"
                : "border-border hover:border-primary/50"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              onChange={handleInputChange}
              className="hidden"
            />
            {selectedFile ? (
              <div className="text-center">
                <p className="text-sm font-medium text-foreground">
                  {selectedFile.name}
                </p>
                <p className="mt-1 text-xs text-muted">
                  {formatFileSize(selectedFile.size)}
                </p>
                <p className="mt-2 text-xs text-primary hover:cursor-pointer">
                  點擊重新選擇檔案
                </p>
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
                <p className="text-sm text-muted">
                  拖曳檔案至此處，或點擊選擇檔案
                </p>
                <p className="mt-1 text-xs text-muted">
                  檔案大小上限 50 MB，禁止上傳 .exe
                </p>
              </div>
            )}
          </div>
          {fileError && (
            <p className="-mt-4 text-sm text-destructive">{fileError}</p>
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
              className="mb-1.5 block text-sm font-medium text-foreground"
            >
              描述<span className="ml-0.5 text-destructive">*</span>
            </label>
            <textarea
              id="skill-description"
              value={description}
              onChange={handleDescriptionChange}
              placeholder="輸入 Skill 描述"
              rows={4}
              className={`min-h-[88px] w-full rounded-xl border bg-input-bg px-3 py-2 text-sm text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20 ${
                descriptionError
                  ? "border-destructive"
                  : "border-input-border"
              }`}
            />
            {descriptionError && (
              <p className="mt-1 text-sm text-destructive">
                {descriptionError}
              </p>
            )}
          </div>

          <div className="flex justify-end gap-3">
            <Button
              variant="secondary"
              onClick={() => router.push("/skills")}
              disabled={isLoading}
            >
              取消
            </Button>
            <Button type="submit" loading={isLoading}>
              上傳
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
