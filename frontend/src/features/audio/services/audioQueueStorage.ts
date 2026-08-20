import type { AudioDeckJob } from '../types'

const AUDIO_QUEUE_STORAGE_KEY = 'flama_deck_audio_queue_v1'

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

export function clearStoredAudioQueue(): void {
  try {
    localStorage.removeItem(AUDIO_QUEUE_STORAGE_KEY)
  } catch (err) {
    console.error('Failed to clear audio queue storage:', err)
  }
}
