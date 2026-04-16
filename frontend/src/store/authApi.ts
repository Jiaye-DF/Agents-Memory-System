import { baseApi } from "./api";
import { setAccessToken } from "@/lib/api/client";
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
      onQueryStarted: async (_arg, { queryFulfilled }) => {
        try {
          const { data } = await queryFulfilled;
          setAccessToken(data.access_token);
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
      onQueryStarted: async (_arg, { queryFulfilled }) => {
        try {
          await queryFulfilled;
        } finally {
          setAccessToken(null);
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
  }),
});

export const {
  useRegisterMutation,
  useLoginMutation,
  useLogoutMutation,
  useRefreshMutation,
  useResetPasswordMutation,
} = authApi;
