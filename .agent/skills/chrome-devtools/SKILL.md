---
name: chrome-devtools
description: >-
  Expert guide for deep app performance profiling, debugging, Core Web Vitals audit,
  and runtime optimization using Chrome DevTools MCP with strictly isolated browser profiles.
---

# Chrome DevTools & Deep App Optimization Skill

This skill guides the agent and developers on executing deep performance audits, memory profiling, render lifecycle debugging, and network optimization for the Flama application (React 19 + Vite + TailwindCSS v4 + Flask REST API) using Chrome DevTools.

---

## 🚨 Golden Rule: Strict Profile Isolation

> [!CAUTION]
> **NEVER** attach remote debugging to or launch Chrome using the user's default/personal profile.
> **ALWAYS** use a dedicated, isolated `--user-data-dir`.

### Why?
1. **Security & Privacy**: Prevents exposing personal cookies, passwords, browsing history, and active sessions to automated tooling or scripts.
2. **Deterministic Profiling**: Eliminates noise from user extensions (ad blockers, password managers), background sync, and cached personal states.
3. **Chrome 136+ Restriction**: Modern Chrome blocks remote debugging on the default user data directory.

### Standard Dedicated Profile Directory
- **Path**: `C:\Users\chung\.gemini\chrome-profiles\flama-devtools` (Windows) or `~/.gemini/chrome-profiles/flama-devtools` (Unix)

---

## 🛠️ Launching Chrome with Isolated Profile

### Option 1: Using the Project Helper Script (Recommended)
```powershell
.\scripts\launch_chrome_devtools.ps1
```

### Option 2: Manual Command Line
```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir="C:\Users\chung\.gemini\chrome-profiles\flama-devtools" `
  --no-first-run `
  --no-default-browser-check `
  "http://localhost:5173"
```

---

## 🔬 Deep Optimization Workflows

### 1. Runtime Performance & Core Web Vitals
- **Metrics to Track**:
  - **LCP (Largest Contentful Paint)**: Target < 1.2s. Inspect image/font loading and flashcard note template rendering.
  - **CLS (Cumulative Layout Shift)**: Target < 0.05. Ensure skeletons or fixed aspect-ratio containers are used for dynamic flashcard media, charts, and decks.
  - **INP (Interaction to Next Paint)**: Target < 100ms. Check click-to-flip latency in flashcards, deck tree expand/collapse, and audio playback triggers.
  - **Long Tasks (> 50ms)**: Identify heavy synchronous operations in JS main thread (e.g., heavy regex parsing, markdown/mustache template compiling, large JSON transformation).

### 2. React 19 Render & Component Tree Optimization
- **Profiler Inspection**:
  - Track unnecessary re-renders in deck tree lists (`DeckTree`), study sessions (`StudySession`), and analytics charts (`Recharts`).
  - Verify `useMemo`, `useCallback`, and custom hooks (`useFlashcardStudy`, `useDeckTree`) don't break reference equality on parent state changes.
  - Ensure Radix UI primitives and Tailwind v4 utility transitions don't cause layout thrashing (`forced reflow`).

### 3. Network Waterfall & Asset Loading
- **Audit Points**:
  - **Vite Bundle Splitting**: Inspect `frontend/dist/assets/` chunk sizes. Lazy-load heavy dependencies (e.g. `recharts`, `@zip.js/zip.js`, `lucide-react` icons).
  - **Media & Audio Streaming**: Check Flama Audio / local TTS response times (`http://127.0.0.1:4791`), audio blob caching, and `/media/proxy/` asset caching headers.
  - **API Payload Size**: Verify Flask API JSON responses (e.g., `/api/decks/browse`, `/api/flashcards/study/queue`) are pruned and do not over-fetch unnecessary fields.
  - **Throttling Tests**: Test study session and media playback under simulated **Fast 3G** and **Slow 3G** to ensure graceful fallback/loading states.

### 4. Memory Leak & DOM Lifecycle Audit
- **Audit Points**:
  - **Heap Snapshots**: Compare snapshots before and after 50 flashcard review cycles. Ensure unmounted card components release all DOM nodes and audio instances.
  - **Detached DOM Elements**: Inspect DOM node count in Chrome DevTools Memory panel. Check if tooltips, popovers (Radix UI), or modal dialogs leave detached elements.
  - **Event Listeners & Timers**: Confirm `useEffect` cleanup functions remove keyboard event listeners (`Space`, `1-4` hotkeys) and clear intervals/timeouts.

### 5. Console & Security/CSP Verification
- Verify Content Security Policy (CSP) headers allow local TTS audio blobs and proxy media assets without console warnings.
- Confirm zero unhandled promise rejections and clean console logs in production builds.

---

## 🚦 Lighthouse SEO & Performance Auditing

Lighthouse runs in an isolated environment against the dedicated profile (`C:\Users\chung\.gemini\chrome-profiles\flama-devtools`).

### Running Lighthouse Audits:

1. **Via PowerShell Script**:
   ```powershell
   # Audit SEO only
   .\scripts\run_lighthouse_audit.ps1 -Categories "seo"

   # Full audit (SEO, Performance, Accessibility, Best Practices)
   .\scripts\run_lighthouse_audit.ps1
   ```

2. **Via Frontend NPM Scripts**:
   ```powershell
   cd frontend
   npm run audit:seo
   npm run audit:lighthouse
   ```

3. **Via Chrome DevTools UI**:
   - Launch Chrome with isolated profile: `.\scripts\launch_chrome_devtools.ps1`
   - Open DevTools (`F12`), switch to **Lighthouse** tab.
   - Select **SEO** (and other categories), click **Analyze page load**.

