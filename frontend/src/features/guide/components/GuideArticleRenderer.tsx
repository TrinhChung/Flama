import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faArrowLeft,
  faArrowRight,
  faCircleCheck,
  faClock,
  faKeyboard,
  faLightbulb,
  faSliders,
  faTriangleExclamation,
  faWrench,
} from '@fortawesome/free-solid-svg-icons'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { GuideBreadcrumb } from './GuideBreadcrumb'
import { getAdjacentArticles } from '../guideData'
import type { GuideArticle, GuideCategory } from '../types'

interface GuideArticleRendererProps {
  article: GuideArticle
  category?: GuideCategory
}

export function GuideArticleRenderer({ article, category }: GuideArticleRendererProps) {
  const { prevArticle, nextArticle } = getAdjacentArticles(category?.slug, article.slug)

  return (
    <article className="space-y-8 animate-in fade-in-50 duration-200">
      {/* Breadcrumb */}
      <GuideBreadcrumb category={category} article={article} />

      {/* Article Header */}
      <div className="space-y-3 pb-6 border-b border-border/80">
        <div className="flex flex-wrap items-center gap-2">
          {category && (
            <Badge variant="secondary" className="text-xs font-semibold rounded-lg">
              {category.title}
            </Badge>
          )}
          {article.readTimeMinutes && (
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <FontAwesomeIcon icon={faClock} className="text-[11px]" />
              <span>{article.readTimeMinutes} phút đọc</span>
            </span>
          )}
        </div>

        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground leading-tight">
          {article.title}
        </h1>

        <p className="text-sm sm:text-base text-muted-foreground leading-relaxed">
          {article.shortDescription}
        </p>
      </div>

      {/* Key Takeaways / Tip banner */}
      {article.keyTakeaways && article.keyTakeaways.length > 0 && (
        <div className="rounded-2xl border border-border/80 bg-card p-4 sm:p-5 space-y-2.5 shadow-2xs">
          <div className="flex items-center gap-2 text-foreground font-bold text-xs uppercase tracking-wider">
            <FontAwesomeIcon icon={faCircleCheck} className="text-primary text-sm" />
            <span>Điểm Cốt Lõi Cần Nhớ</span>
          </div>
          <ul className="space-y-1.5 text-xs sm:text-sm text-foreground/90 leading-relaxed list-disc list-inside">
            {article.keyTakeaways.map((point, idx) => (
              <li key={idx}>{point}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Intro section */}
      {article.intro && (
        <div className="text-sm text-foreground/90 leading-relaxed">
          {article.intro}
        </div>
      )}

      {/* Step-by-step instructions */}
      {article.steps && article.steps.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-base sm:text-lg font-bold tracking-tight text-foreground flex items-center gap-2">
            <FontAwesomeIcon icon={faCircleCheck} className="text-primary text-sm" />
            <span>Quy Trình Thao Tác Từng Bước</span>
          </h2>

          <div className="space-y-3.5">
            {article.steps.map((step, idx) => (
              <div
                key={idx}
                className="p-4 sm:p-5 rounded-2xl border border-border/80 bg-card shadow-2xs space-y-2.5 transition-all hover:border-primary/40"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <div className="flex size-7 items-center justify-center rounded-xl bg-primary text-primary-foreground text-xs font-bold shrink-0 shadow-xs">
                      {idx + 1}
                    </div>
                    <h3 className="font-bold text-sm text-foreground">
                      {step.title}
                    </h3>
                  </div>
                  {step.badge && (
                    <Badge variant="outline" className="text-[10px] h-5 px-1.5 font-semibold text-muted-foreground border-border/60">
                      {step.badge}
                    </Badge>
                  )}
                </div>

                <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed whitespace-pre-line pl-9">
                  {step.description}
                </p>

                {step.tip && (
                  <div className="ml-9 mt-2 flex items-start gap-2 rounded-xl bg-amber-500/10 border border-amber-500/20 p-3 text-xs text-amber-800 dark:text-amber-300">
                    <FontAwesomeIcon icon={faLightbulb} className="text-amber-500 text-xs shrink-0 mt-0.5" />
                    <span className="leading-relaxed">
                      <strong>Mẹo:</strong> {step.tip}
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Detailed Sections */}
      {article.detailedSections && article.detailedSections.length > 0 && (
        <div className="space-y-4">
          {article.detailedSections.map((sec, idx) => (
            <Card key={idx} className="border-border/80 bg-card rounded-2xl shadow-2xs">
              <CardHeader className="p-4 sm:p-5 pb-2">
                <CardTitle className="text-sm sm:text-base font-bold text-foreground">
                  {sec.title}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 sm:p-5 pt-0 space-y-2 text-xs sm:text-sm text-muted-foreground leading-relaxed whitespace-pre-line">
                {sec.content}
                {sec.subitems && (
                  <ul className="list-disc list-inside space-y-1 pt-2">
                    {sec.subitems.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Keyboard shortcuts table */}
      {article.shortcuts && article.shortcuts.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-base sm:text-lg font-bold tracking-tight text-foreground flex items-center gap-2">
            <FontAwesomeIcon icon={faKeyboard} className="text-primary text-sm" />
            <span>Bảng Tra Cứu Phím Tắt Bàn Phím</span>
          </h2>

          <div className="overflow-hidden rounded-2xl border border-border/80 bg-card shadow-2xs">
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-border/80 bg-muted/40 text-foreground font-bold">
                    <th className="py-3 px-4 w-36">Phím Tắt</th>
                    <th className="py-3 px-4 w-44">Tác Vụ</th>
                    <th className="py-3 px-4">Chi Tiết Hoạt Động</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {article.shortcuts.map((sc, idx) => (
                    <tr key={idx} className="hover:bg-muted/30 transition-colors">
                      <td className="py-2.5 px-4 font-mono font-bold text-primary whitespace-nowrap">
                        <kbd className="px-2 py-1 rounded-md bg-muted border border-border/80 shadow-2xs text-[11px]">
                          {sc.key}
                        </kbd>
                      </td>
                      <td className="py-2.5 px-4 font-semibold text-foreground">
                        {sc.action}
                      </td>
                      <td className="py-2.5 px-4 text-muted-foreground">
                        {sc.description}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Parameters Table */}
      {article.params && article.params.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-base sm:text-lg font-bold tracking-tight text-foreground flex items-center gap-2">
            <FontAwesomeIcon icon={faSliders} className="text-primary text-sm" />
            <span>Bảng Tham Số &amp; Tùy Chọn Cấu Hình</span>
          </h2>

          <div className="overflow-hidden rounded-2xl border border-border/80 bg-card shadow-2xs">
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-border/80 bg-muted/40 text-foreground font-bold">
                    <th className="py-3 px-4 w-48">Tên Tham Số</th>
                    <th className="py-3 px-4 w-28">Mặc Định</th>
                    <th className="py-3 px-4">Ý Nghĩa &amp; Khuyến Nghị</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {article.params.map((p, idx) => (
                    <tr key={idx} className="hover:bg-muted/30 transition-colors">
                      <td className="py-2.5 px-4 font-semibold text-foreground">
                        {p.name}
                      </td>
                      <td className="py-2.5 px-4 font-mono text-muted-foreground">
                        {p.defaultValue || '—'}
                      </td>
                      <td className="py-2.5 px-4 text-muted-foreground leading-relaxed">
                        {p.description}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Troubleshooting Items */}
      {article.troubleshoot && article.troubleshoot.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-base sm:text-lg font-bold tracking-tight text-foreground flex items-center gap-2">
            <FontAwesomeIcon icon={faTriangleExclamation} className="text-amber-500 text-sm" />
            <span>Hiện Tượng Quan Sát &amp; Quy Trình Khắc Phục</span>
          </h2>

          <div className="space-y-3.5">
            {article.troubleshoot.map((item, idx) => (
              <div
                key={idx}
                className="p-4 sm:p-5 rounded-2xl border border-amber-500/30 bg-amber-500/10 space-y-3"
              >
                <div>
                  <h3 className="font-bold text-sm text-foreground flex items-start gap-2">
                    <span className="size-2 rounded-full bg-amber-500 mt-1.5 shrink-0" />
                    <span>Hiện tượng: {item.symptom}</span>
                  </h3>
                  <p className="text-xs text-muted-foreground mt-1 pl-4">
                    <strong>Nguyên nhân:</strong> {item.cause}
                  </p>
                </div>

                <div className="rounded-xl bg-card border border-border/80 p-3.5 space-y-1.5 ml-4">
                  <div className="text-xs font-bold text-primary">Các bước xử lý:</div>
                  <ol className="list-decimal list-inside space-y-1 text-xs text-foreground/90">
                    {item.solution.map((sol, sIdx) => (
                      <li key={sIdx}>{sol}</li>
                    ))}
                  </ol>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Contextual Link to Troubleshooting Hub if applicable */}
      {article.troubleshootingSlug && (
        <div className="flex flex-wrap items-center justify-between gap-4 p-4 sm:p-5 rounded-2xl border border-amber-500/30 bg-amber-500/10">
          <div className="flex items-center gap-3 min-w-0">
            <div className="size-9 rounded-xl bg-amber-500/20 text-amber-700 dark:text-amber-300 flex items-center justify-center shrink-0">
              <FontAwesomeIcon icon={faWrench} className="text-sm" />
            </div>
            <div>
              <h4 className="font-bold text-xs sm:text-sm text-foreground">
                Gặp sự cố khi thực hiện chức năng này?
              </h4>
              <p className="text-[11px] sm:text-xs text-muted-foreground">
                Xem ma trận chẩn đoán sự cố theo hiện tượng thực tế để xử lý nhanh.
              </p>
            </div>
          </div>

          <Button asChild variant="outline" size="sm" className="gap-1.5 font-semibold shrink-0 rounded-xl">
            <Link to={`/guide/troubleshooting/${article.troubleshootingSlug}`}>
              <span>Xem bài sửa lỗi</span>
              <FontAwesomeIcon icon={faArrowRight} className="text-xs" />
            </Link>
          </Button>
        </div>
      )}

      {/* Next / Previous Article Navigation */}
      {(prevArticle || nextArticle) && (
        <div className="pt-6 border-t border-border/80 grid gap-3 sm:grid-cols-2">
          {prevArticle ? (
            <Link
              to={prevArticle.url}
              className="flex flex-col p-4 rounded-2xl border border-border/80 bg-card hover:border-primary/50 hover:bg-muted/20 transition-all group"
            >
              <span className="text-[11px] font-semibold text-muted-foreground flex items-center gap-1.5 group-hover:text-primary transition-colors">
                <FontAwesomeIcon icon={faArrowLeft} className="text-[10px]" />
                <span>Bài trước</span>
              </span>
              <span className="font-bold text-xs sm:text-sm text-foreground mt-1 line-clamp-1">
                {prevArticle.title}
              </span>
            </Link>
          ) : (
            <div />
          )}

          {nextArticle && (
            <Link
              to={nextArticle.url}
              className="flex flex-col items-end text-right p-4 rounded-2xl border border-border/80 bg-card hover:border-primary/50 hover:bg-muted/20 transition-all group"
            >
              <span className="text-[11px] font-semibold text-muted-foreground flex items-center gap-1.5 group-hover:text-primary transition-colors">
                <span>Bài tiếp theo</span>
                <FontAwesomeIcon icon={faArrowRight} className="text-[10px]" />
              </span>
              <span className="font-bold text-xs sm:text-sm text-foreground mt-1 line-clamp-1">
                {nextArticle.title}
              </span>
            </Link>
          )}
        </div>
      )}
    </article>
  )
}

