export type StoryTone = 'dark' | 'dusk' | 'light'

export type StoryChapter = {
  id: string
  number: string
  title: string
  lines: string[]
  /** Background tone of the chapter's text panel. */
  tone: StoryTone
  /** Section height in viewport units for the pinned (desktop) mode. */
  span: number
  /** Ember anchor in the 800 x 600 stage coordinate space while the chapter holds. */
  ember: { x: number; y: number; size: number }
}

// One source of truth for motion mode and static mode.
export const storyChapters: StoryChapter[] = [
  {
    id: 'mot-dom-sang',
    number: '01',
    title: 'Một khám phá có thể bắt đầu từ một người.',
    lines: [
      'Ai đó quan sát, thử, rồi giữ được một đốm lửa nhỏ giữa hai bàn tay.',
    ],
    tone: 'dark',
    span: 110,
    ember: { x: 402, y: 380, size: 1 },
  },
  {
    id: 'trao-lua',
    number: '02',
    title: 'Khi được sẻ chia, nó có thể sưởi ấm cả cộng đồng.',
    lines: ['Người trao vẫn giữ ngọn lửa của mình. Người nhận thắp tiếp cho người bên cạnh.'],
    tone: 'dark',
    span: 130,
    ember: { x: 602, y: 380, size: 0.95 },
  },
  {
    id: 'ke-lai-vun-trong',
    number: '03',
    title: 'Ta kể lại. Ta ghi nhớ.',
    lines: ['Để người đến sau không phải bắt đầu từ đầu.'],
    tone: 'dark',
    span: 120,
    ember: { x: 600, y: 465, size: 0.55 },
  },
  {
    id: 'y-tuong-tiep-noi',
    number: '04',
    title: 'Điều một người tìm ra trở thành điểm bắt đầu của người khác.',
    lines: ['Một bản vẽ được trao đi, thêm chi tiết, thử lại, và cỗ máy chuyển động nhờ nhiều bàn tay.'],
    tone: 'dusk',
    span: 100,
    ember: { x: 500, y: 428, size: 0.7 },
  },
  {
    id: 'thap-sang',
    number: '05',
    title: 'Ý tưởng nối tiếp ý tưởng. Những giới hạn dần được mở ra.',
    lines: ['Một chiếc đèn trở thành nhiều điểm sáng nơi người ta đọc, viết và trao đổi.'],
    tone: 'light',
    span: 100,
    ember: { x: 400, y: 158, size: 0.6 },
  },
  {
    id: 'vuot-khoang-cach',
    number: '06',
    title: 'Điều ta biết có thể đến với người chưa từng gặp.',
    lines: ['Mỗi người nhận một mảnh kiến thức, học thêm, rồi bổ sung một mảnh khác.'],
    tone: 'light',
    span: 110,
    ember: { x: 400, y: 265, size: 0.6 },
  },
  {
    id: 'mo-buoc-tien',
    number: '07',
    title: 'Những điều được sẻ chia mở đường cho những bước tiến mới.',
    lines: [
      'Phía sau mỗi bước tiến là nhiều con người tiếp nối hiểu biết của nhau.',
    ],
    tone: 'light',
    span: 110,
    ember: { x: 400, y: 300, size: 0.85 },
  },
  {
    id: 'flama-community',
    number: '08',
    title: 'Flama — cùng nhau thắp sáng kho tri thức chung.',
    lines: [
      'Mỗi điều bạn học được, mỗi điều bạn chia sẻ, đều có thể trở thành điểm bắt đầu của một người khác.',
    ],
    tone: 'light',
    span: 140,
    ember: { x: 400, y: 148, size: 0.6 },
  },
  {
    id: 'ngon-lua-cua-ban',
    number: '09',
    title: 'Bạn biết một điều có thể giúp ai đó đi xa hơn.',
    lines: ['Học điều bạn cần. Chia sẻ điều bạn biết.'],
    tone: 'light',
    span: 130,
    ember: { x: 400, y: 430, size: 1.15 },
  },
]

export const COMMUNITY_ANCHOR = 'flama-community'

export const communityActions = [
  {
    title: 'Học',
    description: 'Nhận tri thức và biến nó thành điều mình hiểu, theo nhịp ôn tập của riêng bạn.',
  },
  {
    title: 'Chia sẻ',
    description: 'Đưa điều mình biết đến những người khác qua bộ thẻ bạn tạo.',
  },
  {
    title: 'Cùng phát triển',
    description: 'Bổ sung, góp ý và cải thiện học liệu chung để người sau học tốt hơn.',
  },
]

export const storyFaqs = [
  {
    question: 'Flama dành cho ai?',
    answer:
      'Cho bất kỳ ai cần nhớ lâu một điều gì đó: ngoại ngữ, chứng chỉ, thuật ngữ IT, Y khoa, Luật hay kiến thức của riêng bạn. Flama không giới hạn ở một lĩnh vực.',
  },
  {
    question: 'Học và chia sẻ bắt đầu thế nào?',
    answer:
      'Tạo tài khoản, tự tạo bộ thẻ hoặc cài một bộ thẻ cộng đồng rồi học mỗi ngày. Khi sẵn sàng, bạn có thể chia sẻ bộ thẻ của mình qua kho bộ thẻ cộng đồng.',
  },
  {
    question: 'Chia sẻ có tự công khai dữ liệu cá nhân của tôi không?',
    answer:
      'Không. Chỉ những bộ thẻ bạn chủ động đăng mới được chia sẻ. Bộ thẻ cài từ cộng đồng giữ tiến độ học của mỗi người tách biệt với học liệu gốc.',
  },
  {
    question: 'Nội dung cộng đồng có miễn phí không?',
    answer:
      'Bạn có thể đăng ký và dùng luồng học cốt lõi. Kho bộ thẻ cộng đồng có cả nội dung miễn phí và trả phí, tùy người chia sẻ.',
  },
]
