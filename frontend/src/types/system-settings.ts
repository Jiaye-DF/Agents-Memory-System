export type SystemSettingValueType =
  | "string"
  | "integer"
  | "boolean"
  | "json";

export interface SystemSetting {
  system_setting_uid: string;
  key: string;
  value: string;
  value_type: SystemSettingValueType;
  description: string | null;
  is_public: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SystemSettingUpdateRequest {
  value?: string;
  description?: string | null;
  is_public?: boolean;
  is_active?: boolean;
}

export type PublicSettings = Record<string, string | number | boolean>;
