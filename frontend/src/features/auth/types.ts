export interface LoginCredentials {
  email: string
  password: string
}

export interface TokenPair {
  access: string
}

export interface RefreshResponse {
  access: string
}
