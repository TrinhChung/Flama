import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { PageError } from '@/shared/components/PageState'
import { TemplateInputBindingEditor } from './TemplateInputBindingEditor'
import type { StudyTemplateComposition, StudyTemplatePreparationState } from '../hooks/useStudyTemplatePreparation'

export type StudyTemplatePreparationProps = {
  preparation: StudyTemplatePreparationState
  deckName?: string | null
  error?: unknown
  disabled?: boolean
  onStart: () => void
}

export function StudyTemplatePreparation({ preparation, deckName, error, disabled = false, onStart }: StudyTemplatePreparationProps) {
  const pending = disabled || preparation.isSaving || preparation.isLoading
  const choices = preparation.availability?.compositions ?? []
  return (
    <div className="flex min-h-[100dvh] w-full items-center justify-center overflow-y-auto bg-background p-4 text-foreground sm:p-6">
      <main className="w-full max-w-2xl rounded-2xl border border-border/80 bg-card p-5 shadow-sm sm:p-7">
        <h1 className="text-2xl font-bold tracking-tight">Chuẩn bị phiên học</h1>
        {deckName ? <p className="mt-2 text-sm text-muted-foreground">{deckName}</p> : null}
        {preparation.error || error ? <div className="mt-4"><PageError error={preparation.error || error} /></div> : null}
        <div className="mt-6 space-y-5">
          <div className="space-y-1.5">
            <label htmlFor="study-template-choice" className="block text-sm font-medium">Template cho phiên này</label>
            <select id="study-template-choice" value={preparation.compositionId ?? ''} disabled={pending}
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm disabled:opacity-50"
              onChange={(event) => preparation.selectComposition(event.target.value)}>
              <option value="" disabled>Chọn template</option>
              {choices.map((choice: StudyTemplateComposition) => <option key={choice.composition_id} value={choice.composition_id}>{choice.note_type_name ? `${choice.note_type_name} · ` : ''}{choice.template_name}</option>)}
            </select>
          </div>
          {preparation.entry ? <section aria-label="Ánh xạ dữ liệu" className="space-y-3">
            <h2 className="font-semibold">Ánh xạ dữ liệu</h2>
            {preparation.staleInputs.length > 0 ? <p role="status" className="text-sm text-amber-700 dark:text-amber-400">Trường đã lưu không còn phù hợp. Hãy chọn lại hoặc để trống.</p> : null}
            <TemplateInputBindingEditor inputSchema={preparation.entry.input_schema} fieldDefs={preparation.entry.field_defs}
              value={preparation.inputBindings} onChange={preparation.changeBindings} disabled={pending} />
          </section> : null}
          <div className="space-y-3 border-t border-border/70 pt-4">
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={preparation.remember} disabled={pending} onChange={(event) => preparation.setRemember(event.target.checked)} />Ghi nhớ cho bộ thẻ này</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={preparation.askBeforeStudy} disabled={pending || !preparation.remember} onChange={(event) => preparation.setAskBeforeStudy(event.target.checked)} />Luôn hỏi trước khi học</label>
          </div>
          <div className="flex flex-wrap justify-between gap-3">
            <Button asChild variant="outline"><Link to="/dashboard">Về tổng quan</Link></Button>
            <Button disabled={pending || !preparation.compositionId} onClick={onStart}>{preparation.error || error ? 'Thử lại' : 'Bắt đầu học'}</Button>
          </div>
        </div>
      </main>
    </div>
  )
}
