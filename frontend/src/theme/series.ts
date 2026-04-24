import type { ThemeItem, ThemeSeries } from "./types";

const ATMOSPHERE_ITEMS: ThemeItem[] = [
  {
    id: "light",
    labelZh: "晨曦",
    labelEn: "Dawn",
    icon: "◐",
    source: "builtin",
    colors: {
      background: "#ffffff",
      foreground: "#171717",
      primary: "#2563eb",
      accent: "#3b82f6",
    },
  },
  {
    id: "cool",
    labelZh: "霧境",
    labelEn: "Nordic",
    icon: "❅",
    source: "builtin",
    colors: {
      background: "#e2eaf3",
      foreground: "#0f172a",
      primary: "#0284c7",
      accent: "#0891b2",
    },
  },
  {
    id: "warm",
    labelZh: "夕映",
    labelEn: "Ember",
    icon: "◉",
    source: "builtin",
    colors: {
      background: "#f0e4d4",
      foreground: "#3a2f27",
      primary: "#c2410c",
      accent: "#d97706",
    },
  },
  {
    id: "purple",
    labelZh: "暮霞",
    labelEn: "Twilight",
    icon: "✦",
    source: "builtin",
    colors: {
      background: "#faf5ff",
      foreground: "#3b0764",
      primary: "#a855f7",
      accent: "#e879f9",
    },
  },
  {
    id: "dark",
    labelZh: "深夜",
    labelEn: "Midnight",
    icon: "☾",
    source: "builtin",
    colors: {
      background: "#0a0a0a",
      foreground: "#ededed",
      primary: "#60a5fa",
      accent: "#93c5fd",
    },
  },
];

export const THEME_SERIES: ThemeSeries[] = [
  {
    key: "atmosphere",
    labelZh: "光影",
    labelEn: "Atmosphere",
    source: "builtin",
    items: ATMOSPHERE_ITEMS,
  },
];

export function findThemeItem(id: string): ThemeItem | undefined {
  for (const series of THEME_SERIES) {
    const item = series.items.find((t) => t.id === id);
    if (item) return item;
  }
  return undefined;
}

export function getAllThemeItems(): ThemeItem[] {
  return THEME_SERIES.flatMap((s) => s.items);
}
