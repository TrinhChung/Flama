export type DiffLineKind = 'same' | 'added' | 'removed'
export type DiffLine = { kind: DiffLineKind; text: string; oldLine: number | null; newLine: number | null }

function splitLines(text: string): string[] {
  if (!text) return []
  return text.replaceAll('\r\n', '\n').split('\n')
}

export function diffLines(oldText: string, newText: string, maxCells = 4_000_000): DiffLine[] {
  const a = splitLines(oldText)
  const b = splitLines(newText)
  const n = a.length
  const m = b.length

  if (n === 0 && m === 0) return []
  if (n === 0) {
    return b.map((text, j) => ({ kind: 'added', text, oldLine: null, newLine: j + 1 }))
  }
  if (m === 0) {
    return a.map((text, i) => ({ kind: 'removed', text, oldLine: i + 1, newLine: null }))
  }

  if (n * m > maxCells) {
    const fallback: DiffLine[] = []
    for (let i = 0; i < n; i++) {
      fallback.push({ kind: 'removed', text: a[i], oldLine: i + 1, newLine: null })
    }
    for (let j = 0; j < m; j++) {
      fallback.push({ kind: 'added', text: b[j], oldLine: null, newLine: j + 1 })
    }
    return fallback
  }

  const L: Uint32Array[] = new Array(n + 1)
  for (let i = 0; i <= n; i++) {
    L[i] = new Uint32Array(m + 1)
  }

  for (let i = n - 1; i >= 0; i--) {
    const row = L[i]
    const nextRow = L[i + 1]
    const ai = a[i]
    for (let j = m - 1; j >= 0; j--) {
      if (ai === b[j]) {
        row[j] = nextRow[j + 1] + 1
      } else {
        const down = nextRow[j]
        const right = row[j + 1]
        row[j] = down >= right ? down : right
      }
    }
  }

  let i = 0
  let j = 0
  const result: DiffLine[] = []

  while (i < n && j < m) {
    if (a[i] === b[j]) {
      result.push({ kind: 'same', text: a[i], oldLine: i + 1, newLine: j + 1 })
      i++
      j++
    } else if (L[i + 1][j] >= L[i][j + 1]) {
      result.push({ kind: 'removed', text: a[i], oldLine: i + 1, newLine: null })
      i++
    } else {
      result.push({ kind: 'added', text: b[j], oldLine: null, newLine: j + 1 })
      j++
    }
  }

  while (i < n) {
    result.push({ kind: 'removed', text: a[i], oldLine: i + 1, newLine: null })
    i++
  }

  while (j < m) {
    result.push({ kind: 'added', text: b[j], oldLine: null, newLine: j + 1 })
    j++
  }

  return result
}

export function summarizeDiff(lines: DiffLine[]): { added: number; removed: number } {
  let added = 0
  let removed = 0
  for (const line of lines) {
    if (line.kind === 'added') {
      added++
    } else if (line.kind === 'removed') {
      removed++
    }
  }
  return { added, removed }
}
