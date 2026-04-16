import { baseApi } from "./api";

export interface LlmModel {
  llm_model_uid: string;
  provider: string;
  model_id: string;
  display_name: string;
}

interface ListModelsResponse {
  items: LlmModel[];
}

export const modelsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listModels: builder.query<ListModelsResponse, void>({
      query: () => ({
        method: "get",
        path: "/models",
      }),
    }),
  }),
});

export const { useListModelsQuery } = modelsApi;
