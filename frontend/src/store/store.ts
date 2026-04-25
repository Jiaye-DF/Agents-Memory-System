import { configureStore } from "@reduxjs/toolkit";
import { baseApi } from "./api";
import skillSuggestionReducer from "./skillSuggestionSlice";

export const makeStore = (): ReturnType<typeof configureStore> =>
  configureStore({
    reducer: {
      [baseApi.reducerPath]: baseApi.reducer,
      skillSuggestion: skillSuggestionReducer,
    },
    middleware: (getDefaultMiddleware) =>
      getDefaultMiddleware().concat(baseApi.middleware),
  });

export type AppStore = ReturnType<typeof makeStore>;
export type RootState = ReturnType<AppStore["getState"]>;
export type AppDispatch = AppStore["dispatch"];
