import { baseApi } from "./api";
import { agentsApi } from "./agentsApi";
import { skillsApi } from "./skillsApi";
import type {
  FavoriteToggleResponse,
  MyFavoritesResponse,
  ResourceType,
} from "@/types";

interface FavoriteMutationArg {
  resourceType: ResourceType;
  resourceUid: string;
}

interface ListMyFavoritesArg {
  type: ResourceType;
  page?: number;
  size?: number;
}

function resourcePath(resourceType: ResourceType): string {
  if (resourceType === "agent") return "agents";
  if (resourceType === "skill") return "skills";
  return "scripts";
}

/**
 * 對 `agentsApi.listAgents` / `skillsApi.listSkills` 的快取做樂觀 patch，
 * 將對應 uid 的 `is_favorited` / `favorite_count` 直接寫入，失敗則由呼叫端 undo。
 */
function patchListCache(
  dispatch: (action: unknown) => unknown,
  getState: () => unknown,
  resourceType: ResourceType,
  resourceUid: string,
  favorited: boolean
): { undo: () => void }[] {
  const patches: { undo: () => void }[] = [];
  if (resourceType === "agent") {
    const entries = agentsApi.util.selectInvalidatedBy(
      getState() as never,
      ["Agents"]
    );
    for (const entry of entries) {
      if (entry.endpointName !== "listAgents") continue;
      const patch = dispatch(
        agentsApi.util.updateQueryData(
          "listAgents",
          entry.originalArgs as never,
          (draft) => {
            for (const item of draft.items) {
              if (item.agent_uid === resourceUid) {
                const wasFavorited = item.is_favorited;
                item.is_favorited = favorited;
                if (favorited && !wasFavorited) {
                  item.favorite_count += 1;
                } else if (!favorited && wasFavorited) {
                  item.favorite_count = Math.max(0, item.favorite_count - 1);
                }
              }
            }
          }
        )
      ) as unknown as { undo: () => void };
      patches.push(patch);
    }
    const single = dispatch(
      agentsApi.util.updateQueryData(
        "getAgent",
        resourceUid,
        (draft) => {
          const wasFavorited = draft.is_favorited;
          draft.is_favorited = favorited;
          if (favorited && !wasFavorited) {
            draft.favorite_count += 1;
          } else if (!favorited && wasFavorited) {
            draft.favorite_count = Math.max(0, draft.favorite_count - 1);
          }
        }
      )
    ) as unknown as { undo: () => void };
    patches.push(single);
  } else if (resourceType === "skill") {
    const entries = skillsApi.util.selectInvalidatedBy(
      getState() as never,
      ["Skills"]
    );
    for (const entry of entries) {
      if (entry.endpointName !== "listSkills") continue;
      const patch = dispatch(
        skillsApi.util.updateQueryData(
          "listSkills",
          entry.originalArgs as never,
          (draft) => {
            for (const item of draft.items) {
              if (item.skill_uid === resourceUid) {
                const wasFavorited = item.is_favorited;
                item.is_favorited = favorited;
                if (favorited && !wasFavorited) {
                  item.favorite_count += 1;
                } else if (!favorited && wasFavorited) {
                  item.favorite_count = Math.max(0, item.favorite_count - 1);
                }
              }
            }
          }
        )
      ) as unknown as { undo: () => void };
      patches.push(patch);
    }
    const single = dispatch(
      skillsApi.util.updateQueryData(
        "getSkill",
        resourceUid,
        (draft) => {
          const wasFavorited = draft.is_favorited;
          draft.is_favorited = favorited;
          if (favorited && !wasFavorited) {
            draft.favorite_count += 1;
          } else if (!favorited && wasFavorited) {
            draft.favorite_count = Math.max(0, draft.favorite_count - 1);
          }
        }
      )
    ) as unknown as { undo: () => void };
    patches.push(single);
  }
  return patches;
}

export const socialApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listMyFavorites: builder.query<MyFavoritesResponse, ListMyFavoritesArg>({
      query: ({ type, page = 1, size = 50 }) => ({
        method: "get",
        path: "/users/me/favorites",
        params: {
          type,
          page: String(page),
          size: String(size),
        },
      }),
      providesTags: (_result, _error, arg) => [
        { type: "Favorites", id: arg.type },
        "Favorites",
      ],
    }),

    favoriteResource: builder.mutation<
      FavoriteToggleResponse,
      FavoriteMutationArg
    >({
      query: ({ resourceType, resourceUid }) => ({
        method: "post",
        path: `/${resourcePath(resourceType)}/${resourceUid}/favorite`,
      }),
      async onQueryStarted(
        { resourceType, resourceUid },
        { dispatch, getState, queryFulfilled }
      ) {
        const patches = patchListCache(
          dispatch,
          getState,
          resourceType,
          resourceUid,
          true
        );
        try {
          await queryFulfilled;
        } catch {
          for (const p of patches) p.undo();
        }
      },
      invalidatesTags: (_result, _error, arg) => [
        { type: "Favorites", id: arg.resourceType },
        "Favorites",
      ],
    }),

    unfavoriteResource: builder.mutation<
      FavoriteToggleResponse,
      FavoriteMutationArg
    >({
      query: ({ resourceType, resourceUid }) => ({
        method: "delete",
        path: `/${resourcePath(resourceType)}/${resourceUid}/favorite`,
      }),
      async onQueryStarted(
        { resourceType, resourceUid },
        { dispatch, getState, queryFulfilled }
      ) {
        const patches = patchListCache(
          dispatch,
          getState,
          resourceType,
          resourceUid,
          false
        );
        try {
          await queryFulfilled;
        } catch {
          for (const p of patches) p.undo();
        }
      },
      invalidatesTags: (_result, _error, arg) => [
        { type: "Favorites", id: arg.resourceType },
        "Favorites",
      ],
    }),
  }),
});

export const {
  useListMyFavoritesQuery,
  useFavoriteResourceMutation,
  useUnfavoriteResourceMutation,
} = socialApi;
