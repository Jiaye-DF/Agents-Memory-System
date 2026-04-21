import { baseApi } from "./api";
import type { PaginatedData } from "@/types";
import type {
  ChatProject,
  ChatProjectCreateRequest,
  ChatProjectUpdateRequest,
  ChatSession,
  ChatSessionCreateRequest,
  ChatSessionMoveRequest,
  ChatSessionUpdateRequest,
  ChatMessage,
  ChatMemory,
} from "@/types";

interface ListProjectsParams {
  limit?: number;
  cursor?: string | null;
}

interface ListSessionsParams {
  projectUid: string;
  limit?: number;
  cursor?: string | null;
}

interface ListOrphanSessionsParams {
  limit?: number;
  cursor?: string | null;
}

interface ListMessagesParams {
  sessionUid: string;
  limit?: number;
  cursor?: string | null;
}

interface ListSessionMemoriesParams {
  sessionUid: string;
}

interface SessionMemoriesData {
  items: ChatMemory[];
}

export const chatApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // ===== ChatProject =====
    listProjects: builder.query<PaginatedData<ChatProject>, ListProjectsParams>({
      query: ({ limit = 20, cursor } = {}) => {
        const params: Record<string, string> = { limit: String(limit) };
        if (cursor) {
          params.cursor = cursor;
        }
        return {
          method: "get",
          path: "/chat/projects",
          params,
        };
      },
      providesTags: ["ChatProjects"],
    }),

    getProject: builder.query<ChatProject, string>({
      query: (projectUid) => ({
        method: "get",
        path: `/chat/projects/${projectUid}`,
      }),
      providesTags: (_result, _error, projectUid) => [
        { type: "ChatProjects", id: projectUid },
      ],
    }),

    createProject: builder.mutation<ChatProject, ChatProjectCreateRequest>({
      query: (body) => ({
        method: "post",
        path: "/chat/projects",
        body,
      }),
      invalidatesTags: ["ChatProjects"],
    }),

    updateProject: builder.mutation<
      ChatProject,
      { projectUid: string; body: ChatProjectUpdateRequest }
    >({
      query: ({ projectUid, body }) => ({
        method: "put",
        path: `/chat/projects/${projectUid}`,
        body,
      }),
      invalidatesTags: ["ChatProjects"],
    }),

    deleteProject: builder.mutation<null, string>({
      query: (projectUid) => ({
        method: "delete",
        path: `/chat/projects/${projectUid}`,
      }),
      invalidatesTags: ["ChatProjects"],
    }),

    // ===== ChatSession =====
    listSessions: builder.query<PaginatedData<ChatSession>, ListSessionsParams>({
      query: ({ projectUid, limit = 20, cursor }) => {
        const params: Record<string, string> = { limit: String(limit) };
        if (cursor) {
          params.cursor = cursor;
        }
        return {
          method: "get",
          path: `/chat/projects/${projectUid}/sessions`,
          params,
        };
      },
      providesTags: ["ChatSessions"],
    }),

    getSession: builder.query<ChatSession, string>({
      query: (sessionUid) => ({
        method: "get",
        path: `/chat/sessions/${sessionUid}`,
      }),
      providesTags: (_result, _error, sessionUid) => [
        { type: "ChatSessions", id: sessionUid },
      ],
    }),

    listOrphanChatSessions: builder.query<
      PaginatedData<ChatSession>,
      ListOrphanSessionsParams
    >({
      query: ({ limit = 20, cursor } = {}) => {
        const params: Record<string, string> = {
          limit: String(limit),
          orphan: "true",
        };
        if (cursor) {
          params.cursor = cursor;
        }
        return {
          method: "get",
          path: "/chat/sessions",
          params,
        };
      },
      providesTags: ["OrphanChatSessions"],
    }),

    createSession: builder.mutation<ChatSession, ChatSessionCreateRequest>({
      query: (body) => ({
        method: "post",
        path: "/chat/sessions",
        body,
      }),
      invalidatesTags: [
        "ChatSessions",
        "OrphanChatSessions",
        "ChatProjects",
      ],
    }),

    moveChatSession: builder.mutation<
      ChatSession,
      { sessionUid: string; body: ChatSessionMoveRequest }
    >({
      query: ({ sessionUid, body }) => ({
        method: "post",
        path: `/chat/sessions/${sessionUid}/move`,
        body,
      }),
      invalidatesTags: [
        "ChatSessions",
        "OrphanChatSessions",
        "ChatProjects",
      ],
    }),

    updateSession: builder.mutation<
      ChatSession,
      { sessionUid: string; body: ChatSessionUpdateRequest }
    >({
      query: ({ sessionUid, body }) => ({
        method: "put",
        path: `/chat/sessions/${sessionUid}`,
        body,
      }),
      invalidatesTags: ["ChatSessions", "OrphanChatSessions"],
    }),

    deleteSession: builder.mutation<null, string>({
      query: (sessionUid) => ({
        method: "delete",
        path: `/chat/sessions/${sessionUid}`,
      }),
      invalidatesTags: [
        "ChatSessions",
        "OrphanChatSessions",
        "ChatProjects",
      ],
    }),

    // ===== ChatMessage（只有 list，送訊息走 SSE 不走 RTK Query） =====
    listMessages: builder.query<PaginatedData<ChatMessage>, ListMessagesParams>({
      query: ({ sessionUid, limit = 50, cursor }) => {
        const params: Record<string, string> = { limit: String(limit) };
        if (cursor) {
          params.cursor = cursor;
        }
        return {
          method: "get",
          path: `/chat/sessions/${sessionUid}/messages`,
          params,
        };
      },
      providesTags: ["ChatMessages"],
    }),

    // ===== ChatMemory =====
    listSessionMemories: builder.query<
      SessionMemoriesData,
      ListSessionMemoriesParams
    >({
      query: ({ sessionUid }) => ({
        method: "get",
        path: `/chat/sessions/${sessionUid}/memories`,
      }),
      providesTags: (_result, _error, { sessionUid }) => [
        { type: "ChatMessages", id: `memories-${sessionUid}` },
      ],
    }),
  }),
});

export const {
  useListProjectsQuery,
  useGetProjectQuery,
  useCreateProjectMutation,
  useUpdateProjectMutation,
  useDeleteProjectMutation,
  useListSessionsQuery,
  useListOrphanChatSessionsQuery,
  useGetSessionQuery,
  useCreateSessionMutation,
  useUpdateSessionMutation,
  useDeleteSessionMutation,
  useMoveChatSessionMutation,
  useListMessagesQuery,
  useListSessionMemoriesQuery,
} = chatApi;
