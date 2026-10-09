import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  ArrowLeft,
  HelpCircle,
  Plus,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import '@/shared/config/i18n'
import { AmbientBackground } from '@/components/ambient-background'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Page, PageHeader } from '@/shared/components/Page'
import { SpotlightTour } from '@/shared/components/SpotlightTour'

import { GUIDE_STORAGE_KEY, getGuideTourSteps } from '../components/guide/guideTourSteps'
import { GuidePromptTab } from '../components/guide/GuidePromptTab'
import { GuideTechTab } from '../components/guide/GuideTechTab'
import { GuideStepsTab } from '../components/guide/GuideStepsTab'
import { GuideRulesTab } from '../components/guide/GuideRulesTab'

export function NoteTypeGuidePage() {
  const { t } = useTranslation('note_types')
  const [copiedMaster, setCopiedMaster] = useState(false)
  const [copiedVocab, setCopiedVocab] = useState(false)
  const [copiedGrammar, setCopiedGrammar] = useState(false)
  const [tourOpen, setTourOpen] = useState(false)

  const tourSteps = useMemo(() => getGuideTourSteps(t), [t])

  // Auto-launch guide tour for first-time visitors
  useEffect(() => {
    const completed = localStorage.getItem(GUIDE_STORAGE_KEY)
    if (!completed) {
      const timer = setTimeout(() => {
        setTourOpen(true)
      }, 500)
      return () => clearTimeout(timer)
    }
  }, [])

  const copyToClipboard = (text: string, type: 'master' | 'vocab' | 'grammar') => {
    navigator.clipboard.writeText(text).then(() => {
      if (type === 'master') {
        setCopiedMaster(true)
        setTimeout(() => setCopiedMaster(false), 2000)
      } else if (type === 'vocab') {
        setCopiedVocab(true)
        setTimeout(() => setCopiedVocab(false), 2000)
      } else {
        setCopiedGrammar(true)
        setTimeout(() => setCopiedGrammar(false), 2000)
      }
      toast.success(t('guide.prompt_tab.copied_toast_title'), {
        description: t('guide.prompt_tab.copied_toast_desc'),
      })
    })
  }

  return (
    <Page className="w-full max-w-6xl px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-6">
      <AmbientBackground intensity="subtle" />

      {/* Standardized Flama PageHeader */}
      <div data-tour="guide-header">
        <PageHeader
          title={t('guide.header.title')}
          description={t('guide.header.description')}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setTourOpen(true)}
                className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-xl"
              >
                <HelpCircle className="size-3.5 mr-1.5 text-primary" />
                {t('guide.header.tour_btn')}
              </Button>
              <Button variant="outline" size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-xl">
                <Link to="/flashcards/note-types">
                  <ArrowLeft className="size-3.5 mr-1.5" /> {t('guide.header.manager_link')}
                </Link>
              </Button>
              <Button
                size="sm"
                asChild
                data-tour="guide-start-btn"
                className="h-8 sm:h-9 px-3 text-xs font-bold rounded-xl shadow-xs"
              >
                <Link to="/flashcards/note-types">
                  <Plus className="size-3.5 mr-1.5" /> {t('guide.header.start_btn')}
                </Link>
              </Button>
            </div>
          }
        />
      </div>

      {/* Main Tabs Container */}
      <Tabs defaultValue="prompt" className="space-y-6">
        <div data-tour="guide-tabs">
          <TabsList className="grid grid-cols-2 sm:grid-cols-4 w-full h-auto p-1 rounded-2xl bg-muted/60 gap-1">
            <TabsTrigger value="prompt" className="h-9 sm:h-10 text-xs sm:text-sm font-semibold rounded-xl">
              {t('guide.tabs.prompt')}
            </TabsTrigger>
            <TabsTrigger value="tech" className="h-9 sm:h-10 text-xs sm:text-sm font-semibold rounded-xl">
              {t('guide.tabs.tech')}
            </TabsTrigger>
            <TabsTrigger value="steps" className="h-9 sm:h-10 text-xs sm:text-sm font-semibold rounded-xl">
              {t('guide.tabs.steps')}
            </TabsTrigger>
            <TabsTrigger value="rules" className="h-9 sm:h-10 text-xs sm:text-sm font-semibold rounded-xl">
              {t('guide.tabs.rules')}
            </TabsTrigger>
          </TabsList>
        </div>

        {/* TAB 1: MASTER PROMPT */}
        <TabsContent value="prompt" className="space-y-6">
          <GuidePromptTab
            onCopy={copyToClipboard}
            copiedMaster={copiedMaster}
            copiedVocab={copiedVocab}
            copiedGrammar={copiedGrammar}
          />
        </TabsContent>

        {/* TAB 2: TECHNOLOGY & SYNTAX */}
        <TabsContent value="tech" className="space-y-6">
          <GuideTechTab />
        </TabsContent>

        {/* TAB 3: STEP BY STEP */}
        <TabsContent value="steps" className="space-y-4">
          <GuideStepsTab />
        </TabsContent>

        {/* TAB 4: RULES */}
        <TabsContent value="rules" className="space-y-4">
          <GuideRulesTab />
        </TabsContent>
      </Tabs>

      {/* Interactive Spotlight Tour for Guide Page */}
      <SpotlightTour
        steps={tourSteps}
        isOpen={tourOpen}
        onClose={() => {
          localStorage.setItem(GUIDE_STORAGE_KEY, 'true')
          setTourOpen(false)
        }}
        onComplete={() => {
          localStorage.setItem(GUIDE_STORAGE_KEY, 'true')
          setTourOpen(false)
        }}
      />
    </Page>
  )
}
