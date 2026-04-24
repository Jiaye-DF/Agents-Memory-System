export interface ThemeColors {
  background: string;
  foreground: string;
  primary: string;
  accent: string;
}

export type ThemeSource = "builtin" | "user";

export interface ThemeItem {
  id: string;
  labelZh: string;
  labelEn: string;
  icon: string;
  source: ThemeSource;
  colors: ThemeColors;
}

export interface ThemeSeries {
  key: string;
  labelZh: string;
  labelEn: string;
  source: ThemeSource;
  items: ThemeItem[];
}
