import { useMemo } from 'react'
import { CardDisplay, renderCardSide } from '@/entities/flashcard/rendering'
import { Button, Textarea } from '@/shared/ui'
import { useMcpTemplatePreview } from '../hooks/useMcpTemplatePreview'

/** Candidate HTML is only passed to the production card sandbox. */
export function TemplatePreviewApp({ initialResult }: { initialResult?: unknown }) {
  const state = useMcpTemplatePreview(initialResult)
  const { preview } = state
  const rendered = useMemo(() => {
    if (!preview?.preview) return null
    try {
      const { template_artifact: template, content_artifact: content } = preview.preview
      return { front: renderCardSide(template, content, 'front'), back: renderCardSide(template, content, 'back') }
    } catch { return { error: 'The candidate could not compile in the Study client renderer.' } }
  }, [preview])

  return <main className="mx-auto max-w-3xl space-y-4 p-4 text-foreground">
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div><h1 className="text-lg font-semibold">Flama · Template preview</h1>
        <p className="text-xs text-muted-foreground">Temporary sample · no data saved</p></div>
      <div className="flex gap-2" aria-label="Card side">
        {(['front', 'back'] as const).map((side) => <Button key={side} size="sm"
          variant={state.side === side ? 'default' : 'outline'} aria-pressed={state.side === side}
          onClick={() => state.setSide(side)}>{side === 'front' ? 'Front' : 'Back'}</Button>)}
      </div>
    </header>
    {state.error && <p role="alert">{state.error}</p>}
    {!preview && !state.error && <p role="status">Waiting for the template preview result…</p>}
    {preview && <>
      {preview.candidate_hash && <p className="break-all text-xs text-muted-foreground" data-testid="candidate-hash">{preview.candidate_hash}</p>}
      {preview.diagnostics.length > 0 && <ul className="space-y-2 text-sm" aria-label="Template diagnostics">
        {preview.diagnostics.map((d, i) => <li key={i}><strong>{d.code}</strong>: {d.message}
          {d.line && <> · {d.source_part}:{d.line}{d.column ? `:${d.column}` : ''}</>} {d.hint}
          {!!d.suggestions?.length && <> Suggested inputs: {d.suggestions.join(', ')}.</>}</li>)}
      </ul>}
      {rendered && 'error' in rendered ? <p role="alert">{rendered.error}</p> : rendered && <div className="h-[440px] min-h-60 overflow-hidden rounded-xl border bg-card">
        <CardDisplay key={preview.candidate_hash} cardId={preview.candidate_hash ?? undefined} side={state.side}
          candidateHash={preview.candidate_hash ?? undefined} mediaBaseUrl={preview.media_base_url}
          frontPayload={rendered.front} backPayload={rendered.back}
          fieldDefs={preview.preview?.template_artifact.field_defs}
          fieldValues={preview.preview?.content_artifact.field_values}
          onDiagnostic={state.onDiagnostic} onReady={state.onReady} scope="mcp_template_preview" />
      </div>}
      <p className="text-xs text-muted-foreground" role="status">{state.readySides.length ? `Sandbox ready: ${state.readySides.join(', ')}.` : 'Sandbox has not reported ready.'} Interaction test: not run.</p>
      {state.diagnostics.length > 0 && <ul role="alert" className="space-y-1 text-sm text-destructive">
        {state.diagnostics.map((d, i) => <li key={i}>{d.side} · {d.code}: {d.message}</li>)}
      </ul>}
      <label className="block space-y-2 text-sm">What did you try and observe?
        <Textarea maxLength={4000} value={state.observation} onChange={(e) => state.setObservation(e.target.value)}
          placeholder="For example: selected answers 1 and 3; feedback stayed empty." />
      </label>
      <Button disabled={!state.connected} onClick={() => void state.sendReport()}>Send report to chat</Button>
      {state.reportStatus && <p role="status" className="text-sm">{state.reportStatus}</p>}
      <details className="text-xs"><summary>Report data</summary><pre className="overflow-auto whitespace-pre-wrap break-all">{JSON.stringify({
        candidate_hash: preview.candidate_hash, side: state.side, ready_sides: state.readySides,
        diagnostics: state.diagnostics, user_observation: state.observation, interaction: 'not_run',
      }, null, 2)}</pre></details>
    </>}
  </main>
}
