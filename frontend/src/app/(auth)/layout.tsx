"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { DialogProvider } from "@/hooks/useDialog";
import { useAuth } from "@/hooks/useAuth";
import { PageLoading } from "@/components/ui/Loading";

interface AuthLayoutProps {
  children: React.ReactNode;
}

export default function AuthLayout({
  children,
}: AuthLayoutProps): React.ReactNode {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace("/dashboard");
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4">
        <PageLoading />
      </div>
    );
  }

  if (isAuthenticated) {
    return null;
  }

  return (
    <DialogProvider>
      <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4">
        {children}
      </div>
    </DialogProvider>
  );
}
