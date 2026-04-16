export interface User {
  user_uid: string;
  username: string;
  account: string;
  role_name: string;
  is_active: boolean;
  login_fail_count: number;
  locked_until: string | null;
  created_at: string;
}

export interface Role {
  user_role_uid: string;
  name: string;
  description: string;
}

export interface UpdateUserRequest {
  role_uid?: string;
  unlock?: boolean;
}
