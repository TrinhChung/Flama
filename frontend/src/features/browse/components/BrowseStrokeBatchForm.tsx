import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { AlertTriangle, Clock, Languages, LoaderCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { cn } from '@/lib/utils'
import { saveStoredStrokeSettings } from '../services/strokeStorage'

export interface BrowseStrokeBatchFormProps {
  isMixedNoteTypes: boolean
  selectedDeck?: { note_type_names?: string[] } | null
  sourceField: string
  setSourceField: (val: string) => void
  targetField: string
  setTargetField: (val: string) => void
  noteFieldNames: string[]
  mediaTargetFieldNames: string[]
  locale: 'ja' | 'zh-CN' | 'zh-TW'
  setLocale: (val: 'ja' | 'zh-CN' | 'zh-TW') => void
  overwrite: boolean
  setOverwrite: (val: boolean) => void
  mode: 'single' | 'batch'
  estimateQuery: {
    isLoading: boolean
    data?: {
      is_heavy_task?: boolean
      estimated_human?: string
      notes_to_update?: number
      notes_skipped?: number
      unique_characters?: number
      cached_characters?: number
      new_characters?: number
    }
  }
}

export function BrowseStrokeBatchForm({
  isMixedNoteTypes,
  selectedDeck,
  sourceField,
  setSourceField,
  targetField,
  setTargetField,
  noteFieldNames,
  mediaTargetFieldNames,
  locale,
  setLocale,
  overwrite,
  setOverwrite,
  mode,
  estimateQuery,
}: BrowseStrokeBatchFormProps) {
  const { t } = useTranslation('browse')

  return (
    <>
      {/* Mixed Note Types Warning Banner */}
      {isMixedNoteTypes && (
        <div className="p-3.5 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-start gap-2.5 text-amber-800 dark:text-amber-200">
          <AlertTriangle className="size-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div className="text-xs space-y-0.5">
            <p className="font-bold">
              {t('stroke_modal.mixed_types_title')}
            </p>
            <p className="text-[11px] text-amber-700/90 dark:text-amber-300/90">
              {selectedDeck?.note_type_names?.length
                ? `${t('stroke_modal.mixed_types_detected', { types: selectedDeck.note_type_names.join(', ') })} `
                : ''}
              {t('stroke_modal.mixed_types_desc')}
            </p>
          </div>
        </div>
      )}

      {/* Form grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        {/* Source field */}
        <div className="space-y-1.5">
          <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            {t('stroke_modal.source_field_label')}
          </Label>
          <NativeSelect
            value={sourceField}
            onChange={(e) => setSourceField(e.target.value)}
            className="h-9 text-xs rounded-lg bg-background"
          >
            {noteFieldNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </NativeSelect>
        </div>

        {/* Target field */}
        <div className="space-y-1.5">
          <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            {t('stroke_modal.target_field_label')}
          </Label>
          <NativeSelect
            value={targetField}
            onChange={(e) => setTargetField(e.target.value)}
            disabled={mediaTargetFieldNames.length === 0}
            className="h-9 text-xs rounded-lg bg-background"
          >
            {mediaTargetFieldNames.length === 0 ? (
              <option value="">{t('stroke_modal.no_media_field')}</option>
            ) : (
              <optgroup label={t('stroke_modal.media_fields_group')}>
                {mediaTargetFieldNames.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </optgroup>
            )}
          </NativeSelect>
        </div>

        {/* Locale */}
        <div className="space-y-1.5 sm:col-span-2">
          <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1">
            <Languages className="size-3.5" />
            <span>{t('stroke_modal.rule_language_label')}</span>
          </Label>
          <NativeSelect
            value={locale}
            onChange={(e) => {
              const nextLocale = e.target.value as 'ja' | 'zh-CN' | 'zh-TW'
              setLocale(nextLocale)
              saveStoredStrokeSettings({ locale: nextLocale })
            }}
            className="h-9 text-xs rounded-lg bg-background"
          >
            <option value="ja">{t('stroke_modal.lang_ja')}</option>
            <option value="zh-CN">{t('stroke_modal.lang_zh_cn')}</option>
            <option value="zh-TW">{t('stroke_modal.lang_zh_tw')}</option>
          </NativeSelect>
        </div>
      </div>

      {/* Overwrite option */}
      <div className="flex items-center space-x-2 pt-0.5">
        <Checkbox
          id="overwrite-strokes"
          checked={overwrite}
          onCheckedChange={(c) => {
            const nextOverwrite = Boolean(c)
            setOverwrite(nextOverwrite)
            saveStoredStrokeSettings({ overwrite: nextOverwrite })
          }}
        />
        <Label
          htmlFor="overwrite-strokes"
          className="text-xs font-medium cursor-pointer select-none text-foreground"
        >
          {t('stroke_modal.overwrite_label')}
        </Label>
      </div>

      {/* Batch ETA & Workload Estimation Card */}
      {mode !== 'single' && Boolean(targetField) && (
        <div
          className={cn(
            'p-3.5 rounded-xl border transition-all text-xs space-y-2',
            estimateQuery.data?.is_heavy_task
              ? 'bg-amber-500/10 border-amber-500/30 text-amber-950 dark:text-amber-200'
              : 'bg-muted/40 border-border/80 text-foreground',
          )}
        >
          <div className="flex items-center justify-between">
            <span className="font-semibold flex items-center gap-1.5 text-xs">
              <Clock
                className={cn(
                  'size-4 shrink-0',
                  estimateQuery.data?.is_heavy_task
                    ? 'text-amber-600 dark:text-amber-400'
                    : 'text-primary',
                )}
              />
              <span>{t('stroke_modal.estimated_time_label')}</span>
            </span>
            {estimateQuery.isLoading ? (
              <span className="text-[11px] text-muted-foreground flex items-center gap-1 font-medium">
                <LoaderCircle className="size-3 animate-spin text-primary" /> {t('stroke_modal.calculating')}
              </span>
            ) : estimateQuery.data ? (
              <Badge
                variant={estimateQuery.data.is_heavy_task ? 'default' : 'secondary'}
                className={cn(
                  'font-bold text-xs px-2 py-0.5',
                  estimateQuery.data.is_heavy_task &&
                    'bg-amber-600 hover:bg-amber-700 text-white',
                )}
              >
                {estimateQuery.data.estimated_human}
              </Badge>
            ) : null}
          </div>

          {estimateQuery.data && (
            <div className="space-y-1.5 pt-1 text-[11px] text-muted-foreground border-t border-border/50">
              <div className="flex flex-wrap items-center justify-between gap-1">
                <span>{t('stroke_modal.workload_label')}</span>
                <span className="font-medium text-foreground">
                  {t('stroke_modal.workload_detail', {
                    update: estimateQuery.data.notes_to_update,
                    skip: estimateQuery.data.notes_skipped,
                  })}
                </span>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-1">
                <span>{t('stroke_modal.characters_label')}</span>
                <span className="font-medium text-foreground">
                  {t('stroke_modal.characters_detail', {
                    unique: estimateQuery.data.unique_characters,
                    cached: estimateQuery.data.cached_characters,
                    new: estimateQuery.data.new_characters,
                  })}
                </span>
              </div>

              {estimateQuery.data.is_heavy_task && (
                <div className="flex items-start gap-1.5 pt-1 text-[11px] text-amber-700 dark:text-amber-300 font-medium">
                  <AlertTriangle className="size-3.5 shrink-0 mt-0.5" />
                  <span>
                    {t('stroke_modal.heavy_task_warning', { count: estimateQuery.data.new_characters })}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </>
  )
}
