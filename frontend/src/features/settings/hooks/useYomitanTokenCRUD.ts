import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { FLAMA_CONNECT_URL } from '@/config/env'

export type IntegrationToken = {
  id: number
  name: string
  token_prefix: string
  scopes: string[]
  status: 'active' | 'expired' | 'revoked' | string
  expires_at: string | null
  last_used_at: string | null
  created_at: string
  token?: string
}

export type TokensResponse = {
  items: IntegrationToken[]
  policy: {
    default_expiry_days: number
    allowed_expiry_days: number[]
    allow_no_expiry: boolean
  }
}

export function useYomitanTokenCRUD() {
  const { t } = useTranslation('settings')
  const queryClient = useQueryClient()
  const queryKey = ['integration-tokens'] as const
  const [name, setName] = useState(() => t('yomitan.tokens.default_name', 'Yomitan - PC cá nhân'))
  const [expiry, setExpiry] = useState('180')
  const [issued, setIssued] = useState<IntegrationToken | null>(null)
  const [copied, setCopied] = useState<string | null>(null)
  const hasAutoProcessedRef = useRef(false)

  const issuedConnectUrl = issued?.token
    ? `${FLAMA_CONNECT_URL.replace(/\/+$/, '')}/${encodeURIComponent(issued.token)}`
    : null

  const query = useQuery({
    queryKey,
    queryFn: () => appApi.get<TokensResponse>('/integration-tokens'),
  })

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey })
  }

  const createMutation = useMutation({
    mutationFn: () => appApi.mutate<{ item: IntegrationToken }>('/integration-tokens', 'POST', {
      name: name.trim(),
      expires_in_days: expiry === 'none' ? null : Number(expiry),
    }),
    onSuccess: async ({ item }) => {
      setIssued(item)
      await refresh()
      toast.success(t('yomitan.messages.create_success'))
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const revokeMutation = useMutation({
    mutationFn: (id: number) => appApi.mutate(`/integration-tokens/${id}`, 'DELETE'),
    onSuccess: async () => {
      await refresh()
      toast.success(t('yomitan.messages.revoke_success'))
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const rotateMutation = useMutation({
    mutationFn: (id: number) => appApi.mutate<{ item: IntegrationToken }>(`/integration-tokens/${id}/rotate`, 'POST', {
      expires_in_days: expiry === 'none' ? null : Number(expiry),
    }),
    onSuccess: async ({ item }) => {
      setIssued(item)
      await refresh()
      toast.success(t('yomitan.messages.rotate_success'))
    },
    onError: (error: Error) => toast.error(error.message),
  })

  useEffect(() => {
    if (!query.data || hasAutoProcessedRef.current || createMutation.isPending || rotateMutation.isPending) return

    const items = query.data.items || []
    const now = Date.now()
    const activeTokens = items.filter(
      (t) => t.status === 'active' && (!t.expires_at || new Date(t.expires_at).getTime() > now)
    )

    if (activeTokens.length === 0) {
      hasAutoProcessedRef.current = true
      const expiredToken = items.find(
        (t) => t.status === 'expired' || (t.expires_at && new Date(t.expires_at).getTime() <= now && t.status !== 'revoked')
      )

      if (expiredToken) {
        toast.info(t('yomitan.messages.renew_detected'))
        rotateMutation.mutate(expiredToken.id)
      } else {
        toast.info(t('yomitan.messages.auto_create'))
        createMutation.mutate()
      }
    }
  }, [query.data, createMutation, rotateMutation, t])

  const copy = async (label: string, value: string) => {
    await navigator.clipboard.writeText(value)
    setCopied(label)
    window.setTimeout(() => setCopied(null), 1800)
    toast.success(t('yomitan.messages.copied'))
  }

  return {
    query,
    name,
    setName,
    expiry,
    setExpiry,
    issued,
    setIssued,
    copied,
    copy,
    issuedConnectUrl,
    refresh,
    createMutation,
    revokeMutation,
    rotateMutation,
  }
}
