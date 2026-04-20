import { baseApi } from "./api";
import type { PaginatedData } from "@/types";
import type {
  Skill,
  SkillUpdateRequest,
  VisibilityRequest,
  FileTreeNode,
  FileContent,
  SkillUploadParams,
} from "@/types";

interface ListSkillsParams {
  limit?: number;
  cursor?: string | null;
}

interface FileTreeResponse {
  tree: FileTreeNode[];
}

export const skillsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listSkills: builder.query<PaginatedData<Skill>, ListSkillsParams>({
      query: ({ limit = 20, cursor }) => {
        const params: Record<string, string> = { limit: String(limit) };
        if (cursor) {
          params.cursor = cursor;
        }
        return {
          method: "get",
          path: "/skills",
          params,
        };
      },
      providesTags: ["Skills"],
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
      query: ({ name, description, file }) => {
        const formData = new FormData();
        formData.append("name", name);
        formData.append("description", description);
        formData.append("file", file);
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
} = skillsApi;
