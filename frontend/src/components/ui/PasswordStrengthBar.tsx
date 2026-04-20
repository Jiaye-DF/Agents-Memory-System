"use client";

import React, { useMemo } from "react";
import {
  getPasswordStrength,
  type PasswordStrength,
} from "@/utils/validation";

interface PasswordStrengthBarProps {
  password: string;
}

const STRENGTH_CONFIG: Record<
  PasswordStrength,
  { label: string; colorClass: string; width: string }
> = {
  weak: { label: "弱", colorClass: "bg-destructive", width: "w-1/3" },
  medium: { label: "中", colorClass: "bg-warning", width: "w-2/3" },
  strong: { label: "強", colorClass: "bg-success", width: "w-full" },
};

export const PasswordStrengthBar = React.memo(function PasswordStrengthBar({
  password,
}: PasswordStrengthBarProps): React.ReactNode {
  const strength = useMemo(
    (): PasswordStrength => getPasswordStrength(password),
    [password]
  );
  const config = STRENGTH_CONFIG[strength];

  if (!password) return null;

  return (
    <div className="mt-1">
      <div className="h-1.5 w-full overflow-hidden rounded-xl bg-muted-bg">
        <div
          className={`h-full rounded-xl transition-all duration-300 ${config.colorClass} ${config.width}`}
        />
      </div>
      <p
        className={`mt-0.5 text-sm ${
          strength === "weak"
            ? "text-destructive"
            : strength === "medium"
              ? "text-warning"
              : "text-success"
        }`}
      >
        密碼強度：{config.label}
      </p>
    </div>
  );
});
