import "@/shared/config/i18n"
import * as React from "react"
import { useTranslation } from "react-i18next"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { SplitPane } from "./SplitPane"

export type WorkspacePane = "primary" | "secondary"

export interface WorkspaceLayoutProps {
  /** Main working surface (code editor, mapping form). */
  primary: React.ReactNode
  /** Companion surface, usually the live preview. */
  secondary: React.ReactNode
  /** Tab labels used below `lg`, where only one pane is shown at a time. */
  primaryLabel: string
  secondaryLabel: string
  /** Accessible name of the mobile tab list. */
  tabsLabel: string
  /** Controlled mobile pane; omit to let the layout manage it. */
  activePane?: WorkspacePane
  onActivePaneChange?: (pane: WorkspacePane) => void
  /** Initial share of the primary pane in percent on large screens (default: 50). */
  defaultRatio?: number
  minRatio?: number
  maxRatio?: number
  /** Persists the user's split per workspace kind, e.g. `flama:template-editor:split`. */
  storageKey?: string
  className?: string
}

/**
 * Two-pane workspace: resizable side by side from `lg`, tabbed below it.
 * Panes get the full height of the layout, so pass `className="lg:flex-1 lg:min-h-0"`
 * inside a filling page and make pane content `h-full`.
 */
export function WorkspaceLayout({
  primary,
  secondary,
  primaryLabel,
  secondaryLabel,
  tabsLabel,
  activePane,
  onActivePaneChange,
  defaultRatio = 50,
  minRatio = 30,
  maxRatio = 70,
  storageKey,
  className,
}: WorkspaceLayoutProps) {
  const { t } = useTranslation("common")
  const [internalPane, setInternalPane] = React.useState<WorkspacePane>("primary")
  const pane = activePane ?? internalPane
  const selectPane = (next: WorkspacePane) => {
    if (activePane === undefined) setInternalPane(next)
    onActivePaneChange?.(next)
  }
  const tabs: Array<[WorkspacePane, string]> = [["primary", primaryLabel], ["secondary", secondaryLabel]]

  return (
    <div data-slot="workspace-layout" className={cn("flex min-h-0 flex-col gap-3", className)}>
      <div role="tablist" aria-label={tabsLabel} className="flex rounded-xl border bg-muted/30 p-1 lg:hidden">
        {tabs.map(([id, label]) => (
          <Button key={id} type="button" role="tab" aria-selected={pane === id} variant={pane === id ? "default" : "ghost"}
            className="flex-1" onClick={() => selectPane(id)}>
            {label}
          </Button>
        ))}
      </div>
      <SplitPane
        className="min-h-0 flex-1"
        sizeUnit="percent"
        collapseBelow="lg"
        handleAppearance="gutter"
        handleLabel={t("layout.resize_panels")}
        defaultSize={defaultRatio}
        minSize={minRatio}
        maxSize={maxRatio}
        step={2}
        storageKey={storageKey}
        mobileActivePane={pane}
        primaryClassName="min-w-0 overflow-visible"
        secondaryClassName="overflow-visible"
        primaryPane={primary}
        secondaryPane={secondary}
      />
    </div>
  )
}
