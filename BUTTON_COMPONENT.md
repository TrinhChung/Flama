# Button Component - Flama Design System

## Overview
Unified button component sử dụng Flama Design System colors. Thay thế tất cả Bootstrap button classes mặc định.

## Button Types

### Primary (Orange)
```jinja2
{% set button_label = 'Create' %}
{% set button_type = 'primary' %}
{% include 'components/button.html' with context %}
```
**Use case:** Hành động chính, CTA (Call-To-Action)
**Color:** `--flama-orange-600` (#E05C07)

### Secondary (Amber)
```jinja2
{% set button_type = 'secondary' %}
{% include 'components/button.html' with context %}
```
**Use case:** Hành động phụ
**Color:** `--flama-amber-600` (#E08D0C)

### Outline (Stroked Orange)
```jinja2
{% set button_type = 'outline' %}
{% include 'components/button.html' with context %}
```
**Use case:** Hành động tùy chọn
**Color:** Border only

### Outline Secondary (Stroked Gray)
```jinja2
{% set button_type = 'outline-secondary' %}
{% include 'components/button.html' with context %}
```
**Use case:** Hành động phụ, Cancel buttons

### Danger (Red)
```jinja2
{% set button_type = 'danger' %}
{% include 'components/button.html' with context %}
```
**Use case:** Xóa, hành động nguy hiểm
**Color:** #dc3545

### Outline Danger (Stroked Red)
```jinja2
{% set button_type = 'outline-danger' %}
{% include 'components/button.html' with context %}
```

### Light (Surface)
```jinja2
{% set button_type = 'light' %}
{% include 'components/button.html' with context %}
```
**Use case:** Surface buttons, secondary actions

### Link
```jinja2
{% set button_type = 'link' %}
{% include 'components/button.html' with context %}
```
**Use case:** Text links chứng chỉ button behavior
**Color:** Orange

## Button Sizes

### Small
```jinja2
{% set button_size = 'sm' %}
```

### Medium (Default)
```jinja2
{% set button_size = 'md' %}
```

### Large
```jinja2
{% set button_size = 'lg' %}
```

## Full Width Button
```jinja2
{% set button_full_width = true %}
```

## Icons
Sử dụng Bootstrap Icons:
```jinja2
{% set icon_class = 'bi bi-plus' %}
```

## Link vs Button
- **Link buttons:** Đặt `button_href`, component sẽ render `<a>` tag
- **Submit buttons:** Default, render `<button type="submit">`

## Examples

### Login Button
```jinja2
{% set button_label = 'Đăng nhập' %}
{% set button_href = url_for('auth.login') %}
{% set button_type = 'primary' %}
{% include 'components/button.html' with context %}
```

### Cancel Button (Modal)
```jinja2
{% set button_label = 'Hủy' %}
{% set button_type = 'outline-secondary' %}
{% set button_disabled = false %}
{% include 'components/button.html' with context %}
```

### Delete Button
```jinja2
{% set button_label = 'Xóa' %}
{% set button_type = 'outline-danger' %}
{% set button_size = 'sm' %}
{% set button_id = 'delete-btn' %}
{% include 'components/button.html' with context %}
```

### Full Width Form Submit
```jinja2
{% set button_label = 'Đăng ký' %}
{% set button_type = 'primary' %}
{% set button_full_width = true %}
{% include 'components/button.html' with context %}
```

## All Available Parameters

| Parameter | Values | Default | Required |
|-----------|--------|---------|----------|
| button_label | string | "Button" | No |
| button_type | primary, secondary, outline, outline-secondary, danger, outline-danger, light, link | primary | No |
| button_size | sm, md, lg | md | No |
| button_href | string (URL) | - | No* |
| button_id | string | - | No |
| button_class | string | - | No |
| button_disabled | true/false | false | No |
| button_full_width | true/false | false | No |
| icon_class | Bootstrap icon class | - | No |

*If `button_href` is provided, renders `<a>` tag. Without it, renders `<button type="submit">`.

## CSS Variables Used
All colors come from Flama Design System (`static/css/variables.css`):
- `--flama-orange-500` - Primary action
- `--flama-orange-600` - Primary hover
- `--flama-orange-700` - Primary active
- `--flama-orange-800` - Primary dark
- `--flama-amber-600` - Secondary
- `--flama-text` - Text color
- `--flama-border` - Border color
- `--flama-surface` - Light backgrounds
