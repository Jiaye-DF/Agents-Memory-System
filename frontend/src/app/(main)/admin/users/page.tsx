"use client";

import React, { useState, useCallback, useMemo, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Table } from "@/components/ui/Table";
import { Pagination } from "@/components/ui/Pagination";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { PageLoading } from "@/components/ui/Loading";
import { useDialog } from "@/hooks/useDialog";
import { useAuth } from "@/hooks/useAuth";
import {
  useListUsersQuery,
  useUpdateUserMutation,
  useListRolesQuery,
} from "@/store/adminApi";
import type { User, Role } from "@/types";

interface UserCardProps {
  user: User;
  roles: Role[];
  onRoleChange: (userUid: string, roleUid: string) => void;
  onUnlock: (userUid: string) => void;
}

const UserCard = React.memo(function UserCard({
  user,
  roles,
  onRoleChange,
  onUnlock,
}: UserCardProps): React.ReactNode {
  const handleRoleChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>): void => {
      onRoleChange(user.user_uid, e.target.value);
    },
    [user.user_uid, onRoleChange]
  );

  const handleUnlock = useCallback((): void => {
    onUnlock(user.user_uid);
  }, [user.user_uid, onUnlock]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="font-medium text-foreground">{user.username}</span>
        <span
          className={`rounded-xl px-2 py-0.5 text-xs font-medium ${
            user.is_active
              ? "bg-success/10 text-success"
              : "bg-destructive/10 text-destructive"
          }`}
        >
          {user.is_active ? "啟用" : "停用"}
        </span>
      </div>
      <div className="text-sm text-muted">帳號：{user.account}</div>
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted">角色：</span>
        <select
          value={roles.find((r) => r.name === user.role_name)?.user_role_uid ?? ""}
          onChange={handleRoleChange}
          className="min-h-[36px] rounded-xl border border-input-border bg-input-bg px-2 py-1 text-sm text-foreground hover:cursor-pointer focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
        >
          {roles.map((role) => (
            <option key={role.user_role_uid} value={role.user_role_uid}>
              {role.name}
            </option>
          ))}
        </select>
      </div>
      {user.locked_until && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-warning">
            鎖定至：{new Date(user.locked_until).toLocaleString("zh-TW")}
          </span>
          <Button size="sm" variant="secondary" onClick={handleUnlock}>
            解除鎖定
          </Button>
        </div>
      )}
      {!user.is_active && !user.locked_until && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-destructive">帳號已被永久鎖定</span>
          <Button size="sm" variant="secondary" onClick={handleUnlock}>
            解除鎖定
          </Button>
        </div>
      )}
      <div className="text-xs text-muted">
        建立時間：{new Date(user.created_at).toLocaleString("zh-TW")}
      </div>
    </div>
  );
});

export default function AdminUsersPage(): React.ReactNode {
  const router = useRouter();
  const { role, isLoading: authLoading } = useAuth();
  const { showDialog } = useDialog();

  const [limit, setLimit] = useState<number>(20);
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);
  const [searchTerm, setSearchTerm] = useState<string>("");

  useEffect(() => {
    if (!authLoading && role !== "admin") {
      router.replace("/403");
    }
  }, [role, authLoading, router]);

  const { data, isLoading, isFetching } = useListUsersQuery(
    { limit, cursor },
    { skip: authLoading || role !== "admin" }
  );
  const { data: rolesData } = useListRolesQuery(undefined, {
    skip: authLoading || role !== "admin",
  });
  const [updateUser] = useUpdateUserMutation();

  const roles = useMemo(
    (): Role[] => rolesData?.roles ?? [],
    [rolesData]
  );

  const filteredUsers = useMemo((): User[] => {
    if (!data?.items) return [];
    if (!searchTerm) return data.items;
    const term = searchTerm.toLowerCase();
    return data.items.filter(
      (user) =>
        user.username.toLowerCase().includes(term) ||
        user.account.toLowerCase().includes(term) ||
        user.role_name.toLowerCase().includes(term)
    );
  }, [data?.items, searchTerm]);

  const handleRoleChange = useCallback(
    (userUid: string, roleUid: string): void => {
      showDialog({
        type: "warning",
        title: "變更角色",
        message: "確定要變更此使用者的角色嗎？",
        onConfirm: async () => {
          try {
            await updateUser({ userUid, body: { role_uid: roleUid } }).unwrap();
          } catch (err: unknown) {
            const message =
              typeof err === "string" ? err : "角色變更失敗，請稍後再試";
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
    [showDialog, updateUser]
  );

  const handleUnlock = useCallback(
    (userUid: string): void => {
      showDialog({
        type: "warning",
        title: "解除鎖定",
        message: "確定要解除此使用者的登入鎖定嗎？",
        onConfirm: async () => {
          try {
            await updateUser({ userUid, body: { unlock: true } }).unwrap();
          } catch (err: unknown) {
            const message =
              typeof err === "string" ? err : "解除鎖定失敗，請稍後再試";
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
    [showDialog, updateUser]
  );

  const handleNextPage = useCallback((): void => {
    if (data?.next_cursor) {
      setCursorHistory((prev) => [...prev, cursor ?? ""]);
      setCursor(data.next_cursor);
    }
  }, [data?.next_cursor, cursor]);

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

  const handleSearchChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setSearchTerm(e.target.value);
    },
    []
  );

  const columns = useMemo(
    () => [
      {
        key: "username",
        header: "使用者名稱",
      },
      {
        key: "account",
        header: "帳號",
      },
      {
        key: "role_name",
        header: "角色",
        render: (user: User): React.ReactNode => (
          <select
            value={roles.find((r) => r.name === user.role_name)?.user_role_uid ?? ""}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
              handleRoleChange(user.user_uid, e.target.value)
            }
            className="min-h-[36px] rounded-xl border border-input-border bg-input-bg px-2 py-1 text-sm text-foreground hover:cursor-pointer focus:border-input-focus focus:outline-none focus:ring-2 focus:ring-input-focus/20"
          >
            {roles.map((role) => (
              <option key={role.user_role_uid} value={role.user_role_uid}>
                {role.name}
              </option>
            ))}
          </select>
        ),
      },
      {
        key: "is_active",
        header: "狀態",
        render: (user: User): React.ReactNode => (
          <span
            className={`rounded-xl px-2 py-0.5 text-xs font-medium ${
              user.is_active
                ? "bg-success/10 text-success"
                : "bg-destructive/10 text-destructive"
            }`}
          >
            {user.is_active ? "啟用" : "停用"}
          </span>
        ),
      },
      {
        key: "locked_until",
        header: "鎖定狀態",
        render: (user: User): React.ReactNode => {
          if (user.locked_until) {
            return (
              <div className="flex items-center gap-2">
                <span className="text-sm text-warning">
                  {new Date(user.locked_until).toLocaleString("zh-TW")}
                </span>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => handleUnlock(user.user_uid)}
                >
                  解鎖
                </Button>
              </div>
            );
          }
          if (!user.is_active) {
            return (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => handleUnlock(user.user_uid)}
              >
                解鎖
              </Button>
            );
          }
          return <span className="text-sm text-muted">-</span>;
        },
      },
      {
        key: "created_at",
        header: "建立時間",
        render: (user: User): React.ReactNode => (
          <span className="text-sm">
            {new Date(user.created_at).toLocaleString("zh-TW")}
          </span>
        ),
      },
    ],
    [roles, handleRoleChange, handleUnlock]
  );

  const keyExtractor = useCallback((user: User): string => user.user_uid, []);

  const cardRender = useCallback(
    (user: User): React.ReactNode => (
      <UserCard
        user={user}
        roles={roles}
        onRoleChange={handleRoleChange}
        onUnlock={handleUnlock}
      />
    ),
    [roles, handleRoleChange, handleUnlock]
  );

  if (authLoading || role !== "admin") {
    return <PageLoading />;
  }

  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold text-foreground">使用者管理</h1>
      <div className="rounded-xl bg-card-bg p-6 shadow-sm">
        <div className="mb-4">
          <Input
            placeholder="搜尋使用者名稱、帳號或角色..."
            value={searchTerm}
            onChange={handleSearchChange}
          />
        </div>

        {isLoading || isFetching ? (
          <PageLoading />
        ) : (
          <>
            <Table
              columns={columns}
              data={filteredUsers}
              keyExtractor={keyExtractor}
              cardRender={cardRender}
              emptyMessage="尚無使用者資料"
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
    </div>
  );
}
