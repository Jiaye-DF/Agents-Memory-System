/**
 * v1.3.6 Agentic Skill 工廠正式版 RTK Query 端點。
 *
 * - useListSkillSuggestionsQuery：個人列表（三 scope）
 * - useGetSkillSuggestionQuery：詳情含來源記憶 inline 摘要
 * - useListAgentSkillSuggestionsQuery：Agent 入口推薦清單
 * - useAcceptSkillSuggestionMutation / useRejectSkillSuggestionMutation：個人視角接受 / 拒絕
 * - useAcceptAgentSkillSuggestionMutation / useRejectAgentSkillSuggestionMutation：Agent 入口
 *
 * tag 設計：
 *   - AgenticSkillSuggestions：個人列表（每筆以 uid 細粒度標記，便於樂觀更新）
 *   - AgentSkillSuggestions：以 agent_uid 為 id 的推薦清單
 *   accept / reject 同步 invalidate 對應 tag + Skills + Agents-{agentUid}
 */

import { baseApi } from "./api";
import type {
  AgenticSkillSuggestionAcceptResponse,
  AgenticSkillSuggestionDetailResponse,
  AgenticSkillSuggestionListResponse,
  AgenticSkillSuggestionRejectResponse,
  AgenticSuggestionScope,
  AgenticSuggestionStatus,
  RecommendSuggestionListResponse,
} from "@/types";

interface ListSkillSuggestionsParams {
  scope?: AgenticSuggestionScope;
  status?: AgenticSuggestionStatus | "all";
  page?: number;
  size?: number;
}

interface GetSkillSuggestionParams {
  uid: string;
}

interface ListAgentSkillSuggestionsParams {
  agentUid: string;
}

interface AcceptSkillSuggestionParams {
  uid: string;
  agentUid?: string | null;
}

interface RejectSkillSuggestionParams {
  uid: string;
}

interface AcceptAgentSkillSuggestionParams {
  agentUid: string;
  suggestionUid: string;
}

interface RejectAgentSkillSuggestionParams {
  agentUid: string;
  suggestionUid: string;
}

export const agenticApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listSkillSuggestions: builder.query<
      AgenticSkillSuggestionListResponse,
      ListSkillSuggestionsParams | void
    >({
      query: (args) => {
        const { scope, status, page = 1, size = 20 } = args ?? {};
        const params: Record<string, string> = {
          page: String(page),
          size: String(size),
        };
        if (scope) params.scope = scope;
        if (status) params.status = status;
        return {
          method: "get",
          path: "/skill-suggestions",
          params,
        };
      },
      providesTags: (result) =>
        result
          ? [
              { type: "AgenticSkillSuggestions" as const, id: "LIST" },
              ...result.items.map((it) => ({
                type: "AgenticSkillSuggestions" as const,
                id: it.uid,
              })),
            ]
          : [{ type: "AgenticSkillSuggestions" as const, id: "LIST" }],
    }),

    getSkillSuggestion: builder.query<
      AgenticSkillSuggestionDetailResponse,
      GetSkillSuggestionParams
    >({
      query: ({ uid }) => ({
        method: "get",
        path: `/skill-suggestions/${uid}`,
      }),
      providesTags: (_result, _error, { uid }) => [
        { type: "AgenticSkillSuggestions", id: uid },
      ],
    }),

    listAgentSkillSuggestions: builder.query<
      RecommendSuggestionListResponse,
      ListAgentSkillSuggestionsParams
    >({
      query: ({ agentUid }) => ({
        method: "get",
        path: `/agents/${agentUid}/skill-suggestions`,
      }),
      providesTags: (_result, _error, { agentUid }) => [
        { type: "AgentSkillSuggestions", id: agentUid },
      ],
    }),

    acceptSkillSuggestion: builder.mutation<
      AgenticSkillSuggestionAcceptResponse,
      AcceptSkillSuggestionParams
    >({
      query: ({ uid, agentUid }) => ({
        method: "post",
        path: `/skill-suggestions/${uid}/accept`,
        body: { agent_uid: agentUid ?? null },
      }),
      invalidatesTags: (_result, _error, { uid, agentUid }) => {
        const tags: Array<
          | { type: "AgenticSkillSuggestions"; id: string }
          | { type: "AgentSkillSuggestions"; id: string }
          | "Skills"
          | "Agents"
        > = [
          { type: "AgenticSkillSuggestions", id: uid },
          { type: "AgenticSkillSuggestions", id: "LIST" },
          "Skills",
          "Agents",
        ];
        if (agentUid) {
          tags.push({ type: "AgentSkillSuggestions", id: agentUid });
        }
        return tags;
      },
    }),

    rejectSkillSuggestion: builder.mutation<
      AgenticSkillSuggestionRejectResponse,
      RejectSkillSuggestionParams
    >({
      query: ({ uid }) => ({
        method: "post",
        path: `/skill-suggestions/${uid}/reject`,
      }),
      invalidatesTags: (_result, _error, { uid }) => [
        { type: "AgenticSkillSuggestions", id: uid },
        { type: "AgenticSkillSuggestions", id: "LIST" },
      ],
    }),

    acceptAgentSkillSuggestion: builder.mutation<
      AgenticSkillSuggestionAcceptResponse,
      AcceptAgentSkillSuggestionParams
    >({
      query: ({ agentUid, suggestionUid }) => ({
        method: "post",
        path: `/agents/${agentUid}/skill-suggestions/${suggestionUid}/accept`,
      }),
      invalidatesTags: (_result, _error, { agentUid, suggestionUid }) => [
        { type: "AgentSkillSuggestions", id: agentUid },
        { type: "AgenticSkillSuggestions", id: suggestionUid },
        { type: "AgenticSkillSuggestions", id: "LIST" },
        "Skills",
        "Agents",
      ],
    }),

    rejectAgentSkillSuggestion: builder.mutation<
      AgenticSkillSuggestionRejectResponse,
      RejectAgentSkillSuggestionParams
    >({
      query: ({ agentUid, suggestionUid }) => ({
        method: "post",
        path: `/agents/${agentUid}/skill-suggestions/${suggestionUid}/reject`,
      }),
      invalidatesTags: (_result, _error, { agentUid, suggestionUid }) => [
        { type: "AgentSkillSuggestions", id: agentUid },
        { type: "AgenticSkillSuggestions", id: suggestionUid },
        { type: "AgenticSkillSuggestions", id: "LIST" },
      ],
    }),
  }),
});

export const {
  useListSkillSuggestionsQuery,
  useGetSkillSuggestionQuery,
  useListAgentSkillSuggestionsQuery,
  useAcceptSkillSuggestionMutation,
  useRejectSkillSuggestionMutation,
  useAcceptAgentSkillSuggestionMutation,
  useRejectAgentSkillSuggestionMutation,
} = agenticApi;
