import { Info } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Page, PageHeader } from '@/shared/components/Page'

export { SupportPage } from '@/features/support/pages/SupportPage'
export { TtsKeyGuidePage } from '@/features/support/pages/TtsKeyGuidePage'


function LegalPage({ title, summary }: { title: string; summary: string }) {
  return (
    <Page className="max-w-4xl">
      <PageHeader title={title} description="Cập nhật lần cuối: 26/07/2026" />
      <Alert>
        <Info />
        <AlertTitle>Tóm tắt</AlertTitle>
        <AlertDescription>{summary}</AlertDescription>
      </Alert>
      <Card>
        <CardHeader>
          <CardTitle>Phạm vi áp dụng</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6 leading-7">
          <p>
            Nội dung đầy đủ sẽ được chuyển từ template Jinja hiện tại sang
            structured content trong giai đoạn nối API/CMS.
          </p>
          <div className="space-y-3">
            <h2 className="text-lg font-semibold">Nguyên tắc chung</h2>
            <ul className="list-disc space-y-2 pl-5 text-muted-foreground">
              <li>Bảo vệ dữ liệu tài khoản và tiến độ học.</li>
              <li>Không chia sẻ thông tin thanh toán nhạy cảm.</li>
              <li>Tôn trọng quyền sở hữu học liệu của tác giả.</li>
            </ul>
          </div>
        </CardContent>
      </Card>
    </Page>
  )
}

export function TermsPage() {
  return <LegalPage title="Điều khoản sử dụng" summary="Các nguyên tắc sử dụng tài khoản, học liệu và marketplace Flama." />
}

export function PrivacyPage() {
  return <LegalPage title="Chính sách bảo mật" summary="Cách Flama thu thập, sử dụng và bảo vệ dữ liệu của người học." />
}

export function CookiesPage() {
  return <LegalPage title="Chính sách cookie" summary="Cookie phiên đăng nhập, CSRF và các lựa chọn cần thiết để ứng dụng hoạt động." />
}
