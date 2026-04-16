"use client";

import { useEffect, useRef, useCallback } from "react";
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
            <span className={`text-lg font-bold ${styles.iconColor}`}>
              {styles.icon}
            </span>
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-lg font-semibold text-foreground">{title}</h3>
            <p className="mt-1 text-sm text-muted">{message}</p>
          </div>
        </div>
        <div className="flex justify-end gap-3">
          {onCancel && (
            <button
              type="button"
              className="min-h-[44px] min-w-[44px] rounded-xl border border-border px-4 py-2 text-sm font-medium text-foreground hover:cursor-pointer hover:bg-muted-bg"
              onClick={onCancel}
            >
              取消
            </button>
          )}
          <button
            type="button"
            className={`min-h-[44px] min-w-[44px] rounded-xl px-4 py-2 text-sm font-medium text-white hover:cursor-pointer ${styles.buttonBg} ${styles.buttonHover}`}
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
