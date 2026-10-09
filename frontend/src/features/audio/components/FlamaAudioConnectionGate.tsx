import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  AlertCircle,
  CheckCircle2,
  Cpu,
  Download,
  LoaderCircle,
  Radio,
  RefreshCw,
} from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { flamaAudioClient } from '@/lib/flamaAudioClient'

type FlamaAudioConnectionGateProps = {
  onConnectionChange?: (isReady: boolean) => void
}

export function FlamaAudioConnectionGate({ onConnectionChange }: FlamaAudioConnectionGateProps) {
  const { t } = useTranslation('audio')
  const [serviceStatus, setServiceStatus] = useState<'checking' | 'offline' | 'online'>('checking')
  const [pairingChallengeId, setPairingChallengeId] = useState<string | null>(null)
  const [isPairingApproved, setIsPairingApproved] = useState<boolean>(false)
  const [appVersion, setAppVersion] = useState<string>('')

  const handleStartPairing = useCallback(async () => {
    try {
      const challenge = await flamaAudioClient.startPairing(window.location.origin)
      setPairingChallengeId(challenge.pairing_id)

      if (challenge.approved && challenge.token) {
        flamaAudioClient.setToken(challenge.token)
        setIsPairingApproved(true)
        setPairingChallengeId(null)
        if (onConnectionChange) onConnectionChange(true)
        return
      }

      let attempts = 0
      const interval = setInterval(async () => {
        attempts++
        if (attempts > 40) {
          clearInterval(interval)
          setPairingChallengeId(null)
          return
        }

        try {
          const status = await flamaAudioClient.getPairingStatus(challenge.pairing_id)
          if (status.approved && status.token) {
            clearInterval(interval)
            flamaAudioClient.setToken(status.token)
            setIsPairingApproved(true)
            setPairingChallengeId(null)
            if (onConnectionChange) onConnectionChange(true)
          }
        } catch {}
      }, 1500)
    } catch {
      setIsPairingApproved(false)
    }
  }, [onConnectionChange])

  const checkHealth = useCallback(async () => {
    setServiceStatus('checking')
    try {
      const health = await flamaAudioClient.getHealth()
      setServiceStatus('online')
      setAppVersion(health.version || '1.0.0')

      const token = flamaAudioClient.getToken()
      if (!token) {
        setIsPairingApproved(false)
        if (onConnectionChange) onConnectionChange(false)
        handleStartPairing()
        return
      }

      try {
        await flamaAudioClient.getVoices('voicevox')
        setIsPairingApproved(true)
        if (onConnectionChange) onConnectionChange(true)
      } catch {
        setIsPairingApproved(false)
        if (onConnectionChange) onConnectionChange(false)
        handleStartPairing()
      }
    } catch {
      setServiceStatus('offline')
      setIsPairingApproved(false)
      if (onConnectionChange) onConnectionChange(false)
    }
  }, [handleStartPairing, onConnectionChange])

  useEffect(() => {
    checkHealth()
  }, [checkHealth])

  return (
    <div className="rounded-2xl border border-border/70 bg-card p-4 sm:p-5 shadow-xs transition-all">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div
            className={`flex size-10 items-center justify-center rounded-xl transition-colors ${
              serviceStatus === 'online' && isPairingApproved
                ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                : serviceStatus === 'checking'
                  ? 'bg-amber-500/10 text-amber-600 animate-pulse'
                  : 'bg-rose-500/10 text-rose-600'
            }`}
          >
            <Radio className="size-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm sm:text-base font-bold text-foreground">
                Flama Audio Desktop Companion
              </h2>
              {serviceStatus === 'online' && isPairingApproved && (
                <Badge
                  variant="outline"
                  className="bg-emerald-500/10 text-emerald-600 border-emerald-500/30 text-[11px] font-semibold"
                >
                  <CheckCircle2 className="mr-1 size-3" />
                  {t('gate.connected_title')} (v{appVersion})
                </Badge>
              )}
              {serviceStatus === 'checking' && (
                <Badge variant="outline" className="text-[11px]">
                  <LoaderCircle className="mr-1 size-3 animate-spin text-amber-500" />
                  {t('gate.checking_state')}
                </Badge>
              )}
              {serviceStatus === 'offline' && (
                <Badge
                  variant="destructive"
                  className="text-[11px] font-semibold"
                >
                  {t('gate.status_disconnected')}
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              {t('gate.description')}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-center">
          <Button
            variant="outline"
            size="sm"
            onClick={checkHealth}
            disabled={serviceStatus === 'checking'}
            className="h-8 text-xs gap-1.5"
          >
            <RefreshCw className={`size-3.5 ${serviceStatus === 'checking' ? 'animate-spin' : ''}`} />
            <span>{t('gate.retry_button')}</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            className="h-8 text-xs gap-1.5 border-primary/30 text-primary hover:bg-primary/10 font-semibold"
            asChild
          >
            <Link to="/guide/flama-audio" target="_blank">
              <Download className="size-3.5" />
              <span>{t('gate.download_button')}</span>
            </Link>
          </Button>
        </div>
      </div>

      {/* Offline Alert */}
      {serviceStatus === 'offline' && (
        <Alert variant="destructive" className="mt-4 rounded-xl">
          <AlertCircle className="size-4" />
          <AlertTitle className="font-bold">{t('gate.disconnected_title')}</AlertTitle>
          <AlertDescription className="text-xs leading-relaxed space-y-2 mt-1">
            <p>{t('gate.offline_instruction')}</p>
          </AlertDescription>
        </Alert>
      )}

      {/* Pairing Challenge Alert */}
      {serviceStatus === 'online' && !isPairingApproved && (
        <Alert className="mt-4 border-amber-500/30 bg-amber-500/5 rounded-xl">
          <Cpu className="size-4 text-amber-600 dark:text-amber-400 shrink-0" />
          <AlertTitle className="font-bold text-amber-900 dark:text-amber-200">
            {t('gate.pairing_title')}
          </AlertTitle>
          <AlertDescription className="text-xs leading-relaxed mt-1.5 space-y-2">
            <p>{t('gate.pairing_instruction')}</p>
            <div className="flex items-center gap-3">
              <code className="bg-amber-500/10 text-amber-800 dark:text-amber-300 px-3 py-1.5 rounded-lg font-mono text-sm font-bold border border-amber-500/20 select-all">
                {pairingChallengeId || t('gate.generating_challenge')}
              </code>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleStartPairing}
                className="text-amber-700 hover:bg-amber-500/10 h-8 text-xs"
              >
                {t('gate.resend_request')}
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}
