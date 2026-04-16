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
}

export const agentsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listAgents: builder.query<PaginatedData<Agent>, ListAgentsParams>({
      query: ({ limit = 20, cursor }) => {
        const params: Record<string, string> = { limit: String(limit) };
        if (cursor) {
          params.cursor = cursor;
        }
        return {
          method: "get",
          path: "/agents",
          params,
        };
      },
      providesTags: ["Agents"],
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
          const { getAccessToken } = await import("@/lib/api/client");
          const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "";
          const token = getAccessToken();
          const headers: Record<string, string> = {};
          if (token) {
            headers["Authorization"] = `Bearer ${token}`;
          }
          const response = await fetch(
            `${baseUrl}/agents/${agentUid}/download`,
            { headers, credentials: "include" }
          );
          if (!response.ok) {
            return { error: "下載失敗" };
          }
          const text = await response.text();
          return { data: text };
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
