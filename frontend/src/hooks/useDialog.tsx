"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { Dialog } from "@/components/ui/Dialog";

type DialogType = "info" | "warning" | "error";

interface DialogConfig {
  type: DialogType;
  title: string;
  message: string;
  onConfirm?: () => void;
  onCancel?: () => void;
}

interface DialogContextValue {
  showDialog: (config: DialogConfig) => void;
}

const DialogContext = createContext<DialogContextValue | null>(null);

interface DialogProviderProps {
  children: ReactNode;
}

export function DialogProvider({
  children,
}: DialogProviderProps): React.ReactNode {
  const [dialogConfig, setDialogConfig] = useState<DialogConfig | null>(null);

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

  return (
    <DialogContext.Provider value={{ showDialog }}>
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
