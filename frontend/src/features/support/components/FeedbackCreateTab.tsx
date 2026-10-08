import {
  CheckCircle2,
  Eye,
  Image as ImageIcon,
  Info,
  Link as LinkIcon,
  Loader2,
  RefreshCw,
  Send,
  Trash2,
  Upload,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useFeedbackForm } from '../hooks/useFeedbackForm'
import { getCommonScreenPresets } from '../utils/supportHelpers'

interface FeedbackCreateTabProps {
  form: ReturnType<typeof useFeedbackForm>
  onPreviewImage: (url: string) => void
}

export function FeedbackCreateTab({ form, onPreviewImage }: FeedbackCreateTabProps) {
  const { t } = useTranslation('support')
  const {
    category,
    setCategory,
    urlPath,
    setUrlPath,
    title,
    setTitle,
    description,
    setDescription,
    reproduceSteps,
    setReproduceSteps,
    attachedUrls,
    setAttachedUrls,
    isUploading,
    isDragging,
    fileInputRef,
    resolvedScreenName,
    activeCategoryConfig,
    categories,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handleFileChange,
    handleSubmitTicket,
    fillCurrentUrl,
    createTicketMutation,
  } = form

  return (
    <form onSubmit={handleSubmitTicket} className="space-y-6">
      {/* 1. Compact Category Selection Grid */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <Label className="text-xs sm:text-sm font-bold text-foreground flex items-center gap-1.5">
            <span className="flex items-center justify-center size-5 rounded-full bg-primary/15 text-primary text-xs font-bold">
              1
            </span>
            <span>{t('feedback.step_category')}</span>
          </Label>
          <span className="text-[11px] text-muted-foreground">
            {t('feedback.step_category_hint')}
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          {categories.map((cat) => {
            const IconComp = cat.icon
            const isSelected = category === cat.key

            return (
              <button
                key={cat.key}
                type="button"
                onClick={() => setCategory(cat.key)}
                className={`flex items-center gap-2.5 p-3 rounded-xl border text-left transition-all cursor-pointer select-none ${
                  isSelected
                    ? `${cat.activeBorder} ${cat.activeBg} shadow-xs font-bold`
                    : 'bg-card border-border/80 text-foreground hover:bg-muted/40 hover:border-border font-medium shadow-2xs'
                }`}
              >
                <div
                  className={`p-1.5 rounded-lg shrink-0 ${
                    isSelected ? 'bg-background/80' : 'bg-muted/50'
                  }`}
                >
                  <IconComp className={`size-4 ${cat.color}`} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-bold truncate text-foreground">
                    {cat.title}
                  </div>
                  <div className="text-[10px] text-muted-foreground truncate hidden sm:block">
                    {cat.subtitle}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* 2. Screen URL Auto Detection */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <Label className="text-xs sm:text-sm font-bold text-foreground flex items-center gap-1.5">
            <span className="flex items-center justify-center size-5 rounded-full bg-primary/15 text-primary text-xs font-bold">
              2
            </span>
            <LinkIcon className="size-3.5 text-primary" />
            <span>{t('feedback.step_screen')}</span>
          </Label>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={fillCurrentUrl}
            className="rounded-full text-xs h-7 gap-1 px-3 bg-card border-border/80 hover:bg-muted font-medium"
          >
            <RefreshCw className="size-3 text-primary" /> {t('feedback.get_current_url')}
          </Button>
        </div>

        <div className="space-y-2">
          <Input
            placeholder={t('feedback.url_placeholder')}
            value={urlPath}
            onChange={(e) => setUrlPath(e.target.value)}
            className="bg-card border-border/80 font-mono text-xs h-10 shadow-2xs rounded-xl text-foreground"
          />

          {/* Quick Pick Presets */}
          <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
            <span className="text-[11px] text-muted-foreground mr-1">
              {t('feedback.quick_presets_label')}
            </span>
            {getCommonScreenPresets(t).map((preset) => (
              <button
                key={preset.url}
                type="button"
                onClick={() => setUrlPath(preset.url)}
                className="text-[11px] px-2.5 py-1 rounded-lg border border-border/80 bg-card hover:bg-muted text-foreground font-medium transition-colors cursor-pointer shadow-2xs"
              >
                {preset.label}
              </button>
            ))}
          </div>

          {/* Recognized Screen Info Banner */}
          <div className="text-xs text-muted-foreground flex items-center gap-2 bg-card p-3 rounded-xl border border-border/80 shadow-2xs">
            <Info className="size-4 text-primary shrink-0" />
            <span>
              {t('feedback.recognized_screen')}{' '}
              <strong className="text-foreground font-semibold">
                {resolvedScreenName}
              </strong>
            </span>
          </div>
        </div>
      </div>

      {/* 3. Title & Description */}
      <div className="space-y-4">
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label className="text-xs sm:text-sm font-bold text-foreground flex items-center gap-1.5">
              <span className="flex items-center justify-center size-5 rounded-full bg-primary/15 text-primary text-xs font-bold">
                3
              </span>
              <span>{t('feedback.step_title')}</span>
            </Label>
            <span className="text-[11px] text-muted-foreground">{t('feedback.optional')}</span>
          </div>
          <Input
            placeholder={activeCategoryConfig.placeholderTitle}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            className="bg-card border-border/80 text-xs sm:text-sm h-10 shadow-2xs rounded-xl text-foreground"
          />
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label className="text-xs sm:text-sm font-bold text-foreground flex items-center gap-1.5">
              <span className="flex items-center justify-center size-5 rounded-full bg-primary/15 text-primary text-xs font-bold">
                4
              </span>
              <span>
                {t('feedback.step_desc')} <strong className="text-rose-500">*</strong>
              </span>
            </Label>
            <span className="text-[11px] text-muted-foreground font-mono">
              {t('feedback.char_count', {
                count: description.length,
                max: 2000,
                defaultValue: `${description.length}/2000 ký tự`,
              })}
            </span>
          </div>
          <Textarea
            placeholder={activeCategoryConfig.placeholderDesc}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={2000}
            className="bg-card border-border/80 min-h-32 rounded-xl text-xs sm:text-sm leading-relaxed p-3.5 shadow-2xs text-foreground"
            required
          />
        </div>

        {/* Reproduce steps (Specific to Bug category) */}
        {category === 'bug' && (
          <div className="space-y-1.5 pt-1">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-bold text-foreground flex items-center gap-1.5">
                <span>{t('feedback.reproduce_steps')}</span>
              </Label>
              <span className="text-[11px] text-muted-foreground">
                {t('feedback.optional')}
              </span>
            </div>
            <Textarea
              placeholder={t('feedback.reproduce_placeholder')}
              value={reproduceSteps}
              onChange={(e) => setReproduceSteps(e.target.value)}
              className="bg-card border-border/80 min-h-24 rounded-xl text-xs font-mono p-3 leading-relaxed shadow-2xs text-foreground"
            />
          </div>
        )}
      </div>

      {/* 4. Screenshot Uploader & Drag-and-Drop */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <Label className="text-xs sm:text-sm font-bold text-foreground flex items-center gap-1.5">
            <span className="flex items-center justify-center size-5 rounded-full bg-primary/15 text-primary text-xs font-bold">
              5
            </span>
            <ImageIcon className="size-4 text-primary" />
            <span>{t('feedback.step_screenshots', { count: attachedUrls.length })}</span>
          </Label>
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 text-[10px] font-mono bg-card rounded border border-border/80">
              Ctrl
            </kbd>
            <span>+</span>
            <kbd className="px-1.5 py-0.5 text-[10px] font-mono bg-card rounded border border-border/80">
              V
            </kbd>
            <span>{t('feedback.paste_hint')}</span>
          </span>
        </div>

        {/* Dropzone & Preview Grid */}
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-3">
            {/* Uploaded Thumbnails */}
            {attachedUrls.map((url, idx) => (
              <div
                key={idx}
                className="relative group size-20 rounded-xl border border-border/80 overflow-hidden shadow-2xs bg-card transition-all hover:ring-2 hover:ring-primary/60"
              >
                <img
                  src={url}
                  alt={`Screenshot ${idx + 1}`}
                  className="size-full object-cover"
                />

                {/* Action Overlay */}
                <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                  <button
                    type="button"
                    onClick={() => onPreviewImage(url)}
                    className="p-1 rounded-full bg-white/20 hover:bg-white/40 text-white transition-colors cursor-pointer"
                    title={t('feedback.view_large_image', 'Xem ảnh lớn')}
                  >
                    <Eye className="size-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setAttachedUrls((prev) => prev.filter((_, i) => i !== idx))
                    }
                    className="p-1 rounded-full bg-rose-600/80 hover:bg-rose-600 text-white transition-colors cursor-pointer"
                    title={t('feedback.delete_image', 'Xóa ảnh')}
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </div>
              </div>
            ))}

            {/* Upload Action Tile */}
            {attachedUrls.length < 5 && (
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`flex flex-col items-center justify-center size-20 rounded-xl border-2 border-dashed transition-all cursor-pointer select-none ${
                  isDragging
                    ? 'border-primary bg-primary/10 scale-105'
                    : 'border-border/80 hover:border-primary bg-card hover:bg-muted/40 shadow-2xs'
                }`}
              >
                {isUploading ? (
                  <Loader2 className="size-5 animate-spin text-primary" />
                ) : (
                  <>
                    <Upload className="size-4 text-muted-foreground mb-1" />
                    <span className="text-[10px] text-muted-foreground font-semibold">
                      {t('feedback.upload_button')}
                    </span>
                  </>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleFileChange}
                  className="hidden"
                  disabled={isUploading}
                />
              </div>
            )}
          </div>

          <p className="text-[11px] text-muted-foreground">{t('feedback.upload_rules')}</p>
        </div>
      </div>

      {/* Submit Action */}
      <div className="pt-4 border-t flex flex-wrap items-center justify-between gap-4">
        <div className="text-xs text-muted-foreground flex items-center gap-1.5">
          <CheckCircle2 className="size-4 text-emerald-600" />
          <span>{t('feedback.submit_note')}</span>
        </div>

        <Button
          type="submit"
          size="lg"
          className="rounded-full px-8 font-bold shadow-md gap-2 text-sm"
          disabled={createTicketMutation.isPending || isUploading || !description.trim()}
        >
          {createTicketMutation.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" /> {t('feedback.submitting')}
            </>
          ) : (
            <>
              <Send className="size-4" /> {t('feedback.submit_button')}
            </>
          )}
        </Button>
      </div>
    </form>
  )
}
