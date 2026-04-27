"use client";

import React from "react";

interface PendingApprovalCardProps {
  /** 頁面標題（與原頁面 H1 對齊） */
  title: string;
  /** 可選副標說明（與原頁面副說明對齊） */
  description?: string;
}

/**
 * df 公司版本：API Token 餘額未開通時的整頁鎖定卡片。
 * 與 `usePendingApprovalDialog` 對話框使用同一句文案，整頁版本用於頁面層級隔離。
 */
export function PendingApprovalCard({
  title,
  description,
}: PendingApprovalCardProps): React.ReactNode {
  return (
    <div>
      <div className="mb-4">
        <h1 className="text-3xl font-bold text-foreground">{title}</h1>
        {description && (
          <p className="mt-1 text-base text-muted">{description}</p>
        )}
      </div>
      <div className="rounded-xl bg-card-bg p-12 text-center shadow-sm">
        <h2 className="mb-2 text-lg font-semibold text-foreground">
          功能尚待審核
        </h2>
        <p className="text-base text-muted">
          此功能尚待審核，暫無 API Token 餘額。
        </p>
      </div>
    </div>
  );
}
