const DAY_MS = 86_400_000
const PYTHON_ORDINAL_AT_UNIX_EPOCH = 719_163
const formatterCache = new Map<string, Intl.DateTimeFormat>()

type ZonedParts = {
  year: number
  month: number
  day: number
  hour: number
  minute: number
  second: number
}

function formatter(timezone: string) {
  const cached = formatterCache.get(timezone)
  if (cached) return cached
  const created = new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  })
  formatterCache.set(timezone, created)
  return created
}

function zonedParts(epochMs: number, timezone: string): ZonedParts {
  const values: Partial<ZonedParts> = {}
  for (const part of formatter(timezone).formatToParts(new Date(epochMs))) {
    if (
      part.type === 'year'
      || part.type === 'month'
      || part.type === 'day'
      || part.type === 'hour'
      || part.type === 'minute'
      || part.type === 'second'
    ) {
      values[part.type] = Number(part.value)
    }
  }
  return values as ZonedParts
}

function ordinalFromDate(year: number, month: number, day: number) {
  return Math.floor(Date.UTC(year, month - 1, day) / DAY_MS)
    + PYTHON_ORDINAL_AT_UNIX_EPOCH
}

function dateFromOrdinal(ordinal: number) {
  const date = new Date(
    (ordinal - PYTHON_ORDINAL_AT_UNIX_EPOCH) * DAY_MS,
  )
  return {
    year: date.getUTCFullYear(),
    month: date.getUTCMonth() + 1,
    day: date.getUTCDate(),
  }
}

function zonedLocalToUtcMs(
  local: ZonedParts,
  timezone: string,
) {
  const desiredWallMs = Date.UTC(
    local.year,
    local.month - 1,
    local.day,
    local.hour,
    local.minute,
    local.second,
  )
  let guess = desiredWallMs
  for (let index = 0; index < 4; index += 1) {
    const actual = zonedParts(guess, timezone)
    const actualWallMs = Date.UTC(
      actual.year,
      actual.month - 1,
      actual.day,
      actual.hour,
      actual.minute,
      actual.second,
    )
    const delta = desiredWallMs - actualWallMs
    guess += delta
    if (delta === 0) break
  }
  return guess
}

export function dayIndex(
  epochMs: number,
  boundaryHour: number,
  timezone: string,
) {
  const local = zonedParts(epochMs, timezone)
  const ordinal = ordinalFromDate(local.year, local.month, local.day)
  return local.hour < boundaryHour ? ordinal - 1 : ordinal
}

export function dayIndexToUtcMs(
  ordinal: number,
  boundaryHour: number,
  timezone: string,
) {
  const date = dateFromOrdinal(ordinal)
  return zonedLocalToUtcMs(
    {
      ...date,
      hour: boundaryHour,
      minute: 0,
      second: 0,
    },
    timezone,
  )
}

export function isoFromEpochMs(epochMs: number) {
  return new Date(Math.trunc(epochMs)).toISOString()
}

export function epochMsFromIso(value: string | null) {
  if (!value) return null
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : null
}
