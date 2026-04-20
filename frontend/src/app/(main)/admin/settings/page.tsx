"use client";

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { PageLoading } from "@/components/ui/Loading";
import { Toggle } from "@/components/ui/Toggle";
import { useDialog } from "@/hooks/useDialog";
import { useAuth } from "@/hooks/useAuth";
import {
  useListAdminSettingsQuery,
  useUpdateSettingMutation,
} from "@/store/systemSettingsApi";
import type { SystemSetting, SystemSettingValueType } from "@/types";
import { formatDateTime } from "@/utils/datetime";

function validateValue(
  raw: string,
  valueType: SystemSettingValueType
): string | null {
  const trimmed = raw.trim();
  if (valueType === "integer") {
    if (!/^-?\d+$/.test(trimmed)) {
      return "整數格式錯誤（請輸入數字）";
    }
  } else if (valueType === "boolean") {
    if (!["true", "false"].includes(trimmed.toLowerCase())) {
      return "布林值需為 true 或 false";
    }
  } else if (valueType === "json") {
    try {
      JSON.parse(trimmed);
    } catch {
      return "JSON 格式錯誤";
    }
  }
  return null;
}

interface SettingFormDialogProps {
  setting: SystemSetting;
  submitting: boolean;
  onSubmit: (payload: {
    value: string;
    description: string | null;
    is_public: boolean;
    is_active: boolean;
  }) => Promise<void>;
  onClose: () => void;
}

const SettingFormDialog = React.memo(function SettingFormDialog({
  setting,
  submitting,
  onSubmit,
  onClose,
}: SettingFormDialogProps): React.ReactNode {
  const overlayRef = useRef<HTMLDivElement>(null);
  const [value, setValue] = useState<string>(setting.value);
  const [description, setDescription] = useState<string>(
    setting.description ?? ""
  );
  const [isPublic, setIsPublic] = useState<boolean>(setting.is_public);
  const [isActive, setIsActive] = useState<boolean>(setting.is_active);
  const [valueError, setValueError] = useState<string>("");

  const handleKeyDown = useCallback(
    (e: KeyboardEvent): void => {
      if (e.key === "Escape") onClose();
    },
    [onClose]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";
    return (): void => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [handleKeyDown]);

  const handleOverlayClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>): void => {
      if (e.target === overlayRef.current) onClose();
    },
    [onClose]
  );

  const handleValueChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>): void => {
      setValue(e.target.value);
      setValueError("");
    },
    []
  );

  const handleToggleValueBoolean = useCallback((next: boolean): void => {
    setValue(next ? "true" : "false");
    setValueError("");
  }, []);

  const handleDescriptionChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>): void => {
      setDescription(e.target.value);
    },
    []
  );

  const handleTogglePublic = useCallback((next: boolean): void => {
    setIsPublic(next);
  }, []);

  const handleToggleActive = useCallback((next: boolean): void => {
    setIsActive(next);
  }, []);

  const handleSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
      e.preventDefault();
      const err = validateValue(value, setting.value_type);
      if (err) {
        setValueError(err);
        return;
      }
      await onSubmit({
        value: value.trim(),
        description: description.trim() || null,
        is_public: isPublic,
        is_active: isActive,
      });
    },
    [value, description, isPublic, isActive, setting.value_type, onSubmit]
  );

  const valueBoolean = value.toLowerCase() === "true";

  const content = (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4"
      onClick={handleOverlayClick}
    >
      <div className="w-full max-w-md rounded-xl bg-card-bg p-6 shadow-lg">
        <h3 className="mb-1 text-xl font-semibold text-foreground">
          {setting.description || "編輯系統設定"}
        </h3>
        <p className="mb-4 font-mono text-sm text-muted">{setting.key}</p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="mb-1.5 block text-base font-medium text-foreground">
              型別
            </label>
            <div className="min-h-11 w-full rounded-xl border border-input-border bg-muted-bg px-3 py-2 font-mono text-base text-muted">
              {setting.value_type}
            </div>
          </div>

          <div>
            <label
              htmlFor="setting-value"
              className="mb-1.5 block text-base font-medium text-foreground"
            >
              Value
              <span className="ml-0.5 text-destructive">*</span>
            </label>
            {setting.value_type === "boolean" ? (
              <div className="flex items-center justify-between rounded-xl border border-input-border bg-input-bg px-3 py-2">
                <span className="font-mono text-base text-foreground">
                  {value || "false"}
                </span>
                <Toggle
                  checked={valueBoolean}
                  onChange={handleToggleValueBoolean}
                  disabled={submitting}
                  label="切換布林值"
                />
              </div>
            ) : setting.value_type === "integer" ? (
              <Input
                id="setting-value"
                type="number"
                value={value}
                onChange={handleValueChange}
                error={valueError}
                disabled={submitting}
              />
            ) : setting.value_type === "json" ? (
              <textarea
                id="setting-value"
                value={value}
                onChange={handleValueChange}
                rows={5}
                disabled={submitting}
                className={`min-h-11 w-full rounded-xl border bg-input-bg px-3 py-2 font-mono text-sm text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20 ${
                  valueError ? "border-destructive" : "border-input-border"
                }`}
              />
            ) : (
              <Input
                id="setting-value"
                value={value}
                onChange={handleValueChange}
                error={valueError}
                disabled={submitting}
              />
            )}
            {valueError && setting.value_type !== "integer" && (
              <p className="mt-1 text-base text-destructive">{valueError}</p>
            )}
          </div>

          <div>
            <label
              htmlFor="setting-desc"
              className="mb-1.5 block text-base font-medium text-foreground"
            >
              說明
            </label>
            <textarea
              id="setting-desc"
              value={description}
              onChange={handleDescriptionChange}
              rows={3}
              disabled={submitting}
              className="min-h-11 w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
            />
          </div>

          <div className="flex items-center justify-between">
            <span className="text-base font-medium text-foreground">
              公開設定（member 可讀取）
            </span>
            <Toggle
              checked={isPublic}
              onChange={handleTogglePublic}
              disabled={submitting}
              label="切換公開設定"
            />
          </div>

          <div className="flex items-center justify-between">
            <span className="text-base font-medium text-foreground">
              啟用狀態
            </span>
            <Toggle
              checked={isActive}
              onChange={handleToggleActive}
              disabled={submitting}
              label="切換啟用狀態"
            />
          </div>

          <div className="mt-2 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="min-h-11 rounded-xl border border-border px-4 py-2 text-base font-medium text-foreground hover:cursor-pointer hover:bg-muted-bg"
            >
              取消
            </button>
            <Button type="submit" loading={submitting}>
              儲存
            </Button>
          </div>
        </form>
      </div>
    </div>
  );

  if (typeof document === "undefined") return null;
  return createPortal(content, document.body);
});

interface SettingRowProps {
  setting: SystemSetting;
  onEdit: (s: SystemSetting) => void;
}

const SettingRow = React.memo(function SettingRow({
  setting,
  onEdit,
}: SettingRowProps): React.ReactNode {
  const handleEdit = useCallback((): void => {
    onEdit(setting);
  }, [setting, onEdit]);

  return (
    <div className="flex flex-col gap-3 px-4 py-4 transition-colors hover:bg-muted-bg/40 md:flex-row md:items-start md:gap-6">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="truncate text-lg font-semibold text-foreground">
            {setting.description || setting.key}
          </h3>
          <span className="shrink-0 rounded-xl bg-muted-bg px-2 py-0.5 font-mono text-sm text-muted">
            {setting.value_type}
          </span>
          {setting.is_public && (
            <span className="shrink-0 rounded-xl bg-info-bg px-2 py-0.5 text-sm font-medium text-info">
              公開
            </span>
          )}
          <span
            className={`shrink-0 rounded-xl px-2 py-0.5 text-sm font-medium ${
              setting.is_active
                ? "bg-success/10 text-success"
                : "bg-muted-bg text-muted"
            }`}
          >
            {setting.is_active ? "啟用" : "停用"}
          </span>
        </div>

        <p className="mt-1 font-mono text-sm text-muted">{setting.key}</p>

        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <span className="shrink-0 text-muted">目前值：</span>
          <code className="break-all rounded-md bg-muted-bg px-2 py-0.5 font-mono text-foreground">
            {setting.value}
          </code>
          <span className="text-muted">
            更新於 {formatDateTime(setting.updated_at)}
          </span>
        </div>
      </div>

      <div className="shrink-0 md:pt-1">
        <Button size="sm" variant="secondary" onClick={handleEdit}>
          編輯
        </Button>
      </div>
    </div>
  );
});

export default function AdminSettingsPage(): React.ReactNode {
  const router = useRouter();
  const { role, isLoading: authLoading } = useAuth();
  const { showDialog } = useDialog();

  const [editTarget, setEditTarget] = useState<SystemSetting | null>(null);

  useEffect(() => {
    if (!authLoading && role !== "admin") {
      router.replace("/403");
    }
  }, [role, authLoading, router]);

  const { data, isLoading, isFetching } = useListAdminSettingsQuery(undefined, {
    skip: authLoading || role !== "admin",
  });

  const [updateSetting, { isLoading: updating }] = useUpdateSettingMutation();

  const items = useMemo(
    (): SystemSetting[] => data?.items ?? [],
    [data]
  );

  const handleOpenEdit = useCallback((s: SystemSetting): void => {
    setEditTarget(s);
  }, []);

  const handleCloseForm = useCallback((): void => {
    setEditTarget(null);
  }, []);

  const handleSubmitForm = useCallback(
    async (payload: {
      value: string;
      description: string | null;
      is_public: boolean;
      is_active: boolean;
    }): Promise<void> => {
      if (!editTarget) return;
      try {
        await updateSetting({
          key: editTarget.key,
          body: payload,
        }).unwrap();
        setEditTarget(null);
        showDialog({
          type: "info",
          title: "更新成功",
          message: "系統設定已更新。",
        });
      } catch (err: unknown) {
        const message =
          typeof err === "string" ? err : "更新失敗，請稍後再試";
        showDialog({
          type: "error",
          title: "操作失敗",
          message,
        });
      }
    },
    [editTarget, updateSetting, showDialog]
  );

  if (authLoading || role !== "admin") {
    return <PageLoading />;
  }

  return (
    <div>
      <h1 className="mb-4 text-3xl font-bold text-foreground">系統設定</h1>
      <div className="overflow-hidden rounded-xl bg-card-bg shadow-sm">
        {isLoading || isFetching ? (
          <PageLoading />
        ) : items.length === 0 ? (
          <div className="py-12 text-center text-base text-muted">
            尚無系統設定
          </div>
        ) : (
          <div className="divide-y divide-border">
            {items.map((setting) => (
              <SettingRow
                key={setting.system_setting_uid}
                setting={setting}
                onEdit={handleOpenEdit}
              />
            ))}
          </div>
        )}
      </div>

      {editTarget && (
        <SettingFormDialog
          setting={editTarget}
          submitting={updating}
          onSubmit={handleSubmitForm}
          onClose={handleCloseForm}
        />
      )}
    </div>
  );
}
