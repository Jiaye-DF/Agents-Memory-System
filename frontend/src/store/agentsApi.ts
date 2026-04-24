import { baseApi } from "./api";
import type { PaginatedData } from "@/types";
import type {
  Agent,
  AgentCreateRequest,
  AgentUpdateRequest,
  VisibilityRequest,
} from "@/types";

interface ListAgentsParams {
  limit?: number;
  cursor?: string | null;
  orderBy?: "favorite_count" | "download_count" | "created_at" | "updated_at";
  order?: "asc" | "desc";
}

export const agentsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listAgents: builder.query<PaginatedData<Agent>, ListAgentsParams>({
      query: ({ limit = 20, cursor, orderBy, order }) => {
        const params: Record<string, string> = { limit: String(limit) };
        if (cursor) {
          params.cursor = cursor;
        }
        if (orderBy) params.order_by = orderBy;
        if (order) params.order = order;
        return {
          method: "get",
          path: "/agents",
          params,
        };
      },
      providesTags: (result) => [
        "Agents",
        ...(result?.items ?? []).map(
          (a) => ({ type: "Agents" as const, id: a.agent_uid })
        ),
      ],
    }),

    getAgent: builder.query<Agent, string>({
      query: (agentUid) => ({
        method: "get",
        path: `/agents/${agentUid}`,
      }),
      providesTags: (_result, _error, agentUid) => [
        { type: "Agents", id: agentUid },
      ],
    }),

    createAgent: builder.mutation<Agent, AgentCreateRequest>({
      query: (body) => ({
        method: "post",
        path: "/agents",
        body,
      }),
      invalidatesTags: ["Agents"],
    }),

    updateAgent: builder.mutation<
      Agent,
      { agentUid: string; body: AgentUpdateRequest }
    >({
      query: ({ agentUid, body }) => ({
        method: "put",
        path: `/agents/${agentUid}`,
        body,
      }),
      invalidatesTags: ["Agents"],
    }),

    deleteAgent: builder.mutation<null, string>({
      query: (agentUid) => ({
        method: "delete",
        path: `/agents/${agentUid}`,
      }),
      invalidatesTags: ["Agents"],
    }),

    toggleAgentVisibility: builder.mutation<
      Agent,
      { agentUid: string; body: VisibilityRequest }
    >({
      query: ({ agentUid, body }) => ({
        method: "patch",
        path: `/agents/${agentUid}/visibility`,
        body,
      }),
      invalidatesTags: ["Agents"],
    }),

    downloadAgent: builder.query<string, string>({
      queryFn: async (agentUid) => {
        try {
          const { downloadText } = await import("@/lib/api/download");
          const result = await downloadText(`/agents/${agentUid}/download`);
          if (!result.ok || result.text === undefined) {
            return { error: "下載失敗" };
          }
          return { data: result.text };
        } catch {
          return { error: "下載失敗" };
        }
      },
    }),
  }),
});

export const {
  useListAgentsQuery,
  useGetAgentQuery,
  useCreateAgentMutation,
  useUpdateAgentMutation,
  useDeleteAgentMutation,
  useToggleAgentVisibilityMutation,
  useLazyDownloadAgentQuery,
} = agentsApi;
