"use client";

import { useCallback } from "react";
import { useDialog } from "@/hooks/useDialog";

interface MutationLike<TArg, TResult> {
  (arg: TArg): { unwrap: () => Promise<TResult> };
}

interface RunOptions {
  /** 成功後顯示的 Dialog 訊息；未提供則不跳成功 Dialog */
  successTitle?: string;
  successMessage?: string;
  /** 失敗預設訊息（伺服器回傳字串時優先顯示伺服器訊息） */
  errorTitle?: string;
  errorMessage?: string;
  /** 成功後的額外 callback（例如關閉表單） */
  onSuccess?: () => void;
  /** 失敗後的額外 callback */
  onError?: (err: unknown) => void;
}

/**
 * 將 RTK Query mutation 與 showDialog 的 try/catch 串起來：
 * - 成功可選擇性跳 info Dialog
 * - 失敗統一跳 error Dialog；若伺服器回傳字串訊息則優先使用
 */
export function useMutationWithDialog<TArg, TResult>(
  mutation: MutationLike<TArg, TResult>
): (arg: TArg, options?: RunOptions) => Promise<boolean> {
  const { showDialog } = useDialog();

  return useCallback(
    async (arg: TArg, options?: RunOptions): Promise<boolean> => {
      try {
        await mutation(arg).unwrap();
        if (options?.successMessage) {
          showDialog({
            type: "info",
            title: options.successTitle ?? "操作成功",
            message: options.successMessage,
          });
        }
        options?.onSuccess?.();
        return true;
      } catch (err: unknown) {
        const fallback = options?.errorMessage ?? "操作失敗，請稍後再試";
        const message = typeof err === "string" ? err : fallback;
        showDialog({
          type: "error",
          title: options?.errorTitle ?? "操作失敗",
          message,
        });
        options?.onError?.(err);
        return false;
      }
    },
    [mutation, showDialog]
  );
}
