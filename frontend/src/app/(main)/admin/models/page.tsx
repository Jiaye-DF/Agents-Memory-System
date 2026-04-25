"use client";

import React, {
  useState,
  useCallback,
  useMemo,
} from "react";
import { Table } from "@/components/ui/Table";
import { Pagination } from "@/components/ui/Pagination";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { PageLoading } from "@/components/ui/Loading";
import { Toggle } from "@/components/ui/Toggle";
import { ModalDialog } from "@/components/ui/ModalDialog";
import { useAdminGuard } from "@/hooks/useAdminGuard";
import { useCursorPagination } from "@/hooks/useCursorPagination";
import { useFilteredList } from "@/hooks/useFilteredList";
import { useMutationWithDialog } from "@/hooks/useMutationWithDialog";
import { useConfirmMutation } from "@/hooks/useConfirmMutation";
import {
  useListAdminModelsQuery,
  useCreateModelMutation,
  useUpdateModelMutation,
  useDeleteModelMutation,
} from "@/store/modelsApi";
import type { LlmModelAdmin } from "@/types";
import { formatDateTime } from "@/utils/datetime";

const MODEL_ID_REGEX = /^[a-z0-9][a-z0-9-]*\/[a-z0-9][a-z0-9.-]*$/;

type FormMode = "create" | "edit";

interface FormState {
  mode: FormMode;
  model?: LlmModelAdmin;
}

interface FormDialogProps {
  mode: FormMode;
  initial?: LlmModelAdmin;
  submitting: boolean;
  onSubmit: (data: {
    model_id: string;
    display_name: string;
    is_active?: boolean;
    is_default: boolean;
    max_output_tokens: number | null;
  }) => Promise<void>;
  onClose: () => void;
}

const FormDialog = React.memo(function FormDialog({
  mode,
  initial,
  submitting,
  onSubmit,
  onClose,
}: FormDialogProps): React.ReactNode {
  const [modelId, setModelId] = useState<string>(initial?.model_id ?? "");
  const [displayName, setDisplayName] = useState<string>(
    initial?.display_name ?? ""
  );
  const [isActive, setIsActive] = useState<boolean>(initial?.is_active ?? true);
  const [isDefault, setIsDefault] = useState<boolean>(
    initial?.is_default ?? false
  );
  const [maxOutputTokens, setMaxOutputTokens] = useState<string>(
    initial?.max_output_tokens != null
      ? String(initial.max_output_tokens)
      : ""
  );
  const [modelIdError, setModelIdError] = useState<string>("");
  const [displayNameError, setDisplayNameError] = useState<string>("");
  const [maxOutputTokensError, setMaxOutputTokensError] = useState<string>("");

  const title = mode === "create" ? "新增 LLM 模型" : "編輯 LLM 模型";

  const handleModelIdChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setModelId(e.target.value.toLowerCase());
      setModelIdError("");
    },
    []
  );

  const handleDisplayNameChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setDisplayName(e.target.value);
      setDisplayNameError("");
    },
    []
  );

  const handleToggleActive = useCallback((next: boolean): void => {
    setIsActive(next);
  }, []);

  const handleToggleDefault = useCallback((next: boolean): void => {
    setIsDefault(next);
  }, []);

  const handleMaxOutputTokensChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setMaxOutputTokens(e.target.value);
      setMaxOutputTokensError("");
    },
    []
  );

  const handleSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
      e.preventDefault();
      let hasError = false;

      const trimmedName = displayName.trim();
      if (!trimmedName) {
        setDisplayNameError("顯示名稱為必填");
        hasError = true;
      } else if (trimmedName.length > 100) {
        setDisplayNameError("顯示名稱不可超過 100 字元");
        hasError = true;
      }

      if (mode === "create") {
        const trimmedId = modelId.trim();
        if (!trimmedId) {
          setModelIdError("Model ID 為必填");
          hasError = true;
        } else if (!MODEL_ID_REGEX.test(trimmedId)) {
          setModelIdError(
            "格式須為 <vendor>/<slug>，例如 anthropic/claude-sonnet-4"
          );
          hasError = true;
        }
      }

      let parsedMaxTokens: number | null = null;
      const trimmedMaxTokens = maxOutputTokens.trim();
      if (trimmedMaxTokens !== "") {
        const num = parseInt(trimmedMaxTokens, 10);
        if (Number.isNaN(num) || num < 1) {
          setMaxOutputTokensError("需為大於 0 的整數，留空表示未設定");
          hasError = true;
        } else {
          parsedMaxTokens = num;
        }
      }

      if (hasError) return;

      if (mode === "create") {
        await onSubmit({
          model_id: modelId.trim(),
          display_name: trimmedName,
          is_default: isDefault,
          max_output_tokens: parsedMaxTokens,
        });
      } else {
        await onSubmit({
          model_id: modelId,
          display_name: trimmedName,
          is_active: isActive,
          is_default: isDefault,
          max_output_tokens: parsedMaxTokens,
        });
      }
    },
    [
      mode,
      modelId,
      displayName,
      isActive,
      isDefault,
      maxOutputTokens,
      onSubmit,
    ]
  );

  return (
    <ModalDialog title={title} onClose={onClose}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <label
            htmlFor="model-id-input"
            className="mb-1.5 block text-base font-medium text-foreground"
          >
            Model ID
            {mode === "create" && (
              <span className="ml-0.5 text-destructive">*</span>
            )}
          </label>
          {mode === "create" ? (
            <Input
              id="model-id-input"
              placeholder="anthropic/claude-sonnet-4"
              value={modelId}
              onChange={handleModelIdChange}
              error={modelIdError}
              disabled={submitting}
            />
          ) : (
            <div className="min-h-11 w-full rounded-xl border border-input-border bg-muted-bg px-3 py-2 font-mono text-base text-muted">
              {modelId}
            </div>
          )}
        </div>

        <Input
          label="顯示名稱"
          required
          value={displayName}
          onChange={handleDisplayNameChange}
          error={displayNameError}
          disabled={submitting}
          placeholder="Claude Sonnet 4"
        />

        {mode === "edit" && (
          <div className="flex items-center justify-between">
            <span className="text-base font-medium text-foreground">
              啟用狀態
            </span>
            <Toggle
              checked={isActive}
              onChange={handleToggleActive}
              disabled={submitting}
              label="啟用狀態切換"
            />
          </div>
        )}

        <div className="flex items-center justify-between">
          <div>
            <span className="block text-base font-medium text-foreground">
              預設模型
            </span>
            <span className="block text-sm text-muted">
              全系統僅能有一個預設模型
            </span>
          </div>
          <Toggle
            checked={isDefault}
            onChange={handleToggleDefault}
            disabled={submitting}
            label="預設模型切換"
          />
        </div>

        <div>
          <label
            htmlFor="max-output-tokens"
            className="mb-1.5 block text-base font-medium text-foreground"
          >
            單次回覆最大 Token 數
          </label>
          <Input
            id="max-output-tokens"
            type="number"
            placeholder="留空表示未設定"
            value={maxOutputTokens}
            onChange={handleMaxOutputTokensChange}
            error={maxOutputTokensError}
            disabled={submitting}
          />
        </div>

        <div className="mt-2 flex justify-end gap-3">
          <button
            type="button"
            className="min-h-11 min-w-11 rounded-xl border border-border px-4 py-2 text-base font-medium text-foreground hover:cursor-pointer hover:bg-muted-bg"
            onClick={onClose}
            disabled={submitting}
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

type StatusFilter = "all" | "active" | "inactive";
type SortOrder = "newest" | "oldest";

interface FilterChipProps {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}

const FilterChip = React.memo(function FilterChip({
  active,
  onClick,
  children,
}: FilterChipProps): React.ReactNode {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-xl px-3 py-1 text-sm font-medium transition-colors hover:cursor-pointer ${
        active
          ? "bg-primary text-white"
          : "bg-muted-bg text-muted hover:bg-border"
      }`}
    >
      {children}
    </button>
  );
});

interface ModelCardProps {
  model: LlmModelAdmin;
  onEdit: (model: LlmModelAdmin) => void;
  onToggleActive: (model: LlmModelAdmin) => void;
  onDelete: (model: LlmModelAdmin) => void;
}

const ModelCard = React.memo(function ModelCard({
  model,
  onEdit,
  onToggleActive,
  onDelete,
}: ModelCardProps): React.ReactNode {
  const handleEdit = useCallback((): void => {
    onEdit(model);
  }, [model, onEdit]);

  const handleToggle = useCallback((): void => {
    onToggleActive(model);
  }, [model, onToggleActive]);

  const handleDelete = useCallback((): void => {
    onDelete(model);
  }, [model, onDelete]);

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="truncate font-medium text-foreground">
          {model.display_name}
        </span>
        {model.is_default && (
          <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            預設
          </span>
        )}
        <span
          className={`shrink-0 rounded-xl px-2 py-0.5 text-xs font-medium ${
            model.is_active
              ? "bg-success/10 text-success"
              : "bg-muted-bg text-muted"
          }`}
        >
          {model.is_active ? "啟用" : "停用"}
        </span>
        <div className="ml-auto flex shrink-0 flex-wrap items-center gap-1.5">
          <Button size="sm" variant="secondary" onClick={handleEdit}>
            編輯
          </Button>
          <Button size="sm" variant="secondary" onClick={handleToggle}>
            {model.is_active ? "停用" : "啟用"}
          </Button>
          <Button size="sm" variant="destructive" onClick={handleDelete}>
            刪除
          </Button>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
        <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
          {model.provider}
        </span>
        <span className="truncate font-mono">{model.model_id}</span>
        <span>·</span>
        <span>
          最大 Token：
          {model.max_output_tokens != null ? model.max_output_tokens : "未設定"}
        </span>
        <span>·</span>
        <span>{formatDateTime(model.created_at)}</span>
      </div>
    </div>
  );
});

export default function AdminModelsPage(): React.ReactNode {
  const { authLoading, isAdmin, shouldBlockRender } = useAdminGuard();
  const pagination = useCursorPagination(20);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [vendorFilter, setVendorFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [sortOrder, setSortOrder] = useState<SortOrder>("newest");
  const [formState, setFormState] = useState<FormState | null>(null);

  const { data, isLoading, isFetching } = useListAdminModelsQuery(
    { limit: pagination.limit, cursor: pagination.cursor },
    { skip: authLoading || !isAdmin }
  );

  const [createModel, { isLoading: creating }] = useCreateModelMutation();
  const [updateModel, { isLoading: updating }] = useUpdateModelMutation();
  const [deleteModel] = useDeleteModelMutation();

  const runCreate = useMutationWithDialog(createModel);
  const runUpdate = useMutationWithDialog(updateModel);
  const runToggleActive = useMutationWithDialog(updateModel);

  const submitting = creating || updating;

  const items = useMemo(
    (): LlmModelAdmin[] => data?.items ?? [],
    [data]
  );

  const vendors = useMemo((): string[] => {
    const set = new Set<string>();
    for (const m of items) {
      const vendor = m.model_id.split("/")[0];
      if (vendor) set.add(vendor);
    }
    return Array.from(set).sort();
  }, [items]);

  const vendorPredicate = useCallback(
    (m: LlmModelAdmin): boolean =>
      vendorFilter === "all" || m.model_id.startsWith(`${vendorFilter}/`),
    [vendorFilter]
  );
  const statusPredicate = useCallback(
    (m: LlmModelAdmin): boolean => {
      if (statusFilter === "active") return m.is_active;
      if (statusFilter === "inactive") return !m.is_active;
      return true;
    },
    [statusFilter]
  );
  const predicates = useMemo(
    () => [vendorPredicate, statusPredicate],
    [vendorPredicate, statusPredicate]
  );
  const searchFields = useMemo(
    () => ["model_id" as const, "display_name" as const],
    []
  );
  const filteredItems = useFilteredList<LlmModelAdmin>({
    items,
    searchTerm,
    searchFields,
    predicates,
  });

  const filteredModels = useMemo((): LlmModelAdmin[] => {
    const sorted = [...filteredItems].sort((a, b) => {
      const diff = a.created_at.localeCompare(b.created_at);
      return sortOrder === "newest" ? -diff : diff;
    });
    return sorted;
  }, [filteredItems, sortOrder]);

  const handleSearchChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setSearchTerm(e.target.value);
    },
    []
  );

  const handleNextPage = useCallback((): void => {
    pagination.handleNextPage(data?.next_cursor);
  }, [pagination, data]);

  const handleOpenCreate = useCallback((): void => {
    setFormState({ mode: "create" });
  }, []);

  const handleOpenEdit = useCallback((model: LlmModelAdmin): void => {
    setFormState({ mode: "edit", model });
  }, []);

  const handleCloseForm = useCallback((): void => {
    setFormState(null);
  }, []);

  const handleSubmitForm = useCallback(
    async (payload: {
      model_id: string;
      display_name: string;
      is_active?: boolean;
      is_default: boolean;
      max_output_tokens: number | null;
    }): Promise<void> => {
      if (!formState) return;
      if (formState.mode === "create") {
        await runCreate(
          {
            model_id: payload.model_id,
            display_name: payload.display_name,
            is_default: payload.is_default,
            max_output_tokens: payload.max_output_tokens,
          },
          {
            successTitle: "建立成功",
            successMessage: "LLM 模型已新增。",
            errorMessage: "新增失敗，請稍後再試",
            onSuccess: () => setFormState(null),
          }
        );
        return;
      }
      if (formState.model) {
        await runUpdate(
          {
            uid: formState.model.llm_model_uid,
            body: {
              display_name: payload.display_name,
              is_active: payload.is_active,
              is_default: payload.is_default,
              max_output_tokens: payload.max_output_tokens,
            },
          },
          {
            successTitle: "更新成功",
            successMessage: "LLM 模型已更新。",
            errorMessage: "更新失敗，請稍後再試",
            onSuccess: () => setFormState(null),
          }
        );
      }
    },
    [formState, runCreate, runUpdate]
  );

  const handleToggleActive = useCallback(
    (model: LlmModelAdmin): void => {
      void runToggleActive(
        {
          uid: model.llm_model_uid,
          body: { is_active: !model.is_active },
        },
        { errorMessage: "切換狀態失敗，請稍後再試" }
      );
    },
    [runToggleActive]
  );

  const deleteOptions = useMemo(
    () => ({
      title: "刪除 LLM 模型",
      message: "確定刪除此模型？已設定此模型的 Agent 將無法使用。",
      successTitle: "刪除成功",
      successMessage: "LLM 模型已刪除。",
      errorMessage: "刪除失敗，請稍後再試",
    }),
    []
  );
  const confirmDelete = useConfirmMutation(deleteModel, deleteOptions);
  const handleDelete = useCallback(
    (model: LlmModelAdmin): void => {
      confirmDelete(model.llm_model_uid);
    },
    [confirmDelete]
  );

  const columns = useMemo(
    () => [
      {
        key: "provider",
        header: "Provider",
        render: (model: LlmModelAdmin): React.ReactNode => (
          <span className="rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
            {model.provider}
          </span>
        ),
      },
      {
        key: "model_id",
        header: "Model ID",
        render: (model: LlmModelAdmin): React.ReactNode => (
          <span className="font-mono text-base text-foreground">
            {model.model_id}
          </span>
        ),
      },
      {
        key: "display_name",
        header: "顯示名稱",
      },
      {
        key: "is_default",
        header: "預設",
        render: (model: LlmModelAdmin): React.ReactNode =>
          model.is_default ? (
            <span className="rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
              預設
            </span>
          ) : (
            <span className="text-sm text-muted">-</span>
          ),
      },
      {
        key: "max_output_tokens",
        header: "最大 Token",
        render: (model: LlmModelAdmin): React.ReactNode => (
          <span className="text-base">
            {model.max_output_tokens != null ? model.max_output_tokens : "-"}
          </span>
        ),
      },
      {
        key: "is_active",
        header: "狀態",
        render: (model: LlmModelAdmin): React.ReactNode => (
          <span
            className={`rounded-xl px-2 py-0.5 text-sm font-medium ${
              model.is_active
                ? "bg-success/10 text-success"
                : "bg-muted-bg text-muted"
            }`}
          >
            {model.is_active ? "啟用" : "停用"}
          </span>
        ),
      },
      {
        key: "created_at",
        header: "建立時間",
        render: (model: LlmModelAdmin): React.ReactNode => (
          <span className="text-base">{formatDateTime(model.created_at)}</span>
        ),
      },
      {
        key: "actions",
        header: "操作",
        render: (model: LlmModelAdmin): React.ReactNode => (
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => handleOpenEdit(model)}
            >
              編輯
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => handleToggleActive(model)}
            >
              {model.is_active ? "停用" : "啟用"}
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => handleDelete(model)}
            >
              刪除
            </Button>
          </div>
        ),
      },
    ],
    [handleOpenEdit, handleToggleActive, handleDelete]
  );

  const keyExtractor = useCallback(
    (model: LlmModelAdmin): string => model.llm_model_uid,
    []
  );

  const cardRender = useCallback(
    (model: LlmModelAdmin): React.ReactNode => (
      <ModelCard
        model={model}
        onEdit={handleOpenEdit}
        onToggleActive={handleToggleActive}
        onDelete={handleDelete}
      />
    ),
    [handleOpenEdit, handleToggleActive, handleDelete]
  );

  if (shouldBlockRender) {
    return <PageLoading />;
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-3xl font-bold text-foreground">LLM 模型管理</h1>
        <Button onClick={handleOpenCreate}>新增模型</Button>
      </div>
      <div className="rounded-xl bg-card-bg p-6 shadow-sm">
        <div className="mb-4 flex flex-col gap-3">
          <Input
            placeholder="搜尋 Model ID 或顯示名稱..."
            value={searchTerm}
            onChange={handleSearchChange}
          />

          <div className="flex flex-wrap items-center gap-2">
            <span className="shrink-0 text-sm text-muted">供應商：</span>
            <FilterChip
              active={vendorFilter === "all"}
              onClick={() => setVendorFilter("all")}
            >
              全部
            </FilterChip>
            {vendors.map((v) => (
              <FilterChip
                key={v}
                active={vendorFilter === v}
                onClick={() => setVendorFilter(v)}
              >
                {v}
              </FilterChip>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="shrink-0 text-sm text-muted">狀態：</span>
            <FilterChip
              active={statusFilter === "all"}
              onClick={() => setStatusFilter("all")}
            >
              全部
            </FilterChip>
            <FilterChip
              active={statusFilter === "active"}
              onClick={() => setStatusFilter("active")}
            >
              啟用
            </FilterChip>
            <FilterChip
              active={statusFilter === "inactive"}
              onClick={() => setStatusFilter("inactive")}
            >
              停用
            </FilterChip>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="shrink-0 text-sm text-muted">按時間：</span>
            <FilterChip
              active={sortOrder === "newest"}
              onClick={() => setSortOrder("newest")}
            >
              由新到舊
            </FilterChip>
            <FilterChip
              active={sortOrder === "oldest"}
              onClick={() => setSortOrder("oldest")}
            >
              由舊到新
            </FilterChip>
          </div>
        </div>

        {isLoading || isFetching ? (
          <PageLoading />
        ) : (
          <>
            <Table
              columns={columns}
              data={filteredModels}
              keyExtractor={keyExtractor}
              cardRender={cardRender}
              emptyMessage="尚無 LLM 模型資料"
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
        <FormDialog
          mode={formState.mode}
          initial={formState.model}
          submitting={submitting}
          onSubmit={handleSubmitForm}
          onClose={handleCloseForm}
        />
      )}
    </div>
  );
}
