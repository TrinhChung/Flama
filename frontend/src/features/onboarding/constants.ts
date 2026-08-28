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

export const SUBJECT_OPTIONS: SubjectOptionConfig[] = [
  {
    id: 'japanese',
    title: 'Tiếng Nhật',
    subtitle: 'JLPT N5 - N1, Kanji, Giao tiếp Kaiwa, IT Nihongo',
    flag: '🇯🇵',
    gradient: 'from-red-500/10 via-rose-500/5 to-transparent',
    borderHover: 'hover:border-rose-500/50 hover:bg-rose-500/5',
    defaultLevel: 'n5',
    levels: [
      { id: 'n5', label: 'N5 (Nhập môn / Sơ cấp 1)', difficulty_band: 'beginner', tag: 'JLPT N5' },
      { id: 'n4', label: 'N4 (Sơ cấp 2)', difficulty_band: 'beginner', tag: 'JLPT N4' },
      { id: 'n3', label: 'N3 (Trung cấp)', difficulty_band: 'intermediate', tag: 'JLPT N3' },
      { id: 'n2', label: 'N2 (Trung cao cấp)', difficulty_band: 'advanced', tag: 'JLPT N2' },
      { id: 'n1', label: 'N1 (Cao cấp)', difficulty_band: 'advanced', tag: 'JLPT N1' },
      { id: 'kanji_n5_n4', label: 'Hán tự Kanji cơ bản', difficulty_band: 'beginner', tag: 'Kanji' },
      { id: 'kaiwa_basic', label: 'Giao tiếp đời sống Kaiwa', difficulty_band: 'beginner', tag: 'Kaiwa' },
    ],
  },
  {
    id: 'english',
    title: 'Tiếng Anh',
    subtitle: 'IELTS, TOEIC, VSTEP, Oxford 3000/5000, Giao tiếp',
    flag: '🇬🇧',
    gradient: 'from-blue-500/10 via-indigo-500/5 to-transparent',
    borderHover: 'hover:border-blue-500/50 hover:bg-blue-500/5',
    defaultLevel: 'toeic_600',
    levels: [
      { id: 'toeic_450', label: 'TOEIC 250 - 450 (Cơ bản)', difficulty_band: 'beginner', tag: 'TOEIC 450' },
      { id: 'toeic_600', label: 'TOEIC 500 - 650 (Tiêu chuẩn)', difficulty_band: 'intermediate', tag: 'TOEIC 650' },
      { id: 'toeic_750', label: 'TOEIC 700 - 850 (Nâng cao)', difficulty_band: 'intermediate', tag: 'TOEIC 850' },
      { id: 'ielts_5_5', label: 'IELTS 5.0 - 6.0', difficulty_band: 'intermediate', tag: 'IELTS 5.5' },
      { id: 'ielts_6_5', label: 'IELTS 6.5 - 7.5+', difficulty_band: 'advanced', tag: 'IELTS 7.0' },
      { id: 'vstep_b1', label: 'VSTEP B1 - B2', difficulty_band: 'intermediate', tag: 'VSTEP' },
      { id: 'oxford_3000', label: 'Từ vựng cốt lõi Oxford', difficulty_band: 'beginner', tag: 'Oxford' },
    ],
  },
  {
    id: 'korean',
    title: 'Tiếng Hàn',
    subtitle: 'TOPIK I & II, Tiếng Hàn tổng hợp, EPS-TOPIK',
    flag: '🇰🇷',
    gradient: 'from-purple-500/10 via-fuchsia-500/5 to-transparent',
    borderHover: 'hover:border-purple-500/50 hover:bg-purple-500/5',
    defaultLevel: 'topik_1',
    levels: [
      { id: 'topik_1', label: 'TOPIK I (Cấp 1 - Nhập môn)', difficulty_band: 'beginner', tag: 'TOPIK 1' },
      { id: 'topik_2', label: 'TOPIK I (Cấp 2 - Đời sống)', difficulty_band: 'beginner', tag: 'TOPIK 2' },
      { id: 'topik_3', label: 'TOPIK II (Cấp 3 - Trung cấp)', difficulty_band: 'intermediate', tag: 'TOPIK 3' },
      { id: 'topik_4', label: 'TOPIK II (Cấp 4 - Nâng cao)', difficulty_band: 'intermediate', tag: 'TOPIK 4' },
      { id: 'korean_beginner', label: 'Tiếng Hàn Tổng hợp Sơ cấp', difficulty_band: 'beginner', tag: 'Sơ cấp' },
      { id: 'eps_manufacturing', label: 'EPS-TOPIK (Xuất khẩu LĐ)', difficulty_band: 'beginner', tag: 'EPS' },
    ],
  },
  {
    id: 'chinese',
    title: 'Tiếng Trung',
    subtitle: 'HSK 1 - 6, HSK 3.0, HSKK Khẩu ngữ, TOCFL',
    flag: '🇨🇳',
    gradient: 'from-amber-500/10 via-orange-500/5 to-transparent',
    borderHover: 'hover:border-amber-500/50 hover:bg-amber-500/5',
    defaultLevel: 'hsk1',
    levels: [
      { id: 'hsk1', label: 'HSK 1 (150 từ cơ bản)', difficulty_band: 'beginner', tag: 'HSK 1' },
      { id: 'hsk2', label: 'HSK 2 (300 từ)', difficulty_band: 'beginner', tag: 'HSK 2' },
      { id: 'hsk3', label: 'HSK 3 (600 từ - Giao tiếp)', difficulty_band: 'intermediate', tag: 'HSK 3' },
      { id: 'hsk4', label: 'HSK 4 (1200 từ)', difficulty_band: 'intermediate', tag: 'HSK 4' },
      { id: 'hsk5', label: 'HSK 5 (2500 từ cao cấp)', difficulty_band: 'advanced', tag: 'HSK 5' },
      { id: 'tocfl_band_a', label: 'TOCFL Phồn thể (Band A)', difficulty_band: 'beginner', tag: 'TOCFL' },
    ],
  },
  {
    id: 'it_coding',
    title: 'CNTT & Lập trình',
    subtitle: 'Frontend, Backend, DevOps, LeetCode, System Design',
    flag: '💻',
    gradient: 'from-emerald-500/10 via-teal-500/5 to-transparent',
    borderHover: 'hover:border-emerald-500/50 hover:bg-emerald-500/5',
    defaultLevel: 'frontend',
    levels: [
      { id: 'frontend', label: 'Frontend (React, TS, Next.js)', difficulty_band: 'intermediate', tag: 'Frontend' },
      { id: 'backend', label: 'Backend (Node, Python, Go, SQL)', difficulty_band: 'intermediate', tag: 'Backend' },
      { id: 'dsa_leetcode', label: 'Cấu trúc dữ liệu & LeetCode', difficulty_band: 'advanced', tag: 'LeetCode' },
      { id: 'devops', label: 'DevOps & Cloud (Docker, K8s)', difficulty_band: 'advanced', tag: 'DevOps' },
      { id: 'database', label: 'Database & SQL Queries', difficulty_band: 'intermediate', tag: 'SQL' },
    ],
  },
  {
    id: 'aws',
    title: 'Cloud & Chứng chỉ',
    subtitle: 'AWS CCP / SAA, Azure AZ-900 / AZ-104, PMP, CFA',
    flag: '☁️',
    gradient: 'from-cyan-500/10 via-sky-500/5 to-transparent',
    borderHover: 'hover:border-cyan-500/50 hover:bg-cyan-500/5',
    defaultLevel: 'foundational',
    levels: [
      { id: 'foundational', label: 'AWS Cloud Practitioner (CCP)', difficulty_band: 'beginner', tag: 'AWS CCP' },
      { id: 'associate', label: 'AWS Solutions Architect (SAA)', difficulty_band: 'intermediate', tag: 'AWS SAA' },
      { id: 'az_900', label: 'Azure Fundamentals (AZ-900)', difficulty_band: 'beginner', tag: 'AZ-900' },
      { id: 'az_104', label: 'Azure Administrator (AZ-104)', difficulty_band: 'intermediate', tag: 'AZ-104' },
      { id: 'pmp_agile', label: 'PMP & Agile Project Management', difficulty_band: 'advanced', tag: 'PMP' },
    ],
  },
  {
    id: 'thpt_qg',
    title: 'Luyện thi THPT QG',
    subtitle: 'Toán, Vật lý, Hóa học, Sinh học, Lịch sử, Địa lý',
    flag: '🎓',
    gradient: 'from-amber-500/10 via-yellow-500/5 to-transparent',
    borderHover: 'hover:border-amber-500/50 hover:bg-amber-500/5',
    defaultLevel: 'thpt_math',
    levels: [
      { id: 'thpt_math', label: 'Công thức Toán học 12', difficulty_band: 'intermediate', tag: 'Toán THPT' },
      { id: 'thpt_physics', label: 'Định luật & Công thức Vật lý', difficulty_band: 'intermediate', tag: 'Vật lý' },
      { id: 'thpt_chemistry', label: 'Phản ứng & Phương trình Hóa học', difficulty_band: 'intermediate', tag: 'Hóa học' },
      { id: 'thpt_biology', label: 'Quy luật Sinh học & Di truyền', difficulty_band: 'intermediate', tag: 'Sinh học' },
      { id: 'thpt_history_geo', label: 'Sự kiện Lịch sử & Địa lý', difficulty_band: 'intermediate', tag: 'Sử - Địa' },
    ],
  },
  {
    id: 'medical',
    title: 'Y Dược & Chuyên ngành',
    subtitle: 'Thuật ngữ Y khoa tiếng Anh, Giải phẫu, Dược lý, Luật',
    flag: '🩺',
    gradient: 'from-teal-500/10 via-emerald-500/5 to-transparent',
    borderHover: 'hover:border-teal-500/50 hover:bg-teal-500/5',
    defaultLevel: 'med_terms',
    levels: [
      { id: 'med_terms', label: 'Thuật ngữ Y khoa tiếng Anh', difficulty_band: 'intermediate', tag: 'Medical' },
      { id: 'anatomy', label: 'Giải phẫu học (Anatomy)', difficulty_band: 'intermediate', tag: 'Anatomy' },
      { id: 'pharmacology', label: 'Dược lý & Tác dụng thuốc', difficulty_band: 'advanced', tag: 'Dược lý' },
      { id: 'civil_law', label: 'Luật Dân sự & Doanh nghiệp', difficulty_band: 'intermediate', tag: 'Luật học' },
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
    label: '5 thẻ / ngày',
    timeEstimate: '~5 phút mỗi ngày',
    description: 'Thong thả, dễ dàng duy trì thói quen học tập bền bỉ.',
    icon: '🌱',
    color: 'border-emerald-500/30 text-emerald-600 dark:text-emerald-400 bg-emerald-500/5',
  },
  {
    value: 10,
    label: '10 thẻ / ngày',
    timeEstimate: '~10 - 15 phút mỗi ngày',
    description: 'Mức học tiêu chuẩn cân bằng, tiến bộ rõ rệt mà không áp lực.',
    badge: 'Khuyên Dùng ⭐',
    badgeVariant: 'default',
    icon: '⚡',
    color: 'border-primary text-primary bg-primary/10 ring-2 ring-primary/20',
  },
  {
    value: 20,
    label: '20 thẻ / ngày',
    timeEstimate: '~25 - 30 phút mỗi ngày',
    description: 'Chăm chỉ, tăng tốc chuẩn bị cho các kỳ thi sắp tới.',
    icon: '🔥',
    color: 'border-orange-500/30 text-orange-600 dark:text-orange-400 bg-orange-500/5',
  },
  {
    value: 30,
    label: '30+ thẻ / ngày',
    timeEstimate: '~45+ phút mỗi ngày',
    description: 'Cấp tốc, đạt mục tiêu từ vựng lớn trong thời gian ngắn.',
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
  { value: 'morning', label: 'Buổi sáng', sub: '06:00 - 08:00 (Tỉnh táo)', icon: '🌅' },
  { value: 'afternoon', label: 'Buổi trưa / Chiều', sub: '12:00 - 14:00 (Nghỉ ngơi)', icon: '☀️' },
  { value: 'evening', label: 'Buổi tối', sub: '19:00 - 22:00 (Tập trung)', icon: '🌙' },
]

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
