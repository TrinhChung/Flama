import type { AudioDeckJob } from '../types'

const AUDIO_QUEUE_STORAGE_KEY = 'flama_deck_audio_queue_v1'
const AUDIO_CONCURRENCY_KEY = 'flama_deck_audio_concurrency_v1'

export const DEFAULT_AUDIO_CONCURRENCY = 3
export const MIN_AUDIO_CONCURRENCY = 1
export const MAX_AUDIO_CONCURRENCY = 5

export function loadStoredConcurrency(): number {
  try {
    const raw = localStorage.getItem(AUDIO_CONCURRENCY_KEY)
    if (!raw) return DEFAULT_AUDIO_CONCURRENCY
    const parsed = parseInt(raw, 10)
    if (isNaN(parsed) || parsed < MIN_AUDIO_CONCURRENCY || parsed > MAX_AUDIO_CONCURRENCY) {
      return DEFAULT_AUDIO_CONCURRENCY
    }
    return parsed
  } catch {
    return DEFAULT_AUDIO_CONCURRENCY
  }
}

export function saveStoredConcurrency(concurrency: number): void {
  try {
    const clamped = Math.max(MIN_AUDIO_CONCURRENCY, Math.min(MAX_AUDIO_CONCURRENCY, concurrency))
    localStorage.setItem(AUDIO_CONCURRENCY_KEY, String(clamped))
  } catch (err) {
    console.error('Failed to save audio concurrency setting:', err)
  }
}

export function loadStoredAudioQueue(): AudioDeckJob[] {
  try {
    const raw = localStorage.getItem(AUDIO_QUEUE_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []

    // Sanitize any interrupted jobs: if state was 'running' during page close, transition to 'paused'
    return parsed.map((job: AudioDeckJob) => {
      if (job.status === 'running') {
        return {
          ...job,
          status: 'paused',
        }
      }
      return job
    })
  } catch (err) {
    console.error('Failed to load audio queue from storage:', err)
    return []
  }
}

export function saveStoredAudioQueue(jobs: AudioDeckJob[]): void {
  try {
    localStorage.setItem(AUDIO_QUEUE_STORAGE_KEY, JSON.stringify(jobs))
  } catch (err) {
    console.error('Failed to save audio queue to storage:', err)
  }
}

let saveDebounceTimer: ReturnType<typeof setTimeout> | null = null

export function saveStoredAudioQueueDebounced(jobs: AudioDeckJob[], delayMs: number = 300): void {
  if (saveDebounceTimer) {
    clearTimeout(saveDebounceTimer)
  }
  saveDebounceTimer = setTimeout(() => {
    saveStoredAudioQueue(jobs)
    saveDebounceTimer = null
  }, delayMs)
}

export function flushStoredAudioQueueSave(jobs: AudioDeckJob[]): void {
  if (saveDebounceTimer) {
    clearTimeout(saveDebounceTimer)
    saveDebounceTimer = null
  }
  saveStoredAudioQueue(jobs)
}

export function clearStoredAudioQueue(): void {
  try {
    if (saveDebounceTimer) {
      clearTimeout(saveDebounceTimer)
      saveDebounceTimer = null
    }
    localStorage.removeItem(AUDIO_QUEUE_STORAGE_KEY)
  } catch (err) {
    console.error('Failed to clear audio queue storage:', err)
  }
}
