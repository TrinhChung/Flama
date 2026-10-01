import * as React from "react"
import { cva } from "class-variance-authority"
import { Check, Copy } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

export const codeSnippetVariants = cva(
  "rounded-lg border border-border bg-muted/20 dark:bg-muted/10 overflow-hidden text-sm",
  {
    variants: {
      variant: {
        default: "border-border bg-muted/20 dark:bg-muted/10",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface CodeSnippetBoxProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "onCopy"> {
  /** The code string to display and copy */
  code: string
  /** Programming language or data format (e.g. 'json', 'bash', 'yaml') */
  language?: string
  /** Optional title or filename */
  title?: string
  /** Whether to show the copy button (default: true) */
  showCopyButton?: boolean
  /** Whether to render line numbers (default: false) */
  showLineNumbers?: boolean
  /** Custom label for copy button (default: 'Sao chép') */
  copyLabel?: string
  /** Custom label for copied state (default: 'Đã chép') */
  copiedLabel?: string
  /** Callback fired when code is successfully copied */
  onCopy?: (code: string) => void
}

export const CodeSnippetBox = React.forwardRef<HTMLDivElement, CodeSnippetBoxProps>(
  (
    {
      code,
      language,
      title,
      showCopyButton = true,
      showLineNumbers = false,
      copyLabel = "Sao chép",
      copiedLabel = "Đã chép",
      onCopy,
      className,
      ...props
    },
    ref
  ) => {
    const [copied, setCopied] = React.useState(false)
    const timeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)

    React.useEffect(() => {
      return () => {
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current)
        }
      }
    }, [])

    const handleCopy = React.useCallback(async () => {
      let success = false
      try {
        if (
          typeof navigator !== "undefined" &&
          navigator.clipboard &&
          navigator.clipboard.writeText
        ) {
          await navigator.clipboard.writeText(code)
          success = true
        } else {
          throw new Error("Clipboard API unavailable")
        }
      } catch {
        // Fallback: document.execCommand('copy')
        try {
          const textArea = document.createElement("textarea")
          textArea.value = code
          textArea.style.position = "fixed"
          textArea.style.left = "-9999px"
          textArea.style.top = "-9999px"
          document.body.appendChild(textArea)
          textArea.focus()
          textArea.select()
          success = document.execCommand("copy")
          textArea.remove()
        } catch {
          success = false
        }
      }

      if (success) {
        setCopied(true)
        onCopy?.(code)
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current)
        }
        timeoutRef.current = setTimeout(() => {
          setCopied(false)
        }, 2000)
      }
    }, [code, onCopy])

    const lines = React.useMemo(() => code.split("\n"), [code])

    return (
      <div
        ref={ref}
        data-slot="code-snippet-box"
        className={cn(codeSnippetVariants(), className)}
        {...props}
      >
        {(title || language || showCopyButton) && (
          <div
            data-slot="code-snippet-header"
            className="flex items-center justify-between border-b border-border/80 bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground"
          >
            <div className="flex items-center gap-2 font-mono">
              {title && (
                <span
                  data-slot="code-snippet-title"
                  className="font-medium text-foreground"
                >
                  {title}
                </span>
              )}
              {language && (
                <span
                  data-slot="code-snippet-language"
                  className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase text-muted-foreground"
                >
                  {language}
                </span>
              )}
            </div>
            {showCopyButton && (
              <Button
                type="button"
                variant="ghost"
                size="xs"
                onClick={handleCopy}
                className="h-6 gap-1 px-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted"
                aria-label={copied ? copiedLabel : copyLabel}
              >
                {copied ? (
                  <>
                    <Check className="size-3 text-emerald-500" />
                    <span>{copiedLabel}</span>
                  </>
                ) : (
                  <>
                    <Copy className="size-3" />
                    <span>{copyLabel}</span>
                  </>
                )}
              </Button>
            )}
          </div>
        )}

        <div className="p-3">
          {showLineNumbers ? (
            <div className="flex font-mono text-xs leading-relaxed">
              <div
                className="select-none pr-3 text-right text-muted-foreground/40"
                aria-hidden="true"
              >
                {lines.map((_, i) => (
                  <div key={i}>{i + 1}</div>
                ))}
              </div>
              <pre className="flex-1 overflow-x-auto text-foreground">
                <code>{code}</code>
              </pre>
            </div>
          ) : (
            <pre className="overflow-x-auto font-mono text-xs leading-relaxed text-foreground">
              <code>{code}</code>
            </pre>
          )}
        </div>
      </div>
    )
  }
)

CodeSnippetBox.displayName = "CodeSnippetBox"
