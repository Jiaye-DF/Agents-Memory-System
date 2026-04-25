/**
 * v1.3.6 Skill 推薦事件即時狀態（暫存當前 session 的最新 SSE 推薦）。
 *
 * - 不 invalidate RTK query 避免 race（agent 列表快取與訊息推薦邏輯不同）
 * - 以 sessionUid 為 key，每次新事件覆蓋當下推薦清單
 */

import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { RecommendSuggestionItem } from "@/types";

interface SkillRecommendationState {
  /** 對應 sessionUid 的最新推薦清單；切換 session 時不清空（讓使用者切回時仍能看到）。 */
  bySession: Record<string, RecommendSuggestionItem[]>;
  /** 最近一次更新時間戳（ms），給前端 toast / 動畫提示用。 */
  lastUpdatedTs: Record<string, number>;
}

const initialState: SkillRecommendationState = {
  bySession: {},
  lastUpdatedTs: {},
};

const slice = createSlice({
  name: "skillSuggestion",
  initialState,
  reducers: {
    setSessionRecommendations(
      state,
      action: PayloadAction<{
        sessionUid: string;
        items: RecommendSuggestionItem[];
      }>,
    ) {
      const { sessionUid, items } = action.payload;
      state.bySession[sessionUid] = items;
      state.lastUpdatedTs[sessionUid] = Date.now();
    },
    removeSuggestion(
      state,
      action: PayloadAction<{ sessionUid: string; uid: string }>,
    ) {
      const { sessionUid, uid } = action.payload;
      const list = state.bySession[sessionUid];
      if (!list) return;
      state.bySession[sessionUid] = list.filter((x) => x.uid !== uid);
    },
    clearSessionRecommendations(
      state,
      action: PayloadAction<{ sessionUid: string }>,
    ) {
      const { sessionUid } = action.payload;
      delete state.bySession[sessionUid];
      delete state.lastUpdatedTs[sessionUid];
    },
  },
});

export const {
  setSessionRecommendations,
  removeSuggestion,
  clearSessionRecommendations,
} = slice.actions;

export default slice.reducer;
