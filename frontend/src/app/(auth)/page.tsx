"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Logo } from "@/components/layout/Logo";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { useDialog } from "@/hooks/useDialog";
import { useLoginMutation } from "@/store/authApi";
import { validateAccount, validatePassword } from "@/utils/validation";

interface FormErrors {
  account: string | null;
  password: string | null;
}

export default function LoginPage(): React.ReactNode {
  const router = useRouter();
  const { showDialog } = useDialog();
  const [login, { isLoading }] = useLoginMutation();

  const [account, setAccount] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [errors, setErrors] = useState<FormErrors>({
    account: null,
    password: null,
  });

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

  const handleAccountBlur = useCallback((): void => {
    if (account) {
      const error = validateAccount(account);
      setErrors((prev) => ({ ...prev, account: error }));
    }
  }, [account]);

  const handlePasswordBlur = useCallback((): void => {
    if (password) {
      const error = validatePassword(password);
      setErrors((prev) => ({ ...prev, password: error }));
    }
  }, [password]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
      e.preventDefault();

      const accountError = validateAccount(account);
      const passwordError = validatePassword(password);

      if (accountError || passwordError) {
        setErrors({ account: accountError, password: passwordError });
        return;
      }

      try {
        await login({ account, password }).unwrap();
        router.push("/dashboard");
      } catch (err: unknown) {
        const message =
          typeof err === "string" ? err : "登入失敗，請確認帳號或密碼是否正確";
        showDialog({
          type: "error",
          title: "登入失敗",
          message,
        });
      }
    },
    [account, password, login, router, showDialog]
  );

  return (
    <div className="w-full max-w-md rounded-xl bg-card-bg p-8 shadow-lg">
      <div className="mb-6 flex flex-col items-center gap-2">
        <Logo className="h-12 w-12" />
        <h1 className="text-2xl font-bold text-foreground">Agents Platform</h1>
        <p className="text-sm text-muted">請登入以繼續</p>
      </div>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          label="帳號"
          placeholder="請輸入帳號"
          value={account}
          onChange={handleAccountChange}
          onBlur={handleAccountBlur}
          error={errors.account ?? undefined}
          required
        />
        <Input
          label="密碼"
          type="password"
          placeholder="請輸入密碼"
          value={password}
          onChange={handlePasswordChange}
          onBlur={handlePasswordBlur}
          error={errors.password ?? undefined}
          required
        />
        <Button type="submit" loading={isLoading} className="mt-2 w-full">
          登入
        </Button>
      </form>
      <div className="mt-4 flex items-center justify-between text-sm">
        <Link
          href="/register"
          className="text-primary transition-colors hover:cursor-pointer hover:text-primary-hover"
        >
          註冊帳號
        </Link>
        <Link
          href="/reset-password"
          className="text-primary transition-colors hover:cursor-pointer hover:text-primary-hover"
        >
          忘記密碼
        </Link>
      </div>
    </div>
  );
}
