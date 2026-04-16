import { baseApi } from "./api";
import type { PaginatedData } from "@/types";
import type { User, Role, UpdateUserRequest } from "@/types";

interface ListUsersParams {
  limit?: number;
  cursor?: string | null;
}

export const adminApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listUsers: builder.query<PaginatedData<User>, ListUsersParams>({
      query: ({ limit = 20, cursor }) => {
        const params: Record<string, string> = { limit: String(limit) };
        if (cursor) {
          params.cursor = cursor;
        }
        return {
          method: "get",
          path: "/admin/users",
          params,
        };
      },
      providesTags: ["Users"],
    }),

    getUser: builder.query<User, string>({
      query: (userUid) => ({
        method: "get",
        path: `/admin/users/${userUid}`,
      }),
      providesTags: (_result, _error, userUid) => [
        { type: "Users", id: userUid },
      ],
    }),

    updateUser: builder.mutation<
      User,
      { userUid: string; body: UpdateUserRequest }
    >({
      query: ({ userUid, body }) => ({
        method: "put",
        path: `/admin/users/${userUid}`,
        body,
      }),
      invalidatesTags: ["Users"],
    }),

    listRoles: builder.query<{ roles: Role[] }, void>({
      query: () => ({
        method: "get",
        path: "/admin/roles",
      }),
    }),
  }),
});

export const {
  useListUsersQuery,
  useGetUserQuery,
  useUpdateUserMutation,
  useListRolesQuery,
} = adminApi;
