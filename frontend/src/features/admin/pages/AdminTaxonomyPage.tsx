import { useState } from 'react'
import {
  Award,
  BookOpen,
  Check,
  Database,
  Edit2,
  GraduationCap,
  Layers,
  Link2,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Tag,
  Trash2,
  X,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
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
import { Switch } from '@/components/ui/switch'
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

type TaxonomyFrameworkLevel = {
  id: string
  framework_id: string
  subject_id: string
  label: string
  difficulty_band: string
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

type SubjectOptionMap = {
  subject_id: string
  option_id: string
  option_type: string
}

const OPTION_TYPES: { id: string; label: string; description: string }[] = [
  { id: 'learning_goal', label: 'Mục tiêu học tập', description: 'Mục đích học tập (Từ vựng, Ngữ pháp, Luyện thi...)' },
  { id: 'primary_topic', label: 'Chủ đề chính', description: 'Chủ đề chi tiết (Kanji, Mẫu câu, Nghe, Đời sống...)' },
  { id: 'format_feature', label: 'Tính năng định dạng', description: 'Đặc điểm thẻ (Có audio, Có ví dụ, Cloze...)' },
  { id: 'audience', label: 'Đối tượng học tập', description: 'Phù hợp đối tượng (Tự học, Luyện thi...)' },
  { id: 'best_used_for', label: 'Phù hợp nhất cho', description: 'Mục đích tối ưu (Note Type display)' },
]

export function AdminTaxonomyPage() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'domains' | 'subjects' | 'frameworks' | 'options' | 'mappings'>('domains')
  const [searchQuery, setSearchQuery] = useState('')

  // Filter Sub-states
  const [selectedDomainFilter, setSelectedDomainFilter] = useState<string>('all')
  const [selectedSubjectFilter, setSelectedSubjectFilter] = useState<string>('all')
  const [selectedOptionTypeFilter, setSelectedOptionTypeFilter] = useState<string>('all')

  // Subject Mapping Tab State
  const [mappingSubjectId, setMappingSubjectId] = useState<string>('')
  const [mappingOptionType, setMappingOptionType] = useState<string>('learning_goal')
  const [selectedOptionIds, setSelectedOptionIds] = useState<string[]>([])

  // Modal States - Domains
  const [isDomainModalOpen, setIsDomainModalOpen] = useState(false)
  const [editingDomain, setEditingDomain] = useState<TaxonomyDomain | null>(null)
  const [domainId, setDomainId] = useState('')
  const [domainLabel, setDomainLabel] = useState('')
  const [domainSortOrder, setDomainSortOrder] = useState('0')
  const [domainIsActive, setDomainIsActive] = useState(true)

  // Modal States - Subjects
  const [isSubjectModalOpen, setIsSubjectModalOpen] = useState(false)
  const [editingSubject, setEditingSubject] = useState<TaxonomySubject | null>(null)
  const [subjectId, setSubjectId] = useState('')
  const [subjectDomainId, setSubjectDomainId] = useState('')
  const [subjectLabel, setSubjectLabel] = useState('')
  const [subjectSortOrder, setSubjectSortOrder] = useState('0')
  const [subjectIsActive, setSubjectIsActive] = useState(true)

  // Modal States - Frameworks
  const [isFrameworkModalOpen, setIsFrameworkModalOpen] = useState(false)
  const [editingFramework, setEditingFramework] = useState<TaxonomyFramework | null>(null)
  const [frameworkId, setFrameworkId] = useState('')
  const [frameworkSubjectId, setFrameworkSubjectId] = useState('')
  const [frameworkLabel, setFrameworkLabel] = useState('')
  const [frameworkSortOrder, setFrameworkSortOrder] = useState('0')
  const [frameworkIsActive, setFrameworkIsActive] = useState(true)

  // Modal States - Framework Levels
  const [isLevelModalOpen, setIsLevelModalOpen] = useState(false)
  const [editingLevel, setEditingLevel] = useState<TaxonomyFrameworkLevel | null>(null)
  const [levelId, setLevelId] = useState('')
  const [levelFrameworkId, setLevelFrameworkId] = useState('')
  const [levelSubjectId, setLevelSubjectId] = useState('')
  const [levelLabel, setLevelLabel] = useState('')
  const [levelDifficulty, setLevelDifficulty] = useState('beginner')
  const [levelSortOrder, setLevelSortOrder] = useState('0')
  const [levelIsActive, setLevelIsActive] = useState(true)

  // Modal States - Options
  const [isOptionModalOpen, setIsOptionModalOpen] = useState(false)
  const [editingOption, setEditingOption] = useState<TaxonomyOption | null>(null)
  const [optionId, setOptionId] = useState('')
  const [optionType, setOptionType] = useState('learning_goal')
  const [optionLabel, setOptionLabel] = useState('')
  const [optionSubLabel, setOptionSubLabel] = useState('')
  const [optionSortOrder, setOptionSortOrder] = useState('0')
  const [optionIsActive, setOptionIsActive] = useState(true)

  // Queries
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

  const levelsQuery = useQuery({
    queryKey: ['admin-taxonomy-levels'],
    queryFn: () => appApi.get<{ levels: TaxonomyFrameworkLevel[] }>('/api/admin/taxonomy/framework-levels?include_inactive=1'),
  })

  const optionsQuery = useQuery({
    queryKey: ['admin-taxonomy-options'],
    queryFn: () => appApi.get<{ options: TaxonomyOption[] }>('/api/admin/taxonomy/options?include_inactive=1'),
  })

  const mappingsQuery = useQuery({
    queryKey: ['admin-taxonomy-mappings', mappingSubjectId, mappingOptionType],
    queryFn: async () => {
      if (!mappingSubjectId) return { mappings: [] }
      const res = await appApi.get<{ mappings: SubjectOptionMap[] }>(
        `/api/admin/taxonomy/subject-mappings?subject_id=${mappingSubjectId}&option_type=${mappingOptionType}`
      )
      setSelectedOptionIds(res.mappings.map((m) => m.option_id))
      return res
    },
    enabled: Boolean(mappingSubjectId),
  })

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['admin-taxonomy-domains'] })
    queryClient.invalidateQueries({ queryKey: ['admin-taxonomy-subjects'] })
    queryClient.invalidateQueries({ queryKey: ['admin-taxonomy-frameworks'] })
    queryClient.invalidateQueries({ queryKey: ['admin-taxonomy-levels'] })
    queryClient.invalidateQueries({ queryKey: ['admin-taxonomy-options'] })
    queryClient.invalidateQueries({ queryKey: ['admin-taxonomy-mappings'] })
    queryClient.invalidateQueries({ queryKey: ['taxonomy-schema'] })
  }

  // --- MUTATIONS ---
  // Reseed Defaults
  const reseedMutation = useMutation({
    mutationFn: () => appApi.mutate('/api/admin/taxonomy/reseed-defaults', 'POST', {}),
    onSuccess: () => {
      toast.success('Đã nạp và đồng bộ taxonomy mặc định vào cơ sở dữ liệu!')
      invalidateAll()
    },
    onError: (err: any) => toast.error(err?.message || 'Không thể đồng bộ taxonomy mẫu.'),
  })

  // Domain Save
  const saveDomainMutation = useMutation({
    mutationFn: () => {
      const payload = {
        label: domainLabel.trim(),
        sort_order: Number(domainSortOrder) || 0,
        is_active: domainIsActive,
      }
      if (editingDomain) {
        return appApi.mutate(`/api/admin/taxonomy/domains/${editingDomain.id}`, 'PUT', payload)
      }
      return appApi.mutate('/api/admin/taxonomy/domains', 'POST', {
        id: domainId.trim().toLowerCase(),
        ...payload,
      })
    },
    onSuccess: () => {
      toast.success(editingDomain ? 'Đã cập nhật Lĩnh vực.' : 'Đã tạo Lĩnh vực mới.')
      setIsDomainModalOpen(false)
      invalidateAll()
    },
    onError: (err: any) => toast.error(err?.message || 'Thao tác thất bại.'),
  })

  const deleteDomainMutation = useMutation({
    mutationFn: (id: string) => appApi.mutate(`/api/admin/taxonomy/domains/${id}`, 'DELETE'),
    onSuccess: () => {
      toast.success('Đã xóa Lĩnh vực.')
      invalidateAll()
    },
    onError: (err: any) => toast.error(err?.message || 'Không thể xóa.'),
  })

  // Subject Save
  const saveSubjectMutation = useMutation({
    mutationFn: () => {
      const payload = {
        domain_id: subjectDomainId,
        label: subjectLabel.trim(),
        sort_order: Number(subjectSortOrder) || 0,
        is_active: subjectIsActive,
      }
      if (editingSubject) {
        return appApi.mutate(`/api/admin/taxonomy/subjects/${editingSubject.id}`, 'PUT', payload)
      }
      return appApi.mutate('/api/admin/taxonomy/subjects', 'POST', {
        id: subjectId.trim().toLowerCase(),
        ...payload,
      })
    },
    onSuccess: () => {
      toast.success(editingSubject ? 'Đã cập nhật Môn học.' : 'Đã tạo Môn học mới.')
      setIsSubjectModalOpen(false)
      invalidateAll()
    },
    onError: (err: any) => toast.error(err?.message || 'Thao tác thất bại.'),
  })

  const deleteSubjectMutation = useMutation({
    mutationFn: (id: string) => appApi.mutate(`/api/admin/taxonomy/subjects/${id}`, 'DELETE'),
    onSuccess: () => {
      toast.success('Đã xóa Môn học.')
      invalidateAll()
    },
    onError: (err: any) => toast.error(err?.message || 'Không thể xóa.'),
  })

  // Framework Save
  const saveFrameworkMutation = useMutation({
    mutationFn: () => {
      const payload = {
        subject_id: frameworkSubjectId,
        label: frameworkLabel.trim(),
        sort_order: Number(frameworkSortOrder) || 0,
        is_active: frameworkIsActive,
      }
      if (editingFramework) {
        return appApi.mutate(`/api/admin/taxonomy/frameworks/${editingFramework.id}`, 'PUT', payload)
      }
      return appApi.mutate('/api/admin/taxonomy/frameworks', 'POST', {
        id: frameworkId.trim().toLowerCase(),
        ...payload,
      })
    },
    onSuccess: () => {
      toast.success(editingFramework ? 'Đã cập nhật Khung chứng chỉ.' : 'Đã tạo Khung chứng chỉ mới.')
      setIsFrameworkModalOpen(false)
      invalidateAll()
    },
    onError: (err: any) => toast.error(err?.message || 'Thao tác thất bại.'),
  })

  const deleteFrameworkMutation = useMutation({
    mutationFn: (id: string) => appApi.mutate(`/api/admin/taxonomy/frameworks/${id}`, 'DELETE'),
    onSuccess: () => {
      toast.success('Đã xóa Khung chứng chỉ.')
      invalidateAll()
    },
    onError: (err: any) => toast.error(err?.message || 'Không thể xóa.'),
  })

  // Level Save
  const saveLevelMutation = useMutation({
    mutationFn: () => {
      const payload = {
        framework_id: levelFrameworkId,
        subject_id: levelSubjectId,
        label: levelLabel.trim(),
        difficulty_band: levelDifficulty,
        sort_order: Number(levelSortOrder) || 0,
        is_active: levelIsActive,
      }
      if (editingLevel) {
        return appApi.mutate(`/api/admin/taxonomy/framework-levels/${editingLevel.id}`, 'PUT', payload)
      }
      return appApi.mutate('/api/admin/taxonomy/framework-levels', 'POST', {
        id: levelId.trim().toLowerCase(),
        ...payload,
      })
    },
    onSuccess: () => {
      toast.success(editingLevel ? 'Đã cập nhật Cấp độ.' : 'Đã tạo Cấp độ mới.')
      setIsLevelModalOpen(false)
      invalidateAll()
    },
    onError: (err: any) => toast.error(err?.message || 'Thao tác thất bại.'),
  })

  const deleteLevelMutation = useMutation({
    mutationFn: (id: string) => appApi.mutate(`/api/admin/taxonomy/framework-levels/${id}`, 'DELETE'),
    onSuccess: () => {
      toast.success('Đã xóa Cấp độ.')
      invalidateAll()
    },
    onError: (err: any) => toast.error(err?.message || 'Không thể xóa.'),
  })

  // Option Save
  const saveOptionMutation = useMutation({
    mutationFn: () => {
      const payload = {
        option_type: optionType,
        label: optionLabel.trim(),
        sub_label: optionSubLabel.trim() || null,
        sort_order: Number(optionSortOrder) || 0,
        is_active: optionIsActive,
      }
      if (editingOption) {
        return appApi.mutate(`/api/admin/taxonomy/options/${editingOption.id}`, 'PUT', payload)
      }
      return appApi.mutate('/api/admin/taxonomy/options', 'POST', {
        id: optionId.trim().toLowerCase(),
        ...payload,
      })
    },
    onSuccess: () => {
      toast.success(editingOption ? 'Đã cập nhật Option.' : 'Đã tạo Option mới.')
      setIsOptionModalOpen(false)
      invalidateAll()
    },
    onError: (err: any) => toast.error(err?.message || 'Thao tác thất bại.'),
  })

  const deleteOptionMutation = useMutation({
    mutationFn: (id: string) => appApi.mutate(`/api/admin/taxonomy/options/${id}`, 'DELETE'),
    onSuccess: () => {
      toast.success('Đã xóa Option.')
      invalidateAll()
    },
    onError: (err: any) => toast.error(err?.message || 'Không thể xóa.'),
  })

  // Subject Mappings Save
  const saveSubjectMappingsMutation = useMutation({
    mutationFn: () =>
      appApi.mutate('/api/admin/taxonomy/subject-mappings', 'POST', {
        subject_id: mappingSubjectId,
        option_type: mappingOptionType,
        option_ids: selectedOptionIds,
      }),
    onSuccess: () => {
      toast.success('Đã lưu ánh xạ metadata cho Môn học thành công!')
      invalidateAll()
    },
    onError: (err: any) => toast.error(err?.message || 'Không thể lưu ánh xạ.'),
  })

  // Data Loading Check
  if (domainsQuery.isPending || subjectsQuery.isPending) {
    return <PageLoading label="Đang tải dữ liệu Phân loại & Metadata..." />
  }
  if (domainsQuery.error) {
    return (
      <Page>
        <PageError error={domainsQuery.error} />
      </Page>
    )
  }

  const domains = domainsQuery.data?.domains || []
  const subjects = subjectsQuery.data?.subjects || []
  const frameworks = frameworksQuery.data?.frameworks || []
  const levels = levelsQuery.data?.levels || []
  const options = optionsQuery.data?.options || []

  // Ensure mapping subject is initialized
  if (!mappingSubjectId && subjects.length > 0) {
    setMappingSubjectId(subjects[0].id)
  }

  // Filtered lists based on search and tab selections
  const filteredDomains = domains.filter(
    (d) =>
      d.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
      d.id.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const filteredSubjects = subjects.filter((s) => {
    const matchesSearch =
      s.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.id.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesDomain = selectedDomainFilter === 'all' || s.domain_id === selectedDomainFilter
    return matchesSearch && matchesDomain
  })

  const filteredFrameworks = frameworks.filter((f) => {
    const matchesSearch =
      f.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.id.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesSubject = selectedSubjectFilter === 'all' || f.subject_id === selectedSubjectFilter
    return matchesSearch && matchesSubject
  })

  const filteredOptions = options.filter((o) => {
    const matchesSearch =
      o.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
      o.id.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesType = selectedOptionTypeFilter === 'all' || o.option_type === selectedOptionTypeFilter
    return matchesSearch && matchesType
  })

  // Helper Modal Openers
  const openDomainModal = (dom?: TaxonomyDomain) => {
    if (dom) {
      setEditingDomain(dom)
      setDomainId(dom.id)
      setDomainLabel(dom.label)
      setDomainSortOrder(String(dom.sort_order))
      setDomainIsActive(dom.is_active)
    } else {
      setEditingDomain(null)
      setDomainId('')
      setDomainLabel('')
      setDomainSortOrder('0')
      setDomainIsActive(true)
    }
    setIsDomainModalOpen(true)
  }

  const openSubjectModal = (sub?: TaxonomySubject) => {
    if (sub) {
      setEditingSubject(sub)
      setSubjectId(sub.id)
      setSubjectDomainId(sub.domain_id)
      setSubjectLabel(sub.label)
      setSubjectSortOrder(String(sub.sort_order))
      setSubjectIsActive(sub.is_active)
    } else {
      setEditingSubject(null)
      setSubjectId('')
      setSubjectDomainId(domains[0]?.id || '')
      setSubjectLabel('')
      setSubjectSortOrder('0')
      setSubjectIsActive(true)
    }
    setIsSubjectModalOpen(true)
  }

  const openFrameworkModal = (fw?: TaxonomyFramework) => {
    if (fw) {
      setEditingFramework(fw)
      setFrameworkId(fw.id)
      setFrameworkSubjectId(fw.subject_id)
      setFrameworkLabel(fw.label)
      setFrameworkSortOrder(String(fw.sort_order))
      setFrameworkIsActive(fw.is_active)
    } else {
      setEditingFramework(null)
      setFrameworkId('')
      setFrameworkSubjectId(subjects[0]?.id || '')
      setFrameworkLabel('')
      setFrameworkSortOrder('0')
      setFrameworkIsActive(true)
    }
    setIsFrameworkModalOpen(true)
  }

  const openLevelModal = (lvl?: TaxonomyFrameworkLevel) => {
    if (lvl) {
      setEditingLevel(lvl)
      setLevelId(lvl.id)
      setLevelFrameworkId(lvl.framework_id)
      setLevelSubjectId(lvl.subject_id)
      setLevelLabel(lvl.label)
      setLevelDifficulty(lvl.difficulty_band)
      setLevelSortOrder(String(lvl.sort_order))
      setLevelIsActive(lvl.is_active)
    } else {
      setEditingLevel(null)
      setLevelId('')
      const defaultFw = frameworks[0]
      setLevelFrameworkId(defaultFw?.id || '')
      setLevelSubjectId(defaultFw?.subject_id || subjects[0]?.id || '')
      setLevelLabel('')
      setLevelDifficulty('beginner')
      setLevelSortOrder('0')
      setLevelIsActive(true)
    }
    setIsLevelModalOpen(true)
  }

  const openOptionModal = (opt?: TaxonomyOption) => {
    if (opt) {
      setEditingOption(opt)
      setOptionId(opt.id)
      setOptionType(opt.option_type)
      setOptionLabel(opt.label)
      setOptionSubLabel(opt.sub_label || '')
      setOptionSortOrder(String(opt.sort_order))
      setOptionIsActive(opt.is_active)
    } else {
      setEditingOption(null)
      setOptionId('')
      setOptionType('learning_goal')
      setOptionLabel('')
      setOptionSubLabel('')
      setOptionSortOrder('0')
      setOptionIsActive(true)
    }
    setIsOptionModalOpen(true)
  }

  return (
    <Page size="wide" className="space-y-6">
      {/* Header */}
      <PageHeader
        title="Quản lý Phân loại & Metadata (Taxonomy)"
        description="Quản lý toàn diện các Lĩnh vực (Domains), Môn học (Subjects), Khung thi (Frameworks), Cấp độ (Levels) và Thuộc tính phân loại động trong Database."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => reseedMutation.mutate()}
              disabled={reseedMutation.isPending}
              className="h-9 gap-1.5 rounded-xl text-xs font-semibold"
              title="Đồng bộ lại cấu trúc mẫu mặc định"
            >
              <Database className="w-3.5 h-3.5 text-primary" />
              Nạp dữ liệu mẫu
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={invalidateAll}
              className="h-9 gap-1.5 rounded-xl text-xs font-semibold"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Làm mới
            </Button>
          </div>
        }
      />

      {/* Top Metric Stats Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <Card className="rounded-xl border border-border/70 p-3.5 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase">Lĩnh vực</span>
            <Layers className="size-4 text-blue-500" />
          </div>
          <p className="text-2xl font-bold mt-1 tabular-nums">{domains.length}</p>
        </Card>
        <Card className="rounded-xl border border-border/70 p-3.5 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase">Môn học</span>
            <BookOpen className="size-4 text-emerald-500" />
          </div>
          <p className="text-2xl font-bold mt-1 tabular-nums">{subjects.length}</p>
        </Card>
        <Card className="rounded-xl border border-border/70 p-3.5 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase">Khung thi</span>
            <GraduationCap className="size-4 text-muted-foreground" />
          </div>
          <p className="text-2xl font-bold mt-1 tabular-nums">{frameworks.length}</p>
        </Card>
        <Card className="rounded-xl border border-border/70 p-3.5 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase">Cấp độ</span>
            <Award className="size-4 text-muted-foreground" />
          </div>
          <p className="text-2xl font-bold mt-1 tabular-nums">{levels.length}</p>
        </Card>
        <Card className="rounded-xl border border-border/70 p-3.5 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase">Metadata</span>
            <Tag className="size-4 text-muted-foreground" />
          </div>
          <p className="text-2xl font-bold mt-1 tabular-nums">{options.length}</p>
        </Card>
      </div>

      {/* Main Tabs Navigation */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)} className="w-full space-y-4">
        <div className="flex flex-col sm:flex-row gap-3 sm:items-center justify-between">
          <TabsList className="grid grid-cols-5 w-full sm:w-auto bg-muted/60 p-1 rounded-xl">
            <TabsTrigger value="domains" className="rounded-lg text-xs font-bold gap-1.5">
              <Layers className="size-3.5" />
              <span className="hidden sm:inline">Lĩnh vực</span> ({domains.length})
            </TabsTrigger>
            <TabsTrigger value="subjects" className="rounded-lg text-xs font-bold gap-1.5">
              <BookOpen className="size-3.5" />
              <span className="hidden sm:inline">Môn học</span> ({subjects.length})
            </TabsTrigger>
            <TabsTrigger value="frameworks" className="rounded-lg text-xs font-bold gap-1.5">
              <GraduationCap className="size-3.5" />
              <span className="hidden sm:inline">Khung & Cấp</span> ({frameworks.length})
            </TabsTrigger>
            <TabsTrigger value="options" className="rounded-lg text-xs font-bold gap-1.5">
              <Tag className="size-3.5" />
              <span className="hidden sm:inline">Metadata</span> ({options.length})
            </TabsTrigger>
            <TabsTrigger value="mappings" className="rounded-lg text-xs font-bold gap-1.5">
              <Link2 className="size-3.5" />
              <span className="hidden sm:inline">Ánh xạ Môn</span>
            </TabsTrigger>
          </TabsList>

          {/* Quick Search */}
          <div className="relative w-full sm:w-64">
            <Input
              placeholder="Tìm theo tên hoặc ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-9 pl-8 pr-8 text-xs bg-background rounded-lg"
            />
            <Search className="size-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X className="size-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* --- TAB 1: DOMAINS --- */}
        <TabsContent value="domains" className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-foreground">Danh sách Lĩnh vực học tập (Domains)</h3>
            <Button size="sm" onClick={() => openDomainModal()} className="h-8.5 text-xs font-bold rounded-xl gap-1.5">
              <Plus className="size-3.5" /> Thêm Lĩnh vực
            </Button>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {filteredDomains.map((dom) => (
              <Card key={dom.id} className="rounded-xl border border-border/80 shadow-2xs hover:shadow-xs transition-all">
                <CardHeader className="p-4 pb-2">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-sm font-bold">{dom.label}</CardTitle>
                    <Badge variant={dom.is_active ? 'secondary' : 'outline'} className="text-[10px]">
                      {dom.is_active ? 'Hoạt động' : 'Tắt'}
                    </Badge>
                  </div>
                  <CardDescription className="text-xs font-mono">ID: {dom.id}</CardDescription>
                </CardHeader>
                <CardContent className="p-4 pt-1 flex items-center justify-between text-xs text-muted-foreground border-t border-border/40 mt-2">
                  <span>Môn học trực thuộc: <strong className="text-foreground">{subjects.filter((s) => s.domain_id === dom.id).length}</strong></span>
                  <div className="flex items-center gap-1">
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openDomainModal(dom)}>
                      <Edit2 className="size-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive hover:bg-destructive/10"
                      onClick={() => deleteDomainMutation.mutate(dom.id)}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* --- TAB 2: SUBJECTS --- */}
        <TabsContent value="subjects" className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3 sm:items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-muted-foreground">Lọc theo Lĩnh vực:</span>
              <NativeSelect
                value={selectedDomainFilter}
                onChange={(e) => setSelectedDomainFilter(e.target.value)}
                className="h-8.5 text-xs w-48"
              >
                <NativeSelectOption value="all">Tất cả Lĩnh vực ({domains.length})</NativeSelectOption>
                {domains.map((d) => (
                  <NativeSelectOption key={d.id} value={d.id}>
                    {d.label}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>

            <Button size="sm" onClick={() => openSubjectModal()} className="h-8.5 text-xs font-bold rounded-xl gap-1.5">
              <Plus className="size-3.5" /> Thêm Môn học mới
            </Button>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {filteredSubjects.map((sub) => {
              const dom = domains.find((d) => d.id === sub.domain_id)
              const subFws = frameworks.filter((f) => f.subject_id === sub.id)
              return (
                <Card key={sub.id} className="rounded-xl border border-border/80 shadow-2xs">
                  <CardHeader className="p-4 pb-2">
                    <div className="flex items-center justify-between gap-2">
                      <CardTitle className="text-sm font-bold">{sub.label}</CardTitle>
                      <Badge variant="outline" className="text-[10px]">
                        {dom?.label || sub.domain_id}
                      </Badge>
                    </div>
                    <CardDescription className="text-xs font-mono">ID: {sub.id}</CardDescription>
                  </CardHeader>
                  <CardContent className="p-4 pt-1 flex items-center justify-between text-xs text-muted-foreground border-t border-border/40 mt-2">
                    <span>Khung thi: <strong className="text-foreground">{subFws.length}</strong></span>
                    <div className="flex items-center gap-1">
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openSubjectModal(sub)}>
                        <Edit2 className="size-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-destructive hover:bg-destructive/10"
                        onClick={() => deleteSubjectMutation.mutate(sub.id)}
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </TabsContent>

        {/* --- TAB 3: FRAMEWORKS & LEVELS --- */}
        <TabsContent value="frameworks" className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3 sm:items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-muted-foreground">Lọc theo Môn học:</span>
              <NativeSelect
                value={selectedSubjectFilter}
                onChange={(e) => setSelectedSubjectFilter(e.target.value)}
                className="h-8.5 text-xs w-48"
              >
                <NativeSelectOption value="all">Tất cả Môn học ({subjects.length})</NativeSelectOption>
                {subjects.map((s) => (
                  <NativeSelectOption key={s.id} value={s.id}>
                    {s.label}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>

            <div className="flex items-center gap-2">
              <Button size="sm" variant="outline" onClick={() => openFrameworkModal()} className="h-8.5 text-xs font-bold rounded-xl gap-1.5">
                <Plus className="size-3.5" /> Thêm Khung (Framework)
              </Button>
              <Button size="sm" onClick={() => openLevelModal()} className="h-8.5 text-xs font-bold rounded-xl gap-1.5">
                <Plus className="size-3.5" /> Thêm Cấp độ (Level)
              </Button>
            </div>
          </div>

          <div className="space-y-4">
            {filteredFrameworks.map((fw) => {
              const sub = subjects.find((s) => s.id === fw.subject_id)
              const fwLevels = levels.filter((l) => l.framework_id === fw.id)

              return (
                <Card key={fw.id} className="rounded-xl border border-border/80 shadow-2xs overflow-hidden">
                  <div className="bg-muted/40 p-3.5 flex items-center justify-between border-b border-border/60">
                    <div className="flex items-center gap-2.5">
                      <GraduationCap className="size-4 text-muted-foreground shrink-0" />
                      <div>
                        <h4 className="text-sm font-bold text-foreground flex items-center gap-2">
                          {fw.label}
                          <Badge variant="outline" className="text-[10px] font-normal">
                            {sub?.label || fw.subject_id}
                          </Badge>
                        </h4>
                        <span className="text-xs font-mono text-muted-foreground">ID: {fw.id}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <Button variant="ghost" size="sm" onClick={() => openFrameworkModal(fw)} className="h-7 text-xs px-2.5">
                        <Edit2 className="size-3 mr-1" /> Sửa Khung
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-destructive hover:bg-destructive/10"
                        onClick={() => deleteFrameworkMutation.mutate(fw.id)}
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </div>
                  </div>

                  <CardContent className="p-3.5 space-y-2">
                    <span className="text-[11px] font-semibold text-muted-foreground uppercase">
                      Danh sách Cấp độ / Trình độ ({fwLevels.length}):
                    </span>
                    {fwLevels.length === 0 ? (
                      <p className="text-xs text-muted-foreground italic py-1">Chưa có cấp độ nào được gán cho khung này.</p>
                    ) : (
                      <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-3">
                        {fwLevels.map((lvl) => (
                          <div
                            key={lvl.id}
                            className="flex items-center justify-between p-2.5 rounded-lg border border-border/60 bg-background/80 hover:bg-muted/30 transition-colors"
                          >
                            <div className="space-y-0.5">
                              <p className="text-xs font-bold text-foreground">{lvl.label}</p>
                              <div className="flex items-center gap-1.5">
                                <span className="text-[10px] font-mono text-muted-foreground">{lvl.id}</span>
                                <Badge variant="secondary" className="text-[9px] px-1 py-0 capitalize">
                                  {lvl.difficulty_band}
                                </Badge>
                              </div>
                            </div>
                            <div className="flex items-center gap-0.5">
                              <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => openLevelModal(lvl)}>
                                <Edit2 className="size-3" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6 text-destructive hover:bg-destructive/10"
                                onClick={() => deleteLevelMutation.mutate(lvl.id)}
                              >
                                <Trash2 className="size-3" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </TabsContent>

        {/* --- TAB 4: OPTIONS (METADATA) --- */}
        <TabsContent value="options" className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3 sm:items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-muted-foreground">Loại Metadata:</span>
              <NativeSelect
                value={selectedOptionTypeFilter}
                onChange={(e) => setSelectedOptionTypeFilter(e.target.value)}
                className="h-8.5 text-xs w-60"
              >
                <NativeSelectOption value="all">Tất cả Loại ({options.length})</NativeSelectOption>
                {OPTION_TYPES.map((t) => (
                  <NativeSelectOption key={t.id} value={t.id}>
                    {t.label}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>

            <Button size="sm" onClick={() => openOptionModal()} className="h-8.5 text-xs font-bold rounded-xl gap-1.5">
              <Plus className="size-3.5" /> Thêm Option Metadata
            </Button>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {filteredOptions.map((opt) => (
              <Card key={`${opt.id}-${opt.option_type}`} className="rounded-xl border border-border/80 shadow-2xs">
                <CardHeader className="p-4 pb-2">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-sm font-bold">{opt.label}</CardTitle>
                    <Badge variant="secondary" className="text-[10px]">
                      {opt.option_type}
                    </Badge>
                  </div>
                  <CardDescription className="text-xs font-mono">ID: {opt.id}</CardDescription>
                  {opt.sub_label && <p className="text-xs text-muted-foreground italic">{opt.sub_label}</p>}
                </CardHeader>
                <CardContent className="p-4 pt-1 flex items-center justify-between text-xs text-muted-foreground border-t border-border/40 mt-2">
                  <Badge variant={opt.is_active ? 'secondary' : 'outline'} className="text-[10px]">
                    {opt.is_active ? 'Hoạt động' : 'Tắt'}
                  </Badge>
                  <div className="flex items-center gap-1">
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openOptionModal(opt)}>
                      <Edit2 className="size-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive hover:bg-destructive/10"
                      onClick={() => deleteOptionMutation.mutate(opt.id)}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* --- TAB 5: SUBJECT MAPPINGS --- */}
        <TabsContent value="mappings" className="space-y-4">
          <Card className="rounded-xl border border-border/80 p-4 space-y-4">
            <div className="flex flex-col sm:flex-row gap-3 sm:items-center justify-between">
              <div className="flex flex-wrap items-center gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-bold text-foreground">Chọn Môn học (Subject):</label>
                  <NativeSelect
                    value={mappingSubjectId}
                    onChange={(e) => setMappingSubjectId(e.target.value)}
                    className="h-8.5 text-xs w-48"
                  >
                    {subjects.map((s) => (
                      <NativeSelectOption key={s.id} value={s.id}>
                        {s.label} ({s.id})
                      </NativeSelectOption>
                    ))}
                  </NativeSelect>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-bold text-foreground">Loại Metadata muốn gán:</label>
                  <NativeSelect
                    value={mappingOptionType}
                    onChange={(e) => setMappingOptionType(e.target.value)}
                    className="h-8.5 text-xs w-56"
                  >
                    {OPTION_TYPES.map((t) => (
                      <NativeSelectOption key={t.id} value={t.id}>
                        {t.label}
                      </NativeSelectOption>
                    ))}
                  </NativeSelect>
                </div>
              </div>

              <div className="flex items-center gap-2 pt-4 sm:pt-0">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    const availableIds = options
                      .filter((o) => o.option_type === mappingOptionType)
                      .map((o) => o.id)
                    setSelectedOptionIds(availableIds)
                  }}
                  className="h-8 text-xs font-semibold rounded-lg"
                >
                  Chọn tất cả
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setSelectedOptionIds([])}
                  className="h-8 text-xs font-semibold rounded-lg"
                >
                  Bỏ chọn
                </Button>
                <Button
                  size="sm"
                  onClick={() => saveSubjectMappingsMutation.mutate()}
                  disabled={saveSubjectMappingsMutation.isPending || !mappingSubjectId}
                  className="h-8 text-xs font-bold rounded-lg shadow-2xs gap-1.5"
                >
                  <Check className="size-3.5" /> Lưu Ánh Xạ
                </Button>
              </div>
            </div>

            <div className="pt-2 border-t border-border/60">
              <div className="flex items-center gap-2 mb-3">
                <h4 className="text-xs font-bold text-muted-foreground uppercase">
                  Danh sách Option ({mappingOptionType}):
                </h4>
                {mappingsQuery.isFetching && (
                  <Loader2 className="size-3.5 animate-spin text-primary" />
                )}
              </div>
              <div className="grid gap-2.5 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
                {options
                  .filter((o) => o.option_type === mappingOptionType)
                  .map((opt) => {
                    const isChecked = selectedOptionIds.includes(opt.id)
                    return (
                      <label
                        key={opt.id}
                        className={`flex items-center gap-2.5 p-3 rounded-lg border cursor-pointer transition-all ${
                          isChecked
                            ? 'bg-primary/10 border-primary/50 text-foreground font-semibold shadow-2xs'
                            : 'bg-background border-border/60 text-muted-foreground hover:bg-muted/40'
                        }`}
                      >
                        <Checkbox
                          checked={isChecked}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              setSelectedOptionIds((prev) => [...prev, opt.id])
                            } else {
                              setSelectedOptionIds((prev) => prev.filter((id) => id !== opt.id))
                            }
                          }}
                        />
                        <div className="space-y-0.5">
                          <p className="text-xs">{opt.label}</p>
                          <p className="text-[10px] font-mono text-muted-foreground">{opt.id}</p>
                        </div>
                      </label>
                    )
                  })}
              </div>
            </div>
          </Card>
        </TabsContent>
      </Tabs>

      {/* --- DIALOGS --- */}
      {/* 1. Domain Dialog */}
      <Dialog open={isDomainModalOpen} onOpenChange={setIsDomainModalOpen}>
        <DialogContent className="sm:max-w-md rounded-2xl">
          <DialogHeader>
            <DialogTitle>{editingDomain ? 'Chỉnh sửa Lĩnh vực (Domain)' : 'Thêm Lĩnh vực mới'}</DialogTitle>
            <DialogDescription>Quản lý tên hiển thị và thứ tự sắp xếp của Lĩnh vực</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Domain ID (slug)</Label>
              <Input
                placeholder="ví dụ: languages, astronomy..."
                value={domainId}
                disabled={Boolean(editingDomain)}
                onChange={(e) => setDomainId(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Tên hiển thị</Label>
              <Input
                placeholder="ví dụ: Ngôn ngữ & Ngoại ngữ..."
                value={domainLabel}
                onChange={(e) => setDomainLabel(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs font-bold">Thứ tự hiển thị</Label>
                <Input
                  type="number"
                  value={domainSortOrder}
                  onChange={(e) => setDomainSortOrder(e.target.value)}
                />
              </div>
              <div className="flex flex-col justify-end space-y-2">
                <Label className="text-xs font-bold">Trạng thái</Label>
                <div className="flex items-center gap-2">
                  <Switch checked={domainIsActive} onCheckedChange={setDomainIsActive} />
                  <span className="text-xs">{domainIsActive ? 'Hoạt động' : 'Tắt'}</span>
                </div>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDomainModalOpen(false)}>
              Hủy
            </Button>
            <Button
              onClick={() => saveDomainMutation.mutate()}
              disabled={saveDomainMutation.isPending || !domainId || !domainLabel}
            >
              Lưu Lĩnh vực
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 2. Subject Dialog */}
      <Dialog open={isSubjectModalOpen} onOpenChange={setIsSubjectModalOpen}>
        <DialogContent className="sm:max-w-md rounded-2xl">
          <DialogHeader>
            <DialogTitle>{editingSubject ? 'Chỉnh sửa Môn học (Subject)' : 'Thêm Môn học mới'}</DialogTitle>
            <DialogDescription>Gắn Môn học vào Lĩnh vực phù hợp</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Lĩnh vực trực thuộc (Domain)</Label>
              <NativeSelect
                value={subjectDomainId}
                onChange={(e) => setSubjectDomainId(e.target.value)}
              >
                {domains.map((d) => (
                  <NativeSelectOption key={d.id} value={d.id}>
                    {d.label}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Subject ID (slug)</Label>
              <Input
                placeholder="ví dụ: japanese, cloud_computing..."
                value={subjectId}
                disabled={Boolean(editingSubject)}
                onChange={(e) => setSubjectId(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Tên Môn học</Label>
              <Input
                placeholder="ví dụ: Tiếng Nhật, Điện toán đám mây..."
                value={subjectLabel}
                onChange={(e) => setSubjectLabel(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs font-bold">Thứ tự hiển thị</Label>
                <Input
                  type="number"
                  value={subjectSortOrder}
                  onChange={(e) => setSubjectSortOrder(e.target.value)}
                />
              </div>
              <div className="flex flex-col justify-end space-y-2">
                <Label className="text-xs font-bold">Trạng thái</Label>
                <div className="flex items-center gap-2">
                  <Switch checked={subjectIsActive} onCheckedChange={setSubjectIsActive} />
                  <span className="text-xs">{subjectIsActive ? 'Hoạt động' : 'Tắt'}</span>
                </div>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsSubjectModalOpen(false)}>
              Hủy
            </Button>
            <Button
              onClick={() => saveSubjectMutation.mutate()}
              disabled={saveSubjectMutation.isPending || !subjectId || !subjectLabel}
            >
              Lưu Môn học
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 3. Framework Dialog */}
      <Dialog open={isFrameworkModalOpen} onOpenChange={setIsFrameworkModalOpen}>
        <DialogContent className="sm:max-w-md rounded-2xl">
          <DialogHeader>
            <DialogTitle>{editingFramework ? 'Chỉnh sửa Khung chứng chỉ' : 'Thêm Khung chứng chỉ mới'}</DialogTitle>
            <DialogDescription>Gắn Khung chứng chỉ vào Môn học phù hợp</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Môn học (Subject)</Label>
              <NativeSelect
                value={frameworkSubjectId}
                onChange={(e) => setFrameworkSubjectId(e.target.value)}
              >
                {subjects.map((s) => (
                  <NativeSelectOption key={s.id} value={s.id}>
                    {s.label}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Framework ID (slug)</Label>
              <Input
                placeholder="ví dụ: jlpt, ielts, aws_cert..."
                value={frameworkId}
                disabled={Boolean(editingFramework)}
                onChange={(e) => setFrameworkId(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Tên Khung chứng chỉ</Label>
              <Input
                placeholder="ví dụ: JLPT, IELTS Academic, AWS Certified..."
                value={frameworkLabel}
                onChange={(e) => setFrameworkLabel(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs font-bold">Thứ tự hiển thị</Label>
                <Input
                  type="number"
                  value={frameworkSortOrder}
                  onChange={(e) => setFrameworkSortOrder(e.target.value)}
                />
              </div>
              <div className="flex flex-col justify-end space-y-2">
                <Label className="text-xs font-bold">Trạng thái</Label>
                <div className="flex items-center gap-2">
                  <Switch checked={frameworkIsActive} onCheckedChange={setFrameworkIsActive} />
                  <span className="text-xs">{frameworkIsActive ? 'Hoạt động' : 'Tắt'}</span>
                </div>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsFrameworkModalOpen(false)}>
              Hủy
            </Button>
            <Button
              onClick={() => saveFrameworkMutation.mutate()}
              disabled={saveFrameworkMutation.isPending || !frameworkId || !frameworkLabel}
            >
              Lưu Khung
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 4. Level Dialog */}
      <Dialog open={isLevelModalOpen} onOpenChange={setIsLevelModalOpen}>
        <DialogContent className="sm:max-w-md rounded-2xl">
          <DialogHeader>
            <DialogTitle>{editingLevel ? 'Chỉnh sửa Cấp độ (Level)' : 'Thêm Cấp độ mới'}</DialogTitle>
            <DialogDescription>Gắn Cấp độ vào Khung chứng chỉ phù hợp</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Khung chứng chỉ (Framework)</Label>
              <NativeSelect
                value={levelFrameworkId}
                onChange={(e) => {
                  const fwId = e.target.value
                  setLevelFrameworkId(fwId)
                  const fw = frameworks.find((f) => f.id === fwId)
                  if (fw) setLevelSubjectId(fw.subject_id)
                }}
              >
                {frameworks.map((f) => (
                  <NativeSelectOption key={f.id} value={f.id}>
                    {f.label} ({f.subject_id})
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Level ID (slug)</Label>
              <Input
                placeholder="ví dụ: n5, n4, ielts_7_0..."
                value={levelId}
                disabled={Boolean(editingLevel)}
                onChange={(e) => setLevelId(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Tên hiển thị Cấp độ</Label>
              <Input
                placeholder="ví dụ: JLPT N5 (Sơ cấp), IELTS 7.0..."
                value={levelLabel}
                onChange={(e) => setLevelLabel(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Mức độ khó (Difficulty Band)</Label>
              <NativeSelect
                value={levelDifficulty}
                onChange={(e) => setLevelDifficulty(e.target.value)}
              >
                <NativeSelectOption value="beginner">Sơ cấp (Beginner)</NativeSelectOption>
                <NativeSelectOption value="intermediate">Trung cấp (Intermediate)</NativeSelectOption>
                <NativeSelectOption value="advanced">Nâng cao (Advanced)</NativeSelectOption>
              </NativeSelect>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsLevelModalOpen(false)}>
              Hủy
            </Button>
            <Button
              onClick={() => saveLevelMutation.mutate()}
              disabled={saveLevelMutation.isPending || !levelId || !levelLabel}
            >
              Lưu Cấp độ
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 5. Option Dialog */}
      <Dialog open={isOptionModalOpen} onOpenChange={setIsOptionModalOpen}>
        <DialogContent className="sm:max-w-md rounded-2xl">
          <DialogHeader>
            <DialogTitle>{editingOption ? 'Chỉnh sửa Option Metadata' : 'Thêm Option Metadata mới'}</DialogTitle>
            <DialogDescription>Tạo mục tiêu hoặc chủ đề phân loại động</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Loại Option</Label>
              <NativeSelect
                value={optionType}
                disabled={Boolean(editingOption)}
                onChange={(e) => setOptionType(e.target.value)}
              >
                {OPTION_TYPES.map((t) => (
                  <NativeSelectOption key={t.id} value={t.id}>
                    {t.label}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Option ID (slug)</Label>
              <Input
                placeholder="ví dụ: kanji, ai_prompting, cloze..."
                value={optionId}
                disabled={Boolean(editingOption)}
                onChange={(e) => setOptionId(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Tên hiển thị</Label>
              <Input
                placeholder="ví dụ: Hán tự / Kanji, Lập trình AI..."
                value={optionLabel}
                onChange={(e) => setOptionLabel(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Mô tả phụ (tùy chọn)</Label>
              <Input
                placeholder="ví dụ: Dành cho học âm Hán Việt..."
                value={optionSubLabel}
                onChange={(e) => setOptionSubLabel(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsOptionModalOpen(false)}>
              Hủy
            </Button>
            <Button
              onClick={() => saveOptionMutation.mutate()}
              disabled={saveOptionMutation.isPending || !optionId || !optionLabel}
            >
              Lưu Option
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Page>
  )
}
