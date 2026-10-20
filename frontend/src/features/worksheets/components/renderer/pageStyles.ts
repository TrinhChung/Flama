/** Overrides that normalize server stroke SVGs and their color / numbering modes. */
export const WORKSHEET_PAGE_CSS = `
        .stroke-box-wrap svg,
        .stroke-step-box svg,
        .stroke-static-box svg,
        .stroke-trace-box svg,
        .flama-static-kanji-box,
        .flama-stroke-char,
        svg.flama-stroke-char {
          width: 100% !important;
          height: 100% !important;
          max-width: 100% !important;
          max-height: 100% !important;
          display: block !important;
        }
        .flama-kvg-num {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace !important;
          font-size: 12px !important;
          font-weight: 800 !important;
          paint-order: stroke fill !important;
          stroke: #ffffff !important;
          stroke-width: 2px !important;
        }
        .flama-mmah-numbers text,
        .flama-stroke-num {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace !important;
          font-size: 56px !important;
          font-weight: 900 !important;
          paint-order: stroke fill !important;
          stroke: #ffffff !important;
          stroke-width: 10px !important;
        }
        .stroke-box-wrap .flama-grid-box rect {
          stroke-width: 3 !important;
        }
        .stroke-box-wrap .flama-grid-box path {
          stroke-width: 2.5 !important;
          stroke-dasharray: 10,10 !important;
        }
        .flama-hide-stroke-numbers .flama-kvg-num,
        .flama-hide-stroke-numbers .flama-mmah-numbers,
        .flama-hide-stroke-numbers .flama-stroke-num {
          display: none !important;
        }
        .flama-stroke-monochrome .flama-stroke-char {
          --flama-stroke-c1: #0f172a !important;
          --flama-stroke-c2: #0f172a !important;
          --flama-stroke-c3: #0f172a !important;
          --flama-stroke-c4: #0f172a !important;
          --flama-stroke-c5: #0f172a !important;
          --flama-stroke-c6: #0f172a !important;
          --flama-stroke-c7: #0f172a !important;
          --flama-stroke-c8: #0f172a !important;
          --flama-stroke-c9: #0f172a !important;
          --flama-stroke-c10: #0f172a !important;
        }
        .flama-stroke-monochrome .flama-kvg-num,
        .flama-stroke-monochrome .flama-mmah-numbers text,
        .flama-stroke-monochrome .flama-stroke-num {
          fill: #0f172a !important;
          stroke: #ffffff !important;
        }
        .flama-stroke-monochrome .flama-kvg-stroke {
          stroke: #0f172a !important;
        }
        .flama-stroke-monochrome path[id^="make-me-a-hanzi-animation"] {
          stroke: #0f172a !important;
        }
        .flama-stroke-same-ref .flama-kvg-stroke {
          stroke: var(--ref-char-color, #e11d48) !important;
        }
        .flama-stroke-same-ref .flama-kvg-num,
        .flama-stroke-same-ref .flama-mmah-numbers text,
        .flama-stroke-same-ref .flama-stroke-num {
          fill: var(--ref-char-color, #e11d48) !important;
          stroke: #ffffff !important;
        }
        .flama-stroke-same-ref path[id^="make-me-a-hanzi-animation"] {
          stroke: var(--ref-char-color, #e11d48) !important;
        }
      `
