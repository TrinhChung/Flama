import { useTranslation } from 'react-i18next'
import { Bot, Check, Copy, Lightbulb } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  MASTER_PROMPT,
  EXAMPLE_VOCAB_PROMPT,
  EXAMPLE_GRAMMAR_PROMPT,
} from './guidePrompts'

interface GuidePromptTabProps {
  onCopy: (text: string, type: 'master' | 'vocab' | 'grammar') => void
  copiedMaster: boolean
  copiedVocab: boolean
  copiedGrammar: boolean
}

export function GuidePromptTab({
  onCopy,
  copiedMaster,
  copiedVocab,
  copiedGrammar,
}: GuidePromptTabProps) {
  const { t } = useTranslation('note_types')

  return (
    <div className="space-y-6">
      <Card data-tour="guide-master-prompt" className="border-border/80 shadow-xs rounded-2xl bg-card">
        <CardHeader className="p-4 sm:p-6 pb-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-1">
              <CardTitle className="text-base sm:text-lg font-bold text-foreground flex items-center gap-2">
                <Bot className="size-4 text-primary" /> {t('guide.prompt_tab.master_title')}
              </CardTitle>
              <CardDescription className="text-xs sm:text-sm text-muted-foreground">
                {t('guide.prompt_tab.master_desc')}
              </CardDescription>
            </div>
            <Button
              onClick={() => onCopy(MASTER_PROMPT, 'master')}
              className="h-9 px-4 text-xs font-bold rounded-xl shadow-xs shrink-0 bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {copiedMaster ? <Check className="size-3.5 mr-1.5 text-emerald-300" /> : <Copy className="size-3.5 mr-1.5" />}
              {copiedMaster ? t('guide.prompt_tab.copied_master') : t('guide.prompt_tab.copy_master')}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-4 sm:p-6 pt-0 space-y-4">
          <div className="relative">
            <pre className="p-4 rounded-xl bg-muted/60 border border-border/80 font-mono text-xs leading-relaxed text-foreground select-all whitespace-pre-wrap max-h-96 overflow-y-auto">
              {MASTER_PROMPT}
            </pre>
          </div>

          <div className="p-3.5 rounded-xl bg-primary/5 border border-primary/20 text-xs text-foreground flex items-start gap-2.5">
            <Lightbulb className="size-4 text-primary shrink-0 mt-0.5" />
            <div>
              <span className="font-bold text-primary">{t('guide.prompt_tab.quick_tip_title')}</span>{' '}
              {t('guide.prompt_tab.quick_tip_text')}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Examples Grid */}
      <div data-tour="guide-example-prompts" className="grid md:grid-cols-2 gap-5">
        <Card className="border-border/80 shadow-xs rounded-2xl bg-card flex flex-col justify-between">
          <CardHeader className="p-4 sm:p-5 pb-2">
            <div className="flex items-center justify-between">
              <Badge variant="outline" className="text-xs font-semibold text-primary border-primary/30">
                {t('guide.prompt_tab.ex1_badge')}
              </Badge>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onCopy(EXAMPLE_VOCAB_PROMPT, 'vocab')}
                className="h-7 px-2.5 text-xs font-medium rounded-lg hover:bg-muted"
              >
                {copiedVocab ? <Check className="size-3 mr-1 text-emerald-500" /> : <Copy className="size-3 mr-1" />}
                {copiedVocab ? t('guide.prompt_tab.copied_btn') : t('guide.prompt_tab.copy_btn')}
              </Button>
            </div>
            <CardTitle className="text-sm font-bold text-foreground mt-2">
              {t('guide.prompt_tab.ex1_title')}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 sm:p-5 pt-0">
            <pre className="p-3 rounded-xl bg-muted/40 border border-border/60 font-mono text-[11px] leading-relaxed text-muted-foreground whitespace-pre-wrap">
              {EXAMPLE_VOCAB_PROMPT}
            </pre>
          </CardContent>
        </Card>

        <Card className="border-border/80 shadow-xs rounded-2xl bg-card flex flex-col justify-between">
          <CardHeader className="p-4 sm:p-5 pb-2">
            <div className="flex items-center justify-between">
              <Badge variant="outline" className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 border-emerald-500/30">
                {t('guide.prompt_tab.ex2_badge')}
              </Badge>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onCopy(EXAMPLE_GRAMMAR_PROMPT, 'grammar')}
                className="h-7 px-2.5 text-xs font-medium rounded-lg hover:bg-muted"
              >
                {copiedGrammar ? <Check className="size-3 mr-1 text-emerald-500" /> : <Copy className="size-3 mr-1" />}
                {copiedGrammar ? t('guide.prompt_tab.copied_btn') : t('guide.prompt_tab.copy_btn')}
              </Button>
            </div>
            <CardTitle className="text-sm font-bold text-foreground mt-2">
              {t('guide.prompt_tab.ex2_title')}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 sm:p-5 pt-0">
            <pre className="p-3 rounded-xl bg-muted/40 border border-border/60 font-mono text-[11px] leading-relaxed text-muted-foreground whitespace-pre-wrap">
              {EXAMPLE_GRAMMAR_PROMPT}
            </pre>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
