import { baseApi } from "./api";
import type { PaginatedData } from "@/types";
import type {
  AgentLanguage,
  AgentLanguageCreateRequest,
  AgentLanguageUpdateRequest,
} from "@/types";

interface ListAgentLanguagesResponse {
  items: AgentLanguage[];
}

interface ListAdminAgentLanguagesParams {
  limit?: number;
  cursor?: string | null;
}

interface DeleteAgentLanguageResponse {
  message: string;
}

export const agentLanguagesApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listAgentLanguages: builder.query<ListAgentLanguagesResponse, void>({
      query: () => ({
        method: "get",
        path: "/agent-languages",
      }),
      providesTags: ["AgentLanguages"],
    }),

    listAdminAgentLanguages: builder.query<
      PaginatedData<AgentLanguage>,
      ListAdminAgentLanguagesParams
    >({
      query: ({ limit = 20, cursor }) => {
        const params: Record<string, string> = { limit: String(limit) };
        if (cursor) {
          params.cursor = cursor;
        }
        return {
          method: "get",
          path: "/admin/agent-languages",
          params,
        };
      },
      providesTags: ["AdminAgentLanguages"],
    }),

    getAdminAgentLanguage: builder.query<AgentLanguage, string>({
      query: (uid) => ({
        method: "get",
        path: `/admin/agent-languages/${uid}`,
      }),
      providesTags: (_result, _error, uid) => [
        { type: "AdminAgentLanguages", id: uid },
      ],
    }),

    createAgentLanguage: builder.mutation<
      AgentLanguage,
      AgentLanguageCreateRequest
    >({
      query: (body) => ({
        method: "post",
        path: "/admin/agent-languages",
        body,
      }),
      invalidatesTags: ["AgentLanguages", "AdminAgentLanguages"],
    }),

    updateAgentLanguage: builder.mutation<
      AgentLanguage,
      { uid: string; body: AgentLanguageUpdateRequest }
    >({
      query: ({ uid, body }) => ({
        method: "put",
        path: `/admin/agent-languages/${uid}`,
        body,
      }),
      invalidatesTags: ["AgentLanguages", "AdminAgentLanguages"],
    }),

    deleteAgentLanguage: builder.mutation<DeleteAgentLanguageResponse, string>({
      query: (uid) => ({
        method: "delete",
        path: `/admin/agent-languages/${uid}`,
      }),
      invalidatesTags: ["AgentLanguages", "AdminAgentLanguages"],
    }),
  }),
});

export const {
  useListAgentLanguagesQuery,
  useListAdminAgentLanguagesQuery,
  useGetAdminAgentLanguageQuery,
  useCreateAgentLanguageMutation,
  useUpdateAgentLanguageMutation,
  useDeleteAgentLanguageMutation,
} = agentLanguagesApi;
