"use client";

import React, {
  useCallback,
  useMemo,
  useState,
} from "react";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { PageLoading } from "@/components/ui/Loading";
import { Toggle } from "@/components/ui/Toggle";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { useAdminGuard } from "@/hooks/useAdminGuard";
import { useMutationWithDialog } from "@/hooks/useMutationWithDialog";
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

interface SettingMeta {
  label: string;
  hint: string;
  unit?: string;
}

const SETTING_META: Record<string, SettingMeta> = {
  "agent.max_skills": {
    label: "每個 Agent 最多可掛載的 Skills",
    hint: "防止單一 Agent 掛載過多 Skills 造成 system prompt token 爆掉；建議 5 ~ 15。",
  },
  "chat.max_sessions_per_project": {
    label: "每個專案可建立的對話上限",
    hint: "參考 ChatGPT Projects 觀察，超過 5 個對話後記憶與回覆品質下降；建議 3 ~ 5。",
  },
  "chat.max_projects_per_user": {
    label: "每位使用者可建立的專案上限",
    hint: "防止濫建；預設 5、最大建議 20。",
  },
  "chat.max_orphan_sessions_per_user": {
    label: "每位使用者可建立的獨立對話上限",
    hint: "不屬於任何專案的對話數量上限；預設 10、硬上限 30。與專案內的對話分開計算。",
  },
  "memory.extractor_model": {
    label: "記憶摘要用的 LLM 模型",
    hint: "負責把對話訊息抽成記憶條目，建議用便宜的小模型（如 claude-haiku / gemini-flash）降低成本。",
  },
  "memory.batch_size": {
    label: "批次大小",
    hint: "每累積 N 則訊息觸發一次摘要；太大記憶延遲、太小 API 成本高。",
    unit: "則訊息",
  },
  "memory.idle_seconds": {
    label: "Idle 閾值",
    hint: "即使未達批次大小，閒置超過 N 秒也會立即摘要；與批次大小任一條件成立即觸發。",
    unit: "秒",
  },
  "memory.skip_rules": {
    label: "預篩規則",
    hint: "訊息短於 min_length、出現在 greeting_whitelist、或超過 max_tokens 會跳過摘要以省 token。",
  },
  "rag.enabled": {
    label: "啟用 RAG 檢索注入",
    hint: "關閉後對話不會參考過去記憶，只用 system prompt + 當前訊息回應。",
  },
  "rag.top_k": {
    label: "檢索 Top-K",
    hint: "每次檢索取最相似的 N 筆記憶注入；太大會稀釋 prompt 焦點，建議 3 ~ 7。",
    unit: "筆",
  },
  "rag.min_score": {
    label: "相似度最低門檻",
    hint: "cosine similarity 低於此值的記憶不注入；0.7 ~ 0.8 通常有效，過低會帶入雜訊。",
  },
};

interface GroupMeta {
  title: string;
  description: string;
}

const GROUP_META: Record<string, GroupMeta> = {
  agent: {
    title: "Agent",
    description: "Agent 建立與掛載限制",
  },
  chat: {
    title: "對話 / 專案",
    description: "專案與對話的建立上限",
  },
  memory: {
    title: "記憶抽取",
    description: "對話訊息的摘要流程與預篩規則",
  },
  rag: {
    title: "RAG 檢索",
    description: "自動檢索歷史記憶注入 system prompt 的行為",
  },
};

const GROUP_ORDER = ["chat", "agent", "memory", "rag"] as const;

function getGroupKey(settingKey: string): string {
  const dot = settingKey.indexOf(".");
  return dot > 0 ? settingKey.slice(0, dot) : "other";
}

function formatDisplayValue(setting: SystemSetting): string {
  const meta = SETTING_META[setting.key];
  if (setting.value_type === "boolean") {
    return setting.value.toLowerCase() === "true" ? "啟用" : "停用";
  }
  if (setting.value_type === "integer" && meta?.unit) {
    return `${setting.value} ${meta.unit}`;
  }
  return setting.value;
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
  const [value, setValue] = useState<string>(setting.value);
  const [description, setDescription] = useState<string>(
    setting.description ?? ""
  );
  const [isPublic, setIsPublic] = useState<boolean>(setting.is_public);
  const [isActive, setIsActive] = useState<boolean>(setting.is_active);
  const [valueError, setValueError] = useState<string>("");

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
  const modalTitle =
    SETTING_META[setting.key]?.label ||
    setting.description ||
    "編輯系統設定";

  return (
    <ModalDialog title={modalTitle} onClose={onClose}>
      <p className="mb-4 -mt-2 font-mono text-sm text-muted">{setting.key}</p>
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
    </ModalDialog>
  );
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

  const meta = SETTING_META[setting.key];
  const title = meta?.label ?? setting.description ?? setting.key;
  const hint = meta?.hint ?? setting.description;
  const showFallbackDesc =
    !meta && setting.description && setting.description !== title;

  return (
    <div className="flex flex-col gap-3 px-4 py-4 transition-colors hover:bg-muted-bg/40 md:flex-row md:items-start md:gap-6">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="truncate text-lg font-semibold text-foreground">
            {title}
          </h3>
          {setting.is_public && (
            <span className="shrink-0 rounded-xl bg-info-bg px-2 py-0.5 text-sm font-medium text-info">
              公開
            </span>
          )}
          {!setting.is_active && (
            <span className="shrink-0 rounded-xl bg-muted-bg px-2 py-0.5 text-sm font-medium text-muted">
              停用
            </span>
          )}
        </div>

        <p className="mt-0.5 font-mono text-sm text-muted">{setting.key}</p>

        {meta && hint && (
          <p className="mt-2 text-sm text-muted">{hint}</p>
        )}
        {showFallbackDesc && (
          <p className="mt-2 text-sm text-muted">{setting.description}</p>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <span className="shrink-0 text-muted">目前值：</span>
          <code className="break-all rounded-md bg-muted-bg px-2 py-0.5 font-mono text-foreground">
            {formatDisplayValue(setting)}
          </code>
          <span className="shrink-0 rounded-xl bg-muted-bg px-2 py-0.5 font-mono text-sm text-muted">
            {setting.value_type}
          </span>
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
  const { authLoading, isAdmin, shouldBlockRender } = useAdminGuard();
  const [editTarget, setEditTarget] = useState<SystemSetting | null>(null);

  const { data, isLoading, isFetching } = useListAdminSettingsQuery(undefined, {
    skip: authLoading || !isAdmin,
  });

  const [updateSetting, { isLoading: updating }] = useUpdateSettingMutation();
  const runUpdate = useMutationWithDialog(updateSetting);

  const items = useMemo(
    (): SystemSetting[] => data?.items ?? [],
    [data]
  );

  const groupedItems = useMemo((): { key: string; items: SystemSetting[] }[] => {
    const bucket = new Map<string, SystemSetting[]>();
    for (const s of items) {
      const g = getGroupKey(s.key);
      const list = bucket.get(g) ?? [];
      list.push(s);
      bucket.set(g, list);
    }
    for (const [, list] of bucket) {
      list.sort((a, b) => a.key.localeCompare(b.key));
    }
    const ordered: { key: string; items: SystemSetting[] }[] = [];
    for (const g of GROUP_ORDER) {
      const list = bucket.get(g);
      if (list && list.length > 0) {
        ordered.push({ key: g, items: list });
        bucket.delete(g);
      }
    }
    for (const [g, list] of bucket) {
      ordered.push({ key: g, items: list });
    }
    return ordered;
  }, [items]);

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
      await runUpdate(
        {
          key: editTarget.key,
          body: payload,
        },
        {
          successTitle: "更新成功",
          successMessage: "系統設定已更新。",
          errorMessage: "更新失敗，請稍後再試",
          onSuccess: () => setEditTarget(null),
        }
      );
    },
    [editTarget, runUpdate]
  );

  if (shouldBlockRender) {
    return <PageLoading />;
  }

  return (
    <div>
      <h1 className="mb-2 text-3xl font-bold text-foreground">系統設定</h1>
      <p className="mb-6 text-base text-muted">
        全域參數調整；「公開」設定前端 member 也可讀取，其餘僅 admin 可見。
      </p>

      {isLoading || isFetching ? (
        <div className="overflow-hidden rounded-xl bg-card-bg shadow-sm">
          <PageLoading />
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-xl bg-card-bg py-12 text-center text-base text-muted shadow-sm">
          尚無系統設定
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {groupedItems.map((group) => {
            const meta = GROUP_META[group.key];
            const title = meta?.title ?? group.key;
            const description = meta?.description;
            return (
              <section key={group.key}>
                <div className="mb-2 px-1">
                  <h2 className="text-xl font-semibold text-foreground">
                    {title}
                    <span className="ml-2 font-mono text-sm font-normal text-muted">
                      {group.key}.*
                    </span>
                  </h2>
                  {description && (
                    <p className="mt-0.5 text-sm text-muted">{description}</p>
                  )}
                </div>
                <div className="overflow-hidden rounded-xl bg-card-bg shadow-sm">
                  <div className="divide-y divide-border">
                    {group.items.map((setting) => (
                      <SettingRow
                        key={setting.system_setting_uid}
                        setting={setting}
                        onEdit={handleOpenEdit}
                      />
                    ))}
                  </div>
                </div>
              </section>
            );
          })}
        </div>
      )}

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
