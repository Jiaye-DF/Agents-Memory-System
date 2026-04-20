"use client";

import React, {
  useCallback,
  useMemo,
  useState,
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
import { useMutationWithDialog } from "@/hooks/useMutationWithDialog";
import { useConfirmMutation } from "@/hooks/useConfirmMutation";
import {
  useListAdminAgentLanguagesQuery,
  useCreateAgentLanguageMutation,
  useUpdateAgentLanguageMutation,
  useDeleteAgentLanguageMutation,
} from "@/store/agentLanguagesApi";
import type { AgentLanguage } from "@/types";
import { formatDateTime } from "@/utils/datetime";

type FormMode = "create" | "edit";

interface FormState {
  mode: FormMode;
  language?: AgentLanguage;
}

interface LanguageFormDialogProps {
  mode: FormMode;
  initial?: AgentLanguage;
  submitting: boolean;
  onSubmit: (payload: {
    code?: string;
    name: string;
    sort_order: number;
    is_default: boolean;
    is_active?: boolean;
  }) => Promise<void>;
  onClose: () => void;
}

const LanguageFormDialog = React.memo(function LanguageFormDialog({
  mode,
  initial,
  submitting,
  onSubmit,
  onClose,
}: LanguageFormDialogProps): React.ReactNode {
  const [code, setCode] = useState<string>(initial?.code ?? "");
  const [name, setName] = useState<string>(initial?.name ?? "");
  const [sortOrder, setSortOrder] = useState<string>(
    String(initial?.sort_order ?? 0)
  );
  const [isDefault, setIsDefault] = useState<boolean>(
    initial?.is_default ?? false
  );
  const [isActive, setIsActive] = useState<boolean>(initial?.is_active ?? true);

  const [codeError, setCodeError] = useState<string>("");
  const [nameError, setNameError] = useState<string>("");
  const [sortOrderError, setSortOrderError] = useState<string>("");

  const title = mode === "create" ? "新增語言" : "編輯語言";

  const handleCodeChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setCode(e.target.value);
      setCodeError("");
    },
    []
  );

  const handleNameChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setName(e.target.value);
      setNameError("");
    },
    []
  );

  const handleSortOrderChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setSortOrder(e.target.value);
      setSortOrderError("");
    },
    []
  );

  const handleToggleDefault = useCallback((next: boolean): void => {
    setIsDefault(next);
  }, []);

  const handleToggleActive = useCallback((next: boolean): void => {
    setIsActive(next);
  }, []);

  const handleSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
      e.preventDefault();
      let hasError = false;

      const trimmedName = name.trim();
      if (!trimmedName) {
        setNameError("顯示名稱為必填");
        hasError = true;
      } else if (trimmedName.length > 50) {
        setNameError("顯示名稱不可超過 50 字元");
        hasError = true;
      }

      if (mode === "create") {
        const trimmedCode = code.trim();
        if (!trimmedCode) {
          setCodeError("語系碼為必填");
          hasError = true;
        } else if (trimmedCode.length > 20) {
          setCodeError("語系碼不可超過 20 字元");
          hasError = true;
        }
      }

      const sortOrderNum = parseInt(sortOrder, 10);
      if (Number.isNaN(sortOrderNum)) {
        setSortOrderError("排序值需為整數");
        hasError = true;
      }

      if (hasError) return;

      if (mode === "create") {
        await onSubmit({
          code: code.trim(),
          name: trimmedName,
          sort_order: sortOrderNum,
          is_default: isDefault,
        });
      } else {
        await onSubmit({
          name: trimmedName,
          sort_order: sortOrderNum,
          is_default: isDefault,
          is_active: isActive,
        });
      }
    },
    [mode, code, name, sortOrder, isDefault, isActive, onSubmit]
  );

  return (
    <ModalDialog title={title} onClose={onClose}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <label
            htmlFor="lang-code"
            className="mb-1.5 block text-base font-medium text-foreground"
          >
            語系碼
            {mode === "create" && (
              <span className="ml-0.5 text-destructive">*</span>
            )}
          </label>
          {mode === "create" ? (
            <Input
              id="lang-code"
              placeholder="例如：zh-TW"
              value={code}
              onChange={handleCodeChange}
              error={codeError}
              disabled={submitting}
            />
          ) : (
            <div className="min-h-11 w-full rounded-xl border border-input-border bg-muted-bg px-3 py-2 font-mono text-base text-muted">
              {code}
            </div>
          )}
        </div>

        <Input
          label="顯示名稱"
          required
          value={name}
          onChange={handleNameChange}
          error={nameError}
          disabled={submitting}
          placeholder="例如：繁體中文"
        />

        <div>
          <label
            htmlFor="lang-sort"
            className="mb-1.5 block text-base font-medium text-foreground"
          >
            排序
          </label>
          <Input
            id="lang-sort"
            type="number"
            value={sortOrder}
            onChange={handleSortOrderChange}
            error={sortOrderError}
            disabled={submitting}
            placeholder="數值越小越前面"
          />
        </div>

        <div className="flex items-center justify-between">
          <span className="text-base font-medium text-foreground">
            設為預設語言
          </span>
          <Toggle
            checked={isDefault}
            onChange={handleToggleDefault}
            disabled={submitting}
            label="切換預設語言"
          />
        </div>

        {mode === "edit" && (
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

interface LanguageCardProps {
  language: AgentLanguage;
  onEdit: (lang: AgentLanguage) => void;
  onDelete: (lang: AgentLanguage) => void;
}

const LanguageCard = React.memo(function LanguageCard({
  language,
  onEdit,
  onDelete,
}: LanguageCardProps): React.ReactNode {
  const handleEdit = useCallback((): void => {
    onEdit(language);
  }, [language, onEdit]);

  const handleDelete = useCallback((): void => {
    onDelete(language);
  }, [language, onDelete]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-medium text-foreground">
          {language.name}
        </span>
        {language.is_default && (
          <span className="shrink-0 rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
            預設
          </span>
        )}
      </div>
      <div className="font-mono text-sm text-muted">{language.code}</div>
      <div className="flex items-center gap-2 text-sm text-muted">
        <span>排序：{language.sort_order}</span>
        <span
          className={`rounded-xl px-2 py-0.5 font-medium ${
            language.is_active
              ? "bg-success/10 text-success"
              : "bg-muted-bg text-muted"
          }`}
        >
          {language.is_active ? "啟用" : "停用"}
        </span>
      </div>
      <div className="text-sm text-muted">
        建立時間：{formatDateTime(language.created_at)}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="secondary" onClick={handleEdit}>
          編輯
        </Button>
        <Button size="sm" variant="destructive" onClick={handleDelete}>
          刪除
        </Button>
      </div>
    </div>
  );
});

export default function AdminAgentLanguagesPage(): React.ReactNode {
  const { authLoading, isAdmin, shouldBlockRender } = useAdminGuard();
  const pagination = useCursorPagination(20);
  const [formState, setFormState] = useState<FormState | null>(null);

  const { data, isLoading, isFetching } = useListAdminAgentLanguagesQuery(
    { limit: pagination.limit, cursor: pagination.cursor },
    { skip: authLoading || !isAdmin }
  );

  const [createLanguage, { isLoading: creating }] =
    useCreateAgentLanguageMutation();
  const [updateLanguage, { isLoading: updating }] =
    useUpdateAgentLanguageMutation();
  const [deleteLanguage] = useDeleteAgentLanguageMutation();

  const runCreate = useMutationWithDialog(createLanguage);
  const runUpdate = useMutationWithDialog(updateLanguage);

  const submitting = creating || updating;

  const items = useMemo(
    (): AgentLanguage[] => data?.items ?? [],
    [data]
  );

  const handleOpenCreate = useCallback((): void => {
    setFormState({ mode: "create" });
  }, []);

  const handleOpenEdit = useCallback((lang: AgentLanguage): void => {
    setFormState({ mode: "edit", language: lang });
  }, []);

  const handleCloseForm = useCallback((): void => {
    setFormState(null);
  }, []);

  const handleSubmitForm = useCallback(
    async (payload: {
      code?: string;
      name: string;
      sort_order: number;
      is_default: boolean;
      is_active?: boolean;
    }): Promise<void> => {
      if (!formState) return;
      if (formState.mode === "create") {
        await runCreate(
          {
            code: payload.code ?? "",
            name: payload.name,
            sort_order: payload.sort_order,
            is_default: payload.is_default,
          },
          {
            successTitle: "建立成功",
            successMessage: "語言已新增。",
            errorMessage: "新增失敗，請稍後再試",
            onSuccess: () => setFormState(null),
          }
        );
        return;
      }
      if (formState.language) {
        await runUpdate(
          {
            uid: formState.language.agent_language_uid,
            body: {
              name: payload.name,
              sort_order: payload.sort_order,
              is_default: payload.is_default,
              is_active: payload.is_active,
            },
          },
          {
            successTitle: "更新成功",
            successMessage: "語言已更新。",
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
      title: "刪除語言",
      message: "確定要刪除此語言嗎？使用此語言的 Agent 將保留原設定值。",
      successTitle: "刪除成功",
      successMessage: "語言已刪除。",
      errorMessage: "刪除失敗，請稍後再試",
    }),
    []
  );
  const confirmDelete = useConfirmMutation(deleteLanguage, deleteOptions);
  const handleDelete = useCallback(
    (lang: AgentLanguage): void => {
      confirmDelete(lang.agent_language_uid);
    },
    [confirmDelete]
  );

  const handleNextPage = useCallback((): void => {
    pagination.handleNextPage(data?.next_cursor);
  }, [pagination, data]);

  const columns = useMemo(
    () => [
      {
        key: "code",
        header: "語系碼",
        render: (lang: AgentLanguage): React.ReactNode => (
          <span className="font-mono text-base text-foreground">
            {lang.code}
          </span>
        ),
      },
      {
        key: "name",
        header: "顯示名稱",
      },
      {
        key: "sort_order",
        header: "排序",
      },
      {
        key: "is_default",
        header: "預設",
        render: (lang: AgentLanguage): React.ReactNode =>
          lang.is_default ? (
            <span className="rounded-xl bg-primary/10 px-2 py-0.5 text-sm font-medium text-primary">
              預設
            </span>
          ) : (
            <span className="text-sm text-muted">-</span>
          ),
      },
      {
        key: "is_active",
        header: "狀態",
        render: (lang: AgentLanguage): React.ReactNode => (
          <span
            className={`rounded-xl px-2 py-0.5 text-sm font-medium ${
              lang.is_active
                ? "bg-success/10 text-success"
                : "bg-muted-bg text-muted"
            }`}
          >
            {lang.is_active ? "啟用" : "停用"}
          </span>
        ),
      },
      {
        key: "created_at",
        header: "建立時間",
        render: (lang: AgentLanguage): React.ReactNode => (
          <span className="text-base">{formatDateTime(lang.created_at)}</span>
        ),
      },
      {
        key: "actions",
        header: "操作",
        render: (lang: AgentLanguage): React.ReactNode => (
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => handleOpenEdit(lang)}
            >
              編輯
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => handleDelete(lang)}
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
    (lang: AgentLanguage): string => lang.agent_language_uid,
    []
  );

  const cardRender = useCallback(
    (lang: AgentLanguage): React.ReactNode => (
      <LanguageCard
        language={lang}
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
        <h1 className="text-3xl font-bold text-foreground">語言管理</h1>
        <Button onClick={handleOpenCreate}>新增語言</Button>
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
              emptyMessage="尚無語言資料"
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
        <LanguageFormDialog
          mode={formState.mode}
          initial={formState.language}
          submitting={submitting}
          onSubmit={handleSubmitForm}
          onClose={handleCloseForm}
        />
      )}
    </div>
  );
}
