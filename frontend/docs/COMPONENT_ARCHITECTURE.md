# Component Architecture Guide

## Overview

This document describes the new component-based architecture for Nihongo templates, CSS, and JavaScript.

## Directory Structure

```
templates/
├── base.html                          (Main layout template)
├── components/                        (Reusable components)
│   ├── navbar.html                   (Navigation bar)
│   ├── alerts.html                   (Flash message alerts)
│   ├── forms/                        (Form components)
│   │   ├── text_input.html          (Text input field)
│   │   ├── email_input.html         (Email input field)
│   │   ├── password_input.html      (Password input field)
│   │   ├── textarea.html            (Textarea field)
│   │   └── form_actions.html        (Submit/Cancel buttons)
│   ├── buttons/                     (Button components)
│   │   ├── primary.html             (Primary button)
│   │   ├── secondary.html           (Secondary button)
│   │   └── link.html                (Link button)
│   ├── modals/                      (Modal components)
│   │   └── base_modal.html          (Generic modal)
│   └── deck/                        (Deck UI components)
│       ├── deck_row.html            (Single deck row)
│       ├── deck_list.html           (Deck list container)
│       └── deck_tabs.html           (Deck navigation tabs)
├── index.html, login.html, register.html   (Page templates)
│
static/
├── css/
│   ├── main.css                      (Global styles)
│   └── components/                  (Component-specific styles)
│       ├── forms.css
│       ├── buttons.css
│       ├── navbar.css
│       ├── modals.css
│       └── deck.css
└── js/
    ├── main.js                       (Global utilities)
    └── components/                  (Component logic)
        ├── forms.js
        ├── modals.js
        └── deck.js
```

## Component Usage Examples

### 1. Form Components

#### Text Input
```html
{% set field_id = 'username' %}
{% set field_name = 'username' %}
{% set label = 'Username' %}
{% set placeholder = 'Enter username' %}
{% set required = true %}
{% include 'components/forms/text_input.html' %}
```

**Parameters**:
- `field_id` (string): HTML id attribute
- `field_name` (string): Form field name
- `label` (string): Field label
- `placeholder` (string): Placeholder text
- `required` (bool): Is field required?
- `value` (string, optional): Pre-filled value

#### Email Input
```html
{% set field_id = 'email' %}
{% set field_name = 'email' %}
{% set label = 'Email Address' %}
{% include 'components/forms/email_input.html' %}
```

#### Password Input
```html
{% set field_id = 'password' %}
{% set field_name = 'password' %}
{% set label = 'Password' %}
{% include 'components/forms/password_input.html' %}
```

#### Textarea
```html
{% set field_id = 'description' %}
{% set field_name = 'description' %}
{% set label = 'Description' %}
{% set rows = 5 %}
{% include 'components/forms/textarea.html' %}
```

#### Form Actions
```html
{% set submit_label = 'Save' %}
{% set cancel_url = url_for('main.dashboard') %}
{% set submit_class = 'primary' %}
{% set cancel_class = 'outline-secondary' %}
{% include 'components/forms/form_actions.html' %}
```

### 2. Button Components

#### Primary Button
```html
{% set label = 'Click Me' %}
{% set id = 'my-btn' %}
{% set onclick = 'alert("Clicked!")' %}
{% include 'components/buttons/primary.html' %}
```

#### Link Button
```html
{% set label = 'Learn More' %}
{% set href = url_for('main.dashboard') %}
{% set size = 'sm' %}
{% include 'components/buttons/link.html' %}
```

### 3. Modal Components

#### Base Modal
```html
{% set modal_id = 'createDeckModal' %}
{% set modal_title = 'Create New Deck' %}
{% set modal_body = '<p>Enter deck details...</p>' %}
{% set confirm_id = 'confirm-create' %}
{% set confirm_label = 'Create' %}
{% set cancel_label = 'Cancel' %}
{% include 'components/modals/base_modal.html' %}
```

### 4. Deck Components

#### Deck List
```html
{% include 'components/deck/deck_tabs.html' %}

<section class="anki-board">
  <header class="anki-board-head">
    <h3>Decks</h3>
    <div class="anki-col-heads">
      <span>New</span>
      <span>Learn</span>
      <span>Due</span>
    </div>
  </header>
  
  {% include 'components/deck/deck_list.html' %}
</section>
```

### 5. Navbar Component

```html
<!-- Automatically included in base.html -->
<!-- Appears at top of every page -->
<!-- Handles auth state (logged in / logged out) -->
```

## JavaScript Component APIs

### FormComponent

```javascript
// Validate required fields
FormComponent.validateRequired(form);  // returns true/false

// Validate email format
FormComponent.validateEmail('user@example.com');  // returns true/false

// Clear form
FormComponent.clearForm(form);

// Show error
FormComponent.showError(field, 'Invalid input');

// Clear error
FormComponent.clearError(field);
```

### ModalComponent

```javascript
// Show modal
ModalComponent.show('myModalId');

// Hide modal
ModalComponent.hide('myModalId');

// Attach confirm handler
ModalComponent.onConfirm('confirmBtnId', () => {
  console.log('User confirmed');
});

// Show alert modal
ModalComponent.showAlert('Error', 'Something went wrong', true);
```

### DeckComponent

```javascript
// Toggle tree expansion
DeckComponent.toggleTree(toggleBtn);

// Select/open deck
DeckComponent.selectDeck(deckRow);

// Start create deck flow
DeckComponent.startCreateDeck();

// Submit create deck
DeckComponent.submitCreateDeck('Parent::Child::Name', () => {
  console.log('Deck created');
});
```

### Utils (Global)

```javascript
// Get element safely
Utils.getElement('id');

// Format date
Utils.formatDate(new Date());  // returns 'DD/MM/YYYY'

// Debounce function
const debouncedSearch = Utils.debounce((q) => search(q), 300);

// Throttle function
const throttledScroll = Utils.throttle(() => handleScroll(), 300);

// Show loading spinner
Utils.showLoading(element);

// Escape HTML
Utils.escapeHtml('<script>alert("XSS")</script>');
```

## CSS Architecture

### Global Styles (main.css)
- Layout and spacing
- Typography
- Global utilities
- Responsive utilities
- Print styles

### Component Styles
Each component has its own CSS file in `static/css/components/`:

| File | Contains |
|------|----------|
| forms.css | Form field, input, textarea styles |
| buttons.css | Button variants and hover states |
| navbar.css | Navigation bar styling |
| modals.css | Modal dialogs and animations |
| deck.css | Deck tree, rows, stats, tabs |

### CSS Naming Convention
- BEM-like naming: `.component-name`, `.component-name__element`
- Utility classes for common patterns
- No inline styles (use CSS classes instead)
- Responsive breakpoints: `@media (max-width: 576px)`, `@media (max-width: 768px)`

## Best Practices

### 1. Adding New Components

**Step 1**: Create component template in `templates/components/<category>/`
```html
{# Component: Component Name #}
{# Usage: {% include 'components/<category>/component.html' with context %} #}
{# Params: param1, param2, param3 #}

<div class="component-name">
  {{ param1 }}
</div>
```

**Step 2**: Create CSS file in `static/css/components/component-name.css`

**Step 3**: Create JavaScript file in `static/js/components/component-name.js` (if needed)

**Step 4**: Link CSS/JS in `base.html`

### 2. Using Components

Always set parameters before including:
```html
{% set param1 = 'value1' %}
{% set param2 = 'value2' %}
{% include 'components/category/component.html' %}
```

### 3. Component Documentation

Include header comment in every component:
```html
{# Component: Clear Name #}
{# Usage: Show where/how to use #}
{# Params: List all parameters #}
```

### 4. Avoiding Duplication

- Extract repeated HTML into components
- Use CSS utility classes for common styling
- Consolidate similar JavaScript into helper functions

## Migration Guide

### Converting Old Pages to Components

**Before**:
```html
<div class="mb-3">
  <label for="email">Email</label>
  <input type="email" id="email" name="email" required />
</div>
```

**After**:
```html
{% set field_id = 'email' %}
{% set field_name = 'email' %}
{% set label = 'Email' %}
{% set required = true %}
{% include 'components/forms/email_input.html' %}
```

Benefits:
- ✅ Consistent styling
- ✅ Easier to maintain
- ✅ Reusable code
- ✅ Centralized logic
- ✅ Better organization

## Testing Components

Each component can be tested independently:

1. **HTML**: Verify markup structure
2. **CSS**: Check visual consistency
3. **JavaScript**: Test event handlers and utilities

Example test:
```html
<!-- Test form validation -->
<form id="test-form">
  {% include 'components/forms/email_input.html' %}
  <button type="submit">Submit</button>
</form>

<script>
  const form = document.getElementById('test-form');
  FormComponent.validateRequired(form);  // Should return false (empty)
</script>
```

## Performance Tips

1. Load component CSS files in parallel (already done in base.html)
2. Defer non-critical JavaScript with `defer` attribute
3. Minify CSS/JS in production
4. Use CSS utility classes to reduce file size
5. Lazy-load components only when needed

## Troubleshooting

### Component Not Showing
- Check if CSS is linked in base.html
- Verify component file exists in correct path
- Check browser console for JavaScript errors

### Style Not Applied
- Check CSS selector specificity
- Verify CSS file is linked before other stylesheets
- Use browser DevTools to inspect element

### JavaScript Error
- Check if dependencies (Bootstrap) are loaded
- Verify component JavaScript file is linked
- Check console for error messages

## Future Improvements

1. Create VueJS/React component versions for more interactivity
2. Add component unit tests
3. Create storybook for component showcase
4. Add accessibility improvements (ARIA labels)
5. Create dark mode variants
6. Add animation/transition library integration
