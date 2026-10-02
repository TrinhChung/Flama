import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Upload, ImageIcon, X, Loader2 } from "lucide-react"

import { cn } from "@/lib/utils"
import { compressImage } from "@/lib/imageCompression"
import { Progress } from "@/components/ui/progress"

export const dropzoneVariants = cva(
  "relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed transition-all cursor-pointer select-none text-center outline-none focus-visible:ring-2 focus-visible:ring-ring",
  {
    variants: {
      variant: {
        default: "p-6 min-h-36 bg-card hover:bg-muted/30",
        compact: "p-3 size-20 min-h-20 bg-card hover:bg-muted/40",
        avatar: "size-32 rounded-full overflow-hidden border-solid border-4 border-muted/80 bg-muted",
      },
      isDragging: {
        true: "border-primary bg-primary/10 scale-102 shadow-md",
        false: "border-border/80 hover:border-primary/50",
      },
      hasError: {
        true: "border-destructive/80 bg-destructive/5 text-destructive",
        false: "",
      },
      disabled: {
        true: "pointer-events-none opacity-50 cursor-not-allowed",
        false: "",
      },
    },
    defaultVariants: {
      variant: "default",
      isDragging: false,
      hasError: false,
      disabled: false,
    },
  }
)

export interface ImageUploadDropzoneProps
  extends Omit<React.ComponentProps<"div">, "onDrop" | "onError">,
    VariantProps<typeof dropzoneVariants> {
  /** Callback fired when valid file(s) are selected, dropped, or pasted */
  onFilesSelected: (files: File[]) => void
  /** Allowed MIME types (e.g. ['image/png', 'image/jpeg', 'image/webp'] or 'image/*') */
  accept?: string[] | string
  /** Maximum file size in bytes (default: 2 * 1024 * 1024 = 2MB) */
  maxSizeBytes?: number
  /** Whether multiple files can be selected/dropped (default: false) */
  multiple?: boolean
  /** Whether an upload or compression operation is in progress */
  isUploading?: boolean
  /** Upload or compression progress percentage (0 - 100) */
  uploadProgress?: number
  /** Existing or preview image URL */
  previewUrl?: string | null
  /** Callback fired when user removes the current preview */
  onRemovePreview?: () => void
  /** Enables listening for Ctrl+V / Cmd+V image paste events (default: true) */
  enablePaste?: boolean
  /** Whether client-side canvas compression is enabled (default: true) */
  compress?: boolean
  /** Maximum pixel dimension for image compression (default: 1600) */
  maxDimension?: number
  /** Compression quality between 0.1 and 1.0 (default: 0.85) */
  compressionQuality?: number
  /** Title text displayed inside the dropzone */
  titleText?: React.ReactNode
  /** Subtitle / hint text displayed below title */
  hintText?: React.ReactNode
  /** Callback fired on validation or compression error */
  onError?: (errorMessage: string) => void
  /** Additional container styling */
  className?: string
  /** Whether the dropzone is disabled */
  disabled?: boolean
}

function matchesAccept(file: File, acceptList: string[]): boolean {
  if (acceptList.length === 0) return true
  const fileType = file.type.toLowerCase()
  const fileName = file.name.toLowerCase()

  return acceptList.some((pattern) => {
    const p = pattern.trim().toLowerCase()
    if (!p) return false
    if (p === "*/*" || p === "image/*") {
      return fileType.startsWith("image/")
    }
    if (p.startsWith(".")) {
      return fileName.endsWith(p)
    }
    if (p.endsWith("/*")) {
      const prefix = p.slice(0, -1)
      return fileType.startsWith(prefix)
    }
    return fileType === p
  })
}

export function ImageUploadDropzone({
  onFilesSelected,
  accept = ["image/*"],
  maxSizeBytes = 2 * 1024 * 1024,
  multiple = false,
  isUploading = false,
  uploadProgress,
  previewUrl,
  onRemovePreview,
  enablePaste = true,
  compress = true,
  maxDimension = 1600,
  compressionQuality = 0.85,
  titleText = "Kéo thả ảnh vào đây hoặc nhấp để chọn tệp",
  hintText = "Hỗ trợ PNG, JPG, WebP (Tối đa 2MB)",
  onError,
  className,
  variant = "default",
  disabled = false,
  ...restProps
}: ImageUploadDropzoneProps) {
  const [isDragging, setIsDragging] = React.useState(false)
  const [hasError, setHasError] = React.useState(false)
  const inputRef = React.useRef<HTMLInputElement | null>(null)
  const dragCounterRef = React.useRef(0)

  const normalizedAccept = React.useMemo(() => {
    if (!accept) return ["image/*"]
    if (Array.isArray(accept)) return accept
    return accept.split(",").map((s) => s.trim())
  }, [accept])

  const acceptString = React.useMemo(() => {
    return normalizedAccept.join(",")
  }, [normalizedAccept])

  const processAndEmitFiles = React.useCallback(
    async (files: File[]) => {
      if (disabled || files.length === 0) return
      setHasError(false)

      const validFiles: File[] = []

      for (const file of files) {
        // 1. MIME Validation
        if (!matchesAccept(file, normalizedAccept)) {
          setHasError(true)
          onError?.("Định dạng tệp không được hỗ trợ.")
          return
        }

        // 2. Compression or direct size validation
        if (compress) {
          try {
            const result = await compressImage(file, {
              maxDimension,
              quality: compressionQuality,
            })
            if (result.file.size > maxSizeBytes) {
              setHasError(true)
              onError?.("Dung lượng tệp vượt quá giới hạn cho phép.")
              return
            }
            validFiles.push(result.file)
          } catch {
            // Fallback to original file if compression canvas is unsupported (e.g. in test env)
            if (file.size > maxSizeBytes) {
              setHasError(true)
              onError?.("Dung lượng tệp vượt quá giới hạn cho phép.")
              return
            }
            validFiles.push(file)
          }
        } else {
          if (file.size > maxSizeBytes) {
            setHasError(true)
            onError?.("Dung lượng tệp vượt quá giới hạn cho phép.")
            return
          }
          validFiles.push(file)
        }
      }

      if (validFiles.length > 0) {
        onFilesSelected(multiple ? validFiles : [validFiles[0]])
      }
    },
    [
      disabled,
      normalizedAccept,
      compress,
      maxDimension,
      compressionQuality,
      maxSizeBytes,
      onError,
      onFilesSelected,
      multiple,
    ]
  )

  const handleDragOver = React.useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      if (disabled) return
      e.preventDefault()
      e.stopPropagation()
      setIsDragging(true)
    },
    [disabled]
  )

  const handleDragEnter = React.useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      if (disabled) return
      e.preventDefault()
      e.stopPropagation()
      dragCounterRef.current += 1
      setIsDragging(true)
    },
    [disabled]
  )

  const handleDragLeave = React.useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      if (disabled) return
      e.preventDefault()
      e.stopPropagation()
      dragCounterRef.current -= 1
      if (dragCounterRef.current <= 0) {
        dragCounterRef.current = 0
        setIsDragging(false)
      }
    },
    [disabled]
  )

  const handleDrop = React.useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      if (disabled) return
      e.preventDefault()
      e.stopPropagation()
      dragCounterRef.current = 0
      setIsDragging(false)

      const files = Array.from(e.dataTransfer?.files || [])
      if (files.length > 0) {
        void processAndEmitFiles(files)
      }
    },
    [disabled, processAndEmitFiles]
  )

  const handlePaste = React.useCallback(
    (e: React.ClipboardEvent<HTMLDivElement>) => {
      if (disabled || !enablePaste) return
      const pastedFiles: File[] = []

      if (e.clipboardData?.items) {
        for (let i = 0; i < e.clipboardData.items.length; i++) {
          const item = e.clipboardData.items[i]
          if (item.type.startsWith("image/")) {
            const f = item.getAsFile()
            if (f) pastedFiles.push(f)
          }
        }
      }

      if (pastedFiles.length === 0 && e.clipboardData?.files) {
        for (let i = 0; i < e.clipboardData.files.length; i++) {
          const f = e.clipboardData.files[i]
          if (f.type.startsWith("image/")) {
            pastedFiles.push(f)
          }
        }
      }

      if (pastedFiles.length > 0) {
        e.preventDefault()
        e.stopPropagation()
        void processAndEmitFiles(pastedFiles)
      }
    },
    [disabled, enablePaste, processAndEmitFiles]
  )

  const handleClick = React.useCallback(() => {
    if (disabled || isUploading) return
    inputRef.current?.click()
  }, [disabled, isUploading])

  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (disabled || isUploading) return
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault()
        inputRef.current?.click()
      }
    },
    [disabled, isUploading]
  )

  const handleInputChange = React.useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || [])
      if (files.length > 0) {
        void processAndEmitFiles(files)
      }
      // Reset input value so re-selecting same file triggers event
      if (inputRef.current) {
        inputRef.current.value = ""
      }
    },
    [processAndEmitFiles]
  )

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      data-slot="image-upload-dropzone"
      data-dragging={isDragging ? "true" : "false"}
      aria-disabled={disabled}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      onDragOver={handleDragOver}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onPaste={handlePaste}
      className={cn(
        dropzoneVariants({
          variant,
          isDragging,
          hasError,
          disabled,
        }),
        className
      )}
      {...restProps}
    >
      <input
        ref={inputRef}
        type="file"
        accept={acceptString}
        multiple={multiple}
        disabled={disabled || isUploading}
        onChange={handleInputChange}
        tabIndex={-1}
        className="sr-only"
        aria-hidden="true"
      />

      {previewUrl ? (
        <div className="relative group/preview size-full flex items-center justify-center overflow-hidden rounded-lg">
          <img
            src={previewUrl}
            alt="Xem trước hình ảnh"
            className={cn(
              "object-cover",
              variant === "avatar"
                ? "size-full rounded-full"
                : variant === "compact"
                  ? "size-full rounded-md"
                  : "max-h-48 rounded-lg shadow-xs"
            )}
          />
          {onRemovePreview && !disabled && (
            <button
              type="button"
              aria-label="Xóa ảnh"
              onClick={(e) => {
                e.stopPropagation()
                onRemovePreview()
              }}
              className="absolute top-2 right-2 rounded-full bg-background/80 p-1.5 text-foreground shadow-md backdrop-blur-xs hover:bg-destructive hover:text-destructive-foreground transition-colors cursor-pointer"
            >
              <X className="size-3.5" />
            </button>
          )}
        </div>
      ) : isUploading ? (
        <div className="flex flex-col items-center gap-2.5 p-2 w-full max-w-xs">
          <Loader2 className="size-6 animate-spin text-primary" />
          <span className="text-xs font-medium text-muted-foreground">
            Đang tải lên...
          </span>
          {uploadProgress !== undefined && (
            <Progress value={uploadProgress} className="h-1.5 w-full mt-1" />
          )}
        </div>
      ) : variant === "compact" ? (
        <div className="flex flex-col items-center justify-center gap-1">
          <Upload className="size-4 text-muted-foreground" />
          <span className="text-[10px] text-muted-foreground font-medium">Tải ảnh</span>
        </div>
      ) : variant === "avatar" ? (
        <div className="flex flex-col items-center justify-center gap-1.5 text-muted-foreground">
          <ImageIcon className="size-8" />
          <span className="text-xs font-medium">Đổi ảnh</span>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2 p-2">
          <div className="rounded-full bg-muted p-3 text-muted-foreground">
            <Upload className="size-6" />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-semibold text-foreground">
              {titleText}
            </p>
            {hintText && (
              <p className="text-xs text-muted-foreground">
                {hintText}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
