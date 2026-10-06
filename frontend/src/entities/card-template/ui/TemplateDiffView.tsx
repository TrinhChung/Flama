import { diffLines, type DiffLine, summarizeDiff } from '../lib/lineDiff'

export type TemplateSources = { front_html: string; back_html: string; shared_css: string }

export type TemplateDiffViewProps = {
  before: TemplateSources
  after: TemplateSources
  beforeLabel: string
  afterLabel: string
}

const SECTIONS = [
  { key: 'front_html', label: 'Front HTML' },
  { key: 'back_html', label: 'Back HTML' },
  { key: 'shared_css', label: 'Shared CSS' },
] as const

const MARK = {
  same: ' ',
  added: '+',
  removed: '-',
} as const

const CLASS = {
  same: 'px-3 text-muted-foreground',
  added: 'px-3 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  removed: 'px-3 bg-rose-500/10 text-rose-700 dark:text-rose-300',
} as const

interface DiffSectionProps {
  label: string
  lines: DiffLine[]
}

function DiffSection({ label, lines }: DiffSectionProps) {
  const { added, removed } = summarizeDiff(lines)

  return (
    <section className="rounded-xl border border-border/80 overflow-hidden">
      <header className="flex items-center justify-between bg-muted/40 px-3 py-1.5 text-xs font-semibold">
        <span>{label}</span>
        <span className="font-mono text-muted-foreground">+{added} −{removed}</span>
      </header>
      {added === 0 && removed === 0 ? (
        <p className="px-3 py-2 text-xs text-muted-foreground">Không có thay đổi</p>
      ) : (
        <pre className="max-h-80 overflow-auto text-xs leading-5 font-mono">
          {lines.map((line, index) => (
            <div key={index} data-kind={line.kind} className={CLASS[line.kind]}>
              <span className="inline-block w-4 select-none">{MARK[line.kind]}</span>
              {line.text}
            </div>
          ))}
        </pre>
      )}
    </section>
  )
}

export function TemplateDiffView({ before, after, beforeLabel, afterLabel }: TemplateDiffViewProps) {
  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">So sánh {beforeLabel} → {afterLabel}</p>
      {SECTIONS.map(({ key, label }) => (
        <DiffSection key={key} label={label} lines={diffLines(before?.[key] ?? '', after?.[key] ?? '')} />
      ))}
    </div>
  )
}
