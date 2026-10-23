import type {
  EnginePackageState,
  LocalAudioServiceStatus,
  PairingChallenge,
  TtsRequest,
  VoiceDescriptor,
} from '@/features/audio/types'

import {
  safeLocalStorageGet,
  safeLocalStorageSet,
  safeLocalStorageRemove,
} from '@/shared/hooks'

const FLAMA_AUDIO_BASE_URL = import.meta.env.VITE_FLAMA_AUDIO_URL || 'http://127.0.0.1:4791'
const TOKEN_STORAGE_KEY = 'flama_audio_pairing_token'

export class FlamaAudioClient {
  private baseUrl: string
  private token: string | null = null

  constructor(baseUrl: string = FLAMA_AUDIO_BASE_URL) {
    this.baseUrl = baseUrl.replace(/\/+$/, '')
    this.token = safeLocalStorageGet<string | null>(TOKEN_STORAGE_KEY, null, (raw) => raw)
  }

  public setToken(token: string | null) {
    this.token = token
    if (token) {
      safeLocalStorageSet(TOKEN_STORAGE_KEY, token, (val) => val)
    } else {
      safeLocalStorageRemove(TOKEN_STORAGE_KEY)
    }
  }

  public getToken(): string | null {
    return this.token
  }

  public async getHealth(signal?: AbortSignal): Promise<LocalAudioServiceStatus> {
    const res = await fetch(`${this.baseUrl}/health`, { credentials: 'omit', signal })
    if (!res.ok) throw new Error(`Flama Audio Service returned HTTP ${res.status}`)
    return res.json()
  }

  public async startPairing(origin: string = window.location.origin, signal?: AbortSignal): Promise<PairingChallenge> {
    const res = await fetch(`${this.baseUrl}/v1/pairing/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ origin }),
      credentials: 'omit',
      signal,
    })
    if (!res.ok) throw new Error(`Start pairing failed with HTTP ${res.status}`)
    return res.json()
  }

  public async getPairingStatus(pairingId: string, signal?: AbortSignal): Promise<PairingChallenge> {
    const res = await fetch(`${this.baseUrl}/v1/pairing/${pairingId}`, { credentials: 'omit', signal })
    if (!res.ok) throw new Error(`Get pairing status failed with HTTP ${res.status}`)
    return res.json()
  }

  public async getEngines(): Promise<EnginePackageState[]> {
    const res = await fetch(`${this.baseUrl}/v1/engines`, {
      headers: this.getAuthHeaders(),
      credentials: 'omit',
    })
    if (!res.ok) throw new Error(`Get engines failed with HTTP ${res.status}`)
    return res.json()
  }

  public async getVoices(engineId: string = 'voicevox', signal?: AbortSignal): Promise<VoiceDescriptor[]> {
    const res = await fetch(`${this.baseUrl}/v1/voices?engine_id=${encodeURIComponent(engineId)}`, {
      headers: this.getAuthHeaders(),
      credentials: 'omit',
      signal,
    })
    if (!res.ok) throw new Error(`Get voices failed with HTTP ${res.status}`)
    return res.json()
  }

  public async installEngine(engineId: string = 'voicevox', signal?: AbortSignal): Promise<{ status: string; message: string }> {
    const res = await fetch(`${this.baseUrl}/v1/engines/${encodeURIComponent(engineId)}/install`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      credentials: 'omit',
      signal,
    })
    if (!res.ok) throw new Error(`Install engine failed with HTTP ${res.status}`)
    return res.json()
  }

  public async launchEngine(engineId: string = 'voicevox', signal?: AbortSignal): Promise<{ status: string; message: string }> {
    const res = await fetch(`${this.baseUrl}/v1/engines/${encodeURIComponent(engineId)}/launch`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      credentials: 'omit',
      signal,
    })
    if (!res.ok) throw new Error(`Launch engine failed with HTTP ${res.status}`)
    return res.json()
  }

  public async synthesize(request: TtsRequest): Promise<Blob> {
    const res = await fetch(`${this.baseUrl}/v1/tts`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(request),
      credentials: 'omit',
    })

    if (!res.ok) {
      let msg = `TTS Synthesis failed with HTTP ${res.status}`
      try {
        const err = await res.json()
        if (err.message || err.detail) msg = err.message || err.detail
      } catch {}
      throw new Error(msg)
    }

    return res.blob()
  }

  private getAuthHeaders(): Record<string, string> {
    const headers: Record<string, string> = {}
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }
    return headers
  }
}

export const flamaAudioClient = new FlamaAudioClient()
