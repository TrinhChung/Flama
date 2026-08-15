---
name: Flama Design System
colors:
  surface: '#fbfaf8'
  surface-dim: '#eae8e2'
  surface-bright: '#fbfaf8'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f4f3ef'
  surface-container: '#eae8e2'
  surface-container-high: '#dfded8'
  surface-container-highest: '#d4d2cb'
  on-surface: '#1c1917'
  on-surface-variant: '#57534e'
  inverse-surface: '#1c1917'
  inverse-on-surface: '#fbfaf8'
  outline: '#d6d3cd'
  outline-variant: '#e7e5e0'
  surface-tint: '#f97316'
  primary: '#f97316'
  on-primary: '#ffffff'
  primary-container: '#ffedd5'
  on-primary-container: '#7c2d12'
  inverse-primary: '#fed7aa'
  secondary: '#475569'
  on-secondary: '#ffffff'
  secondary-container: '#f1f5f9'
  on-secondary-container: '#1e293b'
  tertiary: '#10b981'
  on-tertiary: '#ffffff'
  tertiary-container: '#d1fae5'
  on-tertiary-container: '#064e3b'
  error: '#ef4444'
  on-error: '#ffffff'
  error-container: '#fee2e2'
  on-error-container: '#7f1d1d'
  background: '#fbfaf8'
  on-background: '#1c1917'
  surface-variant: '#f4f3ef'
typography:
  display-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 40px
    fontWeight: '800'
    lineHeight: '1.15'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '700'
    lineHeight: '1.25'
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 22px
    fontWeight: '600'
    lineHeight: '1.3'
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1.4'
    letterSpacing: 0.01em
  label-xs:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: '1.2'
spacing:
  base: 4px
  xs: 8px
  sm: 16px
  md: 24px
  lg: 32px
  xl: 48px
  gutter: 20px
  margin: 24px
---

# Flama Design System: The Focused Ember (Ngọn Lửa Tri Thức)

## 1. Overview & Creative North Star
**Creative North Star: The Focused Ember**

Flama is a modern, high-retention Japanese flashcard and knowledge learning platform. The visual language moves away from sterile corporate dashboards and boring software tools into an inspiring, energizing, and clutter-free study sanctuary.

The experience is defined by **Clean Geometry**, **Warm Natural Japanese Tones (Washi & Warm Ember)**, and **Precise Spacing**. It empowers self-directed learners to master Kanji, Vocabulary, and Grammar with maximum focus and minimum cognitive friction.

## 2. Colors & Surface Philosophy
- **Primary Ember (#f97316)**: The heart of Flama. Represents motivation, focus, and achievement. Used for primary CTAs, active states, streak indicators, and key focus moments.
- **Warm Background (#fbfaf8)**: Soft warm canvas inspired by handmade Japanese paper (washi), reducing eye fatigue during intense multi-hour study sessions.
- **Card Containers (#ffffff)**: Crisp white elevated surface with subtle borders (`#e7e5e0`) and soft ambient shadows.
- **JLPT Level Semantic Palette**:
  - `N5 / N4` (Beginner): Sky Blue tint (`#0284c7`)
  - `N3` (Intermediate): Emerald tint (`#059669`)
  - `N2 / N1` (Advanced): Amber / Coral tint (`#d97706`)

## 3. Typography: Precision & Legibility
- **Display & Headlines (Plus Jakarta Sans)**: Bold, energetic, and clean with slight negative letter-spacing for modern punchiness.
- **Body & Data (Inter)**: High x-height for clear reading across Kanji, Furigana, Vietnamese explanations, and metadata.
- **Tabular Numbers**: All metrics, ratings, due counts, and prices strictly use `font-variant-numeric: tabular-nums`.

## 4. Components & Interactive Patterns
- **Hero & Headers**: Clean title with contextual badges, segmented view switchers, and direct "+ Action" buttons.
- **Search & Filter Bar**: Unified search input with instant keyboard `/` shortcut trigger, active category pill chips with horizontal smooth scroll, and segmented sort tabs (⭐ Đề xuất, 🔥 Phổ biến, 🕒 Mới nhất).
- **Learning Cards**: 
  - Elevated white cards with subtle `1px` border (`#e7e5e0`) and soft hover lift (`-4px` translateY).
  - Top category badge + pricing pill (`Miễn phí` / `Free`).
  - High-contrast title with smooth hover color transition to Ember.
  - Creator info with rounded avatar initial.
  - Card metadata with Star rating, Card count (`350 thẻ`), and Download counts.
  - Contextual action button: "Học ngay" (BookOpen), "Đã cài đặt" (CheckCircle), or "Xem chi tiết" (Eye + ArrowRight).
- **Study / Flashcard Surface**: 3D flip card with Japanese Kanji display, Furigana toggle, Audio playback button, and Anki-style difficulty grade buttons (Again, Hard, Good, Easy).
