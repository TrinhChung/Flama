# Typography System - Flama Design System

## Overview
Unified typography system sử dụng CSS variables để đảm bảo font consistency across tất cả pages.

## Font Stack

### Primary Font Family
```css
--font-family-base: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
```
Sử dụng system fonts cho performance tốt nhất:
- **macOS/iOS:** San Francisco
- **Windows:** Segoe UI  
- **Android:** Roboto
- **Fallback:** Helvetica Neue, Arial

### Monospace Font Family
```css
--font-family-mono: 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', monospace;
```
Dùng cho `<code>` và `<pre>` elements.

## Font Sizes

| Token | Size | Sử dụng |
|-------|------|--------|
| `--font-size-xs` | 0.75rem (12px) | Small labels, captions |
| `--font-size-sm` | 0.875rem (14px) | Navigation, small text |
| `--font-size-base` | 1rem (16px) | Body text, forms (DEFAULT) |
| `--font-size-lg` | 1.125rem (18px) | Modal titles, large labels |
| `--font-size-xl` | 1.25rem (20px) | Headings (h3) |
| `--font-size-2xl` | 1.5rem (24px) | Headings (h2) |
| `--font-size-3xl` | 1.875rem (30px) | Headings (h1) |

## Font Weights

| Token | Weight | Usage |
|-------|--------|-------|
| `--font-weight-normal` | 400 | Body text |
| `--font-weight-medium` | 500 | Labels, navigation |
| `--font-weight-semibold` | 600 | Buttons, strong text |
| `--font-weight-bold` | 700 | Headings, active states |
| `--font-weight-extrabold` | 800 | Brand text, logos |

## Line Heights

| Token | Value | Usage |
|-------|-------|-------|
| `--line-height-tight` | 1.2 | Headings |
| `--line-height-snug` | 1.375 | Subheadings |
| `--line-height-normal` | 1.5 | Body text (DEFAULT) |
| `--line-height-relaxed` | 1.625 | Long paragraphs |
| `--line-height-loose` | 2 | Spacious layouts |

## Usage Examples

### Heading
```html
<h2>My Heading</h2>
```
CSS:
```css
h2 {
  font-family: var(--font-family-base);
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  line-height: var(--line-height-tight);
}
```

### Button
```html
<button class="btn btn-primary">Click me</button>
```
CSS:
```css
.btn {
  font-family: var(--font-family-base);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-normal);
}
```

### Navigation Link
```html
<a class="nav-link" href="#">Link</a>
```
CSS:
```css
.nav-link {
  font-family: var(--font-family-base);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
}
```

### Small Text
```html
<small>Helper text</small>
```
CSS:
```css
small {
  font-size: var(--font-size-sm);
  color: var(--flama-text-2);
}
```

## Component Font Styles

### Navigation Tabs (.anki-tab)
- Font Size: `var(--font-size-sm)` (14px)
- Font Weight: `var(--font-weight-semibold)` (600)
- Family: `var(--font-family-base)`

### Form Labels
- Font Size: `var(--font-size-sm)` (14px)
- Font Weight: `var(--font-weight-medium)` (500)
- Family: `var(--font-family-base)`

### Form Inputs
- Font Size: `var(--font-size-base)` (16px)
- Font Weight: `var(--font-weight-normal)` (400)
- Family: `var(--font-family-base)`

### Modal Title
- Font Size: `var(--font-size-lg)` (18px)
- Font Weight: `var(--font-weight-semibold)` (600)
- Family: `var(--font-family-base)`

### Deck Stats
- Font Size: `var(--font-size-base)` (16px)
- Font Weight: `var(--font-weight-semibold)` (600)
- Family: `var(--font-family-base)`

### Navbar Brand
- Font Size: 1.5rem/1.6rem
- Font Weight: `var(--font-weight-extrabold)` (800)
- Family: `var(--font-family-base)`

## Best Practices

1. **Always use CSS variables** - Never hardcode font-size, font-weight, or font-family
2. **Start with base tokens** - Use `--font-size-base`, `--font-weight-normal` as defaults
3. **Scale consistently** - Use defined size scales, don't invent new sizes
4. **Maintain hierarchy** - Use weight to create visual hierarchy, not size alone
5. **Line height matters** - Adjust line-height when using very large or very small font sizes
6. **Test across browsers** - System fonts render differently across OS/browser combinations

## Breakpoints (Responsive Typography)

Mobile first approach:
```css
/* Base (mobile) */
h1 { font-size: var(--font-size-2xl); }

/* Tablet and larger */
@media (min-width: 768px) {
  h1 { font-size: var(--font-size-3xl); }
}
```

## Accessibility

- **Minimum font size:** 16px for body text (12px minimum for small text)
- **Line height:** Minimum 1.5 for body text readability
- **Contrast:** Ensure 4.5:1 contrast for normal text, 3:1 for large text
- **Line length:** Keep to ~60-80 characters per line for optimal readability

## Troubleshooting

**Font not rendering consistently?**
- Check that `var(--font-family-base)` is included in CSS rule
- Clear browser cache
- Test in different browser

**Text appears too small on mobile?**
- Use responsive font sizing with media queries
- Ensure base font size is at least 16px on mobile
- Check zoom level hasn't been changed

**Font looks blurry?**
- Enable font smoothing: `-webkit-font-smoothing: antialiased;`
- Use `text-rendering: optimizeLegibility;`
