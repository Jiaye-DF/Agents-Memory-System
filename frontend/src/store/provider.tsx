"use client";

import { useState } from "react";
import { Provider } from "react-redux";
import { makeStore } from "./store";
import type { AppStore } from "./store";

interface StoreProviderProps {
  children: React.ReactNode;
}

export function StoreProvider({ children }: StoreProviderProps): React.ReactNode {
  const [store] = useState<AppStore>(makeStore);

  return <Provider store={store}>{children}</Provider>;
}
