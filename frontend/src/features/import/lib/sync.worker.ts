import { executeAnkiSync } from './ankiSyncEngine'
import { setCsrfToken } from '@/shared/api/client'

self.onmessage = async (e: MessageEvent) => {
  const { type, payload } = e.data
  if (type === 'START_SYNC') {
    const {
      deckName,
      modelName,
      fieldMapping,
      syncMode,
      csrfToken,
      options,
    } = payload

    setCsrfToken(csrfToken)

    try {
      const result = await executeAnkiSync(
        deckName,
        modelName,
        fieldMapping,
        syncMode,
        (progress) => {
          self.postMessage({ type: 'PROGRESS', payload: progress })
        },
        options,
      )
      self.postMessage({ type: 'COMPLETED', payload: result })
    } catch (err: any) {
      self.postMessage({
        type: 'ERROR',
        payload: { message: err?.message || String(err) },
      })
    }
  }
}
