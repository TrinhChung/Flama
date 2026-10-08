import { useTranslation } from 'react-i18next'
import { Code2, Layers, Volume2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export function GuideTechTab() {
  const { t } = useTranslation('note_types')

  return (
    <div className="space-y-6">
      <div className="grid sm:grid-cols-3 gap-4">
        <Card className="p-4 border-border/80 rounded-2xl space-y-2 bg-card">
          <div className="p-2 w-fit rounded-xl bg-primary/10 text-primary">
            <Code2 className="size-5" />
          </div>
          <h4 className="text-sm font-bold text-foreground">
            {t('guide.tech_tab.card1_title')}
          </h4>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {t('guide.tech_tab.card1_desc')}
          </p>
        </Card>

        <Card className="p-4 border-border/80 rounded-2xl space-y-2 bg-card">
          <div className="p-2 w-fit rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            <Volume2 className="size-5" />
          </div>
          <h4 className="text-sm font-bold text-foreground">
            {t('guide.tech_tab.card2_title')}
          </h4>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {t('guide.tech_tab.card2_desc')}
          </p>
        </Card>

        <Card className="p-4 border-border/80 rounded-2xl space-y-2 bg-card">
          <div className="p-2 w-fit rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400">
            <Layers className="size-5" />
          </div>
          <h4 className="text-sm font-bold text-foreground">
            {t('guide.tech_tab.card3_title')}
          </h4>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {t('guide.tech_tab.card3_desc')}
          </p>
        </Card>
      </div>

      <Card className="border-border/80 shadow-xs rounded-2xl bg-card">
        <CardHeader className="p-4 sm:p-5 pb-2">
          <CardTitle className="text-sm font-bold text-foreground">
            {t('guide.tech_tab.field_types_title')}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-2">
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <div className="p-3 rounded-xl border border-border/70 bg-muted/20 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="default" className="text-xs font-mono">text</Badge>
                <span className="text-xs font-bold text-foreground">
                  {t('guide.tech_tab.ft_text_title')}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {t('guide.tech_tab.ft_text_desc')}
              </p>
            </div>

            <div className="p-3 rounded-xl border border-border/70 bg-muted/20 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-xs font-mono">richtext</Badge>
                <span className="text-xs font-bold text-foreground">
                  {t('guide.tech_tab.ft_richtext_title')}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {t('guide.tech_tab.ft_richtext_desc')}
              </p>
            </div>

            <div className="p-3 rounded-xl border border-border/70 bg-muted/20 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-xs font-mono">audio</Badge>
                <span className="text-xs font-bold text-foreground">
                  {t('guide.tech_tab.ft_audio_title')}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {t('guide.tech_tab.ft_audio_desc')}
              </p>
            </div>

            <div className="p-3 rounded-xl border border-border/70 bg-muted/20 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-xs font-mono">image</Badge>
                <span className="text-xs font-bold text-foreground">
                  {t('guide.tech_tab.ft_image_title')}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {t('guide.tech_tab.ft_image_desc')}
              </p>
            </div>

            <div className="p-3 rounded-xl border border-border/70 bg-muted/20 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-xs font-mono">markdown</Badge>
                <span className="text-xs font-bold text-foreground">
                  {t('guide.tech_tab.ft_markdown_title')}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {t('guide.tech_tab.ft_markdown_desc')}
              </p>
            </div>

            <div className="p-3 rounded-xl border border-border/70 bg-muted/20 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-xs font-mono">diagram</Badge>
                <span className="text-xs font-bold text-foreground">
                  {t('guide.tech_tab.ft_diagram_title')}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {t('guide.tech_tab.ft_diagram_desc')}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
