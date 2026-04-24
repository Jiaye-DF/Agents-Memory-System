"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { Dialog, ContentDialog, type ContentDialogSize } from "@/components/ui/Dialog";

type DialogType = "info" | "warning" | "error";

interface DialogConfig {
  type: DialogType;
  title: string;
  message: string;
  onConfirm?: () => void;
  onCancel?: () => void;
}

interface ContentDialogConfig {
  title: string;
  content: ReactNode;
  size?: ContentDialogSize;
  onConfirm?: () => void;
  onCancel?: () => void;
  onDismiss?: () => void;
  confirmLabel?: string;
  cancelLabel?: string;
}

interface DialogContextValue {
  showDialog: (config: DialogConfig) => void;
  showContentDialog: (config: ContentDialogConfig) => void;
  closeContentDialog: () => void;
}

const DialogContext = createContext<DialogContextValue | null>(null);

interface DialogProviderProps {
  children: ReactNode;
}

export function DialogProvider({
  children,
}: DialogProviderProps): React.ReactNode {
  const [dialogConfig, setDialogConfig] = useState<DialogConfig | null>(null);
  const [contentDialogConfig, setContentDialogConfig] =
    useState<ContentDialogConfig | null>(null);

  const showDialog = useCallback((config: DialogConfig): void => {
    setDialogConfig(config);
  }, []);

  const handleConfirm = useCallback((): void => {
    dialogConfig?.onConfirm?.();
    setDialogConfig(null);
  }, [dialogConfig]);

  const handleCancel = useCallback((): void => {
    dialogConfig?.onCancel?.();
    setDialogConfig(null);
  }, [dialogConfig]);

  const showContentDialog = useCallback((config: ContentDialogConfig): void => {
    setContentDialogConfig(config);
  }, []);

  const closeContentDialog = useCallback((): void => {
    setContentDialogConfig(null);
  }, []);

  const handleContentConfirm = useCallback((): void => {
    contentDialogConfig?.onConfirm?.();
    setContentDialogConfig(null);
  }, [contentDialogConfig]);

  const handleContentCancel = useCallback((): void => {
    contentDialogConfig?.onCancel?.();
    setContentDialogConfig(null);
  }, [contentDialogConfig]);

  const handleContentDismiss = useCallback((): void => {
    contentDialogConfig?.onDismiss?.();
    setContentDialogConfig(null);
  }, [contentDialogConfig]);

  return (
    <DialogContext.Provider
      value={{ showDialog, showContentDialog, closeContentDialog }}
    >
      {children}
      {dialogConfig && (
        <Dialog
          type={dialogConfig.type}
          title={dialogConfig.title}
          message={dialogConfig.message}
          onConfirm={handleConfirm}
          onCancel={dialogConfig.type === "warning" ? handleCancel : undefined}
        />
      )}
      {contentDialogConfig && (
        <ContentDialog
          title={contentDialogConfig.title}
          size={contentDialogConfig.size}
          onConfirm={
            contentDialogConfig.onConfirm ? handleContentConfirm : undefined
          }
          onCancel={
            contentDialogConfig.onCancel ? handleContentCancel : undefined
          }
          onDismiss={handleContentDismiss}
          confirmLabel={contentDialogConfig.confirmLabel}
          cancelLabel={contentDialogConfig.cancelLabel}
        >
          {contentDialogConfig.content}
        </ContentDialog>
      )}
    </DialogContext.Provider>
  );
}

export function useDialog(): DialogContextValue {
  const context = useContext(DialogContext);
  if (!context) {
    throw new Error("useDialog 必須在 DialogProvider 內使用");
  }
  return context;
}
