"use client";

import React, {
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

type ModalSize = "sm" | "md" | "lg";

interface ModalDialogProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
  size?: ModalSize;
  /** 點擊 overlay 是否可關閉，預設 true */
  closeOnOverlay?: boolean;
  /** 按 ESC 是否可關閉，預設 true */
  closeOnEsc?: boolean;
}

const SIZE_CLASSES: Record<ModalSize, string> = {
  sm: "max-w-md",
  md: "max-w-xl",
  lg: "max-w-3xl",
};

export const ModalDialog = React.memo(function ModalDialog({
  title,
  onClose,
  children,
  size = "sm",
  closeOnOverlay = true,
  closeOnEsc = true,
}: ModalDialogProps): React.ReactNode {
  const overlayRef = useRef<HTMLDivElement>(null);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent): void => {
      if (closeOnEsc && e.key === "Escape") {
        onClose();
      }
    },
    [closeOnEsc, onClose]
  );

  useEffect((): (() => void) => {
    document.addEventListener("keydown", handleKeyDown);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return (): void => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [handleKeyDown]);

  const handleOverlayClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>): void => {
      if (closeOnOverlay && e.target === overlayRef.current) {
        onClose();
      }
    },
    [closeOnOverlay, onClose]
  );

  if (typeof document === "undefined") return null;

  const content = (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4"
      onClick={handleOverlayClick}
    >
      <div
        className={`w-full ${SIZE_CLASSES[size]} rounded-xl bg-card-bg p-6 shadow-lg`}
      >
        <h3 className="mb-4 text-xl font-semibold text-foreground">{title}</h3>
        {children}
      </div>
    </div>
  );

  return createPortal(content, document.body);
});
