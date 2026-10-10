import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import type {
  ConflictResolution,
  ConflictResolutionMode,
  PendingUpdateDto,
} from '../model/types'

export interface ConflictResolutionDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  pendingUpdate: PendingUpdateDto
  onApply: (resolutions: Record<string, ConflictResolution>) => Promise<void>
  isApplying: boolean
}

export function ConflictResolutionDialog({
  open,
  onOpenChange,
  pendingUpdate,
  onApply,
  isApplying,
}: ConflictResolutionDialogProps) {
  const { t } = useTranslation('card_templates')
  const conflictKeys = Object.keys(pendingUpdate.conflicts || {})

  // Initialize resolutions default to 'keep_mine'
  const [resolutions, setResolutions] = useState<Record<string, ConflictResolution>>(() => {
    const initial: Record<string, ConflictResolution> = {}
    for (const key of conflictKeys) {
      initial[key] = { mode: 'keep_mine' }
    }
    return initial
  })

  const [manualValues, setManualValues] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {}
    for (const key of conflictKeys) {
      const val = pendingUpdate.conflicts[key]?.local
      initial[key] = typeof val === 'string' ? val : JSON.stringify(val, null, 2)
    }
    return initial
  })

  const [error, setError] = useState<string | null>(null)

  const handleModeChange = (field: string, mode: ConflictResolutionMode) => {
    setResolutions((prev) => ({
      ...prev,
      [field]: {
        mode,
        value: mode === 'manual' ? manualValues[field] : undefined,
      },
    }))
  }

  const handleManualValueChange = (field: string, val: string) => {
    setManualValues((prev) => ({ ...prev, [field]: val }))
    if (resolutions[field]?.mode === 'manual') {
      setResolutions((prev) => ({
        ...prev,
        [field]: { mode: 'manual', value: val },
      }))
    }
  }

  const handleSubmit = async () => {
    setError(null)
    const finalResolutions: Record<string, ConflictResolution> = {}
    for (const key of conflictKeys) {
      const res = resolutions[key] || { mode: 'keep_mine' }
      if (res.mode === 'manual') {
        finalResolutions[key] = {
          mode: 'manual',
          value: manualValues[key] ?? '',
        }
      } else {
        finalResolutions[key] = { mode: res.mode }
      }
    }

    try {
      await onApply(finalResolutions)
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('distribution.update_error'))
    }
  }

  const getFieldLabel = (field: string) => {
    switch (field) {
      case 'front_html':
        return t('distribution.conflicts.field_front_html')
      case 'back_html':
        return t('distribution.conflicts.field_back_html')
      case 'shared_css':
        return t('distribution.conflicts.field_shared_css')
      case 'input_schema':
        return t('distribution.conflicts.field_input_schema')
      default:
        return field
    }
  }

  const stringifyContent = (val: unknown) => {
    return typeof val === 'string' ? val : JSON.stringify(val, null, 2)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>{t('distribution.conflicts.dialog_title')}</DialogTitle>
          <DialogDescription>{t('distribution.conflicts.dialog_desc')}</DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-6 py-2 pr-1">
          {conflictKeys.map((field) => {
            const conflict = pendingUpdate.conflicts[field]
            const currentMode = resolutions[field]?.mode || 'keep_mine'

            return (
              <div key={field} className="rounded-xl border p-4 space-y-3 bg-card">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-sm">{getFieldLabel(field)}</span>
                  <Badge variant="outline" className="text-amber-600 dark:text-amber-400 border-amber-500/30">
                    {t('distribution.conflicts.badge')}
                  </Badge>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  <div className="rounded border bg-muted/30 p-2.5 space-y-1">
                    <span className="font-medium text-muted-foreground">
                      {t('distribution.conflicts.mode_keep_mine')} (Local)
                    </span>
                    <pre className="font-mono max-h-28 overflow-auto whitespace-pre-wrap break-all text-[11px]">
                      {stringifyContent(conflict?.local)}
                    </pre>
                  </div>
                  <div className="rounded border bg-muted/30 p-2.5 space-y-1">
                    <span className="font-medium text-muted-foreground">
                      {t('distribution.conflicts.mode_keep_upstream')} (Upstream)
                    </span>
                    <pre className="font-mono max-h-28 overflow-auto whitespace-pre-wrap break-all text-[11px]">
                      {stringifyContent(conflict?.upstream)}
                    </pre>
                  </div>
                </div>

                <div className="space-y-2 pt-1">
                  <Label className="text-xs font-medium">{t('distribution.conflicts.choose_resolution')}</Label>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant={currentMode === 'keep_mine' ? 'default' : 'outline'}
                      onClick={() => handleModeChange(field, 'keep_mine')}
                      disabled={isApplying}
                    >
                      {t('distribution.conflicts.mode_keep_mine')}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant={currentMode === 'keep_upstream' ? 'default' : 'outline'}
                      onClick={() => handleModeChange(field, 'keep_upstream')}
                      disabled={isApplying}
                    >
                      {t('distribution.conflicts.mode_keep_upstream')}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant={currentMode === 'manual' ? 'default' : 'outline'}
                      onClick={() => handleModeChange(field, 'manual')}
                      disabled={isApplying}
                    >
                      {t('distribution.conflicts.mode_manual')}
                    </Button>
                  </div>
                </div>

                {currentMode === 'manual' && (
                  <div className="space-y-1.5 pt-1">
                    <Label className="text-xs">{t('distribution.conflicts.mode_manual')}:</Label>
                    <Textarea
                      className="font-mono text-xs"
                      rows={4}
                      value={manualValues[field] ?? ''}
                      onChange={(e) => handleManualValueChange(field, e.target.value)}
                      placeholder={t('distribution.conflicts.manual_input_placeholder')}
                      disabled={isApplying}
                    />
                  </div>
                )}
              </div>
            )
          })}

          {error && <p className="text-xs text-destructive">{error}</p>}
        </div>

        <DialogFooter className="pt-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isApplying}
          >
            {t('setup.cancel')}
          </Button>
          <Button onClick={handleSubmit} disabled={isApplying}>
            {isApplying ? t('distribution.conflicts.applying') : t('distribution.conflicts.btn_apply')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
