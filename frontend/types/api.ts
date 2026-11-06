export interface ApiSuccess<T> {
  success: true;
  data: T;
  message: string;
}

export interface ApiFailure {
  success: false;
  message: string;
  errors: Record<string, unknown>;
  code?: string;
  request_id?: string;
}

export type ApiEnvelope<T> = ApiSuccess<T> | ApiFailure;

export interface Pagination {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface Paginated<T> {
  results: T[];
  pagination: Pagination;
}

export interface HealthStatus {
  status: "ok";
  time: string;
  environment: string;
  database?: "ok";
}
