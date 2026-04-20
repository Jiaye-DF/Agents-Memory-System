"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Logo } from "@/components/layout/Logo";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { PasswordStrengthBar } from "@/components/ui/PasswordStrengthBar";
import { useDialog } from "@/hooks/useDialog";
import { useResetPasswordMutation } from "@/store/authApi";
import {
  validateAccount,
  validateUsername,
  validatePassword,
  validateConfirmPassword,
} from "@/utils/validation";

type Step = "verify" | "reset";

interface VerifyErrors {
  account: string | null;
  username: string | null;
}

interface ResetErrors {
  newPassword: string | null;
  confirmPassword: string | null;
}

export default function ResetPasswordPage(): React.ReactNode {
  const router = useRouter();
  const { showDialog } = useDialog();
  const [resetPassword, { isLoading }] = useResetPasswordMutation();

  const [step, setStep] = useState<Step>("verify");
  const [account, setAccount] = useState<string>("");
  const [username, setUsername] = useState<string>("");
  const [newPassword, setNewPassword] = useState<string>("");
  const [confirmPassword, setConfirmPassword] = useState<string>("");

  const [verifyErrors, setVerifyErrors] = useState<VerifyErrors>({
    account: null,
    username: null,
  });
  const [resetErrors, setResetErrors] = useState<ResetErrors>({
    newPassword: null,
    confirmPassword: null,
  });

  const handleAccountChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setAccount(e.target.value);
      setVerifyErrors((prev) => ({ ...prev, account: null }));
    },
    []
  );

  const handleUsernameChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setUsername(e.target.value);
      setVerifyErrors((prev) => ({ ...prev, username: null }));
    },
    []
  );

  const handleNewPasswordChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setNewPassword(e.target.value);
      setResetErrors((prev) => ({ ...prev, newPassword: null }));
    },
    []
  );

  const handleConfirmPasswordChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setConfirmPassword(e.target.value);
      setResetErrors((prev) => ({ ...prev, confirmPassword: null }));
    },
    []
  );

  const handleAccountBlur = useCallback((): void => {
    if (account) {
      setVerifyErrors((prev) => ({
        ...prev,
        account: validateAccount(account),
      }));
    }
  }, [account]);

  const handleUsernameBlur = useCallback((): void => {
    if (username) {
      setVerifyErrors((prev) => ({
        ...prev,
        username: validateUsername(username),
      }));
    }
  }, [username]);

  const handleNewPasswordBlur = useCallback((): void => {
    if (newPassword) {
      setResetErrors((prev) => ({
        ...prev,
        newPassword: validatePassword(newPassword),
      }));
    }
  }, [newPassword]);

  const handleConfirmPasswordBlur = useCallback((): void => {
    if (confirmPassword) {
      setResetErrors((prev) => ({
        ...prev,
        confirmPassword: validateConfirmPassword(newPassword, confirmPassword),
      }));
    }
  }, [newPassword, confirmPassword]);

  const handleVerifySubmit = useCallback(
    (e: React.FormEvent<HTMLFormElement>): void => {
      e.preventDefault();

      const accountError = validateAccount(account);
      const usernameError = validateUsername(username);

      if (accountError || usernameError) {
        setVerifyErrors({ account: accountError, username: usernameError });
        return;
      }

      setStep("reset");
    },
    [account, username]
  );

  const handleResetSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
      e.preventDefault();

      const newPasswordError = validatePassword(newPassword);
      const confirmPasswordError = validateConfirmPassword(
        newPassword,
        confirmPassword
      );

      if (newPasswordError || confirmPasswordError) {
        setResetErrors({
          newPassword: newPasswordError,
          confirmPassword: confirmPasswordError,
        });
        return;
      }

      try {
        await resetPassword({
          account,
          username,
          new_password: newPassword,
          confirm_password: confirmPassword,
        }).unwrap();
        showDialog({
          type: "info",
          title: "重設密碼成功",
          message: "密碼已更新，請使用新密碼登入",
          onConfirm: () => router.push("/"),
        });
      } catch (err: unknown) {
        const message =
          typeof err === "string" ? err : "重設密碼失敗，請確認帳號與使用者名稱是否正確";
        showDialog({
          type: "error",
          title: "重設密碼失敗",
          message,
        });
      }
    },
    [account, username, newPassword, confirmPassword, resetPassword, showDialog, router]
  );

  const handleBackToVerify = useCallback((): void => {
    setStep("verify");
    setNewPassword("");
    setConfirmPassword("");
    setResetErrors({ newPassword: null, confirmPassword: null });
  }, []);

  return (
    <div className="w-full max-w-md rounded-xl bg-card-bg p-8 shadow-lg">
      <div className="mb-6 flex flex-col items-center gap-2">
        <Logo className="h-12 w-12" />
        <h1 className="text-3xl font-bold text-foreground">重設密碼</h1>
        <p className="text-base text-muted">
          {step === "verify"
            ? "步驟 1：輸入帳號與使用者名稱進行驗證"
            : "步驟 2：設定新密碼"}
        </p>
      </div>

      <div className="mb-6 flex items-center gap-2">
        <div
          className={`flex h-8 w-8 items-center justify-center rounded-full text-base font-medium ${
            step === "verify"
              ? "bg-primary text-white"
              : "bg-success text-white"
          }`}
        >
          {step === "verify" ? "1" : "✓"}
        </div>
        <div
          className={`h-0.5 flex-1 rounded-xl ${
            step === "reset" ? "bg-primary" : "bg-muted-bg"
          }`}
        />
        <div
          className={`flex h-8 w-8 items-center justify-center rounded-full text-base font-medium ${
            step === "reset"
              ? "bg-primary text-white"
              : "bg-muted-bg text-muted"
          }`}
        >
          2
        </div>
      </div>

      {step === "verify" ? (
        <form onSubmit={handleVerifySubmit} className="flex flex-col gap-4">
          <Input
            label="帳號"
            placeholder="請輸入帳號"
            value={account}
            onChange={handleAccountChange}
            onBlur={handleAccountBlur}
            error={verifyErrors.account ?? undefined}
            required
          />
          <Input
            label="使用者名稱"
            placeholder="請輸入使用者名稱"
            value={username}
            onChange={handleUsernameChange}
            onBlur={handleUsernameBlur}
            error={verifyErrors.username ?? undefined}
            required
          />
          <Button type="submit" className="mt-2 w-full">
            下一步
          </Button>
        </form>
      ) : (
        <form onSubmit={handleResetSubmit} className="flex flex-col gap-4">
          <div>
            <Input
              label="新密碼"
              type="password"
              placeholder="至少 8 個字元，含大小寫字母及數字"
              value={newPassword}
              onChange={handleNewPasswordChange}
              onBlur={handleNewPasswordBlur}
              error={resetErrors.newPassword ?? undefined}
              required
            />
            <PasswordStrengthBar password={newPassword} />
          </div>
          <Input
            label="確認新密碼"
            type="password"
            placeholder="請再次輸入新密碼"
            value={confirmPassword}
            onChange={handleConfirmPasswordChange}
            onBlur={handleConfirmPasswordBlur}
            error={resetErrors.confirmPassword ?? undefined}
            required
          />
          <div className="mt-2 flex gap-3">
            <Button
              variant="secondary"
              onClick={handleBackToVerify}
              className="flex-1"
            >
              上一步
            </Button>
            <Button type="submit" loading={isLoading} className="flex-1">
              重設密碼
            </Button>
          </div>
        </form>
      )}

      <div className="mt-4 text-center text-base">
        <Link
          href="/"
          className="text-primary transition-colors hover:cursor-pointer hover:text-primary-hover"
        >
          返回登入
        </Link>
      </div>
    </div>
  );
}
