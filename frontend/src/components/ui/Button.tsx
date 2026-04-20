"use client";

import React from "react";
import { Spinner } from "./Loading";

type ButtonVariant = "primary" | "secondary" | "destructive" | "ghost";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps {
  children: React.ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
  className?: string;
  onClick?: () => void;
}

const VARIANT_STYLES: Record<ButtonVariant, string> = {
  primary: "bg-primary text-white hover:bg-primary-hover",
  secondary: "bg-muted-bg text-foreground border border-border hover:bg-border",
  destructive: "bg-destructive text-white hover:bg-destructive-hover",
  ghost: "text-foreground hover:bg-muted-bg",
};

const SIZE_STYLES: Record<ButtonSize, string> = {
  sm: "min-h-[36px] px-3 py-1.5 text-base",
  md: "min-h-[44px] px-4 py-2 text-base",
  lg: "min-h-[48px] px-6 py-3 text-lg",
};

export const Button = React.memo(function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  disabled = false,
  type = "button",
  className = "",
  onClick,
}: ButtonProps): React.ReactNode {
  const isDisabled = disabled || loading;

  return (
    <button
      type={type}
      disabled={isDisabled}
      onClick={onClick}
      className={`inline-flex min-w-[44px] items-center justify-center gap-2 rounded-xl font-medium transition-colors hover:cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT_STYLES[variant]} ${SIZE_STYLES[size]} ${className}`}
    >
      {loading && <Spinner size="sm" />}
      {children}
    </button>
  );
});
