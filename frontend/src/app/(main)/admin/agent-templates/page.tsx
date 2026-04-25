"use client";

import React, { useCallback, useMemo, useState } from "react";
import { Table } from "@/components/ui/Table";
import { Pagination } from "@/components/ui/Pagination";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { PageLoading } from "@/components/ui/Loading";
import { Toggle } from "@/components/ui/Toggle";
import { Slider } from "@/components/ui/Slider";
import { PresetButton } from "@/components/ui/PresetButton";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { useAdminGuard } from "@/hooks/useAdminGuard";
import { useCursorPagination } from "@/hooks/useCursorPagination";
import { useMutationWithDialog } from "@/hooks/useMutationWithDialog";
import { useConfirmMutation } from "@/hooks/useConfirmMutation";
import {
  useListAdminAgentTemplatesQuery,
  useCreateAgentTemplateMutation,
  useUpdateAgentTemplateMutation,
  useDeleteAgentTemplateMutation,
} from "@/store/agentTemplatesApi";
import { useListAgentLanguagesQuery } from "@/store/agentLanguagesApi";
import type {
  AgentTemplate,
  AgentTemplateCreateRequest,
  AgentTemplateUpdateRequest,
} from "@/types";
import { formatDateTime } from "@/utils/datetime";

type FormMode = "create" | "edit";

interface FormState {
  mode: FormMode;
  template?: AgentTemplate;
}

interface TemplateFormValues {
  template_key: string;
  label: string;
  description: string;
  name: string;
  identity: string;
  language: string;
  style: string;
  role_prompt: string;
  greeting: string;
  temperature: string;
  max_tokens: string;
  response_format: string;
  response_format_example: string;
  sort_order: string;
  is_active: boolean;
}

const TEMPERATURE_PRESETS = [
  { label: "精確", value: 0.2 },
  { label: "自然", value: 0.7 },
  { label: "創意", value: 1.2 },
];

const DEFAULT_VALUES: TemplateFormValues = {
  template_key: "",
  label: "",
  description: "",
  name: "",
  identity: "",
  language: "",
  style: "",
  role_prompt: "",
  greeting: "",
  temperature: "0.7",
  max_tokens: "4096",
  response_format: "markdown",
  response_format_example: "",
  sort_order: "0",
  is_active: true,
};

interface TemplateFormDialogProps {
  mode: FormMode;
  initial?: AgentTemplate;
  submitting: boolean;
  languageOptions: { code: string; name: string }[];
  onSubmit: (
    payload: AgentTemplateCreateRequest | AgentTemplateUpdateRequest
  ) => Promise<void>;
  onClose: () => void;
}

function buildInitialValues(initial?: AgentTemplate): TemplateFormValues {
  if (!initial) return DEFAULT_VALUES;
  return {
    template_key: initial.template_key,
    label: initial.label,
    description: initial.description ?? "",
    name: initial.name ?? "",
    identity: initial.identity ?? "",
    language: initial.language ?? "",
    style: initial.style ?? "",
    role_prompt: initial.role_prompt ?? "",
    greeting: initial.greeting ?? "",
    temperature:
      typeof initial.temperature === "number"
        ? String(initial.temperature)
        : "",
    max_tokens:
      typeof initial.max_tokens === "number" ? String(initial.max_tokens) : "",
    response_format: initial.response_format ?? "markdown",
    response_format_example: initial.response_format_example ?? "",
    sort_order: String(initial.sort_order),
    is_active: initial.is_active,
  };
}

const TemplateFormDialog = React.memo(function TemplateFormDialog({
  mode,
  initial,
  submitting,
  languageOptions,
  onSubmit,
  onClose,
}: TemplateFormDialogProps): React.ReactNode {
  const [values, setValues] = useState<TemplateFormValues>(() =>
    buildInitialValues(initial)
  );
  const [errors, setErrors] = useState<Record<string, string>>({});

  const title = mode === "create" ? "新增範本" : "編輯範本";

  const setField = useCallback(
    <K extends keyof TemplateFormValues>(
      key: K,
      value: TemplateFormValues[K]
    ): void => {
      setValues((prev) => ({ ...prev, [key]: value }));
      setErrors((prev) => ({ ...prev, [key]: "" }));
    },
    []
  );

  const validate = useCallback((): boolean => {
    const next: Record<string, string> = {};
    if (mode === "create") {
      const key = values.template_key.trim();
      if (!key) next.template_key = "識別碼為必填";
      else if (!/^[a-z0-9][a-z0-9-]{0,48}[a-z0-9]$/.test(key)) {
        next.template_key = "僅允許英數小寫與連字號，不可以連字號開頭或結尾";
      }
    }
    if (!values.label.trim()) next.label = "名稱為必填";
    if (values.temperature !== "") {
      const t = Number(values.temperature);
      if (Number.isNaN(t) || t < 0 || t > 2) {
        next.temperature = "溫度需介於 0 至 2 之間";
      }
    }
    if (values.max_tokens !== "") {
      const n = Number(values.max_tokens);
      if (!Number.isInteger(n) || n < 1 || n > 200000) {
        next.max_tokens = "Token 數需為 1 至 200000 之間的整數";
      }
    }
    if (values.sort_order !== "") {
      const n = Number(values.sort_order);
      if (!Number.isInteger(n)) next.sort_order = "排序需為整數";
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }, [mode, values]);

  const toPayload = useCallback((): AgentTemplateCreateRequest => {
    const temperature =
      values.temperature === "" ? null : Number(values.temperature);
    const max_tokens =
      values.max_tokens === "" ? null : Number(values.max_tokens);
    const sort_order =
      values.sort_order === "" ? 0 : Number(values.sort_order);
    return {
      template_key: values.template_key.trim(),
      label: values.label.trim(),
      description: values.description || null,
      name: values.name || null,
      identity: values.identity || null,
      language: values.language || null,
      style: values.style || null,
      role_prompt: values.role_prompt || null,
      greeting: values.greeting || null,
      temperature,
      max_tokens,
      response_format: values.response_format || "markdown",
      response_format_example:
        values.response_format === "json"
          ? values.response_format_example || null
          : null,
      sort_order,
    };
  }, [values]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
      e.preventDefault();
      if (!validate()) return;
      const base = toPayload();
      if (mode === "create") {
        await onSubmit(base);
      } else {
        const update: AgentTemplateUpdateRequest = {
          label: base.label,
          description: base.description,
          name: base.name,
          identity: base.identity,
          language: base.language,
          style: base.style,
          role_prompt: base.role_prompt,
          greeting: base.greeting,
          temperature: base.temperature,
          max_tokens: base.max_tokens,
          response_format: base.response_format,
          response_format_example: base.response_format_example,
          sort_order: base.sort_order,
          is_active: values.is_active,
        };
        await onSubmit(update);
      }
    },
    [mode, onSubmit, toPayload, validate, values.is_active]
  );

  return (
    <ModalDialog title={title} onClose={onClose} size="lg">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <label
            htmlFor="tpl-key"
            className="mb-1.5 block text-base font-medium text-foreground"
          >
            識別碼
            {mode === "create" && (
              <span className="ml-0.5 text-destructive">*</span>
            )}
          </label>
          {mode === "create" ? (
            <Input
              id="tpl-key"
              placeholder="例如：python-dev"
              value={values.template_key}
              onChange={(e) => setField("template_key", e.target.value)}
              error={errors.template_key}
              disabled={submitting}
            />
          ) : (
            <div className="min-h-11 w-full rounded-xl border border-input-border bg-muted-bg px-3 py-2 font-mono text-base text-muted">
              {values.template_key}
            </div>
          )}
        </div>

        <Input
          label="名稱"
          required
          value={values.label}
          onChange={(e) => setField("label", e.target.value)}
          error={errors.label}
          disabled={submitting}
          placeholder="例如：Python 開發助手"
        />

        <div>
          <label
            htmlFor="tpl-desc"
            className="mb-1.5 block text-base font-medium text-foreground"
          >
            描述
          </label>
          <textarea
            id="tpl-desc"
            value={values.description}
            onChange={(e) => setField("description", e.target.value)}
            disabled={submitting}
            rows={2}
            placeholder="簡短說明此範本的用途，例如：協助撰寫與除錯 Python 程式碼"
            className="w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
          />
        </div>

        <Input
          label="預設 Agent 名稱"
          value={values.name}
          onChange={(e) => setField("name", e.target.value)}
          disabled={submitting}
          placeholder="使用者套用範本後預設填入的名稱，例如：Python 開發助手"
        />

        <Input
          label="身分"
          value={values.identity}
          onChange={(e) => setField("identity", e.target.value)}
          disabled={submitting}
          placeholder="例如：資深 Python 工程師，熟悉常用框架"
        />

        <div>
          <label
            htmlFor="tpl-lang"
            className="mb-1.5 block text-base font-medium text-foreground"
          >
            語言
          </label>
          <select
            id="tpl-lang"
            value={values.language}
            onChange={(e) => setField("language", e.target.value)}
            disabled={submitting}
            className="min-h-11 w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground hover:cursor-pointer focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
          >
            <option value="">未指定</option>
            {languageOptions.map((l) => (
              <option key={l.code} value={l.code}>
                {l.name}（{l.code}）
              </option>
            ))}
          </select>
        </div>

        <Input
          label="風格"
          value={values.style}
          onChange={(e) => setField("style", e.target.value)}
          disabled={submitting}
          placeholder="例如：專業、精確、務實"
        />

        <div>
          <label
            htmlFor="tpl-role"
            className="mb-1.5 block text-base font-medium text-foreground"
          >
            角色設定
          </label>
          <textarea
            id="tpl-role"
            value={values.role_prompt}
            onChange={(e) => setField("role_prompt", e.target.value)}
            disabled={submitting}
            rows={6}
            placeholder="描述 Agent 的工作方式與回覆規則，例如：請以資深工程師角度回答，並列出可執行的範例"
            className="w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
          />
        </div>

        <div>
          <label
            htmlFor="tpl-greet"
            className="mb-1.5 block text-base font-medium text-foreground"
          >
            開場白
          </label>
          <textarea
            id="tpl-greet"
            value={values.greeting}
            onChange={(e) => setField("greeting", e.target.value)}
            disabled={submitting}
            rows={2}
            placeholder="Agent 對話開始時的第一句話"
            className="w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
          />
        </div>

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <label
              htmlFor="tpl-temp"
              className="text-base font-medium text-foreground"
            >
              回答風格
              <span className="ml-1 text-sm font-normal text-muted">
                (Temperature)
              </span>
            </label>
            <span className="rounded-xl bg-muted-bg px-2 py-0.5 font-mono text-base text-foreground">
              {(Number(values.temperature) || 0).toFixed(1)}
            </span>
          </div>
          <Slider
            id="tpl-temp"
            ariaLabel="回答風格"
            min={0}
            max={2}
            step={0.1}
            value={Number(values.temperature) || 0}
            onChange={(next) => setField("temperature", String(next))}
            disabled={submitting}
            marks={[
              { value: 0, label: "0.0" },
              { value: 1, label: "1.0" },
              { value: 2, label: "2.0" },
            ]}
          />
          <div className="mt-3 flex flex-wrap gap-2">
            {TEMPERATURE_PRESETS.map((p) => (
              <PresetButton
                key={p.label}
                active={
                  Math.abs((Number(values.temperature) || 0) - p.value) < 0.0001
                }
                onClick={() => setField("temperature", String(p.value))}
                disabled={submitting}
              >
                {p.label} {p.value.toFixed(1)}
              </PresetButton>
            ))}
          </div>
          {errors.temperature && (
            <p className="mt-1 text-base text-destructive">
              {errors.temperature}
            </p>
          )}
        </div>

        <Input
          label="最大 Token"
          type="number"
          value={values.max_tokens}
          onChange={(e) => setField("max_tokens", e.target.value)}
          error={errors.max_tokens}
          disabled={submitting}
        />

        <div>
          <label
            htmlFor="tpl-format"
            className="mb-1.5 block text-base font-medium text-foreground"
          >
            回覆格式
          </label>
          <select
            id="tpl-format"
            value={values.response_format}
            onChange={(e) => setField("response_format", e.target.value)}
            disabled={submitting}
            className="min-h-11 w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 text-base text-foreground hover:cursor-pointer focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
          >
            <option value="markdown">Markdown</option>
            <option value="plain_text">純文字</option>
            <option value="json">JSON</option>
          </select>
        </div>

        {values.response_format === "json" && (
          <div>
            <label
              htmlFor="tpl-json"
              className="mb-1.5 block text-base font-medium text-foreground"
            >
              JSON 範例
            </label>
            <textarea
              id="tpl-json"
              value={values.response_format_example}
              onChange={(e) =>
                setField("response_format_example", e.target.value)
              }
              disabled={submitting}
              rows={6}
              spellCheck={false}
              placeholder={"{\n  \"key\": \"value\"\n}"}
              className="w-full rounded-xl border border-input-border bg-input-bg px-3 py-2 font-mono text-sm text-foreground focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
            />
          </div>
        )}

        <Input
          label="排序"
          type="number"
          value={values.sort_order}
          onChange={(e) => setField("sort_order", e.target.value)}
          error={errors.sort_order}
          disabled={submitting}
          placeholder="數值越小越前面"
        />

        {mode === "edit" && (
          <div className="flex items-center justify-between">
            <span className="text-base font-medium text-foreground">
              啟用狀態
            </span>
            <Toggle
              checked={values.is_active}
              onChange={(next) => setField("is_active", next)}
              disabled={submitting}
              label="切換啟用狀態"
            />
          </div>
        )}

        <div className="mt-2 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="min-h-11 min-w-11 rounded-xl border border-border px-4 py-2 text-base font-medium text-foreground hover:cursor-pointer hover:bg-muted-bg"
          >
            取消
          </button>
          <Button type="submit" loading={submitting}>
            {mode === "create" ? "建立" : "儲存"}
          </Button>
        </div>
      </form>
    </ModalDialog>
  );
});

interface TemplateCardProps {
  template: AgentTemplate;
  onEdit: (tpl: AgentTemplate) => void;
  onDelete: (tpl: AgentTemplate) => void;
}

const TemplateCard = React.memo(function TemplateCard({
  template,
  onEdit,
  onDelete,
}: TemplateCardProps): React.ReactNode {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="truncate font-medium text-foreground">
          {template.label}
        </span>
        <span
          className={`shrink-0 rounded-xl px-2 py-0.5 text-xs font-medium ${
            template.is_active
              ? "bg-success/10 text-success"
              : "bg-muted-bg text-muted"
          }`}
        >
          {template.is_active ? "啟用" : "停用"}
        </span>
        <div className="ml-auto flex shrink-0 flex-wrap items-center gap-1.5">
          <Button
            size="sm"
            variant="secondary"
            onClick={() => onEdit(template)}
          >
            編輯
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => onDelete(template)}
          >
            刪除
          </Button>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
        <span className="truncate font-mono">{template.template_key}</span>
        <span>·</span>
        <span>排序：{template.sort_order}</span>
        <span>·</span>
        <span>{formatDateTime(template.created_at)}</span>
      </div>
      {template.description && (
        <div className="line-clamp-1 text-sm text-muted">
          {template.description}
        </div>
      )}
    </div>
  );
});

export default function AdminAgentTemplatesPage(): React.ReactNode {
  const { authLoading, isAdmin, shouldBlockRender } = useAdminGuard();
  const pagination = useCursorPagination(20);
  const [formState, setFormState] = useState<FormState | null>(null);

  const { data, isLoading, isFetching } = useListAdminAgentTemplatesQuery(
    { limit: pagination.limit, cursor: pagination.cursor },
    { skip: authLoading || !isAdmin }
  );
  const { data: langData } = useListAgentLanguagesQuery(undefined, {
    skip: authLoading || !isAdmin,
  });

  const [createTemplate, { isLoading: creating }] =
    useCreateAgentTemplateMutation();
  const [updateTemplate, { isLoading: updating }] =
    useUpdateAgentTemplateMutation();
  const [deleteTemplate] = useDeleteAgentTemplateMutation();

  const runCreate = useMutationWithDialog(createTemplate);
  const runUpdate = useMutationWithDialog(updateTemplate);

  const submitting = creating || updating;

  const items = useMemo(
    (): AgentTemplate[] => data?.items ?? [],
    [data]
  );

  const languageOptions = useMemo(
    () =>
      (langData?.items ?? []).map((l) => ({ code: l.code, name: l.name })),
    [langData]
  );

  const handleOpenCreate = useCallback((): void => {
    setFormState({ mode: "create" });
  }, []);

  const handleOpenEdit = useCallback((tpl: AgentTemplate): void => {
    setFormState({ mode: "edit", template: tpl });
  }, []);

  const handleCloseForm = useCallback((): void => {
    setFormState(null);
  }, []);

  const handleSubmitForm = useCallback(
    async (
      payload: AgentTemplateCreateRequest | AgentTemplateUpdateRequest
    ): Promise<void> => {
      if (!formState) return;
      if (formState.mode === "create") {
        await runCreate(payload as AgentTemplateCreateRequest, {
          successTitle: "建立成功",
          successMessage: "範本已新增。",
          errorMessage: "新增失敗，請稍後再試",
          onSuccess: () => setFormState(null),
        });
        return;
      }
      if (formState.template) {
        await runUpdate(
          {
            uid: formState.template.agent_template_uid,
            body: payload as AgentTemplateUpdateRequest,
          },
          {
            successTitle: "更新成功",
            successMessage: "範本已更新。",
            errorMessage: "更新失敗，請稍後再試",
            onSuccess: () => setFormState(null),
          }
        );
      }
    },
    [formState, runCreate, runUpdate]
  );

  const deleteOptions = useMemo(
    () => ({
      title: "刪除範本",
      message: "確定要刪除此範本嗎？已建立的 Agent 不會受影響。",
      successTitle: "刪除成功",
      successMessage: "範本已刪除。",
      errorMessage: "刪除失敗，請稍後再試",
    }),
    []
  );
  const confirmDelete = useConfirmMutation(deleteTemplate, deleteOptions);
  const handleDelete = useCallback(
    (tpl: AgentTemplate): void => {
      confirmDelete(tpl.agent_template_uid);
    },
    [confirmDelete]
  );

  const handleNextPage = useCallback((): void => {
    pagination.handleNextPage(data?.next_cursor);
  }, [pagination, data]);

  const columns = useMemo(
    () => [
      {
        key: "template_key",
        header: "識別碼",
        render: (tpl: AgentTemplate): React.ReactNode => (
          <span className="font-mono text-base text-foreground">
            {tpl.template_key}
          </span>
        ),
      },
      {
        key: "label",
        header: "名稱",
      },
      {
        key: "description",
        header: "描述",
        render: (tpl: AgentTemplate): React.ReactNode => (
          <span className="line-clamp-1 text-base text-muted">
            {tpl.description ?? "-"}
          </span>
        ),
      },
      {
        key: "sort_order",
        header: "排序",
      },
      {
        key: "is_active",
        header: "狀態",
        render: (tpl: AgentTemplate): React.ReactNode => (
          <span
            className={`rounded-xl px-2 py-0.5 text-sm font-medium ${
              tpl.is_active
                ? "bg-success/10 text-success"
                : "bg-muted-bg text-muted"
            }`}
          >
            {tpl.is_active ? "啟用" : "停用"}
          </span>
        ),
      },
      {
        key: "created_at",
        header: "建立時間",
        render: (tpl: AgentTemplate): React.ReactNode => (
          <span className="text-base">{formatDateTime(tpl.created_at)}</span>
        ),
      },
      {
        key: "actions",
        header: "操作",
        render: (tpl: AgentTemplate): React.ReactNode => (
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => handleOpenEdit(tpl)}
            >
              編輯
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => handleDelete(tpl)}
            >
              刪除
            </Button>
          </div>
        ),
      },
    ],
    [handleOpenEdit, handleDelete]
  );

  const keyExtractor = useCallback(
    (tpl: AgentTemplate): string => tpl.agent_template_uid,
    []
  );

  const cardRender = useCallback(
    (tpl: AgentTemplate): React.ReactNode => (
      <TemplateCard
        template={tpl}
        onEdit={handleOpenEdit}
        onDelete={handleDelete}
      />
    ),
    [handleOpenEdit, handleDelete]
  );

  if (shouldBlockRender) {
    return <PageLoading />;
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-3xl font-bold text-foreground">Agent 範本</h1>
        <Button onClick={handleOpenCreate}>新增範本</Button>
      </div>
      <div className="rounded-xl bg-card-bg p-6 shadow-sm">
        {isLoading || isFetching ? (
          <PageLoading />
        ) : (
          <>
            <Table
              columns={columns}
              data={items}
              keyExtractor={keyExtractor}
              cardRender={cardRender}
              emptyMessage="尚無範本資料"
            />
            <div className="mt-4">
              <Pagination
                hasNext={data?.has_next ?? false}
                hasPrev={pagination.hasPrev}
                limit={pagination.limit}
                onNextPage={handleNextPage}
                onPrevPage={pagination.handlePrevPage}
                onLimitChange={pagination.handleLimitChange}
              />
            </div>
          </>
        )}
      </div>

      {formState && (
        <TemplateFormDialog
          mode={formState.mode}
          initial={formState.template}
          submitting={submitting}
          languageOptions={languageOptions}
          onSubmit={handleSubmitForm}
          onClose={handleCloseForm}
        />
      )}
    </div>
  );
}
