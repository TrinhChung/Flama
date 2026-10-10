import i18n from '@/shared/config/i18n'
import type {
  DailyTargetOption,
  OnboardingPreferences,
  OnboardingSubject,
  RecommendedDeckItem,
  StudyTimeOption,
} from './types'

export const ONBOARDING_STORAGE_KEY = 'flama_user_onboarding_preferences_v1'
export const ONBOARDING_COMPLETED_KEY = 'flama_onboarding_completed_v1'
export const DASHBOARD_TOUR_STORAGE_KEY = 'flama_dashboard_spotlight_tour_v1'

export const DEFAULT_ONBOARDING_PREFERENCES: OnboardingPreferences = {
  targetDomain: 'language_learning',
  targetSubject: 'japanese',
  frameworkLevel: 'n5',
  difficultyBand: 'beginner',
  dailyNewCards: 10,
  preferredStudyTime: 'evening',
  installedDeckIds: [],
  completedAt: null,
  tourSeen: false,
}

export interface SubjectOptionConfig {
  id: OnboardingSubject
  title: string
  subtitle: string
  flag: string
  gradient: string
  borderHover: string
  defaultLevel: string
  levels: Array<{
    id: string
    label: string
    difficulty_band: 'beginner' | 'intermediate' | 'advanced'
    tag: string
  }>
}

const makeLevel = (
  id: string,
  defaultLabel: string,
  difficulty_band: 'beginner' | 'intermediate' | 'advanced',
  tag: string
) => ({
  id,
  get label() {
    return i18n.t(`onboarding:subjects.level_labels.${id}`, { defaultValue: defaultLabel })
  },
  difficulty_band,
  tag,
})

export const SUBJECT_OPTIONS: SubjectOptionConfig[] = [
  {
    id: 'japanese',
    get title() {
      return i18n.t('onboarding:subjects.japanese.title', { defaultValue: 'Tiếng Nhật' })
    },
    get subtitle() {
      return i18n.t('onboarding:subjects.japanese.subtitle', { defaultValue: 'JLPT N5 - N1, Kanji, Giao tiếp Kaiwa, IT Nihongo' })
    },
    flag: '🇯🇵',
    gradient: 'from-red-500/10 via-rose-500/5 to-transparent',
    borderHover: 'hover:border-rose-500/50 hover:bg-rose-500/5',
    defaultLevel: 'n5',
    levels: [
      makeLevel('n5', 'N5 (Nhập môn / Sơ cấp 1)', 'beginner', 'JLPT N5'),
      makeLevel('n4', 'N4 (Sơ cấp 2)', 'beginner', 'JLPT N4'),
      makeLevel('n3', 'N3 (Trung cấp)', 'intermediate', 'JLPT N3'),
      makeLevel('n2', 'N2 (Trung cao cấp)', 'advanced', 'JLPT N2'),
      makeLevel('n1', 'N1 (Cao cấp)', 'advanced', 'JLPT N1'),
      makeLevel('kanji_n5_n4', 'Hán tự Kanji cơ bản', 'beginner', 'Kanji'),
      makeLevel('kaiwa_basic', 'Giao tiếp đời sống Kaiwa', 'beginner', 'Kaiwa'),
    ],
  },
  {
    id: 'english',
    get title() {
      return i18n.t('onboarding:subjects.english.title', { defaultValue: 'Tiếng Anh' })
    },
    get subtitle() {
      return i18n.t('onboarding:subjects.english.subtitle', { defaultValue: 'IELTS, TOEIC, VSTEP, Oxford 3000/5000, Giao tiếp' })
    },
    flag: '🇬🇧',
    gradient: 'from-blue-500/10 via-indigo-500/5 to-transparent',
    borderHover: 'hover:border-blue-500/50 hover:bg-blue-500/5',
    defaultLevel: 'toeic_600',
    levels: [
      makeLevel('toeic_450', 'TOEIC 250 - 450 (Cơ bản)', 'beginner', 'TOEIC 450'),
      makeLevel('toeic_600', 'TOEIC 500 - 650 (Tiêu chuẩn)', 'intermediate', 'TOEIC 650'),
      makeLevel('toeic_750', 'TOEIC 700 - 850 (Nâng cao)', 'intermediate', 'TOEIC 850'),
      makeLevel('ielts_5_5', 'IELTS 5.0 - 6.0', 'intermediate', 'IELTS 5.5'),
      makeLevel('ielts_6_5', 'IELTS 6.5 - 7.5+', 'advanced', 'IELTS 7.0'),
      makeLevel('vstep_b1', 'VSTEP B1 - B2', 'intermediate', 'VSTEP'),
      makeLevel('oxford_3000', 'Từ vựng cốt lõi Oxford', 'beginner', 'Oxford'),
    ],
  },
  {
    id: 'korean',
    get title() {
      return i18n.t('onboarding:subjects.korean.title', { defaultValue: 'Tiếng Hàn' })
    },
    get subtitle() {
      return i18n.t('onboarding:subjects.korean.subtitle', { defaultValue: 'TOPIK I & II, Tiếng Hàn tổng hợp, EPS-TOPIK' })
    },
    flag: '🇰🇷',
    gradient: 'from-purple-500/10 via-fuchsia-500/5 to-transparent',
    borderHover: 'hover:border-purple-500/50 hover:bg-purple-500/5',
    defaultLevel: 'topik_1',
    levels: [
      makeLevel('topik_1', 'TOPIK I (Cấp 1 - Nhập môn)', 'beginner', 'TOPIK 1'),
      makeLevel('topik_2', 'TOPIK I (Cấp 2 - Đời sống)', 'beginner', 'TOPIK 2'),
      makeLevel('topik_3', 'TOPIK II (Cấp 3 - Trung cấp)', 'intermediate', 'TOPIK 3'),
      makeLevel('topik_4', 'TOPIK II (Cấp 4 - Nâng cao)', 'intermediate', 'TOPIK 4'),
      makeLevel('korean_beginner', 'Tiếng Hàn Tổng hợp Sơ cấp', 'beginner', 'Sơ cấp'),
      makeLevel('eps_manufacturing', 'EPS-TOPIK (Xuất khẩu LĐ)', 'beginner', 'EPS'),
    ],
  },
  {
    id: 'chinese',
    get title() {
      return i18n.t('onboarding:subjects.chinese.title', { defaultValue: 'Tiếng Trung' })
    },
    get subtitle() {
      return i18n.t('onboarding:subjects.chinese.subtitle', { defaultValue: 'HSK 1 - 6, HSK 3.0, HSKK Khẩu ngữ, TOCFL' })
    },
    flag: '🇨🇳',
    gradient: 'from-amber-500/10 via-orange-500/5 to-transparent',
    borderHover: 'hover:border-amber-500/50 hover:bg-amber-500/5',
    defaultLevel: 'hsk1',
    levels: [
      makeLevel('hsk1', 'HSK 1 (150 từ cơ bản)', 'beginner', 'HSK 1'),
      makeLevel('hsk2', 'HSK 2 (300 từ)', 'beginner', 'HSK 2'),
      makeLevel('hsk3', 'HSK 3 (600 từ - Giao tiếp)', 'intermediate', 'HSK 3'),
      makeLevel('hsk4', 'HSK 4 (1200 từ)', 'intermediate', 'HSK 4'),
      makeLevel('hsk5', 'HSK 5 (2500 từ cao cấp)', 'advanced', 'HSK 5'),
      makeLevel('tocfl_band_a', 'TOCFL Phồn thể (Band A)', 'beginner', 'TOCFL'),
    ],
  },
  {
    id: 'it_coding',
    get title() {
      return i18n.t('onboarding:subjects.it_tech.title', { defaultValue: 'CNTT & Lập trình' })
    },
    get subtitle() {
      return i18n.t('onboarding:subjects.it_tech.subtitle', { defaultValue: 'Frontend, Backend, DevOps, LeetCode, System Design' })
    },
    flag: '💻',
    gradient: 'from-emerald-500/10 via-teal-500/5 to-transparent',
    borderHover: 'hover:border-emerald-500/50 hover:bg-emerald-500/5',
    defaultLevel: 'frontend',
    levels: [
      makeLevel('frontend', 'Frontend (React, TS, Next.js)', 'intermediate', 'Frontend'),
      makeLevel('backend', 'Backend (Node, Python, Go, SQL)', 'intermediate', 'Backend'),
      makeLevel('dsa_leetcode', 'Cấu trúc dữ liệu & LeetCode', 'advanced', 'LeetCode'),
      makeLevel('devops', 'DevOps & Cloud (Docker, K8s)', 'advanced', 'DevOps'),
      makeLevel('database', 'Database & SQL Queries', 'intermediate', 'SQL'),
    ],
  },
  {
    id: 'aws',
    get title() {
      return i18n.t('onboarding:subjects.aws.title', { defaultValue: 'Cloud & Chứng chỉ' })
    },
    get subtitle() {
      return i18n.t('onboarding:subjects.aws.subtitle', { defaultValue: 'AWS CCP / SAA, Azure AZ-900 / AZ-104, PMP, CFA' })
    },
    flag: '☁️',
    gradient: 'from-cyan-500/10 via-sky-500/5 to-transparent',
    borderHover: 'hover:border-cyan-500/50 hover:bg-cyan-500/5',
    defaultLevel: 'foundational',
    levels: [
      makeLevel('foundational', 'AWS Cloud Practitioner (CCP)', 'beginner', 'AWS CCP'),
      makeLevel('associate', 'AWS Solutions Architect (SAA)', 'intermediate', 'AWS SAA'),
      makeLevel('az_900', 'Azure Fundamentals (AZ-900)', 'beginner', 'AZ-900'),
      makeLevel('az_104', 'Azure Administrator (AZ-104)', 'intermediate', 'AZ-104'),
      makeLevel('pmp_agile', 'PMP & Agile Project Management', 'advanced', 'PMP'),
    ],
  },
  {
    id: 'thpt_qg',
    get title() {
      return i18n.t('onboarding:subjects.thpt_qg.title', { defaultValue: 'Luyện thi THPT QG' })
    },
    get subtitle() {
      return i18n.t('onboarding:subjects.thpt_qg.subtitle', { defaultValue: 'Toán, Vật lý, Hóa học, Sinh học, Lịch sử, Địa lý' })
    },
    flag: '🎓',
    gradient: 'from-amber-500/10 via-yellow-500/5 to-transparent',
    borderHover: 'hover:border-amber-500/50 hover:bg-amber-500/5',
    defaultLevel: 'thpt_math',
    levels: [
      makeLevel('thpt_math', 'Công thức Toán học 12', 'intermediate', 'Toán THPT'),
      makeLevel('thpt_physics', 'Định luật & Công thức Vật lý', 'intermediate', 'Vật lý'),
      makeLevel('thpt_chemistry', 'Phản ứng & Phương trình Hóa học', 'intermediate', 'Hóa học'),
      makeLevel('thpt_biology', 'Quy luật Sinh học & Di truyền', 'intermediate', 'Sinh học'),
      makeLevel('thpt_history_geo', 'Sự kiện Lịch sử & Địa lý', 'intermediate', 'Sử - Địa'),
    ],
  },
  {
    id: 'medical',
    get title() {
      return i18n.t('onboarding:subjects.medicine.title', { defaultValue: 'Y Dược & Chuyên ngành' })
    },
    get subtitle() {
      return i18n.t('onboarding:subjects.medicine.subtitle', { defaultValue: 'Thuật ngữ Y khoa tiếng Anh, Giải phẫu, Dược lý, Luật' })
    },
    flag: '🩺',
    gradient: 'from-teal-500/10 via-emerald-500/5 to-transparent',
    borderHover: 'hover:border-teal-500/50 hover:bg-teal-500/5',
    defaultLevel: 'med_terms',
    levels: [
      makeLevel('med_terms', 'Thuật ngữ Y khoa tiếng Anh', 'intermediate', 'Medical'),
      makeLevel('anatomy', 'Giải phẫu học (Anatomy)', 'intermediate', 'Anatomy'),
      makeLevel('pharmacology', 'Dược lý & Tác dụng thuốc', 'advanced', 'Dược lý'),
      makeLevel('civil_law', 'Luật Dân sự & Doanh nghiệp', 'intermediate', 'Luật học'),
    ],
  },
]

export interface DailyTargetConfig {
  value: DailyTargetOption
  label: string
  timeEstimate: string
  description: string
  badge?: string
  badgeVariant?: 'default' | 'secondary' | 'outline'
  icon: string
  color: string
}

export const DAILY_TARGET_OPTIONS: DailyTargetConfig[] = [
  {
    value: 5,
    get label() {
      return i18n.t('onboarding:daily_targets.5.label', { defaultValue: '5 thẻ / ngày' })
    },
    get timeEstimate() {
      return i18n.t('onboarding:daily_targets.5.time', { defaultValue: '~5 phút mỗi ngày' })
    },
    get description() {
      return i18n.t('onboarding:daily_targets.5.description', { defaultValue: 'Thong thả, dễ dàng duy trì thói quen học tập bền bỉ.' })
    },
    icon: '🌱',
    color: 'border-emerald-500/30 text-emerald-600 dark:text-emerald-400 bg-emerald-500/5',
  },
  {
    value: 10,
    get label() {
      return i18n.t('onboarding:daily_targets.10.label', { defaultValue: '10 thẻ / ngày' })
    },
    get timeEstimate() {
      return i18n.t('onboarding:daily_targets.10.time', { defaultValue: '~10 - 15 phút mỗi ngày' })
    },
    get description() {
      return i18n.t('onboarding:daily_targets.10.description', { defaultValue: 'Mức học tiêu chuẩn cân bằng, tiến bộ rõ rệt mà không áp lực.' })
    },
    badge: 'Khuyên Dùng ⭐',
    badgeVariant: 'default',
    icon: '⚡',
    color: 'border-primary text-primary bg-primary/10 ring-2 ring-primary/20',
  },
  {
    value: 20,
    get label() {
      return i18n.t('onboarding:daily_targets.20.label', { defaultValue: '20 thẻ / ngày' })
    },
    get timeEstimate() {
      return i18n.t('onboarding:daily_targets.20.time', { defaultValue: '~25 - 30 phút mỗi ngày' })
    },
    get description() {
      return i18n.t('onboarding:daily_targets.20.description', { defaultValue: 'Chăm chỉ, tăng tốc chuẩn bị cho các kỳ thi sắp tới.' })
    },
    icon: '🔥',
    color: 'border-orange-500/30 text-orange-600 dark:text-orange-400 bg-orange-500/5',
  },
  {
    value: 30,
    get label() {
      return i18n.t('onboarding:daily_targets.30.label', { defaultValue: '30+ thẻ / ngày' })
    },
    get timeEstimate() {
      return i18n.t('onboarding:daily_targets.30.time', { defaultValue: '~45+ phút mỗi ngày' })
    },
    get description() {
      return i18n.t('onboarding:daily_targets.30.description', { defaultValue: 'Cấp tốc, đạt mục tiêu từ vựng lớn trong thời gian ngắn.' })
    },
    icon: '🚀',
    color: 'border-rose-500/30 text-rose-600 dark:text-rose-400 bg-rose-500/5',
  },
]

export interface StudyTimeConfig {
  value: StudyTimeOption
  label: string
  sub: string
  icon: string
}

export const STUDY_TIME_OPTIONS: StudyTimeConfig[] = [
  {
    value: 'morning',
    get label() {
      return i18n.t('onboarding:study_times.morning.label', { defaultValue: 'Buổi sáng' })
    },
    get sub() {
      return i18n.t('onboarding:study_times.morning.schedule', { defaultValue: '06:00 - 08:00 (Tỉnh táo)' })
    },
    icon: '🌅',
  },
  {
    value: 'afternoon',
    get label() {
      return i18n.t('onboarding:study_times.afternoon.label', { defaultValue: 'Buổi trưa / Chiều' })
    },
    get sub() {
      return i18n.t('onboarding:study_times.afternoon.schedule', { defaultValue: '12:00 - 14:00 (Nghỉ ngơi)' })
    },
    icon: '☀️',
  },
  {
    value: 'evening',
    get label() {
      return i18n.t('onboarding:study_times.evening.label', { defaultValue: 'Buổi tối' })
    },
    get sub() {
      return i18n.t('onboarding:study_times.evening.schedule', { defaultValue: '19:00 - 22:00 (Tập trung)' })
    },
    icon: '🌙',
  },
]

export const STUDY_SUBJECTS = SUBJECT_OPTIONS
export const DAILY_TARGETS = DAILY_TARGET_OPTIONS
export const STUDY_TIMES = STUDY_TIME_OPTIONS

export const CURATED_STARTER_DECKS: Record<string, RecommendedDeckItem[]> = {
  japanese: [
    {
      id: 'curated-jp-minna-n5',
      title: 'Minna no Nihongo N5 - 25 Bài Từ Vựng Chuẩn',
      description: 'Tổng hợp trọn bộ từ vựng 25 bài Minna no Nihongo sơ cấp với phát âm, Furigana và ví dụ thực tế.',
      primary_category: 'Tiếng Nhật',
      card_count: 750,
      note_count: 750,
      lesson_count: 25,
      rating_avg: 4.9,
      rating_count: 128,
      install_count: 2450,
      price_display: 'Miễn phí',
      pricing_mode: 'free',
      tags: ['jlpt', 'n5', 'minna', 'từ vựng'],
      author: { username: 'Flama Official' },
    },
    {
      id: 'curated-jp-kanji-look-learn',
      title: 'Kanji Look and Learn N5 - N4 (512 Chữ Hán)',
      description: 'Ghi nhớ chữ Hán qua hình ảnh minh họa sinh động, mẹo nhớ âm On/Kun và các từ ghép phổ biến.',
      primary_category: 'Tiếng Nhật',
      card_count: 512,
      note_count: 512,
      lesson_count: 32,
      rating_avg: 4.9,
      rating_count: 94,
      install_count: 1820,
      price_display: 'Miễn phí',
      pricing_mode: 'free',
      tags: ['kanji', 'n5', 'n4', 'look_learn'],
      author: { username: 'Sensei Flama' },
    },
    {
      id: 'curated-jp-tango-n5-n4',
      title: 'Tango 1500 Từ Vựng Trọng Tâm N5 - N4',
      description: 'Bộ từ vựng bám sát cấu trúc đề thi JLPT N5 và N4 với câu ví dụ song ngữ Nhật - Việt.',
      primary_category: 'Tiếng Nhật',
      card_count: 1500,
      note_count: 1500,
      lesson_count: 50,
      rating_avg: 4.8,
      rating_count: 67,
      install_count: 1210,
      price_display: 'Miễn phí',
      pricing_mode: 'free',
      tags: ['jlpt', 'tango', 'n5', 'n4'],
      author: { username: 'NihongoMaster' },
    },
  ],
  english: [
    {
      id: 'curated-en-toeic-600',
      title: '600 Từ Vựng TOEIC Căn Bản (ETS Core)',
      description: '50 chủ đề từ vựng thiết yếu nhất trong bài thi TOEIC Listening & Reading.',
      primary_category: 'Tiếng Anh',
      card_count: 600,
      note_count: 600,
      lesson_count: 50,
      rating_avg: 4.9,
      rating_count: 115,
      install_count: 1980,
      price_display: 'Miễn phí',
      pricing_mode: 'free',
      tags: ['toeic', 'ets', 'tiếng anh'],
      author: { username: 'English Pro' },
    },
    {
      id: 'curated-en-oxford-3000',
      title: 'Oxford 3000 Core Words (A1 - B2)',
      description: '3000 từ vựng tiếng Anh quan trọng nhất giúp hiểu 85% các đoạn hội thoại và văn bản đời sống.',
      primary_category: 'Tiếng Anh',
      card_count: 3000,
      note_count: 3000,
      lesson_count: 60,
      rating_avg: 4.8,
      rating_count: 82,
      install_count: 1540,
      price_display: 'Miễn phí',
      pricing_mode: 'free',
      tags: ['oxford', 'vocabulary', 'giao tiếp'],
      author: { username: 'Flama Official' },
    },
  ],
  korean: [
    {
      id: 'curated-kr-topik-1',
      title: 'TOPIK I (Cấp 1 & 2) - 800 Từ Vựng Đời Sống',
      description: 'Trọn bộ từ vựng và ngữ pháp trọng tâm đề thi TOPIK I kèm âm đọc Hangul chuẩn.',
      primary_category: 'Tiếng Hàn',
      card_count: 800,
      note_count: 800,
      lesson_count: 30,
      rating_avg: 4.8,
      rating_count: 45,
      install_count: 920,
      price_display: 'Miễn phí',
      pricing_mode: 'free',
      tags: ['topik', 'tiếng hàn', 'hangul'],
      author: { username: 'K-Learning' },
    },
  ],
  chinese: [
    {
      id: 'curated-cn-hsk1-2',
      title: 'Trọn Bộ Từ Vựng HSK 1 & HSK 2 (500 Từ)',
      description: 'Kèm Pinyin chuẩn, âm Hán Việt và thứ tự nét viết chữ Hán cơ bản.',
      primary_category: 'Tiếng Trung',
      card_count: 500,
      note_count: 500,
      lesson_count: 20,
      rating_avg: 4.9,
      rating_count: 58,
      install_count: 1100,
      price_display: 'Miễn phí',
      pricing_mode: 'free',
      tags: ['hsk', 'pinyin', 'tiếng trung'],
      author: { username: 'HanziMaster' },
    },
  ],
  it_coding: [
    {
      id: 'curated-it-frontend-interview',
      title: 'Frontend Developer Interview Flashcards (React, JS, TS)',
      description: 'Hơn 200 câu hỏi phỏng vấn và khái niệm cốt lõi: Virtual DOM, Closure, Event Loop, Hooks.',
      primary_category: 'Công nghệ & IT',
      card_count: 220,
      note_count: 220,
      lesson_count: 15,
      rating_avg: 4.9,
      rating_count: 76,
      install_count: 1450,
      price_display: 'Miễn phí',
      pricing_mode: 'free',
      tags: ['frontend', 'react', 'typescript', 'interview'],
      author: { username: 'DevCraft' },
    },
  ],
  aws: [
    {
      id: 'curated-aws-ccp',
      title: 'AWS Certified Cloud Practitioner (CLF-C02) Flashcards',
      description: 'Tổng hợp toàn bộ các dịch vụ AWS cốt lõi, mô hình bảo mật chia sẻ và khái niệm Cloud.',
      primary_category: 'Chứng chỉ',
      card_count: 350,
      note_count: 350,
      lesson_count: 20,
      rating_avg: 4.9,
      rating_count: 88,
      install_count: 1620,
      price_display: 'Miễn phí',
      pricing_mode: 'free',
      tags: ['aws', 'ccp', 'cloud'],
      author: { username: 'CloudArchitect' },
    },
  ],
}
