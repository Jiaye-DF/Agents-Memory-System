import type { ApiResponse } from "@/types/api";
import { isSsoUser, triggerSilentReAuth } from "./silent-reauth";

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface RequestOptions {
  headers?: Record<string, string>;
  body?: unknown;
  params?: Record<string, string>;
  formData?: FormData;
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

let accessToken: string | null = null;
let isRefreshing = false;
let refreshPromise: Promise<string | null> | null = null;
// Silent re-auth dedupe（INTEGRATION.md「Silent Re-Auth Pattern」）：
// 多個並發 401 共用同一個 navigation, 避免重複觸發 redirect。
let reAuthPromise: Promise<void> | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

async function refreshAccessToken(): Promise<string | null> {
  try {
    const response = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    });

    if (!response.ok) {
      setAccessToken(null);
      return null;
    }

    const data: ApiResponse<{ access_token: string }> = await response.json();
    if (data.success && data.data) {
      setAccessToken(data.data.access_token);
      return data.data.access_token;
    }

    setAccessToken(null);
    return null;
  } catch {
    setAccessToken(null);
    return null;
  }
}

function buildUrl(path: string, params?: Record<string, string>): string {
  const url = new URL(`${BASE_URL}${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      url.searchParams.append(key, value);
    });
  }
  return url.toString();
}

async function request<T>(
  method: HttpMethod,
  path: string,
  options: RequestOptions = {}
): Promise<ApiResponse<T>> {
  const { headers = {}, body, params, formData } = options;
  const url = buildUrl(path, params);

  const isFormData = formData instanceof FormData;

  const requestHeaders: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...headers,
  };

  if (accessToken) {
    requestHeaders["Authorization"] = `Bearer ${accessToken}`;
  }

  const fetchOptions: RequestInit = {
    method,
    headers: requestHeaders,
    credentials: "include",
  };

  if (isFormData) {
    fetchOptions.body = formData;
  } else if (body !== undefined && method !== "GET") {
    fetchOptions.body = JSON.stringify(body);
  }

  let response = await fetch(url, fetchOptions);

  if (response.status === 401 && accessToken) {
    if (!isRefreshing) {
      isRefreshing = true;
      refreshPromise = refreshAccessToken();
    }

    const newToken = await refreshPromise;
    isRefreshing = false;
    refreshPromise = null;

    if (newToken) {
      requestHeaders["Authorization"] = `Bearer ${newToken}`;
      response = await fetch(url, {
        ...fetchOptions,
        headers: requestHeaders,
      });
    } else {
      // refresh 失敗：SSO 使用者改走 silent re-auth, 把使用者帶回中央再簽,
      // 中央仍有 session 即可無感回到原頁；只有中央也沒了才會落到登入頁。
      // 本地帳密使用者沒這條路, 維持「踢回登入頁」舊行為。
      if (isSsoUser()) {
        reAuthPromise ??= triggerSilentReAuth();
        await reAuthPromise;
        // 走到此代表 reAuth 沒 navigate（沒設 SSO / 重試上限 / 抓不到 URL）
        reAuthPromise = null;
      }
      return {
        success: false,
        data: null,
        detail: "認證已過期，請重新登入",
        response_code: 401,
      };
    }
  }

  const data: ApiResponse<T> = await response.json();
  return data;
}

export const apiClient = {
  get<T>(path: string, options?: RequestOptions): Promise<ApiResponse<T>> {
    return request<T>("GET", path, options);
  },
  post<T>(path: string, options?: RequestOptions): Promise<ApiResponse<T>> {
    return request<T>("POST", path, options);
  },
  put<T>(path: string, options?: RequestOptions): Promise<ApiResponse<T>> {
    return request<T>("PUT", path, options);
  },
  patch<T>(path: string, options?: RequestOptions): Promise<ApiResponse<T>> {
    return request<T>("PATCH", path, options);
  },
  delete<T>(path: string, options?: RequestOptions): Promise<ApiResponse<T>> {
    return request<T>("DELETE", path, options);
  },
};
