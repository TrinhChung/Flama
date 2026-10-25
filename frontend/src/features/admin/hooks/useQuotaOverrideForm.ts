import { useEffect, useState } from 'react'
import { UNLIMITED_QUOTA, type QuotaOverridePayload, type QuotaPeriod, type QuotaUserKindDetail } from '../types/quotas'

type PeriodChoice = QuotaPeriod | 'policy'

/** Form state for granting one user a quota of one kind. */
export function useQuotaOverrideForm(detail: QuotaUserKindDetail) {
  const current = detail.override
  const [unlimited, setUnlimited] = useState(false)
  const [limit, setLimit] = useState('')
  const [period, setPeriod] = useState<PeriodChoice>('policy')
  const [expiresOn, setExpiresOn] = useState('')
  const [note, setNote] = useState('')

  useEffect(() => {
    const base = current?.limit_value ?? detail.effective.limit_value
    setUnlimited(base < 0)
    setLimit(base < 0 ? '' : String(base))
    setPeriod(current?.period ?? 'policy')
    setExpiresOn(current?.expires_on ?? '')
    setNote(current?.note ?? '')
  }, [current, detail.effective.limit_value])

  const isValid = unlimited || /^\d+$/.test(limit.trim())

  const payload: QuotaOverridePayload = {
    limit_value: unlimited ? UNLIMITED_QUOTA : Number(limit.trim() || 0),
    period: period === 'policy' ? null : period,
    expires_on: expiresOn || null,
    note: note.trim(),
  }

  return {
    unlimited,
    setUnlimited,
    limit,
    setLimit,
    period,
    setPeriod,
    expiresOn,
    setExpiresOn,
    note,
    setNote,
    isValid,
    payload,
  }
}
