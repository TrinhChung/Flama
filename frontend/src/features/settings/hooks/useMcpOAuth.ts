import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { useBootstrap } from '@/shared/api/bootstrap'

export type OAuthEndpointsInfo = {
  base_url: string
  auth_url: string
  token_url: string
  resource_url: string
  userinfo_url: string
  openid_config_url: string
  scopes: string[]
  scopes_string: string
  default_client?: {
    id: number
    client_id: string
    client_name: string
    client_secret: string | null
    redirect_uris: string[]
    is_default: boolean
  } | null
}

export type OAuthClientItem = {
  id: number
  client_id: string
  client_secret?: string | null
  client_name: string
  client_uri: string | null
  redirect_uris: string[]
  is_confidential: boolean
  has_secret?: boolean
  is_default?: boolean
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

function generateRandomKey(prefix = 'flama_sec_'): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-'
  let result = prefix
  for (let i = 0; i < 32; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return result
}

export function useMcpOAuth() {
  const queryClient = useQueryClient()
  const { data: bootstrap } = useBootstrap()
  const isAdmin = Boolean(bootstrap?.user?.is_admin)

  // Form states for creating a new client
  const [clientName, setClientName] = useState('ChatGPT')
  const [clientId, setClientId] = useState('chatgpt_flama')
  const [clientSecret, setClientSecret] = useState('flama_secret_2026')
  const [redirectUrisText, setRedirectUrisText] = useState(
    'https://chatgpt.com/api/actions/callback'
  )
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)

  // Edit states for existing client
  const [editingClient, setEditingClient] = useState<OAuthClientItem | null>(null)
  const [editClientName, setEditClientName] = useState('')
  const [editClientSecret, setEditClientSecret] = useState('')
  const [editRedirectUrisText, setEditRedirectUrisText] = useState('')
  const [isEditOpen, setIsEditOpen] = useState(false)

  // Rotate secret state
  const [rotateClientTarget, setRotateClientTarget] = useState<OAuthClientItem | null>(null)
  const [newRotatedSecret, setNewRotatedSecret] = useState<{ clientName: string; secret: string } | null>(null)

  // 1. Fetch endpoints metadata
  const endpointsQuery = useQuery({
    queryKey: ['oauth-endpoints-info'],
    queryFn: () => appApi.get<OAuthEndpointsInfo>('/api/oauth/endpoints-info'),
  })

  // 2. Fetch registered OAuth clients (Admin only)
  const clientsQuery = useQuery({
    queryKey: ['oauth-clients'],
    queryFn: () => appApi.get<{ items: OAuthClientItem[] }>('/api/oauth/clients'),
    enabled: isAdmin,
  })

  // 3. Fetch connected apps (All authenticated users)
  const connectedAppsQuery = useQuery({
    queryKey: ['oauth-connected-apps'],
    queryFn: () => appApi.get<{ items: ConnectedAppItem[] }>('/api/oauth/connected-apps'),
  })

  const refresh = async () => {
    const invalidations = [
      queryClient.invalidateQueries({ queryKey: ['oauth-connected-apps'] }),
      queryClient.invalidateQueries({ queryKey: ['oauth-endpoints-info'] }),
    ]
    if (isAdmin) {
      invalidations.push(queryClient.invalidateQueries({ queryKey: ['oauth-clients'] }))
    }
    await Promise.all(invalidations)
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

  // Update Client Mutation
  const updateClientMutation = useMutation({
    mutationFn: () => {
      if (!editingClient) throw new Error('Không tìm thấy client để sửa')
      const uris = editRedirectUrisText
        .split('\n')
        .map((u) => u.trim())
        .filter(Boolean)
      return appApi.mutate<{ success: boolean; client: OAuthClientItem }>(
        `/api/oauth/clients/${editingClient.id}`,
        'PUT',
        {
          client_name: editClientName.trim(),
          client_secret: editClientSecret.trim() || null,
          redirect_uris: uris,
        }
      )
    },
    onSuccess: async () => {
      setIsEditOpen(false)
      setEditingClient(null)
      await refresh()
      toast.success('Đã cập nhật thông tin OAuth Client.')
    },
    onError: (error: Error) => toast.error(error.message || 'Không thể cập nhật OAuth Client.'),
  })

  // Rotate Secret Mutation
  const rotateSecretMutation = useMutation({
    mutationFn: ({ clientPk, customSecret }: { clientPk: number; customSecret?: string }) =>
      appApi.mutate<{ success: boolean; client: OAuthClientItem; client_secret: string }>(
        `/api/oauth/clients/${clientPk}/rotate-secret`,
        'POST',
        { new_secret: customSecret || null }
      ),
    onSuccess: async (data) => {
      if (rotateClientTarget) {
        setNewRotatedSecret({
          clientName: rotateClientTarget.client_name,
          secret: data.client_secret,
        })
      }
      setRotateClientTarget(null)
      await refresh()
      toast.success('Đã tạo mới Client Secret thành công!')
    },
    onError: (error: Error) => toast.error(error.message || 'Không thể đổi Secret.'),
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

  // Set Default Client Mutation (Admin only)
  const setDefaultClientMutation = useMutation({
    mutationFn: (clientPk: number) =>
      appApi.mutate<{ success: boolean; client: OAuthClientItem }>(
        `/api/oauth/clients/${clientPk}/set-default`,
        'POST'
      ),
    onSuccess: async (data) => {
      await refresh()
      toast.success(`Đã chọn "${data.client.client_name}" làm bộ thông số mặc định cho người dùng.`)
    },
    onError: (error: Error) => toast.error(error.message || 'Không thể chọn làm mặc định.'),
  })

  const openEditClient = (client: OAuthClientItem) => {
    setEditingClient(client)
    setEditClientName(client.client_name)
    setEditClientSecret(client.client_secret || '')
    setEditRedirectUrisText(client.redirect_uris.join('\n'))
    setIsEditOpen(true)
  }

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
    editingClient,
    setEditingClient,
    editClientName,
    setEditClientName,
    editClientSecret,
    setEditClientSecret,
    editRedirectUrisText,
    setEditRedirectUrisText,
    isEditOpen,
    setIsEditOpen,
    openEditClient,
    rotateClientTarget,
    setRotateClientTarget,
    newRotatedSecret,
    setNewRotatedSecret,
    generateRandomKey,
    copiedKey,
    copy,
    createClientMutation,
    updateClientMutation,
    rotateSecretMutation,
    deleteClientMutation,
    revokeConnectedAppMutation,
    setDefaultClientMutation,
    refresh,
    isAdmin,
  }
}

