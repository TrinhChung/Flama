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
  Sparkles,
  Target,
  TrendingUp,
  Trophy,
  Upload,
  Zap,
} from 'lucide-react'
import { Link } from 'react-router-dom'
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

const steps: Array<{
  title: string
  description: string
  icon: IconType
}> = [
  {
    title: 'Tạo thẻ trong 30 giây',
    description:
      'Thêm công thức, thuật ngữ hay định nghĩa nhanh chóng. Thiết kế tối giản giúp bạn tập trung vào nội dung.',
    icon: Sparkles,
  },
  {
    title: 'Học theo lịch thông minh',
    description:
      'Flama tự động sắp xếp lịch nhắc lại vào đúng khoảnh khắc bạn chuẩn bị quên.',
    icon: CalendarCheck2,
  },
  {
    title: 'Giữ vững động lực',
    description:
      'Theo dõi tải học mỗi ngày và nhìn rõ tiến độ qua New, Learn và Due.',
    icon: TrendingUp,
  },
]

const useCases = [
  'IT · AWS/Security',
  'Lập trình · System Design',
  'JLPT · Kanji/Từ vựng',
  'Y khoa · Thuật ngữ lâm sàng',
  'Luật · Điều khoản cốt lõi',
  'Ngoại ngữ · Cụm từ thường gặp',
]

const benefits: Array<{
  title: string
  description: string
  icon: IconType
}> = [
  {
    title: 'Ôn tập ngắt quãng',
    description:
      'Nhớ lâu hơn với thời gian học ngắn hơn so với học nhồi nhét truyền thống.',
    icon: Zap,
  },
  {
    title: 'Tập trung phần sắp quên',
    description:
      'Hệ thống ưu tiên các thẻ đến hạn và giảm thời gian cho phần bạn đã thuộc.',
    icon: Target,
  },
  {
    title: 'Tiến độ rõ ràng',
    description:
      'Dashboard và thống kê cho bạn thấy tải học, lịch sử và dự báo thẻ đến hạn.',
    icon: BarChart3,
  },
  {
    title: 'Trải nghiệm tập trung',
    description:
      'Luồng học gọn, thao tác nhanh và hoạt động tốt trên cả máy tính lẫn điện thoại.',
    icon: Focus,
  },
]

const roadmap = [
  {
    label: 'Now',
    description: 'Đang có trong sản phẩm',
    tone: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
    items: [
      ['NoteType + Note Editor', 'Tạo thẻ linh hoạt theo mẫu riêng.'],
      ['Study với 4 mức đánh giá', 'Ôn đúng nhịp bằng Again, Hard, Good và Easy.'],
      ['Browse deck tree + card editor', 'Lọc, tìm và sửa thẻ ngay trong collection.'],
      ['Dashboard New/Learn/Due', 'Theo dõi tải học mỗi ngày rõ ràng.'],
      ['Import/Export CSV', 'Chủ động đưa học liệu vào và ra khỏi Flama.'],
    ],
  },
  {
    label: 'Next',
    description: 'Sắp triển khai',
    tone: 'bg-primary/10 text-primary',
    items: [
      ['Báo cáo học tập theo tuần', 'Nhìn rõ xu hướng học trong từng tuần.'],
      ['Preset theo mục tiêu', 'Khởi tạo nhanh theo ngành học cụ thể.'],
      ['Marketplace tinh gọn hơn', 'Tìm bộ thẻ phù hợp nhanh và chính xác hơn.'],
    ],
  },
  {
    label: 'Later',
    description: 'Kế hoạch dài hạn',
    tone: 'bg-violet-500/10 text-violet-700 dark:text-violet-300',
    items: [
      ['Đồng bộ đa thiết bị sâu hơn', 'Học liền mạch trên mọi thiết bị.'],
      ['Không gian học nhóm', 'Chia sẻ deck và nhịp học nội bộ.'],
      ['Ứng dụng mobile', 'Tối ưu các phiên ôn nhanh khi di chuyển.'],
    ],
  },
]

const updates = [
  {
    tag: 'Giao diện',
    date: '04/03/2026',
    title: 'Tối ưu lại giao diện học',
    description:
      'Bố cục học thẻ gọn, rõ và dễ theo dõi hơn khi bạn ôn nhiều từ liên tục.',
  },
  {
    tag: 'Tập trung',
    date: '04/03/2026',
    title: 'Học toàn màn hình không ngắt nhịp',
    description:
      'Phiên học giữ trạng thái ổn định để bạn tập trung khi chuyển qua từng thẻ.',
  },
  {
    tag: 'Chỉnh sửa',
    date: '04/03/2026',
    title: 'Chỉnh sửa thẻ an toàn hơn',
    description:
      'Giảm rủi ro ghi đè nhầm dữ liệu khi cập nhật nội dung trong collection.',
  },
  {
    tag: 'Âm thanh',
    date: '04/03/2026',
    title: 'Tạo audio tiếng Nhật bằng VoiceVox',
    description:
      'Tạo audio từ từ vựng hoặc câu ví dụ và nghe trực tiếp ngay trên thẻ.',
  },
]

const faqs = [
  {
    question: 'Điểm khác biệt của Flama là gì?',
    answer:
      'Flama kết hợp note type linh hoạt, bộ thẻ cộng đồng, audio và spaced repetition trong một luồng học thống nhất. Học liệu được tổ chức để có thể dùng ngay nhưng vẫn chỉnh sửa theo mục tiêu riêng.',
  },
  {
    question: 'Mục đích của Flama là gì?',
    answer:
      'Flama giúp bạn tự do tạo bộ thẻ theo cách riêng và duy trì nhịp học mỗi ngày. Xa hơn, Flama hướng tới một cộng đồng chia sẻ tri thức dễ tiếp cận và có cấu trúc.',
  },
  {
    question: 'Flama phù hợp với ai?',
    answer:
      'Phù hợp với người học theo kiểu mỗi ngày một chút nhưng đều: học ngoại ngữ, ôn chứng chỉ, ghi nhớ thuật ngữ IT, Y khoa, Luật hoặc bất kỳ kiến thức nào cần nhớ lâu.',
  },
  {
    question: 'Tôi có thể tự tạo bộ thẻ không?',
    answer:
      'Có. Bạn có thể tạo note type, nhập nội dung, tổ chức theo deck và tùy chỉnh template hiển thị theo cách học của mình.',
  },
  {
    question: 'Audio trong Flama dùng để làm gì?',
    answer:
      'Audio giúp luyện cách đọc, nhịp nói và phản xạ nghe ngay trong lúc ôn thẻ thay vì chỉ học bằng mặt chữ.',
  },
  {
    question: 'Flama có dùng tốt trên điện thoại không?',
    answer:
      'Có. Giao diện responsive hỗ trợ các phiên học ngắn trên điện thoại cũng như quản lý nội dung trên máy tính.',
  },
  {
    question: 'Deck lớn có làm tôi bị ngợp không?',
    answer:
      'Flama chia thẻ theo New, Learn và Due, sau đó ưu tiên phần sắp quên để bạn tập trung vào khối lượng thực sự cần học hôm nay.',
  },
  {
    question: 'Tôi có thể chia sẻ bộ thẻ không?',
    answer:
      'Có. Marketplace hỗ trợ chia sẻ deck và note type. Deck được cài theo logical overlay để nguồn học liệu và tiến độ cá nhân luôn tách biệt.',
  },
  {
    question: 'Tôi có thể chuyển dữ liệu sang nền tảng khác không?',
    answer:
      'Có. Flama hỗ trợ các luồng import và export phổ biến như CSV/TSV để bạn chủ động với dữ liệu của mình.',
  },
  {
    question: 'Flama có miễn phí không?',
    answer:
      'Bạn có thể đăng ký và dùng luồng học cốt lõi. Marketplace có cả nội dung miễn phí và trả phí tùy người chia sẻ.',
  },
]

const sponsors = [
  {
    label: 'Kim cương',
    icon: Gem,
    names: ['Trịnh Văn Chung'],
    className: 'border-sky-500/25 bg-sky-500/8 text-sky-700 dark:text-sky-300',
  },
  {
    label: 'Vàng',
    icon: Trophy,
    names: ['Hoàn Xuân Nguyên', 'Nguyễn Xuân Bách'],
    className: 'border-amber-500/25 bg-amber-500/8 text-amber-700 dark:text-amber-300',
  },
  {
    label: 'Bạch kim',
    icon: Award,
    names: ['Thân Đức Trí', 'Đỗ Việt Hưng'],
    className: 'border-violet-500/25 bg-violet-500/8 text-violet-700 dark:text-violet-300',
  },
]

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
  return (
    <div className="grid grid-cols-3 gap-2 text-center text-[11px] font-semibold">
      <span className="rounded-md bg-rose-500/10 px-2 py-1.5 text-rose-700 dark:text-rose-300">
        Khó
      </span>
      <span className="rounded-md bg-emerald-500/10 px-2 py-1.5 text-emerald-700 dark:text-emerald-300">
        Tốt
      </span>
      <span className="rounded-md bg-sky-500/10 px-2 py-1.5 text-sky-700 dark:text-sky-300">
        Dễ
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
  return (
    <section className="relative overflow-hidden border-y bg-muted/20 py-16 md:py-24">
      <div className="pointer-events-none absolute inset-0 -z-20 bg-[radial-gradient(circle_at_50%_30%,color-mix(in_oklab,var(--color-primary)_12%,transparent),transparent_50%)]" />
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[linear-gradient(to_right,color-mix(in_oklab,var(--color-border)_22%,transparent)_1px,transparent_1px),linear-gradient(to_bottom,color-mix(in_oklab,var(--color-border)_22%,transparent)_1px,transparent_1px)] bg-[size:36px_36px] [mask-image:radial-gradient(ellipse_85%_75%_at_50%_50%,black_70%,transparent_100%)]" />
      <div className="mx-auto w-full max-w-7xl px-4 md:px-6">
        <SectionHeading
          eyebrow="Product preview"
          title="Một workspace cho toàn bộ vòng đời flashcard"
          description="Tạo nội dung, học theo scheduler và quản lý collection mà không phải nhảy qua nhiều công cụ."
        />
        <div className="grid gap-5 lg:grid-cols-3">
          <PreviewFrame
            path="/flashcards/notes/new"
            title="Tạo note linh hoạt"
            description="Chọn NoteType, nhập field và gán deck trong một luồng."
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
            title="Ôn đúng thẻ cần nhớ"
            description="Scheduler đưa thẻ đến hạn vào một phiên học tập trung."
            icon={Brain}
          >
            <div className="space-y-4">
              <div className="flex justify-center gap-2">
                <Badge variant="secondary">New 16</Badge>
                <Badge variant="outline">Learn 7</Badge>
                <Badge variant="destructive">Due 24</Badge>
              </div>
              <div className="rounded-xl border bg-background p-5 text-center">
                <p className="font-semibold">What is least privilege?</p>
                <p className="mt-2 text-xs text-muted-foreground">
                  Design principle for limiting permissions.
                </p>
              </div>
              <ReviewButtons />
            </div>
          </PreviewFrame>
          <PreviewFrame
            path="/browse"
            title="Tìm và sửa nhanh"
            description="Duyệt deck tree, lọc thẻ và kiểm tra nội dung tại chỗ."
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
  const [revealed, setRevealed] = useState(false)
  const [rating, setRating] = useState<'again' | 'hard' | 'good' | 'easy'>('good')
  const labels = {
    again: 'Nhắc lại sau 1 phút',
    hard: 'Nhắc lại sau 10 phút',
    good: 'Nhắc lại sau 1 ngày',
    easy: 'Nhắc lại sau 5 ngày',
  }

  return (
    <section className="relative overflow-hidden py-16 md:py-24">
      <div className="pointer-events-none absolute inset-0 -z-20 bg-[radial-gradient(circle_at_75%_35%,color-mix(in_oklab,var(--color-primary)_16%,transparent),transparent_50%)]" />
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[linear-gradient(to_right,color-mix(in_oklab,var(--color-border)_25%,transparent)_1px,transparent_1px),linear-gradient(to_bottom,color-mix(in_oklab,var(--color-border)_25%,transparent)_1px,transparent_1px)] bg-[size:36px_36px] [mask-image:radial-gradient(ellipse_75%_65%_at_50%_50%,black_70%,transparent_100%)]" />
      <div className="mx-auto grid w-full max-w-7xl items-center gap-10 px-4 md:px-6 lg:grid-cols-[0.8fr_1.2fr]">
        <div>
          <Badge variant="secondary">Mini demo</Badge>
          <h2 className="mt-4 text-3xl font-bold tracking-tight md:text-4xl">
            Học một thẻ trong vài giây
          </h2>
          <p className="mt-4 text-lg leading-8 text-muted-foreground">
            Lật thẻ, tự đánh giá mức độ nhớ và để Flama đề xuất nhịp ôn tiếp theo.
          </p>
          <ul className="mt-6 space-y-3 text-sm">
            {[
              'Front/Back rõ ràng, tập trung kiến thức chính.',
              'Again/Hard/Good/Easy điều chỉnh lịch học.',
              'Phù hợp cho các phiên ôn ngắn mỗi ngày.',
            ].map((item) => (
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
                    Mặt trước
                  </span>
                  <strong className="mt-4 text-2xl leading-relaxed">
                    IAM Role khác IAM User ở điểm nào?
                  </strong>
                  <span className="mt-4 text-xs text-muted-foreground">
                    Chạm để lật thẻ
                  </span>
                </div>
                <div className="absolute inset-0 flex flex-col items-center justify-center rounded-2xl bg-muted/25 p-8 text-center backface-hidden rotate-y-180">
                  <span className="text-xs font-semibold tracking-[0.16em] text-primary uppercase">
                    Mặt sau
                  </span>
                  <strong className="mt-4 text-2xl leading-relaxed">
                    Role dùng credentials tạm thời; User thường có danh tính cố định.
                  </strong>
                  <span className="mt-4 text-xs text-muted-foreground">
                    Chạm để xem lại câu hỏi
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
              Lịch gợi ý: <strong className="text-foreground">{labels[rating]}</strong>
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
  const { data } = useBootstrap()
  const authenticated = Boolean(data?.user)
  const primaryTo = authenticated ? '/dashboard' : '/register'
  const secondaryTo = authenticated ? '/statistics' : '/login'

  return (
    <div className="overflow-hidden">
      <section className="relative overflow-hidden border-b">
        <div className="pointer-events-none absolute inset-0 -z-20 bg-[radial-gradient(circle_at_25%_25%,color-mix(in_oklab,var(--color-primary)_20%,transparent),transparent_55%),radial-gradient(circle_at_75%_75%,color-mix(in_oklab,var(--color-primary)_12%,transparent),transparent_45%)]" />
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[linear-gradient(to_right,color-mix(in_oklab,var(--color-border)_25%,transparent)_1px,transparent_1px),linear-gradient(to_bottom,color-mix(in_oklab,var(--color-border)_25%,transparent)_1px,transparent_1px)] bg-[size:36px_36px] [mask-image:radial-gradient(ellipse_75%_65%_at_50%_50%,black_70%,transparent_100%)]" />
        <div className="mx-auto grid min-h-[calc(100svh-4rem)] w-full max-w-7xl items-center gap-14 px-4 py-16 md:px-6 md:py-24 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="space-y-7">
            <Badge className="border-primary/20 bg-primary/8 text-primary" variant="secondary">
              <Flame className="fill-current" />
              Học đều hơn, nhớ lâu hơn
            </Badge>
            <div className="space-y-5">
              <h1 className="max-w-3xl text-5xl font-bold tracking-[-0.045em] text-balance sm:text-6xl lg:text-7xl">
                Giữ <span className="text-primary">lửa</span> học tập cho mọi kiến thức.
              </h1>
              <p className="max-w-2xl text-lg leading-8 text-muted-foreground md:text-xl">
                Tự do sáng tạo bộ thẻ theo cách riêng và dùng spaced repetition để ghi
                nhớ ngoại ngữ, IT, Y khoa, Luật hay bất kỳ chủ đề nào bạn theo đuổi.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button size="lg" asChild>
                <Link to={primaryTo}>
                  {authenticated ? 'Mở dashboard' : 'Bắt đầu học miễn phí'}
                  <ArrowRight />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link to={secondaryTo}>
                  {authenticated ? 'Xem tiến độ' : 'Đăng nhập'}
                </Link>
              </Button>
            </div>
            <div className="flex flex-wrap gap-x-6 gap-y-3 pt-2 text-sm text-muted-foreground">
              {['Tạo tài khoản nhanh', 'Import CSV/TSV', 'Responsive trên mobile'].map((item) => (
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
              category="Tiếng Anh"
              categoryClassName="bg-violet-500/10 text-violet-700 dark:text-violet-300"
              front="affect vs effect"
              back={<span>affect (v) = ảnh hưởng · effect (n) = kết quả</span>}
            />
            <HeroCard
              className="top-12 hero-stack-card hero-stack-card-2"
              category="IT · AWS"
              categoryClassName="bg-amber-500/10 text-amber-700 dark:text-amber-300"
              front="S3 dùng để làm gì?"
              back={<span>Object storage có độ bền và khả năng mở rộng cao.</span>}
            />
            <HeroCard
              className="top-12 hero-stack-card hero-stack-card-1"
              category="Vật lý cơ bản"
              categoryClassName="bg-sky-500/10 text-sky-700 dark:text-sky-300"
              front={<>Định luật II Newton</>}
              back={<span className="text-2xl">F = ma</span>}
            />
          </div>
        </div>
      </section>

      <section className="relative overflow-hidden bg-muted/25 py-16 md:py-24">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[linear-gradient(to_right,color-mix(in_oklab,var(--color-border)_20%,transparent)_1px,transparent_1px),linear-gradient(to_bottom,color-mix(in_oklab,var(--color-border)_20%,transparent)_1px,transparent_1px)] bg-[size:36px_36px] [mask-image:radial-gradient(ellipse_75%_65%_at_50%_50%,black_60%,transparent_100%)]" />
        <div className="mx-auto w-full max-w-7xl px-4 md:px-6">
          <SectionHeading
            eyebrow="Cách hoạt động"
            title="Từ kiến thức mới đến trí nhớ dài hạn"
            description="Một vòng lặp đơn giản để bạn bắt đầu nhanh và duy trì được nhịp học."
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
            eyebrow="Linh hoạt"
            title="Một phương pháp, nhiều lĩnh vực"
            description="Bất kỳ kiến thức nào cần ghi nhớ đều có thể trở thành một deck có cấu trúc."
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
          <SectionHeading eyebrow="Lợi ích" title="Tại sao chọn Flama?" />
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
            eyebrow="Roadmap"
            title="Flama đang đi tới đâu?"
            description="Những gì đã có, đang được ưu tiên và nằm trong tầm nhìn dài hạn."
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
            eyebrow="Product updates"
            title="Cập nhật mới cho người học"
            description="Những cải tiến gần đây giúp phiên học nhanh, an toàn và tự nhiên hơn."
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
          <SectionHeading eyebrow="FAQ" title="Câu hỏi thường gặp" />
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
            eyebrow="Community"
            title="Nhà tài trợ thiên thần"
            description="Cảm ơn những người đã góp sức duy trì hạ tầng và phát triển Flama."
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
          <h2 className="mt-5 text-2xl font-bold">Dữ liệu của bạn thuộc về bạn.</h2>
          <p className="mt-3 max-w-2xl leading-7 text-muted-foreground">
            Flama tôn trọng quyền riêng tư và giữ dữ liệu học tập tách biệt theo tài khoản.
            Đọc thêm trong{' '}
            <Link className="font-medium text-primary hover:underline" to="/terms">
              Điều khoản
            </Link>{' '}
            và{' '}
            <Link className="font-medium text-primary hover:underline" to="/privacy">
              Chính sách bảo mật
            </Link>.
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
                Sẵn sàng giữ lửa học tập mỗi ngày?
              </h2>
              <p className="mt-5 text-lg leading-8 text-background/70">
                Bắt đầu bằng một bộ thẻ nhỏ và duy trì nhịp ôn đều đặn.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <Button size="lg" asChild>
                  <Link to={primaryTo}>
                    {authenticated ? 'Tiếp tục học' : 'Bắt đầu học miễn phí'}
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
                    {authenticated ? 'Xem thống kê' : 'Đăng nhập'}
                  </Link>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="pb-16">
        <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-center gap-x-8 gap-y-3 px-4 text-sm text-muted-foreground md:px-6">
          <span className="inline-flex items-center gap-2"><Layers3 className="size-4" /> NoteType linh hoạt</span>
          <span className="inline-flex items-center gap-2"><Upload className="size-4" /> Import/Export</span>
          <span className="inline-flex items-center gap-2"><Clock3 className="size-4" /> Spaced repetition</span>
          <span className="inline-flex items-center gap-2"><Smartphone className="size-4" /> Responsive</span>
          <span className="inline-flex items-center gap-2"><ShieldCheck className="size-4" /> Logical overlay</span>
        </div>
      </section>
    </div>
  )
}
