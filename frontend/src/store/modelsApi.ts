import { baseApi } from "./api";
import type { PaginatedData } from "@/types";
import type {
  LlmModelAdmin,
  LlmModelCreateRequest,
  LlmModelUpdateRequest,
} from "@/types";

export interface LlmModel {
  llm_model_uid: string;
  provider: string;
  model_id: string;
  display_name: string;
}

interface ListModelsResponse {
  items: LlmModel[];
}

interface ListAdminModelsParams {
  limit?: number;
  cursor?: string | null;
}

interface DeleteModelResponse {
  message: string;
}

export const modelsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listModels: builder.query<ListModelsResponse, void>({
      query: () => ({
        method: "get",
        path: "/models",
      }),
    }),

    listAdminModels: builder.query<
      PaginatedData<LlmModelAdmin>,
      ListAdminModelsParams
    >({
      query: ({ limit = 20, cursor }) => {
        const params: Record<string, string> = { limit: String(limit) };
        if (cursor) {
          params.cursor = cursor;
        }
        return {
          method: "get",
          path: "/admin/llm-models",
          params,
        };
      },
      providesTags: ["AdminLlmModels"],
    }),

    getAdminModel: builder.query<LlmModelAdmin, string>({
      query: (uid) => ({
        method: "get",
        path: `/admin/llm-models/${uid}`,
      }),
      providesTags: (_result, _error, uid) => [
        { type: "AdminLlmModels", id: uid },
      ],
    }),

    createModel: builder.mutation<LlmModelAdmin, LlmModelCreateRequest>({
      query: (body) => ({
        method: "post",
        path: "/admin/llm-models",
        body,
      }),
      invalidatesTags: ["AdminLlmModels"],
    }),

    updateModel: builder.mutation<
      LlmModelAdmin,
      { uid: string; body: LlmModelUpdateRequest }
    >({
      query: ({ uid, body }) => ({
        method: "put",
        path: `/admin/llm-models/${uid}`,
        body,
      }),
      invalidatesTags: ["AdminLlmModels"],
    }),

    deleteModel: builder.mutation<DeleteModelResponse, string>({
      query: (uid) => ({
        method: "delete",
        path: `/admin/llm-models/${uid}`,
      }),
      invalidatesTags: ["AdminLlmModels"],
    }),
  }),
});

export const {
  useListModelsQuery,
  useListAdminModelsQuery,
  useGetAdminModelQuery,
  useCreateModelMutation,
  useUpdateModelMutation,
  useDeleteModelMutation,
} = modelsApi;
