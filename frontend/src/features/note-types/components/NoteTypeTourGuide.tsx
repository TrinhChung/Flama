import { useState, useEffect } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ExternalLink,
  X,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

const STORAGE_KEY = 'flama_notetype_tour_completed_v1'

interface NoteTypeTourGuideProps {
  forceOpen?: boolean
  onClose?: () => void
  hasNoteTypes?: boolean
}

export function NoteTypeTourGuide({ forceOpen, onClose, hasNoteTypes }: NoteTypeTourGuideProps) {
  const [currentStep, setCurrentStep] = useState(1)
  const [isOpen, setIsOpen] = useState(false)

  const totalSteps = 4

  useEffect(() => {
    if (forceOpen) {
      setCurrentStep(1)
      setIsOpen(true)
      return
    }

    const completed = localStorage.getItem(STORAGE_KEY)
    if (!completed && !hasNoteTypes) {
      // First-time user with no note types
      setIsOpen(true)
    }
  }, [forceOpen, hasNoteTypes])

  const handleDismiss = () => {
    localStorage.setItem(STORAGE_KEY, 'true')
    setIsOpen(false)
    if (onClose) onClose()
  }

  const handleNext = () => {
    if (currentStep < totalSteps) {
      setCurrentStep((prev) => prev + 1)
    } else {
      handleDismiss()
    }
  }

  const handlePrev = () => {
    if (currentStep > 1) {
      setCurrentStep((prev) => prev - 1)
    }
  }

  if (!isOpen) return null

  return (
    <div className="relative overflow-hidden rounded-2xl border border-primary/30 bg-gradient-to-br from-primary/10 via-background to-primary/5 p-4 sm:p-6 shadow-md animate-in fade-in slide-in-from-top-2 duration-300">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <Badge variant="default" className="px-2.5 py-0.5 text-xs font-bold bg-primary text-primary-foreground">
            Tour Hướng Dẫn: Bước {currentStep}/{totalSteps}
          </Badge>
          <span className="text-xs text-muted-foreground font-medium">Dành cho người mới bắt đầu</span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={handleDismiss}
          className="size-7 rounded-lg text-muted-foreground hover:text-foreground"
          title="Bỏ qua hướng dẫn"
        >
          <X className="size-4" />
        </Button>
      </div>

      {/* Step Contents */}
      <div className="space-y-3 min-h-[110px]">
        {currentStep === 1 && (
          <div className="space-y-1.5 animate-in fade-in duration-200">
            <h4 className="text-sm sm:text-base font-bold text-foreground flex items-center gap-2">
              🎉 1. Chào mừng bạn đến với Quản lý Note Type!
            </h4>
            <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
              <strong>Note Type (Loại thẻ)</strong> là khung xương định nghĩa cấu trúc dữ liệu (như từ vựng, âm Hán Việt, file audio, ảnh...) và quyết định giao diện hiển thị của các thẻ Flashcard.
            </p>
          </div>
        )}

        {currentStep === 2 && (
          <div className="space-y-1.5 animate-in fade-in duration-200">
            <h4 className="text-sm sm:text-base font-bold text-foreground flex items-center gap-2">
              ✨ 2. Không cần biết lập trình? Dùng Prompt AI!
            </h4>
            <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
              Flama cung cấp sẵn <strong>Master Prompt</strong> chuẩn hóa. Bạn chỉ cần sao chép prompt, điền mong muốn và gửi cho ChatGPT / Claude để AI tự sinh mã thẻ HTML/CSS hoàn hảo.
            </p>
            <div className="pt-1">
              <Button
                variant="outline"
                size="sm"
                asChild
                className="h-7 px-2.5 text-xs font-semibold text-primary border-primary/30 hover:bg-primary/10 rounded-lg"
              >
                <Link to="/flashcards/note-types/guide" target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="size-3 mr-1" /> Mở trang Prompt AI trong tab mới
                </Link>
              </Button>
            </div>
          </div>
        )}

        {currentStep === 3 && (
          <div className="space-y-1.5 animate-in fade-in duration-200">
            <h4 className="text-sm sm:text-base font-bold text-foreground flex items-center gap-2">
              📝 3. Tạo Loại Thẻ Mới
            </h4>
            <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
              Hãy nhập tên loại thẻ bạn muốn tạo (Ví dụ: <em>Từ vựng JLPT N3</em>, <em>Ngữ pháp N2</em>) vào ô <strong>"Tạo Loại Thẻ Mới"</strong> ngay bên dưới rồi bấm <strong>Tạo NoteType</strong>.
            </p>
          </div>
        )}

        {currentStep === 4 && (
          <div className="space-y-1.5 animate-in fade-in duration-200">
            <h4 className="text-sm sm:text-base font-bold text-foreground flex items-center gap-2">
              🚀 4. Quản lý Trường & Soạn Thảo Template
            </h4>
            <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
              Sau khi tạo xong, hệ thống sẽ đưa bạn đến trang <strong>Quản lý Trường</strong> để thêm các cột dữ liệu. Tiếp theo, bạn vào trang <strong>Chi tiết Template</strong> để dán mã Front/Back/CSS và kiểm tra Live Preview.
            </p>
          </div>
        )}
      </div>

      {/* Progress Dots & Navigation Footer */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-4 border-t border-border/60">
        <div className="flex items-center gap-1.5">
          {Array.from({ length: totalSteps }).map((_, index) => (
            <button
              key={index}
              type="button"
              onClick={() => setCurrentStep(index + 1)}
              className={`size-2 rounded-full transition-all ${
                currentStep === index + 1
                  ? 'w-6 bg-primary'
                  : 'bg-muted-foreground/30 hover:bg-muted-foreground/50'
              }`}
              aria-label={`Chuyển đến bước ${index + 1}`}
            />
          ))}
        </div>

        <div className="flex items-center gap-2">
          {currentStep > 1 && (
            <Button
              variant="outline"
              size="sm"
              onClick={handlePrev}
              className="h-8 px-3 text-xs font-semibold rounded-xl"
            >
              <ArrowLeft className="size-3.5 mr-1" /> Quay lại
            </Button>
          )}

          <Button
            variant="ghost"
            size="sm"
            onClick={handleDismiss}
            className="h-8 px-3 text-xs text-muted-foreground hover:text-foreground rounded-xl"
          >
            Bỏ qua
          </Button>

          <Button
            size="sm"
            onClick={handleNext}
            className="h-8 px-3.5 text-xs font-bold rounded-xl shadow-xs bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {currentStep === totalSteps ? (
              <>
                <Check className="size-3.5 mr-1" /> Hoàn tất & Bắt đầu
              </>
            ) : (
              <>
                Tiếp tục <ArrowRight className="size-3.5 ml-1" />
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
