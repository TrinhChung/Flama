export type McpMode = 'admin' | 'user'
export type McpTokenStatus = 'active' | 'expired' | 'exhausted' | 'revoked' | string

export interface McpToken {
  id: number
  name: string
  status: McpTokenStatus
  scopes: string[]
  expires_at: string | null
  max_requests: number
  used_requests: number
  remaining_requests: number
  created_at: string | null
  last_used_at: string | null
  token?: string
  // Admin-optional fields
  user_id?: number
  username?: string
  email?: string
  client_id?: number | null
  client_name?: string | null
  revoked?: boolean
}

export interface CreateTokenPayload {
  name: string
  expires_in_days: number | null
  scopes: string[]
  user_id?: number
  custom_token?: string
}

export interface UpdateTokenPayload {
  id: number
  name: string
  scopes: string[]
  expires_in_days?: number | null | 'keep' | 'none'
}

export interface RotateTokenPayload {
  id: number
  expires_in_days: number | null | 'none'
}

export interface IssuedTokenResult {
  token: string
  name: string
  username?: string
  expires_at?: string | null
}

export interface UseMcpTokensOptions {
  mode: McpMode
  userId?: number
  onSuccessMutation?: () => void
}

export interface UseMcpTokensReturn {
  mode: McpMode
  tokens: McpToken[]
  isLoading: boolean
  isError: boolean
  error: Error | null
  refetch: () => Promise<unknown>
  search: string
  setSearch: (query: string) => void
  statusFilter: 'all' | 'active' | 'revoked' | 'expired'
  setStatusFilter: (status: 'all' | 'active' | 'revoked' | 'expired') => void
  page: number
  setPage: (page: number | ((p: number) => number)) => void
  totalPages: number
  totalItems: number
  inactiveCount: number
  canManageTokens: boolean
  createToken: (payload: CreateTokenPayload) => Promise<IssuedTokenResult>
  updateToken: (payload: UpdateTokenPayload) => Promise<McpToken>
  rotateToken: (payload: RotateTokenPayload) => Promise<IssuedTokenResult>
  revokeToken: (id: number) => Promise<void>
  purgeToken: (id: number) => Promise<void>
  cleanupExpired: () => Promise<{ success: boolean; purged_count: number }>
  isCreating: boolean
  isUpdating: boolean
  isRotating: boolean
  isRevoking: boolean
  isPurging: boolean
  isCleaningUp: boolean
}

export {
  ALL_MCP_SCOPES,
  SCOPE_CATEGORIES,
  SCOPE_PRESETS,
  type McpScopeItem,
  type McpScopeCategory,
  type McpPolicy,
} from '@/features/settings/hooks/useMcpTokenCRUD'
