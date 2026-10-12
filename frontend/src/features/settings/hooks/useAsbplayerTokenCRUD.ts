import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { FLAMA_ANKI_CONNECT_URL } from '@/config/env'
import type { IntegrationToken, TokensResponse } from './useYomitanTokenCRUD'

export type AsbplayerTokenPreset = 'mining-text' | 'mining-media'

export function useAsbplayerTokenCRUD() {
  const { t } = useTranslation('settings')
  const queryClient = useQueryClient()
  const queryKey = ['integration-tokens'] as const
  const [name, setName] = useState(() => t('asbplayer.tokens.default_name', 'asbplayer - Trình duyệt PC'))
  const [expiry, setExpiry] = useState('180')
  const [preset, setPreset] = useState<AsbplayerTokenPreset>('mining-text')
  const [issued, setIssued] = useState<IntegrationToken | null>(null)
  const [copied, setCopied] = useState<string | null>(null)

  const issuedConnectUrl = issued?.token ? FLAMA_ANKI_CONNECT_URL : null
  const issuedMiningKey = issued?.token ?? null

  const query = useQuery({
    queryKey,
    queryFn: () => appApi.get<TokensResponse>('/integration-tokens'),
  })

  const rawTokens = query.data?.items || []
  const tokens = rawTokens.filter(
    (item) => item.preset === 'mining-text' || item.preset === 'mining-media'
  )

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey })
  }

  const createMutation = useMutation({
    mutationFn: () =>
      appApi.mutate<{ item: IntegrationToken }>('/integration-tokens', 'POST', {
        name: name.trim(),
        expires_in_days: expiry === 'none' ? null : Number(expiry),
        preset,
      }),
    onSuccess: async ({ item }) => {
      setIssued(item)
      await refresh()
      toast.success(t('asbplayer.messages.create_success'))
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const revokeMutation = useMutation({
    mutationFn: (id: number) => appApi.mutate(`/integration-tokens/${id}`, 'DELETE'),
    onSuccess: async () => {
      await refresh()
      toast.success(t('asbplayer.messages.revoke_success'))
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const rotateMutation = useMutation({
    mutationFn: (id: number) =>
      appApi.mutate<{ item: IntegrationToken }>(`/integration-tokens/${id}/rotate`, 'POST', {
        expires_in_days: expiry === 'none' ? null : Number(expiry),
      }),
    onSuccess: async ({ item }) => {
      setIssued(item)
      await refresh()
      toast.success(t('asbplayer.messages.rotate_success'))
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const setupMiningMutation = useMutation({
    mutationFn: () => appApi.mutate('/integration-tokens/sentence-mining-setup', 'POST', {}),
    onSuccess: () => toast.success(t('asbplayer.messages.setup_success')),
    onError: (error: Error) => toast.error(error.message),
  })

  const copy = async (label: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(label)
      window.setTimeout(() => setCopied(null), 1800)
      toast.success(t('asbplayer.messages.copied'))
    } catch {
      toast.error(t('asbplayer.messages.copy_failed', 'Không thể sao chép vào bộ nhớ tạm.'))
    }
  }

  return {
    query,
    tokens,
    name,
    setName,
    expiry,
    setExpiry,
    preset,
    setPreset,
    issued,
    setIssued,
    copied,
    copy,
    issuedConnectUrl,
    issuedMiningKey,
    refresh,
    createMutation,
    revokeMutation,
    rotateMutation,
    setupMiningMutation,
  }
}
