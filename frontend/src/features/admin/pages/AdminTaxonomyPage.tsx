import { useState } from 'react'
import {
  BookOpen,
  Layers,
  Plus,
  RefreshCw,
  Sparkles,
  Tag,
  Trash2,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'

type TaxonomyDomain = {
  id: string
  label: string
  sort_order: number
  is_active: boolean
}

type TaxonomySubject = {
  id: string
  domain_id: string
  label: string
  sort_order: number
  is_active: boolean
}

type TaxonomyFramework = {
  id: string
  subject_id: string
  label: string
  sort_order: number
  is_active: boolean
}

type TaxonomyOption = {
  id: string
  option_type: string
  label: string
  sub_label?: string | null
  sort_order: number
  is_active: boolean
}

export function AdminTaxonomyPage() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'domains' | 'subjects' | 'frameworks' | 'options'>('domains')

  // Domain Modal
  const [isAddDomainOpen, setIsAddDomainOpen] = useState(false)
  const [domainId, setDomainId] = useState('')
  const [domainLabel, setDomainLabel] = useState('')

  // Subject Modal
  const [isAddSubjectOpen, setIsAddSubjectOpen] = useState(false)
  const [subjectId, setSubjectId] = useState('')
  const [subjectDomainId, setSubjectDomainId] = useState('')
  const [subjectLabel, setSubjectLabel] = useState('')

  // Framework Modal
  const [isAddFrameworkOpen, setIsAddFrameworkOpen] = useState(false)
  const [frameworkId, setFrameworkId] = useState('')
  const [frameworkSubjectId, setFrameworkSubjectId] = useState('')
  const [frameworkLabel, setFrameworkLabel] = useState('')

  // Option Modal
  const [isAddOptionOpen, setIsAddOptionOpen] = useState(false)
  const [optionId, setOptionId] = useState('')
  const [optionType, setOptionType] = useState('learning_goal')
  const [optionLabel, setOptionLabel] = useState('')

  const domainsQuery = useQuery({
    queryKey: ['admin-taxonomy-domains'],
    queryFn: () => appApi.get<{ domains: TaxonomyDomain[] }>('/api/admin/taxonomy/domains?include_inactive=1'),
  })

  const subjectsQuery = useQuery({
    queryKey: ['admin-taxonomy-subjects'],
    queryFn: () => appApi.get<{ subjects: TaxonomySubject[] }>('/api/admin/taxonomy/subjects?include_inactive=1'),
  })

  const frameworksQuery = useQuery({
    queryKey: ['admin-taxonomy-frameworks'],
    queryFn: () => appApi.get<{ frameworks: TaxonomyFramework[] }>('/api/admin/taxonomy/frameworks?include_inactive=1'),
  })

  const optionsQuery = useQuery({
    queryKey: ['admin-taxonomy-options'],
    queryFn: () => appApi.get<{ options: TaxonomyOption[] }>('/api/admin/taxonomy/options?include_inactive=1'),
  })

  // Mutations
  const createDomainMutation = useMutation({
    mutationFn: () =>
      appApi.mutate('/api/admin/taxonomy/domains', 'POST', {
        id: domainId.trim().toLowerCase(),
        label: domainLabel.trim(),
      }),
    onSuccess: () => {
      toast.success('Đã tạo Lĩnh vực (Domain) mới thành công!')
      setIsAddDomainOpen(false)
      setDomainId('')
      setDomainLabel('')
      queryClient.invalidateQueries({ queryKey: ['admin-taxonomy-domains'] })
      queryClient.invalidateQueries({ queryKey: ['taxonomy-schema'] })
    },
    onError: (err: any) => toast.error(err?.message || 'Không thể tạo Lĩnh vực.'),
  })

  const createSubjectMutation = useMutation({
    mutationFn: () =>
      appApi.mutate('/api/admin/taxonomy/subjects', 'POST', {
        id: subjectId.trim().toLowerCase(),
        domain_id: subjectDomainId,
        label: subjectLabel.trim(),
      }),
    onSuccess: () => {
      toast.success('Đã tạo Môn học / Ngôn ngữ (Subject) mới thành công!')
      setIsAddSubjectOpen(false)
      setSubjectId('')
      setSubjectLabel('')
      queryClient.invalidateQueries({ queryKey: ['admin-taxonomy-subjects'] })
      queryClient.invalidateQueries({ queryKey: ['taxonomy-schema'] })
    },
    onError: (err: any) => toast.error(err?.message || 'Không thể tạo Môn học.'),
  })

  const createFrameworkMutation = useMutation({
    mutationFn: () =>
      appApi.mutate('/api/admin/taxonomy/frameworks', 'POST', {
        id: frameworkId.trim().toLowerCase(),
        subject_id: frameworkSubjectId,
        label: frameworkLabel.trim(),
      }),
    onSuccess: () => {
      toast.success('Đã tạo Khung chứng chỉ (Framework) thành công!')
      setIsAddFrameworkOpen(false)
      setFrameworkId('')
      setFrameworkLabel('')
      queryClient.invalidateQueries({ queryKey: ['admin-taxonomy-frameworks'] })
      queryClient.invalidateQueries({ queryKey: ['taxonomy-schema'] })
    },
    onError: (err: any) => toast.error(err?.message || 'Không thể tạo Khung chứng chỉ.'),
  })

  const createOptionMutation = useMutation({
    mutationFn: () =>
      appApi.mutate('/api/admin/taxonomy/options', 'POST', {
        id: optionId.trim().toLowerCase(),
        option_type: optionType,
        label: optionLabel.trim(),
      }),
    onSuccess: () => {
      toast.success('Đã tạo Option thành công!')
      setIsAddOptionOpen(false)
      setOptionId('')
      setOptionLabel('')
      queryClient.invalidateQueries({ queryKey: ['admin-taxonomy-options'] })
      queryClient.invalidateQueries({ queryKey: ['taxonomy-schema'] })
    },
    onError: (err: any) => toast.error(err?.message || 'Không thể tạo Option.'),
  })

  const deleteDomainMutation = useMutation({
    mutationFn: (id: string) => appApi.mutate(`/api/admin/taxonomy/domains/${id}`, 'DELETE'),
    onSuccess: () => {
      toast.success('Đã xóa Lĩnh vực.')
      queryClient.invalidateQueries({ queryKey: ['admin-taxonomy-domains'] })
      queryClient.invalidateQueries({ queryKey: ['taxonomy-schema'] })
    },
    onError: (err: any) => toast.error(err?.message || 'Không thể xóa.'),
  })

  const deleteSubjectMutation = useMutation({
    mutationFn: (id: string) => appApi.mutate(`/api/admin/taxonomy/subjects/${id}`, 'DELETE'),
    onSuccess: () => {
      toast.success('Đã xóa Môn học.')
      queryClient.invalidateQueries({ queryKey: ['admin-taxonomy-subjects'] })
      queryClient.invalidateQueries({ queryKey: ['taxonomy-schema'] })
    },
    onError: (err: any) => toast.error(err?.message || 'Không thể xóa.'),
  })

  if (domainsQuery.isPending || subjectsQuery.isPending) return <PageLoading label="Đang tải dữ liệu Phân loại..." />
  if (domainsQuery.error) return <Page><PageError error={domainsQuery.error} /></Page>

  const domains = domainsQuery.data?.domains || []
  const subjects = subjectsQuery.data?.subjects || []
  const frameworks = frameworksQuery.data?.frameworks || []
  const options = optionsQuery.data?.options || []

  return (
    <Page className="space-y-6">
      <PageHeader
        title="Quản lý Phân loại & Metadata (Taxonomy)"
        description="Quản lý các Lĩnh vực (Domains), Môn học/Ngôn ngữ (Subjects), Khung chứng chỉ (Frameworks) và Metadata động lưu trữ trong Database."
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              queryClient.invalidateQueries({ queryKey: ['admin-taxonomy-domains'] })
              queryClient.invalidateQueries({ queryKey: ['admin-taxonomy-subjects'] })
              queryClient.invalidateQueries({ queryKey: ['admin-taxonomy-frameworks'] })
              queryClient.invalidateQueries({ queryKey: ['admin-taxonomy-options'] })
            }}
            className="h-9 gap-1.5 rounded-xl"
          >
            <RefreshCw className="w-4 h-4" />
            Làm mới
          </Button>
        }
      />

      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)} className="w-full">
        <TabsList className="grid grid-cols-4 max-w-2xl bg-muted/60 p-1 rounded-2xl">
          <TabsTrigger value="domains" className="rounded-xl text-xs font-bold gap-1.5">
            <Layers className="w-3.5 h-3.5" /> Lĩnh vực ({domains.length})
          </TabsTrigger>
          <TabsTrigger value="subjects" className="rounded-xl text-xs font-bold gap-1.5">
            <BookOpen className="w-3.5 h-3.5" /> Môn học ({subjects.length})
          </TabsTrigger>
          <TabsTrigger value="frameworks" className="rounded-xl text-xs font-bold gap-1.5">
            <Sparkles className="w-3.5 h-3.5" /> Khung thi ({frameworks.length})
          </TabsTrigger>
          <TabsTrigger value="options" className="rounded-xl text-xs font-bold gap-1.5">
            <Tag className="w-3.5 h-3.5" /> Options ({options.length})
          </TabsTrigger>
        </TabsList>

        {/* TAB 1: DOMAINS */}
        <TabsContent value="domains" className="pt-4 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-foreground">Danh sách Lĩnh vực (Domains)</h3>
            <Button size="sm" onClick={() => setIsAddDomainOpen(true)} className="h-8 text-xs font-bold rounded-xl gap-1.5">
              <Plus className="w-3.5 h-3.5" /> Thêm Lĩnh vực mới
            </Button>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {domains.map((dom) => (
              <Card key={dom.id} className="rounded-2xl border border-border/80 shadow-2xs hover:shadow-xs transition-shadow">
                <CardHeader className="p-4 pb-2">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-sm font-bold">{dom.label}</CardTitle>
                    <Badge variant={dom.is_active ? 'secondary' : 'outline'} className="text-[10px]">
                      {dom.is_active ? 'Hoạt động' : 'Tắt'}
                    </Badge>
                  </div>
                  <CardDescription className="text-xs font-mono">ID: {dom.id}</CardDescription>
                </CardHeader>
                <CardContent className="p-4 pt-0 flex items-center justify-between text-xs text-muted-foreground">
                  <span>Môn học gắn kèm: {subjects.filter((s) => s.domain_id === dom.id).length}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-destructive hover:bg-destructive/10"
                    onClick={() => deleteDomainMutation.mutate(dom.id)}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* TAB 2: SUBJECTS */}
        <TabsContent value="subjects" className="pt-4 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-foreground">Danh sách Ngôn ngữ & Môn học (Subjects)</h3>
            <Button
              size="sm"
              onClick={() => {
                if (domains.length > 0) setSubjectDomainId(domains[0].id)
                setIsAddSubjectOpen(true)
              }}
              className="h-8 text-xs font-bold rounded-xl gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" /> Thêm Môn học mới
            </Button>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {subjects.map((sub) => (
              <Card key={sub.id} className="rounded-2xl border border-border/80 shadow-2xs">
                <CardHeader className="p-4 pb-2">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-sm font-bold">{sub.label}</CardTitle>
                    <Badge variant="outline" className="text-[10px] font-mono">
                      Domain: {sub.domain_id}
                    </Badge>
                  </div>
                  <CardDescription className="text-xs font-mono">ID: {sub.id}</CardDescription>
                </CardHeader>
                <CardContent className="p-4 pt-0 flex items-center justify-between text-xs text-muted-foreground">
                  <span>Khung chứng chỉ: {frameworks.filter((f) => f.subject_id === sub.id).length}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-destructive hover:bg-destructive/10"
                    onClick={() => deleteSubjectMutation.mutate(sub.id)}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* TAB 3: FRAMEWORKS */}
        <TabsContent value="frameworks" className="pt-4 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-foreground">Khung chứng chỉ & Kỳ thi (Frameworks)</h3>
            <Button
              size="sm"
              onClick={() => {
                if (subjects.length > 0) setFrameworkSubjectId(subjects[0].id)
                setIsAddFrameworkOpen(true)
              }}
              className="h-8 text-xs font-bold rounded-xl gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" /> Thêm Khung mới
            </Button>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {frameworks.map((fw) => (
              <Card key={fw.id} className="rounded-2xl border border-border/80 shadow-2xs">
                <CardHeader className="p-4 pb-2">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-sm font-bold">{fw.label}</CardTitle>
                    <Badge variant="outline" className="text-[10px] font-mono">
                      Subject: {fw.subject_id}
                    </Badge>
                  </div>
                  <CardDescription className="text-xs font-mono">ID: {fw.id}</CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* TAB 4: OPTIONS */}
        <TabsContent value="options" className="pt-4 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-foreground">Options (Goals, Topics, Format Features)</h3>
            <Button size="sm" onClick={() => setIsAddOptionOpen(true)} className="h-8 text-xs font-bold rounded-xl gap-1.5">
              <Plus className="w-3.5 h-3.5" /> Thêm Option mới
            </Button>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {options.map((opt) => (
              <Card key={`${opt.id}-${opt.option_type}`} className="rounded-2xl border border-border/80 shadow-2xs">
                <CardHeader className="p-4 pb-2">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-sm font-bold">{opt.label}</CardTitle>
                    <Badge variant="secondary" className="text-[10px]">
                      {opt.option_type}
                    </Badge>
                  </div>
                  <CardDescription className="text-xs font-mono">ID: {opt.id}</CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>

      {/* Dialog Add Domain */}
      <Dialog open={isAddDomainOpen} onOpenChange={setIsAddDomainOpen}>
        <DialogContent className="sm:max-w-md rounded-2xl">
          <DialogHeader>
            <DialogTitle>Thêm Lĩnh vực học tập (Domain)</DialogTitle>
            <DialogDescription>Nhập ID độc nhất và tên hiển thị cho Domain mới</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Domain ID (slug)</Label>
              <Input placeholder="ví dụ: astronomy, financial_skills..." value={domainId} onChange={(e) => setDomainId(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Tên hiển thị</Label>
              <Input placeholder="ví dụ: Thiên văn & Vũ trụ, Tài chính..." value={domainLabel} onChange={(e) => setDomainLabel(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddDomainOpen(false)}>Hủy</Button>
            <Button onClick={() => createDomainMutation.mutate()} disabled={createDomainMutation.isPending || !domainId || !domainLabel}>
              Tạo Lĩnh vực
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog Add Subject */}
      <Dialog open={isAddSubjectOpen} onOpenChange={setIsAddSubjectOpen}>
        <DialogContent className="sm:max-w-md rounded-2xl">
          <DialogHeader>
            <DialogTitle>Thêm Môn học / Ngôn ngữ (Subject)</DialogTitle>
            <DialogDescription>Gắn Môn học mới vào Lĩnh vực (Domain) phù hợp</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Lĩnh vực (Domain)</Label>
              <NativeSelect value={subjectDomainId} onChange={(e) => setSubjectDomainId(e.target.value)}>
                {domains.map((d) => (
                  <NativeSelectOption key={d.id} value={d.id}>{d.label}</NativeSelectOption>
                ))}
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Subject ID (slug)</Label>
              <Input placeholder="ví dụ: space_physics, corporate_law..." value={subjectId} onChange={(e) => setSubjectId(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Tên Môn học</Label>
              <Input placeholder="ví dụ: Vật lý Thiên văn, Luật Doanh nghiệp..." value={subjectLabel} onChange={(e) => setSubjectLabel(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddSubjectOpen(false)}>Hủy</Button>
            <Button onClick={() => createSubjectMutation.mutate()} disabled={createSubjectMutation.isPending || !subjectId || !subjectLabel}>
              Tạo Môn học
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog Add Framework */}
      <Dialog open={isAddFrameworkOpen} onOpenChange={setIsAddFrameworkOpen}>
        <DialogContent className="sm:max-w-md rounded-2xl">
          <DialogHeader>
            <DialogTitle>Thêm Khung chứng chỉ (Framework)</DialogTitle>
            <DialogDescription>Gắn Khung mới vào Môn học phù hợp</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Môn học (Subject)</Label>
              <NativeSelect value={frameworkSubjectId} onChange={(e) => setFrameworkSubjectId(e.target.value)}>
                {subjects.map((s) => (
                  <NativeSelectOption key={s.id} value={s.id}>{s.label}</NativeSelectOption>
                ))}
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Framework ID (slug)</Label>
              <Input placeholder="ví dụ: sat_exam, sat_digital..." value={frameworkId} onChange={(e) => setFrameworkId(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Tên Khung chứng chỉ</Label>
              <Input placeholder="ví dụ: SAT Digital, IELTS Academic..." value={frameworkLabel} onChange={(e) => setFrameworkLabel(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddFrameworkOpen(false)}>Hủy</Button>
            <Button onClick={() => createFrameworkMutation.mutate()} disabled={createFrameworkMutation.isPending || !frameworkId || !frameworkLabel}>
              Tạo Khung
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog Add Option */}
      <Dialog open={isAddOptionOpen} onOpenChange={setIsAddOptionOpen}>
        <DialogContent className="sm:max-w-md rounded-2xl">
          <DialogHeader>
            <DialogTitle>Thêm Option (Goal / Topic / Feature)</DialogTitle>
            <DialogDescription>Tạo mục tiêu hoặc chủ đề phân loại mới</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Loại Option</Label>
              <NativeSelect value={optionType} onChange={(e) => setOptionType(e.target.value)}>
                <NativeSelectOption value="learning_goal">Mục tiêu học tập (Learning Goal)</NativeSelectOption>
                <NativeSelectOption value="primary_topic">Chủ đề chính (Primary Topic)</NativeSelectOption>
                <NativeSelectOption value="format_feature">Tính năng định dạng (Format Feature)</NativeSelectOption>
                <NativeSelectOption value="audience">Đối tượng học tập (Audience)</NativeSelectOption>
                <NativeSelectOption value="best_used_for">Phù hợp nhất cho (Best Used For)</NativeSelectOption>
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Option ID (slug)</Label>
              <Input placeholder="ví dụ: quantum_computing, ai_prompting..." value={optionId} onChange={(e) => setOptionId(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Tên hiển thị</Label>
              <Input placeholder="ví dụ: Điện toán lượng tử, Lập trình AI..." value={optionLabel} onChange={(e) => setOptionLabel(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddOptionOpen(false)}>Hủy</Button>
            <Button onClick={() => createOptionMutation.mutate()} disabled={createOptionMutation.isPending || !optionId || !optionLabel}>
              Tạo Option
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Page>
  )
}
