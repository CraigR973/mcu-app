// Shared domain types — expanded in later phases

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  per_page: number
}

export interface ApiError {
  message: string
  code?: string
}
