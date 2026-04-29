import { baseApi } from "./api";
import { setAccessToken } from "@/lib/api/client";
import { clearSsoLogin } from "@/lib/api/silent-reauth";
import type {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  ResetPasswordRequest,
} from "@/types";

export const authApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    register: builder.mutation<RegisterResponse, RegisterRequest>({
      query: (body) => ({
        method: "post",
        path: "/auth/register",
        body,
      }),
    }),

    login: builder.mutation<LoginResponse, LoginRequest>({
      query: (body) => ({
        method: "post",
        path: "/auth/login",
        body,
      }),
      onQueryStarted: async (_arg, { queryFulfilled, dispatch }) => {
        try {
          const { data } = await queryFulfilled;
          setAccessToken(data.access_token);
          // 本地登入：清掉前一輪 SSO 留下的 marker / re-auth 計數, 避免 401 走錯分支
          clearSsoLogin();
          // 防止前一位使用者的 RTK Query cache 在新登入後被沿用
          dispatch(baseApi.util.resetApiState());
        } catch {
          // 登入失敗不做額外處理
        }
      },
    }),

    logout: builder.mutation<null, void>({
      query: () => ({
        method: "post",
        path: "/auth/logout",
      }),
      onQueryStarted: async (_arg, { queryFulfilled, dispatch }) => {
        try {
          await queryFulfilled;
        } finally {
          setAccessToken(null);
          clearSsoLogin();
          dispatch(baseApi.util.resetApiState());
        }
      },
    }),

    refresh: builder.mutation<LoginResponse, void>({
      query: () => ({
        method: "post",
        path: "/auth/refresh",
      }),
      onQueryStarted: async (_arg, { queryFulfilled }) => {
        try {
          const { data } = await queryFulfilled;
          setAccessToken(data.access_token);
        } catch {
          setAccessToken(null);
        }
      },
    }),

    resetPassword: builder.mutation<null, ResetPasswordRequest>({
      query: (body) => ({
        method: "post",
        path: "/auth/reset-password",
        body,
      }),
    }),

    // DF-SSO authorize URL（避免 NEXT_PUBLIC_* 在 build 時固化；改成 runtime 從 backend 取）
    ssoAuthorizeUrl: builder.query<{ message: string }, void>({
      query: () => ({
        method: "get",
        path: "/auth/sso/authorize-url",
      }),
    }),
  }),
});

export const {
  useRegisterMutation,
  useLoginMutation,
  useLogoutMutation,
  useRefreshMutation,
  useResetPasswordMutation,
  useSsoAuthorizeUrlQuery,
} = authApi;
