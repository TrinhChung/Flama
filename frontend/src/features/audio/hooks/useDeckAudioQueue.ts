import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { updateCardFieldValues } from '@/entities/flashcard/model/cardContentUpdates'
import { flamaAudioClient } from '@/lib/flamaAudioClient'
import { uploadNoteMediaBlob } from '@/shared/api/noteMedia'
import {
  clearStoredAudioQueue,
  flushStoredAudioQueueSave,
  loadStoredAudioQueue,
  loadStoredConcurrency,
  saveStoredAudioQueueDebounced,
  saveStoredConcurrency,
} from '../services/audioQueueStorage'
import { resolveLocaleFromVoiceId } from '../services/ttsTextNormalizer'
import type { AudioDeckJob, AudioJobItem } from '../types'

export function useDeckAudioQueue() {
  const [jobs, setJobs] = useState<AudioDeckJob[]>(() => loadStoredAudioQueue())
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [concurrency, setConcurrencyState] = useState<number>(() => loadStoredConcurrency())

  const concurrencyRef = useRef<number>(concurrency)
  const isExecutingRef = useRef<boolean>(false)
  const shouldPauseRef = useRef<boolean>(false)

  // Update concurrency setting
  const setConcurrency = useCallback((newVal: number) => {
    const clamped = Math.max(1, Math.min(5, newVal))
    setConcurrencyState(clamped)
    concurrencyRef.current = clamped
    saveStoredConcurrency(clamped)
  }, [])

  // Sync state changes to storage (debounced)
  useEffect(() => {
    saveStoredAudioQueueDebounced(jobs)
  }, [jobs])

  // Current active job
  const activeJob =
    jobs.find((j) => j.id === activeJobId) || jobs.find((j) => j.status === 'running') || null

  // Process a single item: synthesize + upload
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
        await updateCardFieldValues({
          cardId: item.cardId,
          noteId: item.noteId,
          fieldValues: { [item.destinationField]: res.url },
        })
      }

      return { success: true, assetUrl: res.url }
    } catch (err) {
      return {
        success: false,
        error: err instanceof Error ? err.message : 'Tạo audio thất bại',
      }
    }
  }

  // Queue Executor Loop with Multi-Worker Concurrency Pool
  const runQueueWorker = useCallback(async () => {
    if (isExecutingRef.current) return
    isExecutingRef.current = true
    shouldPauseRef.current = false

    while (true) {
      // Find current running or next queued job
      const currentJobs = loadStoredAudioQueue()
      let targetJob =
        currentJobs.find((j) => j.id === activeJobId && j.status === 'running') ||
        currentJobs.find((j) => j.status === 'running') ||
        currentJobs.find((j) => j.status === 'queued')

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
          concurrency: concurrencyRef.current,
        }
        setJobs((prev) => {
          const next = prev.map((j) => (j.id === currentJobId ? targetJob! : j))
          flushStoredAudioQueueSave(next)
          return next
        })
      }

      // Check Flama Audio Health
      try {
        await flamaAudioClient.getHealth()
      } catch {
        toast.error('Mất kết nối với Flama Audio Desktop. Đang tạm dừng hàng đợi...')
        setJobs((prev) => {
          const next = prev.map((j) =>
            j.id === currentJobId ? { ...j, status: 'paused' as const } : j,
          )
          flushStoredAudioQueueSave(next)
          return next
        })
        break
      }

      // Prepare items and concurrency tracking
      const items = [...targetJob.items]
      let cursor = 0
      let activeWorkersCount = 0
      const activeWordsMap = new Map<number, { word: string; field: string }>()
      const sessionStartTime = Date.now()
      let completedInSession = 0

      const updateJobProgressState = (currentItems: AudioJobItem[]) => {
        const completed = currentItems.filter((it) => it.status === 'done').length
        const failed = currentItems.filter((it) => it.status === 'failed').length
        const skipped = currentItems.filter((it) => it.status === 'skipped').length
        const progress = Math.round(((completed + failed + skipped) / currentItems.length) * 100)

        const elapsedSec = (Date.now() - sessionStartTime) / 1000
        const itemsPerSecond =
          completedInSession > 0 && elapsedSec > 0.5
            ? Math.round((completedInSession / elapsedSec) * 10) / 10
            : 0

        const remainingCount = currentItems.length - (completed + failed + skipped)
        const estimatedSecondsRemaining =
          itemsPerSecond > 0 ? Math.round(remainingCount / itemsPerSecond) : undefined

        const activeWords = Array.from(activeWordsMap.values()).map((v) => v.word)
        const firstActive = activeWordsMap.values().next().value

        setJobs((prev) => {
          const next = prev.map((j) => {
            if (j.id !== currentJobId) return j
            return {
              ...j,
              items: [...currentItems],
              concurrency: concurrencyRef.current,
              stats: {
                ...j.stats,
                completedItems: completed,
                failedItems: failed,
                skippedItems: skipped,
                progressPercent: progress,
                activeWorkers: activeWorkersCount,
                itemsPerSecond,
                estimatedSecondsRemaining,
                activeWords,
                currentWord: firstActive?.word,
                currentField: firstActive?.field,
              },
            }
          })
          saveStoredAudioQueueDebounced(next)
          return next
        })
      }

      // Worker task
      const worker = async () => {
        while (true) {
          if (shouldPauseRef.current) {
            break
          }

          // Pick next pending item
          let itemIndex = -1
          while (cursor < items.length) {
            const idx = cursor++
            const it = items[idx]
            if (it && it.status !== 'done' && it.status !== 'skipped') {
              itemIndex = idx
              break
            }
          }

          if (itemIndex === -1) {
            break
          }

          const currentItem = items[itemIndex]
          activeWorkersCount++
          activeWordsMap.set(itemIndex, {
            word: currentItem.word,
            field: currentItem.destinationField,
          })

          // Mark item as synthesizing
          items[itemIndex] = { ...currentItem, status: 'synthesizing' }
          updateJobProgressState(items)

          if (shouldPauseRef.current) {
            items[itemIndex] = { ...currentItem, status: 'pending' }
            activeWorkersCount--
            activeWordsMap.delete(itemIndex)
            updateJobProgressState(items)
            break
          }

          // Synthesize & upload
          const result = await processItem(currentItem)

          activeWorkersCount--
          activeWordsMap.delete(itemIndex)

          if (result.success) {
            completedInSession++
            items[itemIndex] = {
              ...currentItem,
              status: 'done',
              assetUrl: result.assetUrl,
            }
          } else {
            items[itemIndex] = {
              ...currentItem,
              status: 'failed',
              error: result.error,
            }
          }

          updateJobProgressState(items)
        }
      }

      // Spawn concurrent workers
      const poolSize = Math.max(1, Math.min(5, concurrencyRef.current))
      const workers = Array.from({ length: poolSize }, () => worker())
      await Promise.all(workers)

      if (shouldPauseRef.current) {
        setJobs((prev) => {
          const next = prev.map((j) =>
            j.id === currentJobId
              ? {
                  ...j,
                  status: 'paused' as const,
                  stats: { ...j.stats, activeWorkers: 0, activeWords: [] },
                }
              : j,
          )
          flushStoredAudioQueueSave(next)
          return next
        })
        break
      }

      const allCompleted = items.every((it) => it.status === 'done' || it.status === 'skipped')
      const hasFailures = items.some((it) => it.status === 'failed')

      if (allCompleted || hasFailures) {
        setJobs((prev) => {
          const next = prev.map((j) =>
            j.id === currentJobId
              ? {
                  ...j,
                  status: 'completed' as const,
                  completedAt: new Date().toISOString(),
                  stats: {
                    ...j.stats,
                    activeWorkers: 0,
                    activeWords: [],
                    progressPercent: 100,
                  },
                }
              : j,
          )
          flushStoredAudioQueueSave(next)
          return next
        })

        const failedCount = items.filter((it) => it.status === 'failed').length
        if (failedCount > 0) {
          toast.warning(
            `Hoàn tất tạo âm thanh cho Deck "${targetJob.deckName}" với ${failedCount} mục lỗi.`,
          )
        } else {
          toast.success(`Đã hoàn tất tạo âm thanh cho Deck "${targetJob.deckName}"!`)
        }
      }
    }

    isExecutingRef.current = false
    setActiveJobId(null)
  }, [activeJobId])

  // Auto-start queue if there are queued/running jobs on mount or state update
  const triggerQueue = useCallback(() => {
    setTimeout(() => {
      runQueueWorker()
    }, 100)
  }, [runQueueWorker])

  // Public Queue Actions
  const addJobToQueue = (job: AudioDeckJob) => {
    const jobWithConcurrency = {
      ...job,
      concurrency: concurrencyRef.current,
    }
    setJobs((prev) => {
      const next = [...prev, jobWithConcurrency]
      flushStoredAudioQueueSave(next)
      return next
    })
    toast.success(`Đã thêm Deck "${job.deckName}" vào hàng đợi (${job.items.length} mục).`)
    triggerQueue()
  }

  const pauseActiveJob = () => {
    shouldPauseRef.current = true
    setJobs((prev) => {
      const next = prev.map((j) =>
        j.status === 'running'
          ? {
              ...j,
              status: 'paused' as const,
              stats: { ...j.stats, activeWorkers: 0, activeWords: [] },
            }
          : j,
      )
      flushStoredAudioQueueSave(next)
      return next
    })
    toast.info('Đang tạm dừng hàng đợi tạo âm thanh...')
  }

  const resumeJob = (jobId: string) => {
    setJobs((prev) => {
      const next = prev.map((j) => (j.id === jobId ? { ...j, status: 'queued' as const } : j))
      flushStoredAudioQueueSave(next)
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
      const next = prev.map((j) =>
        j.id === jobId
          ? {
              ...j,
              status: 'cancelled' as const,
              stats: { ...j.stats, activeWorkers: 0, activeWords: [] },
            }
          : j,
      )
      flushStoredAudioQueueSave(next)
      return next
    })
    toast.info('Đã hủy tác vụ.')
  }

  const removeQueuedJob = (jobId: string) => {
    setJobs((prev) => {
      const next = prev.filter((j) => j.id !== jobId)
      flushStoredAudioQueueSave(next)
      return next
    })
    toast.info('Đã xóa khỏi hàng đợi.')
  }

  const clearCompleted = () => {
    setJobs((prev) => {
      const next = prev.filter(
        (j) => j.status === 'running' || j.status === 'queued' || j.status === 'paused',
      )
      flushStoredAudioQueueSave(next)
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
    concurrency,
    setConcurrency,
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

