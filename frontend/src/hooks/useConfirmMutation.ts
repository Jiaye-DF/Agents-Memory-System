"use client";

import { useCallback } from "react";
import { useDialog } from "@/hooks/useDialog";
import { useMutationWithDialog } from "@/hooks/useMutationWithDialog";

interface MutationLike<TArg, TResult> {
  (arg: TArg): { unwrap: () => Promise<TResult> };
}

interface ConfirmOptions {
  title: string;
  message: string;
  successTitle?: string;
  successMessage?: string;
  errorTitle?: string;
  errorMessage?: string;
}

/**
 * 「Warning Dialog 確認後執行 mutation」的組合；常見於刪除 / 解鎖 / 切換可見性。
 * 回傳一個呼叫即觸發流程的 handler：確認 → 執行 → 成功/失敗 Dialog。
 */
export function useConfirmMutation<TArg, TResult>(
  mutation: MutationLike<TArg, TResult>,
  options: ConfirmOptions
): (arg: TArg) => void {
  const { showDialog } = useDialog();
  const run = useMutationWithDialog(mutation);

  return useCallback(
    (arg: TArg): void => {
      showDialog({
        type: "warning",
        title: options.title,
        message: options.message,
        onConfirm: () => {
          void run(arg, {
            successTitle: options.successTitle,
            successMessage: options.successMessage,
            errorTitle: options.errorTitle,
            errorMessage: options.errorMessage,
          });
        },
        onCancel: () => {},
      });
    },
    [showDialog, run, options]
  );
}
