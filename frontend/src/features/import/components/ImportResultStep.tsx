import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Layers,
  FileSpreadsheet,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { useFileImportWizard } from '../hooks/useFileImportWizard'

interface ImportResultStepProps {
  wizard: ReturnType<typeof useFileImportWizard>
}

export function ImportResultStep({ wizard }: ImportResultStepProps) {
  const { t } = useTranslation('import')
  const {
    isBatchMode,
    estimateMutation,
    batchEstimateMutation,
    executeMutation,
    batchExecuteMutation,
    handleEstimate,
    handleExecute,
    report,
    batchReport,
    executionDone,
    hasEstimated,
  } = wizard

  const isPending =
    estimateMutation.isPending ||
    batchEstimateMutation.isPending ||
    executeMutation.isPending ||
    batchExecuteMutation.isPending

  return (
    <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
      <CardHeader className="pb-3 border-b bg-card/50">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <CheckCircle2 className="size-4 text-primary" />
          {isBatchMode
            ? t('file_import.step4.title_batch', 'Rà soát & Thực thi Import (Hàng loạt)')
            : t('file_import.step4.title', 'Rà soát & Thực thi Import')}
        </CardTitle>
        <CardDescription className="text-xs">
          {t(
            'file_import.step4.desc',
            'Chạy ước lượng thử nghiệm hoặc tiến hành nạp dữ liệu chính thức vào hệ thống.'
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-4 space-y-4">
        <div className="flex flex-wrap gap-3">
          <Button
            variant="outline"
            disabled={isPending}
            onClick={handleEstimate}
            className="font-medium"
          >
            {isPending && (estimateMutation.isPending || batchEstimateMutation.isPending) ? (
              <>
                <Loader2 className="size-4 animate-spin mr-1.5" />
                {t('file_import.step4.estimating', 'Đang ước lượng dữ liệu…')}
              </>
            ) : (
              t('file_import.step4.btn_estimate', '1. Ước lượng thử nghiệm')
            )}
          </Button>

          <Button
            disabled={!hasEstimated || isPending}
            onClick={handleExecute}
            className="font-semibold shadow-sm"
          >
            {isPending && (executeMutation.isPending || batchExecuteMutation.isPending) ? (
              <>
                <Loader2 className="size-4 animate-spin mr-1.5" />
                {t('file_import.step4.executing', 'Đang nạp thẻ vào hệ thống…')}
              </>
            ) : (
              t('file_import.step4.btn_execute', '2. Thực thi import')
            )}
          </Button>
        </div>

        {isPending && (
          <div className="space-y-1.5">
            <Progress value={85} className="h-2" />
            <p className="text-xs text-muted-foreground text-center">
              {t('file_import.step4.progress_label', 'Đang xử lý dữ liệu import…')}
            </p>
          </div>
        )}

        {/* Batch Report Display */}
        {isBatchMode && batchReport && (
          <div className="space-y-4 pt-2">
            <Alert className={executionDone ? 'border-primary/40 bg-primary/5' : 'border-border/80 bg-muted/30'}>
              {executionDone ? <CheckCircle2 className="size-5 text-primary" /> : <AlertTriangle className="size-5 text-muted-foreground" />}
              <AlertTitle className="font-bold text-foreground">
                {executionDone
                  ? t('file_import.step4.result_batch_success_title', 'Thực thi Import Hàng loạt thành công!')
                  : t('file_import.step4.result_estimate_title', 'Kết quả ước lượng trước import (Hàng loạt)')}
              </AlertTitle>
              <AlertDescription className="mt-2 text-xs">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-medium">
                  <div>Tổng số bài: {batchReport.overall_summary.total_files}</div>
                  <div className="text-primary font-bold">Deck con tạo mới: {batchReport.overall_summary.created_decks}</div>
                  <div className="text-primary font-bold">
                    {t('file_import.step4.stat_inserted', 'Thêm mới')}: {batchReport.overall_summary.inserted}
                  </div>
                  <div className="font-semibold">
                    {t('file_import.step4.stat_updated', 'Cập nhật')}: {batchReport.overall_summary.updated}
                  </div>
                  <div className="text-muted-foreground">
                    {t('file_import.step4.stat_skipped', 'Bỏ qua')}: {batchReport.overall_summary.skipped}
                  </div>
                  <div className="text-destructive font-semibold">
                    {t('file_import.step4.stat_errors', 'Lỗi')}: {batchReport.overall_summary.errors}
                  </div>
                </div>
              </AlertDescription>
            </Alert>

            {/* Per-file Reports Table */}
            <div className="border border-border/80 rounded-2xl overflow-hidden shadow-sm">
              <div className="bg-muted/40 p-3 border-b text-xs font-bold text-foreground flex items-center gap-2">
                <Layers className="size-4 text-primary" />
                Chi tiết kết quả từng bài học ({batchReport.file_reports.length} bài)
              </div>
              <div className="overflow-x-auto">
                <Table className="text-xs">
                  <TableHeader className="bg-muted/20">
                    <TableRow>
                      <TableHead className="min-w-44">Tệp</TableHead>
                      <TableHead className="min-w-44">Deck con</TableHead>
                      <TableHead className="w-28 text-center">Trạng thái</TableHead>
                      <TableHead className="w-24 text-right">
                        {t('file_import.step4.stat_inserted', 'Thêm mới')}
                      </TableHead>
                      <TableHead className="w-24 text-right">
                        {t('file_import.step4.stat_updated', 'Cập nhật')}
                      </TableHead>
                      <TableHead className="w-24 text-right">
                        {t('file_import.step4.stat_skipped', 'Bỏ qua')}
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {batchReport.file_reports.map((fReport) => (
                      <TableRow key={fReport.file_id}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <FileSpreadsheet className="size-4 text-primary/70 shrink-0" />
                            <span className="font-medium truncate max-w-44">{fReport.filename}</span>
                          </div>
                        </TableCell>
                        <TableCell className="font-medium text-foreground">
                          {fReport.deck_name}
                        </TableCell>
                        <TableCell className="text-center">
                          {fReport.status === 'skipped' ? (
                            <Badge variant="outline" className="text-[10px]">
                              {t('file_import.step4.stat_skipped', 'Đã bỏ qua')}
                            </Badge>
                          ) : fReport.summary.errors > 0 ? (
                            <Badge variant="destructive" className="text-[10px]">
                              {t('file_import.step4.stat_errors', 'Có lỗi')}
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20 text-[10px]">Thành công</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-right font-bold text-primary">
                          {fReport.summary.inserted}
                        </TableCell>
                        <TableCell className="text-right font-medium">
                          {fReport.summary.updated}
                        </TableCell>
                        <TableCell className="text-right text-muted-foreground">
                          {fReport.summary.skipped}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          </div>
        )}

        {/* Single File Report Display */}
        {!isBatchMode && report && (
          <div className="space-y-4 pt-2">
            <Alert className={executionDone ? 'border-primary/40 bg-primary/5' : 'border-border/80 bg-muted/30'}>
              {executionDone ? <CheckCircle2 className="size-5 text-primary" /> : <AlertTriangle className="size-5 text-muted-foreground" />}
              <AlertTitle className="font-bold text-foreground">
                {executionDone
                  ? t('file_import.step4.result_success_title', 'Thực thi Import thành công!')
                  : t('file_import.step4.result_estimate_title', 'Kết quả ước lượng trước import')}
              </AlertTitle>
              <AlertDescription className="mt-2 text-xs">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-medium">
                  <div>{t('file_import.step4.stat_total', 'Tổng số dòng')}: {report.summary.total_rows}</div>
                  <div>{t('file_import.step4.stat_valid', 'Dòng hợp lệ')}: {report.summary.valid_rows}</div>
                  <div className="text-primary font-bold">
                    {t('file_import.step4.stat_inserted', 'Thêm mới')}: {report.summary.inserted}
                  </div>
                  <div className="font-semibold">
                    {t('file_import.step4.stat_updated', 'Cập nhật')}: {report.summary.updated}
                  </div>
                  <div className="text-muted-foreground">
                    {t('file_import.step4.stat_skipped', 'Bỏ qua')}: {report.summary.skipped}
                  </div>
                  <div className="text-destructive font-semibold">
                    {t('file_import.step4.stat_errors', 'Lỗi')}: {report.summary.errors}
                  </div>
                </div>
              </AlertDescription>
            </Alert>

            {report.issues && report.issues.length > 0 && (
              <div className="border border-border/80 rounded-xl overflow-hidden">
                <div className="bg-destructive/10 p-3 text-destructive font-semibold text-xs">
                  {t('file_import.step4.issues_title', 'Danh sách vấn đề phát hiện (Issues)')} ({report.issues.length})
                </div>
                <div className="overflow-x-auto">
                  <Table className="text-xs">
                    <TableHeader className="bg-muted/40">
                      <TableRow>
                        <TableHead className="w-16 font-semibold">Dòng</TableHead>
                        <TableHead className="w-24 font-semibold">Loại</TableHead>
                        <TableHead className="w-36 font-semibold">Lý do</TableHead>
                        <TableHead className="font-semibold">Chi tiết</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {report.issues.map((issue, idx) => (
                        <TableRow key={idx}>
                          <TableCell className="font-mono">{issue.row}</TableCell>
                          <TableCell><Badge variant="outline">{issue.kind}</Badge></TableCell>
                          <TableCell className="font-medium">{issue.reason}</TableCell>
                          <TableCell className="text-muted-foreground">{issue.message}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
