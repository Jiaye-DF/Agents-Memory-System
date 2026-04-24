import { baseApi } from "./api";
import type {
  RankingOrderBy,
  RankingResponse,
  RankingTypeFilter,
} from "@/types";

interface GetRankingsParams {
  type: RankingTypeFilter;
  orderBy: RankingOrderBy;
  limit?: number;
}

export const dashboardApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getRankings: builder.query<RankingResponse, GetRankingsParams>({
      query: ({ type, orderBy, limit }) => {
        const params: Record<string, string> = {
          type,
          order_by: orderBy,
        };
        if (limit !== undefined) {
          params.limit = String(limit);
        }
        return {
          method: "get",
          path: "/dashboard/rankings",
          params,
        };
      },
      providesTags: (_result, _error, arg) => [
        { type: "Rankings", id: `${arg.type}:${arg.orderBy}` },
        "Rankings",
      ],
    }),
  }),
});

export const { useGetRankingsQuery } = dashboardApi;
