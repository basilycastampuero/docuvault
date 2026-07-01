export interface LoginCredentials {
  email: string
  password: string
}

export interface TokenPair {
  access: string
  refresh: string
}

export interface RefreshResponse {
  access: string
  refresh: string
}
