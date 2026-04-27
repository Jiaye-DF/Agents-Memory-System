export interface ApiResponse<T = unknown> {
  success: boolean;
  data: T | null;
  detail: string | null;
  response_code: number;
}

export interface PaginatedData<T = unknown> {
  items: T[];
  next_cursor: string | null;
  has_next: boolean;
}

export interface PaginationParams {
  limit?: number;
  cursor?: string | null;
}
