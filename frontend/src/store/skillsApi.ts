import { baseApi } from "./api";
import type { PaginatedData } from "@/types";
import type {
  Skill,
  SkillUpdateRequest,
  VisibilityRequest,
  FileTreeNode,
  FileContent,
  SkillUploadParams,
  SkillUsageResponse,
  SkillReuploadParams,
  SkillFileUpdateParams,
  SkillFileUpdateResult,
} from "@/types";

interface ListSkillsParams {
  limit?: number;
  cursor?: string | null;
  orderBy?: "favorite_count" | "download_count" | "created_at" | "updated_at";
  order?: "asc" | "desc";
}

interface FileTreeResponse {
  tree: FileTreeNode[];
}

export const skillsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listSkills: builder.query<PaginatedData<Skill>, ListSkillsParams>({
      query: ({ limit = 20, cursor, orderBy, order }) => {
        const params: Record<string, string> = { limit: String(limit) };
        if (cursor) {
          params.cursor = cursor;
        }
        if (orderBy) params.order_by = orderBy;
        if (order) params.order = order;
        return {
          method: "get",
          path: "/skills",
          params,
        };
      },
      providesTags: (result) => [
        "Skills",
        ...(result?.items ?? []).map(
          (s) => ({ type: "Skills" as const, id: s.skill_uid })
        ),
      ],
    }),

    getSkill: builder.query<Skill, string>({
      query: (skillUid) => ({
        method: "get",
        path: `/skills/${skillUid}`,
      }),
      providesTags: (_result, _error, skillUid) => [
        { type: "Skills", id: skillUid },
      ],
    }),

    uploadSkill: builder.mutation<Skill, SkillUploadParams>({
      query: ({ name, description, files }) => {
        const formData = new FormData();
        formData.append("name", name);
        formData.append("description", description);
        for (const f of files) {
          const relative = (f as File & { webkitRelativePath?: string })
            .webkitRelativePath;
          formData.append("files", f, relative && relative.length > 0 ? relative : f.name);
        }
        return {
          method: "post",
          path: "/skills",
          formData,
        };
      },
      invalidatesTags: ["Skills"],
    }),

    updateSkill: builder.mutation<
      Skill,
      { skillUid: string; body: SkillUpdateRequest }
    >({
      query: ({ skillUid, body }) => ({
        method: "put",
        path: `/skills/${skillUid}`,
        body,
      }),
      invalidatesTags: ["Skills"],
    }),

    deleteSkill: builder.mutation<null, string>({
      query: (skillUid) => ({
        method: "delete",
        path: `/skills/${skillUid}`,
      }),
      invalidatesTags: ["Skills"],
    }),

    toggleSkillVisibility: builder.mutation<
      Skill,
      { skillUid: string; body: VisibilityRequest }
    >({
      query: ({ skillUid, body }) => ({
        method: "patch",
        path: `/skills/${skillUid}/visibility`,
        body,
      }),
      invalidatesTags: ["Skills"],
    }),

    getFileTree: builder.query<FileTreeResponse, string>({
      query: (skillUid) => ({
        method: "get",
        path: `/skills/${skillUid}/tree`,
      }),
    }),

    getFileContent: builder.query<
      FileContent,
      { skillUid: string; path: string }
    >({
      query: ({ skillUid, path }) => ({
        method: "get",
        path: `/skills/${skillUid}/file`,
        params: { path },
      }),
      providesTags: (_result, _error, { skillUid, path }) => [
        { type: "Skills", id: `${skillUid}:${path}` },
      ],
    }),

    getSkillUsage: builder.query<SkillUsageResponse, string>({
      query: (skillUid) => ({
        method: "get",
        path: `/skills/${skillUid}/usage`,
      }),
      providesTags: (_result, _error, skillUid) => [
        { type: "Skills", id: `usage:${skillUid}` },
      ],
    }),

    reuploadSkill: builder.mutation<Skill, SkillReuploadParams>({
      query: ({ skillUid, files, expectedUpdatedAt }) => {
        const formData = new FormData();
        formData.append("expected_updated_at", expectedUpdatedAt);
        for (const f of files) {
          const relative = (f as File & { webkitRelativePath?: string })
            .webkitRelativePath;
          formData.append(
            "files",
            f,
            relative && relative.length > 0 ? relative : f.name
          );
        }
        return {
          method: "post",
          path: `/skills/${skillUid}/reupload`,
          formData,
        };
      },
      invalidatesTags: (_result, _error, { skillUid }) => [
        "Skills",
        { type: "Skills", id: skillUid },
      ],
    }),

    updateSkillFile: builder.mutation<
      SkillFileUpdateResult,
      SkillFileUpdateParams
    >({
      query: ({ skillUid, path, body }) => ({
        method: "put",
        path: `/skills/${skillUid}/file`,
        params: { path },
        body,
      }),
      invalidatesTags: (_result, _error, { skillUid, path }) => [
        "Skills",
        { type: "Skills", id: skillUid },
        { type: "Skills", id: `${skillUid}:${path}` },
      ],
    }),
  }),
});

export const {
  useListSkillsQuery,
  useGetSkillQuery,
  useUploadSkillMutation,
  useUpdateSkillMutation,
  useDeleteSkillMutation,
  useToggleSkillVisibilityMutation,
  useGetFileTreeQuery,
  useGetFileContentQuery,
  useGetSkillUsageQuery,
  useReuploadSkillMutation,
  useUpdateSkillFileMutation,
} = skillsApi;
