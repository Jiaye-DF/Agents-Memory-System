"use client";

import { useCallback } from "react";
import { useDialog } from "@/hooks/useDialog";

/**
 * df 公司版本：尚未開通 API Token 餘額時的統一提示。
 * 用於 block 建立對話 / 建立專案 / Skill 建議等需 LLM token 的入口。
 */
export function usePendingApprovalDialog(): () => void {
  const { showDialog } = useDialog();
  return useCallback((): void => {
    showDialog({
      type: "info",
      title: "功能審核中",
      message: "功能正在管理審核中，敬請期待未來更新。",
    });
  }, [showDialog]);
}
