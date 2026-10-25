import { useEffect, useMemo, useState } from 'react'
import {
  UNLIMITED_QUOTA,
  type QuotaPeriod,
  type QuotaPolicy,
  type QuotaPolicyPayload,
  type QuotaRole,
} from '../types/quotas'

export type RoleLimitDraft = { unlimited: boolean; value: string }

function draftFrom(policy: QuotaPolicy, roles: QuotaRole[]): Record<string, RoleLimitDraft> {
  return Object.fromEntries(
    roles.map((role) => {
      const limit = policy.role_limits[role.code] ?? UNLIMITED_QUOTA
      return [role.code, { unlimited: limit < 0, value: limit < 0 ? '' : String(limit) }]
    }),
  )
}

/** Editable copy of one policy; resets whenever the server copy changes. */
export function useQuotaPolicyForm(policy: QuotaPolicy, roles: QuotaRole[]) {
  const [enforce, setEnforce] = useState(policy.enforce)
  const [period, setPeriod] = useState<QuotaPeriod>(policy.period)
  const [limits, setLimits] = useState(() => draftFrom(policy, roles))

  useEffect(() => {
    setEnforce(policy.enforce)
    setPeriod(policy.period)
    setLimits(draftFrom(policy, roles))
  }, [policy, roles])

  const invalidRole = useMemo(
    () =>
      roles.find((role) => {
        const draft = limits[role.code]
        return draft && !draft.unlimited && !/^\d+$/.test(draft.value.trim())
      }) ?? null,
    [limits, roles],
  )

  const payload: QuotaPolicyPayload = useMemo(
    () => ({
      enforce,
      period,
      role_limits: Object.fromEntries(
        roles.map((role) => {
          const draft = limits[role.code]
          return [role.code, !draft || draft.unlimited ? UNLIMITED_QUOTA : Number(draft.value.trim())]
        }),
      ),
    }),
    [enforce, period, limits, roles],
  )

  const isDirty =
    enforce !== policy.enforce ||
    period !== policy.period ||
    roles.some(
      (role) => (payload.role_limits?.[role.code] ?? UNLIMITED_QUOTA) !== (policy.role_limits[role.code] ?? UNLIMITED_QUOTA),
    )

  const setRoleLimit = (code: string, draft: Partial<RoleLimitDraft>) =>
    setLimits((current) => ({ ...current, [code]: { ...current[code], ...draft } }))

  return { enforce, setEnforce, period, setPeriod, limits, setRoleLimit, invalidRole, payload, isDirty }
}
