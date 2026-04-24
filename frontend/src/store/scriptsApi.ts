import { baseApi } from "./api";
import type { PaginatedData } from "@/types";
import type {
  Script,
  ScriptCreateParams,
  ScriptUpdateRequest,
} from "@/types";

interface ListScriptsParams {
  limit?: number;
  cursor?: string | null;
  orderBy?: "favorite_count" | "download_count" | "created_at" | "updated_at";
  order?: "asc" | "desc";
}

export const scriptsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listScripts: builder.query<PaginatedData<Script>, ListScriptsParams>({
      query: ({ limit = 20, cursor, orderBy, order }) => {
        const params: Record<string, string> = { limit: String(limit) };
        if (cursor) params.cursor = cursor;
        if (orderBy) params.order_by = orderBy;
        if (order) params.order = order;
        return {
          method: "get",
          path: "/scripts",
          params,
        };
      },
      providesTags: (result) => [
        "Scripts",
        ...(result?.items ?? []).map(
          (s) => ({ type: "Scripts" as const, id: s.script_uid })
        ),
      ],
    }),

    getScript: builder.query<Script, string>({
      query: (scriptUid) => ({
        method: "get",
        path: `/scripts/${scriptUid}`,
      }),
      providesTags: (_result, _error, scriptUid) => [
        { type: "Scripts", id: scriptUid },
      ],
    }),

    createScript: builder.mutation<Script, ScriptCreateParams>({
      query: ({ name, description, files, relativePaths }) => {
        const formData = new FormData();
        formData.append("name", name);
        if (description !== undefined && description !== null) {
          formData.append("description", description);
        }
        for (let i = 0; i < files.length; i += 1) {
          const f = files[i];
          formData.append("files", f, f.name);
          formData.append(
            "relative_paths",
            relativePaths[i] ?? f.name
          );
        }
        return {
          method: "post",
          path: "/scripts",
          formData,
        };
      },
      invalidatesTags: ["Scripts"],
    }),

    updateScript: builder.mutation<
      Script,
      { scriptUid: string; body: ScriptUpdateRequest }
    >({
      query: ({ scriptUid, body }) => ({
        method: "patch",
        path: `/scripts/${scriptUid}`,
        body,
      }),
      invalidatesTags: (_result, _error, { scriptUid }) => [
        "Scripts",
        { type: "Scripts", id: scriptUid },
      ],
    }),

    deleteScript: builder.mutation<null, string>({
      query: (scriptUid) => ({
        method: "delete",
        path: `/scripts/${scriptUid}`,
      }),
      invalidatesTags: ["Scripts"],
    }),
  }),
});

export const {
  useListScriptsQuery,
  useGetScriptQuery,
  useCreateScriptMutation,
  useUpdateScriptMutation,
  useDeleteScriptMutation,
} = scriptsApi;
