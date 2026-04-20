import { baseApi } from "./api";
import type { PaginatedData } from "@/types";
import type {
  AgentTemplate,
  AgentTemplateCreateRequest,
  AgentTemplateUpdateRequest,
} from "@/types";

interface ListAgentTemplatesResponse {
  items: AgentTemplate[];
}

interface ListAdminAgentTemplatesParams {
  limit?: number;
  cursor?: string | null;
}

interface DeleteAgentTemplateResponse {
  message: string;
}

export const agentTemplatesApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listAgentTemplates: builder.query<ListAgentTemplatesResponse, void>({
      query: () => ({
        method: "get",
        path: "/agent-templates",
      }),
      providesTags: ["AgentTemplates"],
    }),

    listAdminAgentTemplates: builder.query<
      PaginatedData<AgentTemplate>,
      ListAdminAgentTemplatesParams
    >({
      query: ({ limit = 20, cursor }) => {
        const params: Record<string, string> = { limit: String(limit) };
        if (cursor) {
          params.cursor = cursor;
        }
        return {
          method: "get",
          path: "/admin/agent-templates",
          params,
        };
      },
      providesTags: ["AdminAgentTemplates"],
    }),

    getAdminAgentTemplate: builder.query<AgentTemplate, string>({
      query: (uid) => ({
        method: "get",
        path: `/admin/agent-templates/${uid}`,
      }),
      providesTags: (_result, _error, uid) => [
        { type: "AdminAgentTemplates", id: uid },
      ],
    }),

    createAgentTemplate: builder.mutation<
      AgentTemplate,
      AgentTemplateCreateRequest
    >({
      query: (body) => ({
        method: "post",
        path: "/admin/agent-templates",
        body,
      }),
      invalidatesTags: ["AgentTemplates", "AdminAgentTemplates"],
    }),

    updateAgentTemplate: builder.mutation<
      AgentTemplate,
      { uid: string; body: AgentTemplateUpdateRequest }
    >({
      query: ({ uid, body }) => ({
        method: "put",
        path: `/admin/agent-templates/${uid}`,
        body,
      }),
      invalidatesTags: ["AgentTemplates", "AdminAgentTemplates"],
    }),

    deleteAgentTemplate: builder.mutation<DeleteAgentTemplateResponse, string>({
      query: (uid) => ({
        method: "delete",
        path: `/admin/agent-templates/${uid}`,
      }),
      invalidatesTags: ["AgentTemplates", "AdminAgentTemplates"],
    }),
  }),
});

export const {
  useListAgentTemplatesQuery,
  useListAdminAgentTemplatesQuery,
  useGetAdminAgentTemplateQuery,
  useCreateAgentTemplateMutation,
  useUpdateAgentTemplateMutation,
  useDeleteAgentTemplateMutation,
} = agentTemplatesApi;
