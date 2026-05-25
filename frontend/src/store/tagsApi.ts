import { baseApi } from "./api";
import type {
  EntityTagsRequest,
  EntityType,
  Skill,
  Script,
  Agent,
  TagCreateResponse,
  TagDetail,
  TagListResponse,
} from "@/types";

interface ListTagsParams {
  q?: string;
}

interface RenameTagParams {
  tagUid: string;
  name: string;
}

interface SetEntityTagsParams {
  entityType: EntityType;
  entityUid: string;
  body: EntityTagsRequest;
}

type SetEntityTagsResult = Skill | Script | Agent;

const ENTITY_PATH: Record<EntityType, string> = {
  skill: "skills",
  script: "scripts",
  agent: "agents",
};

const ENTITY_TAG_CACHE: Record<EntityType, "Skills" | "Scripts" | "Agents"> = {
  skill: "Skills",
  script: "Scripts",
  agent: "Agents",
};

export const tagsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listTags: builder.query<TagListResponse, ListTagsParams | void>({
      query: (arg) => {
        const params: Record<string, string> = {};
        if (arg?.q) params.q = arg.q;
        return { method: "get", path: "/tags", params };
      },
      providesTags: (result) => [
        "Tags",
        ...(result?.items ?? []).map(
          (t) => ({ type: "Tags" as const, id: t.tag_uid })
        ),
      ],
    }),

    createTag: builder.mutation<TagCreateResponse, { name: string }>({
      query: ({ name }) => ({
        method: "post",
        path: "/tags",
        body: { name },
      }),
      invalidatesTags: ["Tags"],
    }),

    renameTag: builder.mutation<TagDetail, RenameTagParams>({
      query: ({ tagUid, name }) => ({
        method: "put",
        path: `/tags/${tagUid}`,
        body: { name },
      }),
      invalidatesTags: (_result, _error, { tagUid }) => [
        "Tags",
        { type: "Tags", id: tagUid },
        // Tag name 變了 → entity 上顯示的 tag 也得 invalidate
        "Skills",
        "Scripts",
        "Agents",
      ],
    }),

    deleteTag: builder.mutation<null, string>({
      query: (tagUid) => ({
        method: "delete",
        path: `/tags/${tagUid}`,
      }),
      invalidatesTags: ["Tags", "Skills", "Scripts", "Agents"],
    }),

    setEntityTags: builder.mutation<SetEntityTagsResult, SetEntityTagsParams>({
      query: ({ entityType, entityUid, body }) => ({
        method: "put",
        path: `/${ENTITY_PATH[entityType]}/${entityUid}/tags`,
        body,
      }),
      invalidatesTags: (_result, _error, { entityType, entityUid }) => [
        "Tags",
        ENTITY_TAG_CACHE[entityType],
        { type: ENTITY_TAG_CACHE[entityType], id: entityUid },
      ],
    }),
  }),
});

export const {
  useListTagsQuery,
  useCreateTagMutation,
  useRenameTagMutation,
  useDeleteTagMutation,
  useSetEntityTagsMutation,
} = tagsApi;
