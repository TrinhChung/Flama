import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { TabsContent } from '@/components/ui/tabs'
import { EmptyState } from '@/shared/components/PageState'
import {
  Check,
  Copy,
  KeyRound,
  RefreshCw,
  ShieldAlert,
  Trash2,
} from 'lucide-react'
import type { useYomitanTokenCRUD } from '../hooks/useYomitanTokenCRUD'

type TokenCrudResult = ReturnType<typeof useYomitanTokenCRUD>

interface YomitanTokensTabProps {
  hookResult: TokenCrudResult
}

function displayDate(value: string | null) {
  return value ? new Date(value).toLocaleString('vi-VN') : 'Không hết hạn'
}

export function YomitanTokensTab({ hookResult }: YomitanTokensTabProps) {
  const {
    query,
    name,
    setName,
    expiry,
    setExpiry,
    copied,
    copy,
    issuedConnectUrl,
    refresh,
    createMutation,
    revokeMutation,
    rotateMutation,
  } = hookResult

  return (
    <TabsContent value="tokens" className="space-y-6">
      <Card className="shadow-2xs">
        <CardHeader className="p-4 sm:p-6">
          <CardTitle className="text-base sm:text-lg font-bold">Tạo API Token Flama Connect</CardTitle>
          <CardDescription className="text-xs sm:text-sm">
            Mỗi thiết bị hoặc trình duyệt nên dùng 1 token riêng để dễ dàng theo dõi và thu hồi bảo mật khi cần thiết.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 sm:p-6 pt-0 space-y-5 sm:space-y-6">
          <div className="grid gap-4 md:grid-cols-[1fr_240px_auto] md:items-end">
            <div className="space-y-2">
              <Label htmlFor="connect-token-name" className="text-xs font-semibold">Tên thiết bị / Trình duyệt</Label>
              <Input
                id="connect-token-name"
                value={name}
                maxLength={120}
                placeholder="Ví dụ: Yomitan - Chrome PC / Kiwi Mobile"
                className="h-10 text-sm"
                onChange={(event) => setName(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="connect-token-expiry" className="text-xs font-semibold">Thời hạn hiệu lực</Label>
              <NativeSelect
                id="connect-token-expiry"
                className="w-full h-10 text-sm"
                value={expiry}
                onChange={(event) => setExpiry(event.target.value)}
              >
                <NativeSelectOption value="30">30 ngày</NativeSelectOption>
                <NativeSelectOption value="90">90 ngày</NativeSelectOption>
                <NativeSelectOption value="180">180 ngày (mặc định)</NativeSelectOption>
                <NativeSelectOption value="365">365 ngày</NativeSelectOption>
                <NativeSelectOption value="none">Không hết hạn</NativeSelectOption>
              </NativeSelect>
            </div>
            <Button
              size="lg"
              className="w-full md:w-auto h-10 font-semibold shadow-2xs"
              disabled={!name.trim() || createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              <KeyRound className="mr-2 size-4" /> Tạo token mới
            </Button>
          </div>

          <Alert className="border-sky-500/30 bg-sky-50/50 dark:bg-sky-950/20 p-3.5 sm:p-4">
            <ShieldAlert className="size-4 text-sky-600 dark:text-sky-400 shrink-0 mt-0.5" />
            <div>
              <AlertTitle className="text-sky-900 dark:text-sky-200 text-xs sm:text-sm font-semibold">Cấu hình nhanh trong Yomitan</AlertTitle>
              <AlertDescription className="mt-1 text-xs text-sky-800 dark:text-sky-300 leading-relaxed">
                Tạo token rồi dán toàn bộ URL được cấp vào ô <strong>Server URL</strong> trong phần tích hợp của Yomitan (không cần nhập API Key riêng). Xem hướng dẫn chi tiết tại tab <strong>Hướng dẫn Cài đặt</strong>.
              </AlertDescription>
            </div>
          </Alert>

          {issuedConnectUrl ? (
            <Alert className="border-amber-500/50 bg-amber-50 dark:bg-amber-950/30 p-3.5 sm:p-4">
              <ShieldAlert className="size-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              <div className="space-y-2.5 w-full min-w-0">
                <AlertTitle className="text-amber-900 dark:text-amber-200 font-bold text-xs sm:text-sm">
                  Sao chép URL này ngay — Flama sẽ không hiển thị lại URL đầy đủ sau khi bạn rời trang!
                </AlertTitle>
                <AlertDescription className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 pt-1">
                  <code className="min-w-0 flex-1 break-all rounded-lg border bg-background p-3 text-xs font-mono select-all overflow-x-auto max-h-32">
                    {issuedConnectUrl}
                  </code>
                  <Button
                    variant="default"
                    className="w-full sm:w-auto shrink-0 bg-amber-600 hover:bg-amber-700 text-white h-10 font-semibold"
                    onClick={() => copy('connect-url', issuedConnectUrl)}
                  >
                    {copied === 'connect-url' ? <Check className="mr-2 size-4 text-white" /> : <Copy className="mr-2 size-4" />}
                    {copied === 'connect-url' ? 'Đã sao chép URL' : 'Sao chép URL'}
                  </Button>
                </AlertDescription>
              </div>
            </Alert>
          ) : null}
        </CardContent>
      </Card>

      {/* Tokens List */}
      <Card className="shadow-2xs">
        <CardHeader className="p-4 sm:p-6 flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base sm:text-lg font-bold">Danh sách Token đã tạo</CardTitle>
            <CardDescription className="text-xs">Các API Key đang hoạt động hoặc đã thu hồi của tài khoản</CardDescription>
          </div>
          <Button size="sm" variant="outline" onClick={refresh} title="Tải lại danh sách" className="h-8 px-2.5 text-xs">
            <RefreshCw className="size-3.5 mr-1" /> Làm mới
          </Button>
        </CardHeader>
        <CardContent className="p-4 sm:p-6 pt-0">
          {!query.data?.items.length ? (
            <EmptyState title="Chưa có token Yomitan" description="Hãy tạo token đầu tiên để kết nối tiện ích Yomitan với Flama." />
          ) : (
            <>
              {/* Mobile View */}
              <div className="grid gap-3.5 md:hidden">
                {query.data.items.map((token) => (
                  <div key={token.id} className="rounded-xl border bg-card p-4 space-y-3 shadow-2xs">
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-1 min-w-0">
                        <div className="font-semibold text-sm truncate">{token.name}</div>
                        <code className="text-[11px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded font-mono">
                          {token.token_prefix}…
                        </code>
                      </div>
                      <Badge
                        variant={
                          token.status === 'active'
                            ? 'default'
                            : token.status === 'revoked'
                            ? 'destructive'
                            : 'secondary'
                        }
                        className="text-[11px] shrink-0"
                      >
                        {token.status === 'active' ? 'Đang hoạt động' : token.status === 'revoked' ? 'Đã thu hồi' : token.status}
                      </Badge>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground pt-1 border-t">
                      <div>
                        <span className="block text-[10px] font-medium text-muted-foreground/70 uppercase">Hết hạn</span>
                        <span className="text-foreground font-medium">{displayDate(token.expires_at)}</span>
                      </div>
                      <div>
                        <span className="block text-[10px] font-medium text-muted-foreground/70 uppercase">Dùng gần nhất</span>
                        <span className="text-foreground font-medium">{token.last_used_at ? displayDate(token.last_used_at) : 'Chưa dùng'}</span>
                      </div>
                    </div>

                    {token.status === 'active' ? (
                      <div className="flex gap-2 pt-2 border-t">
                        <Button
                          size="sm"
                          variant="outline"
                          className="flex-1 h-9 text-xs"
                          disabled={rotateMutation.isPending}
                          onClick={() =>
                            window.confirm('Thu hồi token cũ và tạo token mới với tên này?') &&
                            rotateMutation.mutate(token.id)
                          }
                        >
                          <RefreshCw className="mr-1.5 size-3.5 text-muted-foreground" /> Tạo lại
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="flex-1 h-9 text-xs text-destructive hover:text-destructive hover:bg-destructive/10 border-destructive/30"
                          disabled={revokeMutation.isPending}
                          onClick={() =>
                            window.confirm('Bạn có chắc chắn muốn thu hồi token này ngay lập tức?') &&
                            revokeMutation.mutate(token.id)
                          }
                        >
                          <Trash2 className="mr-1.5 size-3.5" /> Thu hồi
                        </Button>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>

              {/* Desktop View */}
              <div className="hidden md:block overflow-x-auto rounded-xl border">
                <Table>
                  <TableHeader className="bg-muted/50">
                    <TableRow>
                      <TableHead>Tên thiết bị</TableHead>
                      <TableHead>Trạng thái</TableHead>
                      <TableHead>Hết hạn</TableHead>
                      <TableHead>Lần dùng gần nhất</TableHead>
                      <TableHead className="text-right">Thao tác</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {query.data.items.map((token) => (
                      <TableRow key={token.id} className="hover:bg-muted/30">
                        <TableCell>
                          <div className="font-semibold text-sm">{token.name}</div>
                          <code className="text-[11px] text-muted-foreground">{token.token_prefix}…</code>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              token.status === 'active'
                                ? 'default'
                                : token.status === 'revoked'
                                ? 'destructive'
                                : 'secondary'
                            }
                            className="text-[11px]"
                          >
                            {token.status === 'active' ? 'Đang hoạt động' : token.status === 'revoked' ? 'Đã thu hồi' : token.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs">{displayDate(token.expires_at)}</TableCell>
                        <TableCell className="text-xs">
                          {token.last_used_at ? displayDate(token.last_used_at) : 'Chưa từng sử dụng'}
                        </TableCell>
                        <TableCell className="text-right">
                          {token.status === 'active' ? (
                            <div className="flex justify-end gap-1">
                              <Button
                                size="sm"
                                variant="ghost"
                                disabled={rotateMutation.isPending}
                                onClick={() =>
                                  window.confirm('Thu hồi token cũ và tạo token mới với tên này?') &&
                                  rotateMutation.mutate(token.id)
                                }
                              >
                                <RefreshCw className="mr-1 size-3.5 text-muted-foreground" /> Tạo lại
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="text-destructive hover:text-destructive hover:bg-destructive/10"
                                disabled={revokeMutation.isPending}
                                onClick={() =>
                                  window.confirm('Bạn có chắc chắn muốn thu hồi token này ngay lập tức?') &&
                                  revokeMutation.mutate(token.id)
                                }
                              >
                                <Trash2 className="mr-1 size-3.5" /> Thu hồi
                              </Button>
                            </div>
                          ) : null}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </TabsContent>
  )
}
