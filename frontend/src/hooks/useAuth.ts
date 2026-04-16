"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken, setAccessToken } from "@/lib/api/client";
import { useLogoutMutation, useRefreshMutation } from "@/store/authApi";
import type { TokenPayload } from "@/types";

interface UseAuthReturn {
  isAuthenticated: boolean;
  isLoading: boolean;
  userUid: string | null;
  role: string | null;
  username: string | null;
  logout: () => Promise<void>;
}

function decodeTokenPayload(token: string): TokenPayload | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return payload as TokenPayload;
  } catch {
    return null;
  }
}

function isTokenExpired(payload: TokenPayload): boolean {
  return payload.exp * 1000 < Date.now();
}

export function useAuth(): UseAuthReturn {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [tokenPayload, setTokenPayload] = useState<TokenPayload | null>(null);
  const [logoutMutation] = useLogoutMutation();
  const [refreshMutation] = useRefreshMutation();

  useEffect(() => {
    const initAuth = async (): Promise<void> => {
      const token = getAccessToken();

      if (token) {
        const payload = decodeTokenPayload(token);
        if (payload && !isTokenExpired(payload)) {
          setTokenPayload(payload);
          setIsLoading(false);
          return;
        }
      }

      try {
        const result = await refreshMutation().unwrap();
        const payload = decodeTokenPayload(result.access_token);
        setTokenPayload(payload);
      } catch {
        setAccessToken(null);
        setTokenPayload(null);
      } finally {
        setIsLoading(false);
      }
    };

    void initAuth();
  }, [refreshMutation]);

  const logout = useCallback(async (): Promise<void> => {
    try {
      await logoutMutation().unwrap();
    } catch {
      setAccessToken(null);
    }
    setTokenPayload(null);
    router.push("/");
  }, [logoutMutation, router]);

  const username = useMemo((): string | null => {
    if (!tokenPayload) return null;
    const payload = tokenPayload as TokenPayload & { username?: string };
    return payload.username ?? null;
  }, [tokenPayload]);

  return {
    isAuthenticated: tokenPayload !== null,
    isLoading,
    userUid: tokenPayload?.user_uid ?? null,
    role: tokenPayload?.role ?? null,
    username,
    logout,
  };
}
