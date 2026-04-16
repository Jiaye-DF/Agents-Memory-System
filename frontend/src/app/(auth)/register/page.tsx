"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Logo } from "@/components/layout/Logo";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { PasswordStrengthBar } from "@/components/ui/PasswordStrengthBar";
import { useDialog } from "@/hooks/useDialog";
import { useRegisterMutation } from "@/store/authApi";
import {
  validateUsername,
  validateAccount,
  validatePassword,
  validateConfirmPassword,
} from "@/utils/validation";

interface FormErrors {
  username: string | null;
  account: string | null;
  password: string | null;
  confirmPassword: string | null;
}

export default function RegisterPage(): React.ReactNode {
  const router = useRouter();
  const { showDialog } = useDialog();
  const [register, { isLoading }] = useRegisterMutation();

  const [username, setUsername] = useState<string>("");
  const [account, setAccount] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [confirmPassword, setConfirmPassword] = useState<string>("");
  const [errors, setErrors] = useState<FormErrors>({
    username: null,
    account: null,
    password: null,
    confirmPassword: null,
  });

  const handleUsernameChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setUsername(e.target.value);
      setErrors((prev) => ({ ...prev, username: null }));
    },
    []
  );

  const handleAccountChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setAccount(e.target.value);
      setErrors((prev) => ({ ...prev, account: null }));
    },
    []
  );

  const handlePasswordChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setPassword(e.target.value);
      setErrors((prev) => ({ ...prev, password: null }));
    },
    []
  );

  const handleConfirmPasswordChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      setConfirmPassword(e.target.value);
      setErrors((prev) => ({ ...prev, confirmPassword: null }));
    },
    []
  );

  const handleUsernameBlur = useCallback((): void => {
    if (username) {
      setErrors((prev) => ({ ...prev, username: validateUsername(username) }));
    }
  }, [username]);

  const handleAccountBlur = useCallback((): void => {
    if (account) {
      setErrors((prev) => ({ ...prev, account: validateAccount(account) }));
    }
  }, [account]);

  const handlePasswordBlur = useCallback((): void => {
    if (password) {
      setErrors((prev) => ({ ...prev, password: validatePassword(password) }));
    }
  }, [password]);

  const handleConfirmPasswordBlur = useCallback((): void => {
    if (confirmPassword) {
      setErrors((prev) => ({
        ...prev,
        confirmPassword: validateConfirmPassword(password, confirmPassword),
      }));
    }
  }, [password, confirmPassword]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
      e.preventDefault();

      const usernameError = validateUsername(username);
      const accountError = validateAccount(account);
      const passwordError = validatePassword(password);
      const confirmPasswordError = validateConfirmPassword(
        password,
        confirmPassword
      );

      if (usernameError || accountError || passwordError || confirmPasswordError) {
        setErrors({
          username: usernameError,
          account: accountError,
          password: passwordError,
          confirmPassword: confirmPasswordError,
        });
        return;
      }

      try {
        await register({
          username,
          account,
          password,
          confirm_password: confirmPassword,
        }).unwrap();
        showDialog({
          type: "info",
          title: "註冊成功",
          message: "帳號已建立，請登入系統",
          onConfirm: () => router.push("/"),
        });
      } catch (err: unknown) {
        const message =
          typeof err === "string" ? err : "註冊失敗，請稍後再試";
        showDialog({
          type: "error",
          title: "註冊失敗",
          message,
        });
      }
    },
    [username, account, password, confirmPassword, register, showDialog, router]
  );

  return (
    <div className="w-full max-w-md rounded-xl bg-card-bg p-8 shadow-lg">
      <div className="mb-6 flex flex-col items-center gap-2">
        <Logo className="h-12 w-12" />
        <h1 className="text-2xl font-bold text-foreground">建立帳號</h1>
        <p className="text-sm text-muted">填寫以下資訊註冊新帳號</p>
      </div>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          label="使用者名稱"
          placeholder="2-50 個字元"
          value={username}
          onChange={handleUsernameChange}
          onBlur={handleUsernameBlur}
          error={errors.username ?? undefined}
          required
        />
        <Input
          label="帳號"
          placeholder="至少 8 個字元，含字母及數字"
          value={account}
          onChange={handleAccountChange}
          onBlur={handleAccountBlur}
          error={errors.account ?? undefined}
          required
        />
        <div>
          <Input
            label="密碼"
            type="password"
            placeholder="至少 8 個字元，含大小寫字母及數字"
            value={password}
            onChange={handlePasswordChange}
            onBlur={handlePasswordBlur}
            error={errors.password ?? undefined}
            required
          />
          <PasswordStrengthBar password={password} />
        </div>
        <Input
          label="確認密碼"
          type="password"
          placeholder="請再次輸入密碼"
          value={confirmPassword}
          onChange={handleConfirmPasswordChange}
          onBlur={handleConfirmPasswordBlur}
          error={errors.confirmPassword ?? undefined}
          required
        />
        <Button type="submit" loading={isLoading} className="mt-2 w-full">
          註冊
        </Button>
      </form>
      <div className="mt-4 text-center text-sm">
        <span className="text-muted">已有帳號？</span>{" "}
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
