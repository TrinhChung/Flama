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
} from 'lucide-react'
import type { useFileImportWizard } from '../hooks/useFileImportWizard'

interface ImportResultStepProps {
  wizard: ReturnType<typeof useFileImportWizard>
}

export function ImportResultStep({ wizard }: ImportResultStepProps) {
  const {
    estimateMutation,
    executeMutation,
    handleEstimate,
    handleExecute,
    report,
    executionDone,
    hasEstimated,
  } = wizard

  return (
    <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
      <CardHeader className="pb-3 border-b bg-card/50">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <CheckCircle2 className="size-4 text-primary" />
          Rà soát &amp; Thực thi Import
        </CardTitle>
        <CardDescription className="text-xs">
          Chạy ước lượng thử nghiệm hoặc tiến hành nạp dữ liệu chính thức.
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-4 space-y-4">
        <div className="flex flex-wrap gap-3">
          <Button
            variant="outline"
            disabled={estimateMutation.isPending || executeMutation.isPending}
            onClick={handleEstimate}
            className="font-medium"
          >
            {estimateMutation.isPending ? <Loader2 className="size-4 animate-spin mr-1.5" /> : null}
            1. Ước lượng thử nghiệm
          </Button>

          <Button
            disabled={!hasEstimated || estimateMutation.isPending || executeMutation.isPending}
            onClick={handleExecute}
            className="font-semibold shadow-sm"
          >
            {executeMutation.isPending ? <Loader2 className="size-4 animate-spin mr-1.5" /> : null}
            2. Thực thi import
          </Button>
        </div>

        {(estimateMutation.isPending || executeMutation.isPending) && (
          <div className="space-y-1.5">
            <Progress value={85} className="h-2" />
            <p className="text-xs text-muted-foreground text-center">Đang xử lý dữ liệu import…</p>
          </div>
        )}

        {report && (
          <div className="space-y-4 pt-2">
            <Alert className={executionDone ? 'border-primary/40 bg-primary/5' : 'border-border/80 bg-muted/30'}>
              {executionDone ? <CheckCircle2 className="size-5 text-primary" /> : <AlertTriangle className="size-5 text-muted-foreground" />}
              <AlertTitle className="font-bold text-foreground">
                {executionDone ? 'Thực thi Import thành công!' : 'Kết quả ước lượng trước import'}
              </AlertTitle>
              <AlertDescription className="mt-2 text-xs">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-medium">
                  <div>Tổng dòng: {report.summary.total_rows}</div>
                  <div>Dòng hợp lệ: {report.summary.valid_rows}</div>
                  <div className="text-primary font-bold">Thêm mới: {report.summary.inserted}</div>
                  <div className="font-semibold">Cập nhật: {report.summary.updated}</div>
                  <div className="text-muted-foreground">Bỏ qua: {report.summary.skipped}</div>
                  <div className="text-destructive font-semibold">Lỗi: {report.summary.errors}</div>
                </div>
              </AlertDescription>
            </Alert>

            {report.issues && report.issues.length > 0 && (
              <div className="border border-border/80 rounded-xl overflow-hidden">
                <div className="bg-destructive/10 p-3 text-destructive font-semibold text-xs">
                  Báo cáo chi tiết dòng gặp sự cố ({report.issues.length} vấn đề)
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
