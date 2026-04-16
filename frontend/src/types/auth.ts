export interface LoginRequest {
  account: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
}

export interface RegisterRequest {
  username: string;
  account: string;
  password: string;
  confirm_password: string;
}

export interface RegisterResponse {
  user_uid: string;
}

export interface ResetPasswordRequest {
  account: string;
  username: string;
  new_password: string;
  confirm_password: string;
}

export interface TokenPayload {
  user_uid: string;
  role: string;
  exp: number;
  iat: number;
}
