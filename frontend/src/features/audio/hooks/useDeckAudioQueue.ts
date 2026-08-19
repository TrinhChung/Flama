import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { updateCardFieldValuesInSessions } from '@/features/study/session/sessionStore'
import { flamaAudioClient } from '@/lib/flamaAudioClient'
import { uploadNoteMediaBlob } from '@/shared/api/noteMedia'
import {
  clearStoredAudioQueue,
  loadStoredAudioQueue,
  saveStoredAudioQueue,
} from '../services/audioQueueStorage'
import { resolveLocaleFromVoiceId } from '../services/ttsTextNormalizer'
import type { AudioDeckJob, AudioJobItem } from '../types'

export function useDeckAudioQueue() {
  const [jobs, setJobs] = useState<AudioDeckJob[]>(() => loadStoredAudioQueue())
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const isExecutingRef = useRef<boolean>(false)
  const shouldPauseRef = useRef<boolean>(false)

  // Sync state changes to storage
  useEffect(() => {
    saveStoredAudioQueue(jobs)
  }, [jobs])

  // Current active job
  const activeJob = jobs.find((j) => j.id === activeJobId) || jobs.find((j) => j.status === 'running') || null

  // Process a single item
  const processItem = async (
    item: AudioJobItem,
  ): Promise<{ success: boolean; error?: string; assetUrl?: string }> => {
    if (!item.text.trim()) {
      return { success: false, error: 'Văn bản nguồn rỗng' }
    }

    try {
      const wavBlob = await flamaAudioClient.synthesize({
        request_id: `deck_${Date.now()}_${item.id}`,
        engine_id: item.engineId,
        language: item.engineId === 'kokoro' ? resolveLocaleFromVoiceId(item.voiceId) : 'ja-JP',
        voice_id: item.voiceId,
        text: item.text,
        options: item.options,
      })

      const res = await uploadNoteMediaBlob(
        item.noteId,
        item.destinationField,
        wavBlob,
        `${item.engineId}_${item.noteId}_${item.destinationField}.wav`,
      )

      if (res.url && item.cardId) {
        updateCardFieldValuesInSessions(item.cardId, { [item.destinationField]: res.url })
      }

      return { success: true, assetUrl: res.url }
    } catch (err) {
      return {
        success: false,
        error: err instanceof Error ? err.message : 'Tạo audio thất bại',
      }
    }
  }

  // Queue Executor Loop
  const runQueueWorker = useCallback(async () => {
    if (isExecutingRef.current) return
    isExecutingRef.current = true
    shouldPauseRef.current = false

    while (true) {
      // Find current running or next queued job
      let currentJobs = loadStoredAudioQueue()
      let targetJob = currentJobs.find((j) => j.status === 'running') || currentJobs.find((j) => j.status === 'queued')

      if (!targetJob) {
        break
      }

      const currentJobId = targetJob.id
      setActiveJobId(currentJobId)

      // Transition queued to running if needed
      if (targetJob.status === 'queued') {
        targetJob = {
          ...targetJob,
          status: 'running',
          startedAt: targetJob.startedAt || new Date().toISOString(),
        }
        setJobs((prev) => {
          const next = prev.map((j) => (j.id === currentJobId ? targetJob! : j))
          saveStoredAudioQueue(next)
          return next
        })
      }

      // Check Flama Audio Health
      try {
        await flamaAudioClient.getHealth()
      } catch {
        toast.error('Mất kết nối với Flama Audio Desktop. Đang tạm dừng hàng đợi...')
        setJobs((prev) => {
          const next = prev.map((j) => (j.id === currentJobId ? { ...j, status: 'paused' as const } : j))
          saveStoredAudioQueue(next)
          return next
        })
        break
      }

      let isJobFinished = true

      // Iterate through items
      for (let i = 0; i < targetJob.items.length; i++) {
        if (shouldPauseRef.current) {
          isJobFinished = false
          break
        }

        const item = targetJob.items[i]
        if (item.status === 'done' || item.status === 'skipped') {
          continue
        }

        // Update item status: synthesizing
        setJobs((prev) => {
          const next = prev.map((j) => {
            if (j.id !== currentJobId) return j
            const updatedItems = [...j.items]
            updatedItems[i] = { ...updatedItems[i], status: 'synthesizing' }
            return {
              ...j,
              items: updatedItems,
              stats: {
                ...j.stats,
                currentItemIndex: i + 1,
                currentWord: item.word,
                currentField: item.destinationField,
              },
            }
          })
          saveStoredAudioQueue(next)
          return next
        })

        // Execute synthesis & upload
        const result = await processItem(item)

        // Update item status: done or failed
        setJobs((prev) => {
          const next = prev.map((j) => {
            if (j.id !== currentJobId) return j
            const updatedItems = [...j.items]
            updatedItems[i] = {
              ...updatedItems[i],
              status: result.success ? 'done' : 'failed',
              error: result.error,
              assetUrl: result.assetUrl,
            }

            const completed = updatedItems.filter((it) => it.status === 'done').length
            const failed = updatedItems.filter((it) => it.status === 'failed').length
            const skipped = updatedItems.filter((it) => it.status === 'skipped').length
            const progress = Math.round(((completed + failed + skipped) / updatedItems.length) * 100)

            return {
              ...j,
              items: updatedItems,
              stats: {
                ...j.stats,
                completedItems: completed,
                failedItems: failed,
                skippedItems: skipped,
                currentItemIndex: i + 1,
                progressPercent: progress,
              },
            }
          })
          saveStoredAudioQueue(next)
          return next
        })
      }

      if (shouldPauseRef.current) {
        setJobs((prev) => {
          const next = prev.map((j) => (j.id === currentJobId ? { ...j, status: 'paused' as const } : j))
          saveStoredAudioQueue(next)
          return next
        })
        break
      }

      if (isJobFinished) {
        // Mark job as completed
        setJobs((prev) => {
          const next = prev.map((j) =>
            j.id === currentJobId
              ? {
                  ...j,
                  status: 'completed' as const,
                  completedAt: new Date().toISOString(),
                  stats: { ...j.stats, progressPercent: 100 },
                }
              : j,
          )
          saveStoredAudioQueue(next)
          return next
        })
        toast.success(`Đã hoàn tất tạo âm thanh cho Deck "${targetJob.deckName}"!`)
      }
    }

    isExecutingRef.current = false
    setActiveJobId(null)
  }, [])

  // Auto-start queue if there are queued/running jobs on mount or state update
  const triggerQueue = useCallback(() => {
    setTimeout(() => {
      runQueueWorker()
    }, 100)
  }, [runQueueWorker])

  // Public Queue Actions
  const addJobToQueue = (job: AudioDeckJob) => {
    setJobs((prev) => {
      const next = [...prev, job]
      saveStoredAudioQueue(next)
      return next
    })
    toast.success(`Đã thêm Deck "${job.deckName}" vào hàng đợi (${job.items.length} mục).`)
    triggerQueue()
  }

  const pauseActiveJob = () => {
    shouldPauseRef.current = true
    setJobs((prev) => {
      const next = prev.map((j) => (j.status === 'running' ? { ...j, status: 'paused' as const } : j))
      saveStoredAudioQueue(next)
      return next
    })
    toast.info('Đang tạm dừng hàng đợi tạo âm thanh...')
  }

  const resumeJob = (jobId: string) => {
    setJobs((prev) => {
      const next = prev.map((j) => (j.id === jobId ? { ...j, status: 'queued' as const } : j))
      saveStoredAudioQueue(next)
      return next
    })
    toast.success('Đã kích hoạt lại tác vụ.')
    triggerQueue()
  }

  const cancelJob = (jobId: string) => {
    if (activeJobId === jobId) {
      shouldPauseRef.current = true
    }
    setJobs((prev) => {
      const next = prev.map((j) => (j.id === jobId ? { ...j, status: 'cancelled' as const } : j))
      saveStoredAudioQueue(next)
      return next
    })
    toast.info('Đã hủy tác vụ.')
  }

  const removeQueuedJob = (jobId: string) => {
    setJobs((prev) => {
      const next = prev.filter((j) => j.id !== jobId)
      saveStoredAudioQueue(next)
      return next
    })
    toast.info('Đã xóa khỏi hàng đợi.')
  }

  const clearCompleted = () => {
    setJobs((prev) => {
      const next = prev.filter((j) => j.status === 'running' || j.status === 'queued' || j.status === 'paused')
      saveStoredAudioQueue(next)
      return next
    })
    toast.info('Đã dọn dẹp các tác vụ đã hoàn tất.')
  }

  const clearAll = () => {
    shouldPauseRef.current = true
    setJobs([])
    clearStoredAudioQueue()
    toast.info('Đã xóa toàn bộ hàng đợi.')
  }

  return {
    jobs,
    activeJob,
    activeJobId,
    addJobToQueue,
    pauseActiveJob,
    resumeJob,
    cancelJob,
    removeQueuedJob,
    clearCompleted,
    clearAll,
    triggerQueue,
  }
}
