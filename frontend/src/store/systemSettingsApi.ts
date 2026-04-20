import { baseApi } from "./api";
import type {
  PublicSettings,
  SystemSetting,
  SystemSettingUpdateRequest,
} from "@/types";

interface ListAdminSettingsResponse {
  items: SystemSetting[];
}

export const systemSettingsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getPublicSettings: builder.query<PublicSettings, void>({
      query: () => ({
        method: "get",
        path: "/settings/public",
      }),
      providesTags: ["PublicSettings"],
    }),

    listAdminSettings: builder.query<ListAdminSettingsResponse, void>({
      query: () => ({
        method: "get",
        path: "/admin/settings",
      }),
      providesTags: ["AdminSettings"],
    }),

    updateSetting: builder.mutation<
      SystemSetting,
      { key: string; body: SystemSettingUpdateRequest }
    >({
      query: ({ key, body }) => ({
        method: "put",
        path: `/admin/settings/${key}`,
        body,
      }),
      invalidatesTags: ["AdminSettings", "PublicSettings"],
    }),
  }),
});

export const {
  useGetPublicSettingsQuery,
  useListAdminSettingsQuery,
  useUpdateSettingMutation,
} = systemSettingsApi;
