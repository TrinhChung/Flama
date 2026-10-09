import { useState, type ComponentType } from 'react'
import {
  ArrowRight,
  Award,
  BarChart3,
  Brain,
  CalendarCheck2,
  Check,
  Clock3,
  Flame,
  Focus,
  Gem,
  Layers3,
  PencilLine,
  Rocket,
  Search,
  ShieldCheck,
  Smartphone,
  Target,
  TrendingUp,
  Trophy,
  Upload,
  Zap,
} from 'lucide-react'
import { Link, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { useBootstrap } from '@/shared/api/bootstrap'

type IconType = ComponentType<{ className?: string }>

function SectionHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow?: string
  title: string
  description?: string
}) {
  return (
    <div className="mx-auto mb-10 max-w-3xl space-y-3 text-center md:mb-14">
      {eyebrow ? (
        <p className="text-xs font-semibold tracking-[0.2em] text-primary uppercase">
          {eyebrow}
        </p>
      ) : null}
      <h2 className="text-3xl font-bold tracking-tight text-balance md:text-4xl">
        {title}
      </h2>
      {description ? (
        <p className="text-base leading-7 text-muted-foreground md:text-lg">
          {description}
        </p>
      ) : null}
    </div>
  )
}

function ReviewButtons() {
  const { t } = useTranslation('landing')
  return (
    <div className="grid grid-cols-4 gap-1.5 text-center text-[11px] font-semibold">
      <span className="rounded-md bg-rose-500/10 px-1.5 py-1.5 text-rose-700 dark:text-rose-300">
        {t('hero.review_buttons.again')}
      </span>
      <span className="rounded-md bg-amber-500/10 px-1.5 py-1.5 text-amber-700 dark:text-amber-300">
        {t('hero.review_buttons.hard')}
      </span>
      <span className="rounded-md bg-emerald-500/10 px-1.5 py-1.5 text-emerald-700 dark:text-emerald-300">
        {t('hero.review_buttons.good')}
      </span>
      <span className="rounded-md bg-sky-500/10 px-1.5 py-1.5 text-sky-700 dark:text-sky-300">
        {t('hero.review_buttons.easy')}
      </span>
    </div>
  )
}

function HeroCard({
  className,
  category,
  categoryClassName,
  front,
  back,
}: {
  className: string
  category: string
  categoryClassName: string
  front: React.ReactNode
  back: React.ReactNode
}) {
  return (
    <div
      className={`absolute inset-x-0 mx-auto w-[min(92%,25rem)] rounded-3xl border bg-card p-5 shadow-2xl transition-transform duration-500 sm:p-6 ${className}`}
    >
      <Badge className={categoryClassName} variant="secondary">{category}</Badge>
      <div className="flex min-h-24 items-center justify-center py-5 text-center text-2xl font-bold">
        {front}
      </div>
      <div className="border-t pt-4">
        <div className="mb-4 text-center text-base font-semibold">{back}</div>
        <ReviewButtons />
      </div>
    </div>
  )
}

function ProductPreview() {
  const { t } = useTranslation('landing')
  return (
    <section className="relative overflow-hidden border-y bg-muted/20 py-16 md:py-24">
      <div className="pointer-events-none absolute inset-0 -z-20 bg-[radial-gradient(circle_at_50%_30%,color-mix(in_oklab,var(--color-primary)_12%,transparent),transparent_50%)]" />
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[linear-gradient(to_right,color-mix(in_oklab,var(--color-border)_22%,transparent)_1px,transparent_1px),linear-gradient(to_bottom,color-mix(in_oklab,var(--color-border)_22%,transparent)_1px,transparent_1px)] bg-[size:36px_36px] [mask-image:radial-gradient(ellipse_85%_75%_at_50%_50%,black_70%,transparent_100%)]" />
      <div className="mx-auto w-full max-w-7xl px-4 md:px-6">
        <SectionHeading
          eyebrow={t('product_preview.eyebrow')}
          title={t('product_preview.title')}
          description={t('product_preview.description')}
        />
        <div className="grid gap-5 lg:grid-cols-3">
          <PreviewFrame
            path="/flashcards/notes/new"
            title={t('product_preview.frame_create.title')}
            description={t('product_preview.frame_create.description')}
            icon={PencilLine}
          >
            <div className="space-y-3">
              <div className="h-3 w-32 rounded-full bg-primary/15" />
              <div className="grid grid-cols-2 gap-3">
                <div className="h-9 rounded-lg border bg-background" />
                <div className="h-9 rounded-lg border bg-background" />
              </div>
              <div className="h-24 rounded-xl border bg-background" />
              <div className="flex gap-2">
                <div className="h-8 w-24 rounded-lg bg-primary" />
                <div className="h-8 w-20 rounded-lg border bg-background" />
              </div>
            </div>
          </PreviewFrame>
          <PreviewFrame
            path="/study?deck_id=…"
            title={t('product_preview.frame_study.title')}
            description={t('product_preview.frame_study.description')}
            icon={Brain}
          >
            <div className="space-y-4">
              <div className="flex justify-center gap-2">
                <Badge variant="secondary">{t('product_preview.frame_study.badge_new')}</Badge>
                <Badge variant="outline">{t('product_preview.frame_study.badge_learn')}</Badge>
                <Badge variant="destructive">{t('product_preview.frame_study.badge_due')}</Badge>
              </div>
              <div className="rounded-xl border bg-background p-5 text-center">
                <p className="font-semibold">{t('product_preview.frame_study.mock_front')}</p>
                <p className="mt-2 text-xs text-muted-foreground">
                  {t('product_preview.frame_study.mock_back')}
                </p>
              </div>
              <ReviewButtons />
            </div>
          </PreviewFrame>
          <PreviewFrame
            path="/browse"
            title={t('product_preview.frame_browse.title')}
            description={t('product_preview.frame_browse.description')}
            icon={Search}
          >
            <div className="grid h-44 grid-cols-[0.7fr_1.5fr] gap-3">
              <div className="space-y-2 rounded-xl border bg-background p-3">
                {[0, 1, 2, 3].map((item) => (
                  <div key={item} className="h-4 rounded bg-muted" />
                ))}
              </div>
              <div className="space-y-2 rounded-xl border bg-background p-3">
                {[0, 1, 2, 3, 4].map((item) => (
                  <div key={item} className="grid grid-cols-3 gap-2">
                    <span className="h-4 rounded bg-primary/10" />
                    <span className="h-4 rounded bg-muted" />
                    <span className="h-4 rounded bg-muted" />
                  </div>
                ))}
              </div>
            </div>
          </PreviewFrame>
        </div>
      </div>
    </section>
  )
}

function PreviewFrame({
  path,
  title,
  description,
  icon: Icon,
  children,
}: {
  path: string
  title: string
  description: string
  icon: IconType
  children: React.ReactNode
}) {
  return (
    <Card className="overflow-hidden border-border/80 shadow-none">
      <div className="flex items-center gap-1.5 border-b bg-muted/50 px-4 py-3">
        <span className="size-2.5 rounded-full bg-rose-400" />
        <span className="size-2.5 rounded-full bg-amber-400" />
        <span className="size-2.5 rounded-full bg-emerald-400" />
        <code className="ml-2 truncate text-[11px] text-muted-foreground">{path}</code>
      </div>
      <CardContent className="space-y-5 p-5">
        <div className="rounded-2xl bg-muted/35 p-4">{children}</div>
        <div className="flex gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Icon className="size-4" />
          </span>
          <div>
            <h3 className="font-semibold">{title}</h3>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function MiniDemo() {
  const { t } = useTranslation('landing')
  const [revealed, setRevealed] = useState(false)
  const [rating, setRating] = useState<'again' | 'hard' | 'good' | 'easy'>('good')
  const labels = {
    again: t('mini_demo.rating_intervals.again'),
    hard: t('mini_demo.rating_intervals.hard'),
    good: t('mini_demo.rating_intervals.good'),
    easy: t('mini_demo.rating_intervals.easy'),
  }

  const bullets = (t('mini_demo.bullets', { returnObjects: true }) as string[]) || [
    'Front/Back rõ ràng, tập trung kiến thức chính.',
    'Again/Hard/Good/Easy điều chỉnh lịch học.',
    'Phù hợp cho các phiên ôn ngắn mỗi ngày.',
  ]

  return (
    <section className="relative overflow-hidden py-16 md:py-24">
      <div className="pointer-events-none absolute inset-0 -z-20 bg-[radial-gradient(circle_at_75%_35%,color-mix(in_oklab,var(--color-primary)_16%,transparent),transparent_50%)]" />
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[linear-gradient(to_right,color-mix(in_oklab,var(--color-border)_25%,transparent)_1px,transparent_1px),linear-gradient(to_bottom,color-mix(in_oklab,var(--color-border)_25%,transparent)_1px,transparent_1px)] bg-[size:36px_36px] [mask-image:radial-gradient(ellipse_75%_65%_at_50%_50%,black_70%,transparent_100%)]" />
      <div className="mx-auto grid w-full max-w-7xl items-center gap-10 px-4 md:px-6 lg:grid-cols-[0.8fr_1.2fr]">
        <div>
          <Badge variant="secondary">{t('mini_demo.badge')}</Badge>
          <h2 className="mt-4 text-3xl font-bold tracking-tight md:text-4xl">
            {t('mini_demo.title')}
          </h2>
          <p className="mt-4 text-lg leading-8 text-muted-foreground">
            {t('mini_demo.description')}
          </p>
          <ul className="mt-6 space-y-3 text-sm">
            {bullets.map((item) => (
              <li key={item} className="flex gap-3">
                <Check className="mt-0.5 size-4 shrink-0 text-primary" />
                {item}
              </li>
            ))}
          </ul>
        </div>
        <Card className="overflow-hidden border-primary/15 bg-card shadow-xl shadow-primary/5">
          <CardContent className="space-y-5 p-5 sm:p-8">
            <div className="perspective-1000 w-full min-h-64">
              <div
                className={`relative min-h-64 w-full cursor-pointer rounded-2xl border transition-transform duration-500 transform-style-3d ${
                  revealed ? 'rotate-y-180' : ''
                }`}
                onClick={() => setRevealed((value) => !value)}
              >
                <div className="absolute inset-0 flex flex-col items-center justify-center rounded-2xl bg-muted/25 p-8 text-center backface-hidden">
                  <span className="text-xs font-semibold tracking-[0.16em] text-primary uppercase">
                    {t('mini_demo.card.front_label')}
                  </span>
                  <strong className="mt-4 text-2xl leading-relaxed">
                    {t('mini_demo.card.question')}
                  </strong>
                  <span className="mt-4 text-xs text-muted-foreground">
                    {t('mini_demo.card.front_hint')}
                  </span>
                </div>
                <div className="absolute inset-0 flex flex-col items-center justify-center rounded-2xl bg-muted/25 p-8 text-center backface-hidden rotate-y-180">
                  <span className="text-xs font-semibold tracking-[0.16em] text-primary uppercase">
                    {t('mini_demo.card.back_label')}
                  </span>
                  <strong className="mt-4 text-2xl leading-relaxed">
                    {t('mini_demo.card.answer')}
                  </strong>
                  <span className="mt-4 text-xs text-muted-foreground">
                    {t('mini_demo.card.back_hint')}
                  </span>
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {(Object.keys(labels) as Array<keyof typeof labels>).map((value) => (
                <Button
                  key={value}
                  type="button"
                  variant={rating === value ? 'default' : 'outline'}
                  onClick={() => {
                    setRating(value)
                    setRevealed(true)
                  }}
                >
                  {value[0].toUpperCase() + value.slice(1)}
                </Button>
              ))}
            </div>
            <p className="text-center text-sm text-muted-foreground">
              {t('mini_demo.schedule_label', { schedule: '___' }).split('___')[0]}
              <strong className="text-foreground">{labels[rating]}</strong>
            </p>
          </CardContent>
        </Card>
      </div>
    </section>
  )
}

function SponsorLane({
  label,
  icon: Icon,
  names,
  className,
  reverse,
}: {
  label: string
  icon: IconType
  names: string[]
  className: string
  reverse?: boolean
}) {
  const repeated = Array.from({ length: 6 }, () => names).flat()
  return (
    <div className={`flex items-center gap-3 overflow-hidden rounded-2xl border p-3 ${className}`}>
      <span className="relative z-10 flex shrink-0 items-center gap-2 rounded-xl bg-background/90 px-3 py-2 text-xs font-bold shadow-sm">
        <Icon className="size-4" />
        {label}
      </span>
      <div className="min-w-0 flex-1 overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_8%,black_92%,transparent)]">
        <div className={`landing-sponsor-track ${reverse ? 'landing-sponsor-track--reverse' : ''}`}>
          {[0, 1].map((segment) => (
            <div key={segment} className="flex shrink-0 items-center gap-8 pr-8" aria-hidden={segment === 1}>
              {repeated.map((name, index) => (
                <span key={`${segment}-${name}-${index}`} className="whitespace-nowrap text-sm font-semibold">
                  {name}
                </span>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export function LandingPage() {
  const { t } = useTranslation('landing')
  const { data } = useBootstrap()
  const authenticated = Boolean(data?.user)

  if (authenticated) {
    return <Navigate to="/dashboard" replace />
  }

  const primaryTo = '/register'
  const secondaryTo = '/login'

  const steps = [
    {
      title: t('how_it_works.steps.step_1.title'),
      description: t('how_it_works.steps.step_1.description'),
      icon: PencilLine,
    },
    {
      title: t('how_it_works.steps.step_2.title'),
      description: t('how_it_works.steps.step_2.description'),
      icon: CalendarCheck2,
    },
    {
      title: t('how_it_works.steps.step_3.title'),
      description: t('how_it_works.steps.step_3.description'),
      icon: TrendingUp,
    },
  ]

  const useCases = (t('use_cases.items', { returnObjects: true }) as string[]) || []

  const benefits = [
    {
      title: t('benefits.items.srs.title'),
      description: t('benefits.items.srs.description'),
      icon: Zap,
    },
    {
      title: t('benefits.items.due_focus.title'),
      description: t('benefits.items.due_focus.description'),
      icon: Target,
    },
    {
      title: t('benefits.items.clear_progress.title'),
      description: t('benefits.items.clear_progress.description'),
      icon: BarChart3,
    },
    {
      title: t('benefits.items.focused_experience.title'),
      description: t('benefits.items.focused_experience.description'),
      icon: Focus,
    },
  ]

  const roadmap = [
    {
      label: t('roadmap.tiers.now.label'),
      description: t('roadmap.tiers.now.description'),
      tone: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
      items: (
        t('roadmap.tiers.now.items', { returnObjects: true }) as Array<{
          title: string
          desc: string
        }>
      ).map((item) => [item.title, item.desc] as [string, string]),
    },
    {
      label: t('roadmap.tiers.next.label'),
      description: t('roadmap.tiers.next.description'),
      tone: 'bg-primary/10 text-primary',
      items: (
        t('roadmap.tiers.next.items', { returnObjects: true }) as Array<{
          title: string
          desc: string
        }>
      ).map((item) => [item.title, item.desc] as [string, string]),
    },
    {
      label: t('roadmap.tiers.later.label'),
      description: t('roadmap.tiers.later.description'),
      tone: 'bg-violet-500/10 text-violet-700 dark:text-violet-300',
      items: (
        t('roadmap.tiers.later.items', { returnObjects: true }) as Array<{
          title: string
          desc: string
        }>
      ).map((item) => [item.title, item.desc] as [string, string]),
    },
  ]

  const updates = (
    t('updates.items', { returnObjects: true }) as Array<{
      tag: string
      date: string
      title: string
      description: string
    }>
  ) || []

  const faqs = (
    t('faq.items', { returnObjects: true }) as Array<{
      question: string
      answer: string
    }>
  ) || []

  const sponsors = [
    {
      label: t('sponsors.tiers.diamond'),
      icon: Gem,
      names: ['Trịnh Văn Chung'],
      className: 'border-sky-500/25 bg-sky-500/8 text-sky-700 dark:text-sky-300',
    },
    {
      label: t('sponsors.tiers.gold'),
      icon: Trophy,
      names: ['Hoàn Xuân Nguyên', 'Nguyễn Xuân Bách'],
      className: 'border-amber-500/25 bg-amber-500/8 text-amber-700 dark:text-amber-300',
    },
    {
      label: t('sponsors.tiers.platinum'),
      icon: Award,
      names: ['Thân Đức Trí', 'Đỗ Việt Hưng'],
      className: 'border-violet-500/25 bg-violet-500/8 text-violet-700 dark:text-violet-300',
    },
  ]

  return (
    <div className="overflow-hidden">
      <section className="relative overflow-hidden border-b">
        <div className="pointer-events-none absolute inset-0 -z-20 bg-[radial-gradient(circle_at_25%_25%,color-mix(in_oklab,var(--color-primary)_20%,transparent),transparent_55%),radial-gradient(circle_at_75%_75%,color-mix(in_oklab,var(--color-primary)_12%,transparent),transparent_45%)]" />
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[linear-gradient(to_right,color-mix(in_oklab,var(--color-border)_25%,transparent)_1px,transparent_1px),linear-gradient(to_bottom,color-mix(in_oklab,var(--color-border)_25%,transparent)_1px,transparent_1px)] bg-[size:36px_36px] [mask-image:radial-gradient(ellipse_75%_65%_at_50%_50%,black_70%,transparent_100%)]" />
        <div className="mx-auto grid min-h-[calc(100svh-4rem)] w-full max-w-7xl items-center gap-14 px-4 py-16 md:px-6 md:py-24 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="space-y-7">
            <Badge className="border-primary/20 bg-primary/8 text-primary" variant="secondary">
              <Flame className="fill-current" />
              {t('hero.badge')}
            </Badge>
            <div className="space-y-5">
              <h1 className="max-w-3xl text-5xl font-bold tracking-[-0.045em] text-balance sm:text-6xl lg:text-7xl">
                {t('hero.title_start')}<span className="text-primary">{t('hero.title_highlight')}</span>{t('hero.title_end')}
              </h1>
              <p className="max-w-2xl text-lg leading-8 text-muted-foreground md:text-xl">
                {t('hero.description')}
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button size="lg" asChild>
                <Link to={primaryTo}>
                  {authenticated ? t('hero.cta_open_dashboard') : t('hero.cta_start_free')}
                  <ArrowRight />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link to={secondaryTo}>
                  {authenticated ? t('hero.cta_view_progress') : t('hero.cta_login')}
                </Link>
              </Button>
            </div>
            <div className="flex flex-wrap gap-x-6 gap-y-3 pt-2 text-sm text-muted-foreground">
              {[
                t('hero.proof_points.all_fields'),
                t('hero.proof_points.community_data'),
                t('hero.proof_points.smart_srs'),
              ].map((item) => (
                <span key={item} className="inline-flex items-center gap-2">
                  <Check className="size-4 text-emerald-600" />
                  {item}
                </span>
              ))}
            </div>
          </div>
          <div className="relative min-h-130 lg:min-h-150 perspective-1000">
            <div className="absolute inset-0 m-auto h-80 w-80 rounded-full bg-primary/10 blur-3xl" />
            <HeroCard
              className="top-12 hero-stack-card hero-stack-card-3"
              category={t('hero.cards.english.category')}
              categoryClassName="bg-violet-500/10 text-violet-700 dark:text-violet-300"
              front={t('hero.cards.english.front')}
              back={<span>{t('hero.cards.english.back')}</span>}
            />
            <HeroCard
              className="top-12 hero-stack-card hero-stack-card-2"
              category={t('hero.cards.it_aws.category')}
              categoryClassName="bg-amber-500/10 text-amber-700 dark:text-amber-300"
              front={t('hero.cards.it_aws.front')}
              back={<span>{t('hero.cards.it_aws.back')}</span>}
            />
            <HeroCard
              className="top-12 hero-stack-card hero-stack-card-1"
              category={t('hero.cards.physics.category')}
              categoryClassName="bg-sky-500/10 text-sky-700 dark:text-sky-300"
              front={<>{t('hero.cards.physics.front')}</>}
              back={<span className="text-2xl">{t('hero.cards.physics.back')}</span>}
            />
          </div>
        </div>
      </section>

      <section className="relative overflow-hidden bg-muted/25 py-16 md:py-24">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[linear-gradient(to_right,color-mix(in_oklab,var(--color-border)_20%,transparent)_1px,transparent_1px),linear-gradient(to_bottom,color-mix(in_oklab,var(--color-border)_20%,transparent)_1px,transparent_1px)] bg-[size:36px_36px] [mask-image:radial-gradient(ellipse_75%_65%_at_50%_50%,black_60%,transparent_100%)]" />
        <div className="mx-auto w-full max-w-7xl px-4 md:px-6">
          <SectionHeading
            eyebrow={t('how_it_works.eyebrow')}
            title={t('how_it_works.title')}
            description={t('how_it_works.description')}
          />
          <div className="grid gap-5 md:grid-cols-3">
            {steps.map((item, index) => (
              <Card key={item.title} className="relative overflow-hidden shadow-none">
                <span className="absolute top-3 right-4 text-6xl font-black text-primary/5">
                  {index + 1}
                </span>
                <CardHeader>
                  <span className="mb-3 flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                    <item.icon className="size-5" />
                  </span>
                  <CardTitle>{index + 1}. {item.title}</CardTitle>
                  <CardDescription className="leading-6">{item.description}</CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <ProductPreview />

      <section className="py-16 md:py-24">
        <div className="mx-auto w-full max-w-7xl px-4 md:px-6">
          <SectionHeading
            eyebrow={t('use_cases.eyebrow')}
            title={t('use_cases.title')}
            description={t('use_cases.description')}
          />
          <div className="flex flex-wrap justify-center gap-3">
            {useCases.map((item) => (
              <Badge
                key={item}
                className="rounded-full px-4 py-2 text-sm font-medium"
                variant="outline"
              >
                {item}
              </Badge>
            ))}
          </div>
        </div>
      </section>

      <section className="border-y bg-muted/25 py-16 md:py-24">
        <div className="mx-auto w-full max-w-7xl px-4 md:px-6">
          <SectionHeading eyebrow={t('benefits.eyebrow')} title={t('benefits.title')} />
          <div className="grid gap-x-10 gap-y-8 md:grid-cols-2">
            {benefits.map((item) => (
              <div key={item.title} className="flex gap-4">
                <span className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <item.icon className="size-5" />
                </span>
                <div>
                  <h3 className="text-lg font-semibold">{item.title}</h3>
                  <p className="mt-2 leading-7 text-muted-foreground">{item.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <MiniDemo />

      <section className="relative overflow-hidden border-y bg-muted/25 py-16 md:py-24">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[linear-gradient(to_right,color-mix(in_oklab,var(--color-border)_20%,transparent)_1px,transparent_1px),linear-gradient(to_bottom,color-mix(in_oklab,var(--color-border)_20%,transparent)_1px,transparent_1px)] bg-[size:36px_36px] [mask-image:radial-gradient(ellipse_80%_70%_at_50%_50%,black_60%,transparent_100%)]" />
        <div className="mx-auto w-full max-w-7xl px-4 md:px-6">
          <SectionHeading
            eyebrow={t('roadmap.eyebrow')}
            title={t('roadmap.title')}
            description={t('roadmap.description')}
          />
          <div className="grid gap-5 lg:grid-cols-3">
            {roadmap.map((column) => (
              <Card key={column.label} className="shadow-none">
                <CardHeader>
                  <Badge className={`w-fit ${column.tone}`} variant="secondary">
                    {column.label}
                  </Badge>
                  <CardDescription>{column.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-5">
                    {column.items.map(([title, description]) => (
                      <li key={title} className="flex gap-3">
                        <Check className="mt-0.5 size-4 shrink-0 text-primary" />
                        <div>
                          <p className="font-medium">{title}</p>
                          <p className="mt-1 text-sm leading-6 text-muted-foreground">
                            {description}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section id="landing-updates" className="py-16 md:py-24">
        <div className="mx-auto w-full max-w-7xl px-4 md:px-6">
          <SectionHeading
            eyebrow={t('updates.eyebrow')}
            title={t('updates.title')}
            description={t('updates.description')}
          />
          <div className="grid gap-5 md:grid-cols-2">
            {updates.map((item) => (
              <Card key={item.title} className="shadow-none">
                <CardHeader>
                  <div className="flex items-center justify-between gap-4">
                    <Badge variant="secondary">{item.tag}</Badge>
                    <time className="text-xs text-muted-foreground">{item.date}</time>
                  </div>
                  <CardTitle className="pt-2">{item.title}</CardTitle>
                  <CardDescription className="leading-6">{item.description}</CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="border-y bg-muted/25 py-16 md:py-24">
        <div className="mx-auto w-full max-w-4xl px-4 md:px-6">
          <SectionHeading eyebrow={t('faq.eyebrow')} title={t('faq.title')} />
          <div className="space-y-3">
            {faqs.map((item, index) => (
              <details
                key={item.question}
                className="group rounded-2xl border bg-card px-5 open:shadow-sm"
                open={index === 0}
              >
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-5 font-semibold">
                  {item.question}
                  <span className="text-xl font-light text-primary transition-transform group-open:rotate-45">
                    +
                  </span>
                </summary>
                <p className="border-t pb-5 pt-4 leading-7 text-muted-foreground">
                  {item.answer}
                </p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="py-16 md:py-24">
        <div className="mx-auto w-full max-w-7xl px-4 md:px-6">
          <SectionHeading
            eyebrow={t('sponsors.eyebrow')}
            title={t('sponsors.title')}
            description={t('sponsors.description')}
          />
          <div className="space-y-3">
            {sponsors.map((sponsor, index) => (
              <SponsorLane key={sponsor.label} {...sponsor} reverse={index === 1} />
            ))}
          </div>
        </div>
      </section>

      <section className="border-y bg-muted/25 py-14">
        <div className="mx-auto flex w-full max-w-4xl flex-col items-center px-4 text-center md:px-6">
          <span className="flex size-12 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-700 dark:text-emerald-300">
            <ShieldCheck className="size-6" />
          </span>
          <h2 className="mt-5 text-2xl font-bold">{t('privacy_callout.title')}</h2>
          <p className="mt-3 max-w-2xl leading-7 text-muted-foreground">
            {t('privacy_callout.description_prefix')}
            <Link className="font-medium text-primary hover:underline" to="/terms">
              {t('privacy_callout.terms_link')}
            </Link>
            {t('privacy_callout.and')}
            <Link className="font-medium text-primary hover:underline" to="/privacy">
              {t('privacy_callout.privacy_link')}
            </Link>
            {t('privacy_callout.dot')}
          </p>
        </div>
      </section>

      <section className="py-16 md:py-24">
        <div className="mx-auto w-full max-w-7xl px-4 md:px-6">
          <div className="relative overflow-hidden rounded-3xl border bg-foreground px-6 py-14 text-center text-background shadow-2xl md:px-12 md:py-18">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,color-mix(in_oklab,var(--color-primary)_45%,transparent),transparent_40%)] opacity-70" />
            <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.06)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.06)_1px,transparent_1px)] bg-[size:36px_36px] [mask-image:radial-gradient(ellipse_85%_85%_at_50%_50%,black_70%,transparent_100%)]" />
            <div className="relative mx-auto max-w-3xl">
              <Rocket className="mx-auto size-8 text-primary" />
              <h2 className="mt-5 text-3xl font-bold tracking-tight text-balance md:text-5xl">
                {t('final_cta.title')}
              </h2>
              <p className="mt-5 text-lg leading-8 text-background/70">
                {t('final_cta.description')}
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <Button size="lg" asChild>
                  <Link to={primaryTo}>
                    {authenticated ? t('final_cta.btn_continue_study') : t('final_cta.btn_start_free')}
                    <ArrowRight />
                  </Link>
                </Button>
                <Button
                  size="lg"
                  variant="outline"
                  className="border-background/25 bg-transparent text-background hover:bg-background/10 hover:text-background"
                  asChild
                >
                  <Link to={secondaryTo}>
                    {authenticated ? t('final_cta.btn_view_stats') : t('final_cta.btn_login')}
                  </Link>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="pb-16">
        <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-center gap-x-8 gap-y-3 px-4 text-sm text-muted-foreground md:px-6">
          <span className="inline-flex items-center gap-2"><Layers3 className="size-4" /> {t('feature_badges.flexible_notetype')}</span>
          <span className="inline-flex items-center gap-2"><Upload className="size-4" /> {t('feature_badges.import_export')}</span>
          <span className="inline-flex items-center gap-2"><Clock3 className="size-4" /> {t('feature_badges.spaced_repetition')}</span>
          <span className="inline-flex items-center gap-2"><Smartphone className="size-4" /> {t('feature_badges.responsive')}</span>
          <span className="inline-flex items-center gap-2"><ShieldCheck className="size-4" /> {t('feature_badges.logical_overlay')}</span>
        </div>
      </section>
    </div>
  )
}
