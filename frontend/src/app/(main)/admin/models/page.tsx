"use client";

import React, {
  useState,
  useCallback,
  useMemo,
  useEffect,
  useRef,
} from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import { Table } from "@/components/ui/Table";
import { Pagination } from "@/components/ui/Pagination";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { PageLoading } from "@/components/ui/Loading";
import { useDialog } from "@/hooks/useDialog";
import { useAuth } from "@/hooks/useAuth";
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
  const overlayRef = useRef<HTMLDivElement>(null);
  const [modelId, setModelId] = useState<string>(initial?.model_id ?? "");
  const [displayName, setDisplayName] = useState<string>(
    initial?.display_name ?? ""
  );
  const [isActive, setIsActive] = useState<boolean>(initial?.is_active ?? true);
  const [modelIdError, setModelIdError] = useState<string>("");
  const [displayNameError, setDisplayNameError] = useState<string>("");

  const title = mode === "create" ? "新增 LLM 模型" : "編輯 LLM 模型";

  const handleKeyDown = useCallback(
    (e: KeyboardEvent): void => {
      if (e.key === "Escape") {
        onClose();
      }
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
      if (e.target === overlayRef.current) {
        onClose();
      }
    },
    [onClose]
  );

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

  const handleToggleActive = useCallback((): void => {
    setIsActive((prev) => !prev);
  }, []);

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

      if (hasError) return;

      if (mode === "create") {
        await onSubmit({
          model_id: modelId.trim(),
          display_name: trimmedName,
        });
      } else {
        await onSubmit({
          model_id: modelId,
          display_name: trimmedName,
          is_active: isActive,
        });
      }
    },
    [mode, modelId, displayName, isActive, onSubmit]
  );

  const content = (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4"
      onClick={handleOverlayClick}
    >
      <div className="w-full max-w-md rounded-xl bg-card-bg p-6 shadow-lg">
        <h3 className="mb-4 text-xl font-semibold text-foreground">{title}</h3>
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
              <div className="min-h-[44px] w-full rounded-xl border border-input-border bg-muted-bg px-3 py-2 font-mono text-base text-muted">
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
          )}

          <div className="mt-2 flex justify-end gap-3">
            <button
              type="button"
              className="min-h-[44px] min-w-[44px] rounded-xl border border-border px-4 py-2 text-base font-medium text-foreground hover:cursor-pointer hover:bg-muted-bg"
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
      </div>
    </div>
  );

  if (typeof document === "undefined") return null;
  return createPortal(content, document.body);
});

type StatusFilter = "all" | "active" | "inactive";

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
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-medium text-foreground">
          {model.display_name}
        </span>
        <span
          className={`shrink-0 rounded-xl px-2 py-0.5 text-sm font-medium ${
            model.is_active
              ? "bg-success/10 text-success"
              : "bg-muted-bg text-muted"
          }`}
        >
          {model.is_active ? "啟用" : "停用"}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
          {model.provider}
        </span>
        <span className="truncate font-mono text-sm text-muted">
          {model.model_id}
        </span>
      </div>
      <div className="text-sm text-muted">
        建立時間：{formatDateTime(model.created_at)}
      </div>
      <div className="flex flex-wrap items-center gap-2">
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
  );
});

export default function AdminModelsPage(): React.ReactNode {
  const router = useRouter();
  const { role, isLoading: authLoading } = useAuth();
  const { showDialog } = useDialog();

  const [limit, setLimit] = useState<number>(20);
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [vendorFilter, setVendorFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [formState, setFormState] = useState<FormState | null>(null);

  useEffect(() => {
    if (!authLoading && role !== "admin") {
      router.replace("/403");
    }
  }, [role, authLoading, router]);

  const { data, isLoading, isFetching } = useListAdminModelsQuery(
    { limit, cursor },
    { skip: authLoading || role !== "admin" }
  );

  const [createModel, { isLoading: creating }] = useCreateModelMutation();
  const [updateModel, { isLoading: updating }] = useUpdateModelMutation();
  const [deleteModel] = useDeleteModelMutation();

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

  const filteredModels = useMemo((): LlmModelAdmin[] => {
    const term = searchTerm.trim().toLowerCase();
    return items.filter((m) => {
      if (vendorFilter !== "all" && !m.model_id.startsWith(`${vendorFilter}/`)) {
        return false;
      }
      if (statusFilter === "active" && !m.is_active) return false;
      if (statusFilter === "inactive" && m.is_active) return false;
      if (!term) return true;
      return (
        m.model_id.toLowerCase().includes(term) ||
        m.display_name.toLowerCase().includes(term)
      );
    });
  }, [items, searchTerm, vendorFilter, statusFilter]);

  const handleSearchChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setSearchTerm(e.target.value);
    },
    []
  );

  const handleNextPage = useCallback((): void => {
    if (data?.next_cursor) {
      setCursorHistory((prev) => [...prev, cursor ?? ""]);
      setCursor(data.next_cursor);
    }
  }, [data, cursor]);

  const handlePrevPage = useCallback((): void => {
    setCursorHistory((prev) => {
      const newHistory = [...prev];
      const prevCursor = newHistory.pop();
      setCursor(prevCursor || null);
      return newHistory;
    });
  }, []);

  const handleLimitChange = useCallback((newLimit: number): void => {
    setLimit(newLimit);
    setCursor(null);
    setCursorHistory([]);
  }, []);

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
    }): Promise<void> => {
      if (!formState) return;
      try {
        if (formState.mode === "create") {
          await createModel({
            model_id: payload.model_id,
            display_name: payload.display_name,
          }).unwrap();
          setFormState(null);
          showDialog({
            type: "info",
            title: "建立成功",
            message: "LLM 模型已新增。",
          });
        } else if (formState.model) {
          await updateModel({
            uid: formState.model.llm_model_uid,
            body: {
              display_name: payload.display_name,
              is_active: payload.is_active,
            },
          }).unwrap();
          setFormState(null);
          showDialog({
            type: "info",
            title: "更新成功",
            message: "LLM 模型已更新。",
          });
        }
      } catch (err: unknown) {
        const message =
          typeof err === "string"
            ? err
            : formState.mode === "create"
              ? "新增失敗，請稍後再試"
              : "更新失敗，請稍後再試";
        showDialog({
          type: "error",
          title: "操作失敗",
          message,
        });
      }
    },
    [formState, createModel, updateModel, showDialog]
  );

  const handleToggleActive = useCallback(
    (model: LlmModelAdmin): void => {
      const nextActive = !model.is_active;
      const toggleAsync = async (): Promise<void> => {
        try {
          await updateModel({
            uid: model.llm_model_uid,
            body: { is_active: nextActive },
          }).unwrap();
        } catch (err: unknown) {
          const message =
            typeof err === "string" ? err : "切換狀態失敗，請稍後再試";
          showDialog({
            type: "error",
            title: "操作失敗",
            message,
          });
        }
      };
      void toggleAsync();
    },
    [updateModel, showDialog]
  );

  const handleDelete = useCallback(
    (model: LlmModelAdmin): void => {
      showDialog({
        type: "warning",
        title: "刪除 LLM 模型",
        message: "確定刪除此模型？已設定此模型的 Agent 將無法使用。",
        onConfirm: async () => {
          try {
            await deleteModel(model.llm_model_uid).unwrap();
            showDialog({
              type: "info",
              title: "刪除成功",
              message: "LLM 模型已刪除。",
            });
          } catch (err: unknown) {
            const message =
              typeof err === "string" ? err : "刪除失敗，請稍後再試";
            showDialog({
              type: "error",
              title: "操作失敗",
              message,
            });
          }
        },
        onCancel: () => {},
      });
    },
    [deleteModel, showDialog]
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

  if (authLoading || role !== "admin") {
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
                hasPrev={cursorHistory.length > 0}
                limit={limit}
                onNextPage={handleNextPage}
                onPrevPage={handlePrevPage}
                onLimitChange={handleLimitChange}
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
