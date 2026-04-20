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
import { Table } from "@/components/ui/Table";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { PageLoading } from "@/components/ui/Loading";
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

  const handleToggleValueBoolean = useCallback((): void => {
    setValue((prev) => (prev.toLowerCase() === "true" ? "false" : "true"));
    setValueError("");
  }, []);

  const handleDescriptionChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>): void => {
      setDescription(e.target.value);
    },
    []
  );

  const handleTogglePublic = useCallback((): void => {
    setIsPublic((prev) => !prev);
  }, []);

  const handleToggleActive = useCallback((): void => {
    setIsActive((prev) => !prev);
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
        <h3 className="mb-4 text-xl font-semibold text-foreground">
          編輯系統設定
        </h3>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="mb-1.5 block text-base font-medium text-foreground">
              Key
            </label>
            <div className="min-h-[44px] w-full rounded-xl border border-input-border bg-muted-bg px-3 py-2 font-mono text-base text-muted">
              {setting.key}
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-base font-medium text-foreground">
              型別
            </label>
            <div className="min-h-[44px] w-full rounded-xl border border-input-border bg-muted-bg px-3 py-2 font-mono text-base text-muted">
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
                <button
                  type="button"
                  onClick={handleToggleValueBoolean}
                  disabled={submitting}
                  className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors hover:cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 ${
                    valueBoolean ? "bg-primary" : "bg-muted-bg"
                  }`}
                  aria-pressed={valueBoolean}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      valueBoolean ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </button>
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
                className={`min-h-[44px] w-full rounded-xl border bg-input-bg px-3 py-2 font-mono text-sm text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20 ${
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
              className="min-h-[44px] w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground transition-colors placeholder:text-muted focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
            />
          </div>

          <div className="flex items-center justify-between">
            <span className="text-base font-medium text-foreground">
              公開設定（member 可讀取）
            </span>
            <button
              type="button"
              onClick={handleTogglePublic}
              disabled={submitting}
              className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors hover:cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 ${
                isPublic ? "bg-primary" : "bg-muted-bg"
              }`}
              aria-pressed={isPublic}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  isPublic ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-base font-medium text-foreground">
              啟用狀態
            </span>
            <button
              type="button"
              onClick={handleToggleActive}
              disabled={submitting}
              className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors hover:cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 ${
                isActive ? "bg-primary" : "bg-muted-bg"
              }`}
              aria-pressed={isActive}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  isActive ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>

          <div className="mt-2 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="min-h-[44px] rounded-xl border border-border px-4 py-2 text-base font-medium text-foreground hover:cursor-pointer hover:bg-muted-bg"
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

interface SettingCardProps {
  setting: SystemSetting;
  onEdit: (s: SystemSetting) => void;
}

const SettingCard = React.memo(function SettingCard({
  setting,
  onEdit,
}: SettingCardProps): React.ReactNode {
  const handleEdit = useCallback((): void => {
    onEdit(setting);
  }, [setting, onEdit]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-mono font-medium text-foreground">
          {setting.key}
        </span>
        <span className="shrink-0 rounded-xl bg-muted-bg px-2 py-0.5 font-mono text-sm text-muted">
          {setting.value_type}
        </span>
      </div>
      <div className="break-all rounded-xl bg-muted-bg/60 p-2 font-mono text-sm text-foreground">
        {setting.value}
      </div>
      {setting.description && (
        <div className="text-sm text-muted">{setting.description}</div>
      )}
      <div className="flex items-center gap-2 text-sm">
        {setting.is_public && (
          <span className="rounded-xl bg-info-bg px-2 py-0.5 font-medium text-info">
            公開
          </span>
        )}
        <span
          className={`rounded-xl px-2 py-0.5 font-medium ${
            setting.is_active
              ? "bg-success/10 text-success"
              : "bg-muted-bg text-muted"
          }`}
        >
          {setting.is_active ? "啟用" : "停用"}
        </span>
      </div>
      <div className="text-sm text-muted">
        更新時間：{formatDateTime(setting.updated_at)}
      </div>
      <div>
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

  const columns = useMemo(
    () => [
      {
        key: "key",
        header: "Key",
        render: (s: SystemSetting): React.ReactNode => (
          <span className="font-mono text-base text-foreground">{s.key}</span>
        ),
      },
      {
        key: "value_type",
        header: "型別",
        render: (s: SystemSetting): React.ReactNode => (
          <span className="rounded-xl bg-muted-bg px-2 py-0.5 font-mono text-sm text-muted">
            {s.value_type}
          </span>
        ),
      },
      {
        key: "value",
        header: "值",
        render: (s: SystemSetting): React.ReactNode => (
          <span className="break-all font-mono text-base text-foreground">
            {s.value}
          </span>
        ),
      },
      {
        key: "description",
        header: "說明",
        render: (s: SystemSetting): React.ReactNode => (
          <span className="text-base text-muted">{s.description ?? "-"}</span>
        ),
      },
      {
        key: "is_public",
        header: "公開",
        render: (s: SystemSetting): React.ReactNode =>
          s.is_public ? (
            <span className="rounded-xl bg-info-bg px-2 py-0.5 text-sm font-medium text-info">
              公開
            </span>
          ) : (
            <span className="text-sm text-muted">-</span>
          ),
      },
      {
        key: "is_active",
        header: "狀態",
        render: (s: SystemSetting): React.ReactNode => (
          <span
            className={`rounded-xl px-2 py-0.5 text-sm font-medium ${
              s.is_active
                ? "bg-success/10 text-success"
                : "bg-muted-bg text-muted"
            }`}
          >
            {s.is_active ? "啟用" : "停用"}
          </span>
        ),
      },
      {
        key: "actions",
        header: "操作",
        render: (s: SystemSetting): React.ReactNode => (
          <Button
            size="sm"
            variant="secondary"
            onClick={() => handleOpenEdit(s)}
          >
            編輯
          </Button>
        ),
      },
    ],
    [handleOpenEdit]
  );

  const keyExtractor = useCallback(
    (s: SystemSetting): string => s.system_setting_uid,
    []
  );

  const cardRender = useCallback(
    (s: SystemSetting): React.ReactNode => (
      <SettingCard setting={s} onEdit={handleOpenEdit} />
    ),
    [handleOpenEdit]
  );

  if (authLoading || role !== "admin") {
    return <PageLoading />;
  }

  return (
    <div>
      <h1 className="mb-4 text-3xl font-bold text-foreground">系統設定</h1>
      <div className="rounded-xl bg-card-bg p-6 shadow-sm">
        {isLoading || isFetching ? (
          <PageLoading />
        ) : (
          <Table
            columns={columns}
            data={items}
            keyExtractor={keyExtractor}
            cardRender={cardRender}
            emptyMessage="尚無系統設定"
          />
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
