import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link2, LoaderCircle, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import type { SocialLink } from '../types/profile'

const SOCIAL_PLATFORMS = [
  'website',
  'github',
  'youtube',
  'facebook',
  'x',
  'linkedin',
  'discord',
  'other',
] as const

export interface ProfileEditSocialLinksTabProps {
  initialLinks: SocialLink[]
  isPending: boolean
  onCancel: () => void
  onSave: (links: SocialLink[]) => void
}

export function ProfileEditSocialLinksTab({
  initialLinks,
  isPending,
  onCancel,
  onSave,
}: ProfileEditSocialLinksTabProps) {
  const { t } = useTranslation('profile')
  const [socialLinks, setSocialLinks] = useState<SocialLink[]>(initialLinks)

  useEffect(() => {
    setSocialLinks(initialLinks)
  }, [initialLinks])

  const handleAddSocialLink = () => {
    if (socialLinks.length >= 10) {
      toast.warning(t('edit.toast.max_links'))
      return
    }
    setSocialLinks((prev) => [
      ...prev,
      { type: 'website', url: '', label: '' },
    ])
  }

  const handleUpdateSocialLink = (
    index: number,
    field: keyof SocialLink,
    value: string
  ) => {
    setSocialLinks((prev) => {
      const copy = [...prev]
      copy[index] = { ...copy[index], [field]: value }
      return copy
    })
  }

  const handleRemoveSocialLink = (index: number) => {
    setSocialLinks((prev) => prev.filter((_, i) => i !== index))
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSave(socialLinks.filter((l) => Boolean(l.url.trim())))
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 pt-2">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          {t('edit.links.description')}
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleAddSocialLink}
          className="h-8 gap-1 text-xs font-semibold self-start sm:self-auto shrink-0 cursor-pointer"
        >
          <Plus className="size-3.5" />
          {t('edit.links.btn_add')}
        </Button>
      </div>

      {socialLinks.length === 0 ? (
        <div className="py-8 text-center rounded-xl border border-dashed border-border/80">
          <Link2 className="size-8 mx-auto text-muted-foreground/40 mb-2" />
          <p className="text-xs text-muted-foreground">
            {t('edit.links.empty')}
          </p>
        </div>
      ) : (
        <div className="space-y-2.5 max-h-[300px] overflow-y-auto pr-1">
          {socialLinks.map((link, idx) => (
            <div
              key={idx}
              className="flex flex-col sm:flex-row sm:items-center gap-2 rounded-lg border border-border/60 p-2.5 bg-muted/20"
            >
              <div className="flex items-center gap-2 w-full sm:w-auto">
                <NativeSelect
                  value={link.type}
                  onChange={(e) =>
                    handleUpdateSocialLink(idx, 'type', e.target.value)
                  }
                  className="w-full sm:w-32 shrink-0 text-xs"
                >
                  {SOCIAL_PLATFORMS.map((platform) => (
                    <NativeSelectOption key={platform} value={platform}>
                      {t(`edit.platforms.${platform}` as const)}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => handleRemoveSocialLink(idx)}
                  className="size-8 p-0 text-destructive hover:bg-destructive/10 shrink-0 sm:hidden cursor-pointer"
                  title={t('edit.links.btn_delete')}
                >
                  <Trash2 className="size-4" />
                </Button>
              </div>

              <Input
                value={link.url}
                onChange={(e) =>
                  handleUpdateSocialLink(idx, 'url', e.target.value)
                }
                placeholder={t('edit.links.url_placeholder')}
                className="text-xs flex-1"
              />

              <Input
                value={link.label || ''}
                onChange={(e) =>
                  handleUpdateSocialLink(idx, 'label', e.target.value)
                }
                placeholder={t('edit.links.label_placeholder')}
                className="w-full sm:w-28 shrink-0 text-xs"
              />

              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => handleRemoveSocialLink(idx)}
                className="size-8 p-0 text-destructive hover:bg-destructive/10 shrink-0 hidden sm:flex cursor-pointer"
                title={t('edit.links.btn_delete')}
              >
                <Trash2 className="size-4" />
              </Button>
            </div>
          ))}
        </div>
      )}

      <DialogFooter className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={isPending}
          className="w-full sm:w-auto"
        >
          {t('edit.btn_cancel')}
        </Button>
        <Button type="submit" disabled={isPending} className="w-full sm:w-auto">
          {isPending ? (
            <>
              <LoaderCircle className="mr-2 size-4 animate-spin" />
              {t('edit.btn_saving')}
            </>
          ) : (
            t('edit.links.btn_save')
          )}
        </Button>
      </DialogFooter>
    </form>
  )
}
