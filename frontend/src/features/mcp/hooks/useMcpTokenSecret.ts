import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { FLAMA_MCP_URL } from '@/shared/config/env'
import type { IssuedTokenResult, McpMode } from '../types'

type CopyTarget = 'token' | 'url'
type CopySession = {
  active: boolean
  timers: Partial<Record<CopyTarget, ReturnType<typeof setTimeout>>>
}

export function useMcpTokenSecret({ issuedToken, isOpen, mode }: {
  issuedToken: IssuedTokenResult | null
  isOpen: boolean
  mode: McpMode
}) {
  const { t } = useTranslation('mcp')
  const [copied, setCopied] = useState({ token: false, url: false })
  const sessionRef = useRef<CopySession | null>(null)
  const token = issuedToken?.token

  useEffect(() => {
    const session: CopySession = { active: isOpen && Boolean(token), timers: {} }
    sessionRef.current = session
    setCopied({ token: false, url: false })
    return () => {
      session.active = false
      for (const timer of Object.values(session.timers)) clearTimeout(timer)
    }
  }, [isOpen, token])

  const serverUrl = issuedToken
    ? `${FLAMA_MCP_URL.replace(/\/+$/, '')}/${encodeURIComponent(issuedToken.token)}`
    : ''
  const jsonConfig = issuedToken
    ? JSON.stringify({ mcpServers: { flama: {
      url: serverUrl, headers: { Authorization: `Bearer ${issuedToken.token}` },
    } } }, null, 2)
    : ''

  async function copy(target: CopyTarget, value: string | undefined) {
    const session = sessionRef.current
    if (!value || !session?.active) return
    try {
      if (typeof navigator === 'undefined' || !navigator.clipboard?.writeText) {
        throw new Error('Clipboard API unavailable')
      }
      await navigator.clipboard.writeText(value)
      // A write may finish after close, unmount, or issuance of another token.
      if (!session.active || sessionRef.current !== session) return
      clearTimeout(session.timers[target])
      setCopied((current) => ({ ...current, [target]: true }))
      toast.success(t(`secret_modal.copied_${target}_toast_${mode}`))
      session.timers[target] = setTimeout(() => {
        delete session.timers[target]
        if (session.active && sessionRef.current === session) {
          setCopied((current) => ({ ...current, [target]: false }))
        }
      }, 2000)
    } catch {
      if (session.active && sessionRef.current === session) {
        toast.error(t(`secret_modal.copy_failed_toast_${mode}`))
      }
    }
  }

  return {
    serverUrl, jsonConfig,
    copiedToken: copied.token, copiedUrl: copied.url,
    handleCopyToken: () => copy('token', token),
    handleCopyUrl: () => copy('url', serverUrl),
  }
}
