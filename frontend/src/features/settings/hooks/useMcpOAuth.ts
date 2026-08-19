import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'

export type OAuthEndpointsInfo = {
  base_url: string
  auth_url: string
  token_url: string
  resource_url: string
  userinfo_url: string
  openid_config_url: string
  scopes: string[]
  scopes_string: string
}

export type OAuthClientItem = {
  id: number
  client_id: string
  client_name: string
  client_uri: string | null
  redirect_uris: string[]
  is_confidential: boolean
  is_active: boolean
  created_at: string | null
}

export type ConnectedAppItem = {
  client_id: string
  client_name: string
  client_uri: string | null
  authorized_at: string | null
  last_used_at: string | null
  token_id: number
}

export function useMcpOAuth() {
  const queryClient = useQueryClient()

  // Form states for creating a new client
  const [clientName, setClientName] = useState('ChatGPT')
  const [clientId, setClientId] = useState('chatgpt_flama')
  const [clientSecret, setClientSecret] = useState('flama_secret_2026')
  const [redirectUrisText, setRedirectUrisText] = useState(
    'https://chatgpt.com/api/actions/callback'
  )
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)

  // 1. Fetch endpoints metadata
  const endpointsQuery = useQuery({
    queryKey: ['oauth-endpoints-info'],
    queryFn: () => appApi.get<OAuthEndpointsInfo>('/api/oauth/endpoints-info'),
  })

  // 2. Fetch registered OAuth clients
  const clientsQuery = useQuery({
    queryKey: ['oauth-clients'],
    queryFn: () => appApi.get<{ items: OAuthClientItem[] }>('/api/oauth/clients'),
  })

  // 3. Fetch connected apps
  const connectedAppsQuery = useQuery({
    queryKey: ['oauth-connected-apps'],
    queryFn: () => appApi.get<{ items: ConnectedAppItem[] }>('/api/oauth/connected-apps'),
  })

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['oauth-clients'] }),
      queryClient.invalidateQueries({ queryKey: ['oauth-connected-apps'] }),
      queryClient.invalidateQueries({ queryKey: ['oauth-endpoints-info'] }),
    ])
  }

  // Create Client Mutation
  const createClientMutation = useMutation({
    mutationFn: () => {
      const uris = redirectUrisText
        .split('\n')
        .map((u) => u.trim())
        .filter(Boolean)
      return appApi.mutate<{ success: boolean; client: OAuthClientItem }>(
        '/api/oauth/clients',
        'POST',
        {
          client_name: clientName.trim(),
          client_id: clientId.trim(),
          client_secret: clientSecret.trim() || null,
          redirect_uris: uris,
        }
      )
    },
    onSuccess: async () => {
      setIsCreateOpen(false)
      await refresh()
      toast.success('Đã lưu OAuth Client thành công! Bạn có thể dùng Client ID này trên ChatGPT.')
    },
    onError: (error: Error) => toast.error(error.message || 'Không thể tạo OAuth Client.'),
  })

  // Delete Client Mutation
  const deleteClientMutation = useMutation({
    mutationFn: (clientPk: number) =>
      appApi.mutate(`/api/oauth/clients/${clientPk}`, 'DELETE'),
    onSuccess: async () => {
      await refresh()
      toast.success('Đã xóa OAuth Client.')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  // Revoke Connected App Mutation
  const revokeConnectedAppMutation = useMutation({
    mutationFn: (targetClientId: string) =>
      appApi.mutate(`/api/oauth/connected-apps/${encodeURIComponent(targetClientId)}/revoke`, 'POST'),
    onSuccess: async () => {
      await refresh()
      toast.success('Đã thu hồi quyền truy cập của ứng dụng.')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const copy = async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedKey(key)
      window.setTimeout(() => setCopiedKey(null), 2000)
      toast.success(`Đã sao chép vào bộ nhớ tạm.`)
    } catch {
      toast.error('Không thể sao chép.')
    }
  }

  return {
    endpointsQuery,
    clientsQuery,
    connectedAppsQuery,
    clientName,
    setClientName,
    clientId,
    setClientId,
    clientSecret,
    setClientSecret,
    redirectUrisText,
    setRedirectUrisText,
    isCreateOpen,
    setIsCreateOpen,
    copiedKey,
    copy,
    createClientMutation,
    deleteClientMutation,
    revokeConnectedAppMutation,
    refresh,
  }
}
