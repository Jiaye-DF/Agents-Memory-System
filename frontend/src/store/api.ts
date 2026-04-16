import { createApi, fakeBaseQuery } from "@reduxjs/toolkit/query/react";
import { apiClient } from "@/lib/api/client";
import type { ApiResponse } from "@/types/api";

interface BaseQueryArgs {
  method: "get" | "post" | "put" | "patch" | "delete";
  path: string;
  body?: unknown;
  params?: Record<string, string>;
  formData?: FormData;
}

const customBaseQuery = fakeBaseQuery<string>();

export const baseApi = createApi({
  reducerPath: "api",
  baseQuery: async (args: BaseQueryArgs) => {
    try {
      const result: ApiResponse<unknown> = await apiClient[args.method](
        args.path,
        {
          body: args.body,
          params: args.params,
          formData: args.formData,
        }
      );

      if (result.success) {
        return { data: result.data };
      }

      return {
        error: result.detail ?? "發生未知錯誤",
      };
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : "網路連線異常";
      return { error: message };
    }
  },
  tagTypes: ["Users", "Agents", "Skills"],
  endpoints: () => ({}),
});

void customBaseQuery;
