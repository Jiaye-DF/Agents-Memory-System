"use client";

import React, { useCallback, useState } from "react";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

interface EditResourceDialogProps {
  title: string;
  initialName: string;
  initialDescription: string;
  /** description 是否必填（skill 必填、script 可選）*/
  descriptionRequired?: boolean;
  onClose: () => void;
  onSubmit: (next: { name: string; description: string }) => Promise<void>;
}

export const EditResourceDialog = React.memo(function EditResourceDialog({
  title,
  initialName,
  initialDescription,
  descriptionRequired = false,
  onClose,
  onSubmit,
}: EditResourceDialogProps): React.ReactNode {
  const [name, setName] = useState<string>(initialName);
  const [description, setDescription] = useState<string>(initialDescription);
  const [nameError, setNameError] = useState<string>("");
  const [descriptionError, setDescriptionError] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);

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
      if (descriptionRequired && !description.trim()) {
        setDescriptionError("描述為必填");
        hasError = true;
      }
      if (hasError) return;

      setSubmitting(true);
      try {
        await onSubmit({
          name: name.trim(),
          description: description.trim(),
        });
        onClose();
      } finally {
        setSubmitting(false);
      }
    },
    [name, description, descriptionRequired, onSubmit, onClose]
  );

  return (
    <ModalDialog title={title} onClose={onClose} size="md">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          label="名稱"
          required
          value={name}
          onChange={handleNameChange}
          error={nameError}
          placeholder="輸入名稱"
        />

        <div className="w-full">
          <label
            htmlFor="edit-resource-description"
            className="mb-1.5 block text-base font-medium text-foreground"
          >
            描述
            {descriptionRequired && (
              <span className="ml-0.5 text-destructive">*</span>
            )}
          </label>
          <textarea
            id="edit-resource-description"
            value={description}
            onChange={handleDescriptionChange}
            placeholder="輸入描述"
            rows={4}
            className={`min-h-22 w-full rounded-xl border bg-input-bg px-3 py-2 text-base text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20 ${
              descriptionError ? "border-destructive" : "border-input-border"
            }`}
          />
          {descriptionError && (
            <p className="mt-1 text-base text-destructive">
              {descriptionError}
            </p>
          )}
        </div>

        <div className="flex justify-end gap-2">
          <Button
            variant="secondary"
            onClick={onClose}
            disabled={submitting}
          >
            取消
          </Button>
          <Button type="submit" loading={submitting}>
            儲存
          </Button>
        </div>
      </form>
    </ModalDialog>
  );
});
