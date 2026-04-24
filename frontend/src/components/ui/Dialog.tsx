"use client";

import React, { useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";

type DialogType = "info" | "warning" | "error";

interface DialogProps {
  type: DialogType;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel?: () => void;
}

const TYPE_STYLES: Record<
  DialogType,
  { icon: string; iconBg: string; iconColor: string; buttonBg: string; buttonHover: string }
> = {
  info: {
    icon: "i",
    iconBg: "bg-info-bg",
    iconColor: "text-info",
    buttonBg: "bg-primary",
    buttonHover: "hover:bg-primary-hover",
  },
  warning: {
    icon: "!",
    iconBg: "bg-warning-bg",
    iconColor: "text-warning",
    buttonBg: "bg-warning",
    buttonHover: "hover:bg-warning/80",
  },
  error: {
    icon: "x",
    iconBg: "bg-error-bg",
    iconColor: "text-destructive",
    buttonBg: "bg-destructive",
    buttonHover: "hover:bg-destructive-hover",
  },
};

export function Dialog({
  type,
  title,
  message,
  onConfirm,
  onCancel,
}: DialogProps): React.ReactNode {
  const overlayRef = useRef<HTMLDivElement>(null);
  const styles = TYPE_STYLES[type];

  const handleKeyDown = useCallback(
    (e: KeyboardEvent): void => {
      if (e.key === "Escape") {
        if (onCancel) {
          onCancel();
        } else {
          onConfirm();
        }
      }
    },
    [onConfirm, onCancel]
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
        if (onCancel) {
          onCancel();
        } else {
          onConfirm();
        }
      }
    },
    [onConfirm, onCancel]
  );

  const dialog = (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4"
      onClick={handleOverlayClick}
    >
      <div className="w-full max-w-md rounded-xl bg-card-bg p-6 shadow-lg">
        <div className="mb-4 flex items-start gap-4">
          <div
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${styles.iconBg}`}
          >
            <span className={`text-xl font-bold ${styles.iconColor}`}>
              {styles.icon}
            </span>
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-xl font-semibold text-foreground">{title}</h3>
            <p className="mt-1 text-base text-muted">{message}</p>
          </div>
        </div>
        <div className="flex justify-end gap-3">
          {onCancel && (
            <button
              type="button"
              className="min-h-11 min-w-11 rounded-xl border border-border px-4 py-2 text-base font-medium text-foreground hover:cursor-pointer hover:bg-muted-bg"
              onClick={onCancel}
            >
              取消
            </button>
          )}
          <button
            type="button"
            className={`min-h-11 min-w-11 rounded-xl px-4 py-2 text-base font-medium text-white hover:cursor-pointer ${styles.buttonBg} ${styles.buttonHover}`}
            onClick={onConfirm}
          >
            確認
          </button>
        </div>
      </div>
    </div>
  );

  if (typeof document === "undefined") return null;
  return createPortal(dialog, document.body);
}

export type ContentDialogSize = "sm" | "md" | "lg";

interface ContentDialogProps {
  title: string;
  children: React.ReactNode;
  size?: ContentDialogSize;
  onConfirm?: () => void;
  onCancel?: () => void;
  onDismiss?: () => void;
  confirmLabel?: string;
  cancelLabel?: string;
}

const CONTENT_SIZE_CLASSES: Record<ContentDialogSize, string> = {
  sm: "sm:max-w-sm",
  md: "sm:max-w-md",
  lg: "sm:max-w-2xl",
};

export function ContentDialog({
  title,
  children,
  size = "md",
  onConfirm,
  onCancel,
  onDismiss,
  confirmLabel = "確認",
  cancelLabel = "取消",
}: ContentDialogProps): React.ReactNode {
  const overlayRef = useRef<HTMLDivElement>(null);

  const handleDismiss = useCallback((): void => {
    onDismiss?.();
  }, [onDismiss]);

  const handleCancel = useCallback((): void => {
    onCancel?.();
  }, [onCancel]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent): void => {
      if (e.key === "Escape") {
        handleDismiss();
      }
    },
    [handleDismiss]
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
        handleDismiss();
      }
    },
    [handleDismiss]
  );

  const showFooter = onConfirm !== undefined || onCancel !== undefined;

  const dialog = (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-end justify-center bg-overlay sm:items-center sm:p-4"
      onClick={handleOverlayClick}
    >
      <div
        className={`flex max-h-[90vh] w-full flex-col rounded-t-xl bg-card-bg shadow-lg sm:rounded-xl ${CONTENT_SIZE_CLASSES[size]}`}
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h3 className="text-xl font-semibold text-foreground">{title}</h3>
          <button
            type="button"
            onClick={handleDismiss}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-muted transition-colors hover:cursor-pointer hover:bg-muted-bg hover:text-foreground"
            aria-label="關閉"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path
                d="M4 4L14 14M14 4L4 14"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-4">{children}</div>
        {showFooter && (
          <div className="flex justify-end gap-3 border-t border-border px-6 py-4">
            {onCancel && (
              <button
                type="button"
                className="min-h-11 min-w-11 rounded-xl border border-border px-4 py-2 text-base font-medium text-foreground hover:cursor-pointer hover:bg-muted-bg"
                onClick={handleCancel}
              >
                {cancelLabel}
              </button>
            )}
            {onConfirm && (
              <button
                type="button"
                className="min-h-11 min-w-11 rounded-xl bg-primary px-4 py-2 text-base font-medium text-white hover:cursor-pointer hover:bg-primary-hover"
                onClick={onConfirm}
              >
                {confirmLabel}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );

  if (typeof document === "undefined") return null;
  return createPortal(dialog, document.body);
}
