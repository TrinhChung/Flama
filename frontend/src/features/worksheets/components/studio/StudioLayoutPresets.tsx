import { useTranslation } from 'react-i18next'
import {
  Check,
  RotateCcw,
  Sparkles,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { isLayoutPresetActive, layoutPresetsFor, type LayoutPreset } from '../../config/layoutPresets'
import type { StudioLayoutTabProps } from './StudioLayoutTab'

function PresetOptionButton({
  preset,
  isActive,
  onApply,
}: {
  preset: LayoutPreset
  isActive: boolean
  onApply: (preset: LayoutPreset) => void
}) {
  const { t } = useTranslation('worksheets')
  const label = preset.labelKey ? t(preset.labelKey, preset.label) : preset.label
  const description = preset.descriptionKey ? t(preset.descriptionKey, preset.description) : preset.description

  return (
    <button
      type="button"
      onClick={() => onApply(preset)}
      className={`p-2 rounded-lg border-2 text-left transition-all relative ${
        isActive
          ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
          : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
      }`}
    >
      <div className="flex items-center justify-between">
        <div className={`text-xs font-bold ${isActive ? 'text-primary' : 'text-foreground'}`}>
          {preset.icon && `${preset.icon} `}{label}
        </div>
        {isActive && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
      </div>
      <div className={`text-[10px] line-clamp-1 ${isActive ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
        {description}
      </div>
    </button>
  )
}

export function StudioLayoutPresets({
  currentTemplate,
  layoutOptions,
  setLayoutOptions,
  activePresetId,
  setActivePresetId,
  handleResetCurrentTemplateDefaults,
}: Pick<
  StudioLayoutTabProps,
  | 'currentTemplate'
  | 'layoutOptions'
  | 'setLayoutOptions'
  | 'activePresetId'
  | 'setActivePresetId'
  | 'handleResetCurrentTemplateDefaults'
>) {
  const { t } = useTranslation('worksheets')
  if (!currentTemplate) return null
  const presets = layoutPresetsFor(currentTemplate)

  const applyPreset = (preset: LayoutPreset) => {
    setActivePresetId(preset.id)
    setLayoutOptions((prev) => ({ ...prev, ...preset.options }))
    toast.success(preset.toastKey ? t(preset.toastKey, preset.toast) : preset.toast)
  }

  return (
    <div className="space-y-2.5 bg-card p-3.5 rounded-xl border border-border/70 shadow-xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Sparkles className="size-3.5 text-primary" />
          <span className="text-xs font-bold text-foreground">
            {t('studio.layout_tab.presets_title', 'Bố cục mẫu 1-chạm (Quick Presets)')}
          </span>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleResetCurrentTemplateDefaults}
          className="h-6 text-[10.5px] px-2 text-muted-foreground hover:text-foreground"
          title={t('studio.layout_tab.reset_defaults_title', 'Khôi phục lại thiết lập mặc định tối ưu của mẫu này')}
        >
          <RotateCcw className="size-3 mr-1" />
          <span>{t('studio.layout_tab.reset_defaults', 'Mặc định tối ưu')}</span>
        </Button>
      </div>

      {/* Presets according to current template */}
      {presets.length > 0 && (
        <div className="grid grid-cols-3 gap-1.5">
          {presets.map((preset) => (
            <PresetOptionButton
              key={preset.id}
              preset={preset}
              isActive={isLayoutPresetActive(preset, activePresetId, layoutOptions)}
              onApply={applyPreset}
            />
          ))}
        </div>
      )}
    </div>
  )
}
