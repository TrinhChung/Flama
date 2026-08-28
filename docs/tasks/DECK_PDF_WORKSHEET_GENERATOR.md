# Task: Generate printable PDF worksheets from Decks

**Target branch:** `develop`

## Goal

Add a feature that allows users to generate printable PDF worksheets from an existing Flama Deck.

The first target use cases are:

- Kanji handwriting practice.
- Vocabulary / word writing practice.
- Custom table-based worksheets where the user chooses which Note fields are rendered.

The system must be template-based so more worksheet types can be added later without rewriting the PDF generation flow.

---

## User flow

From a Deck, add an action such as:

```text
Generate worksheet / Xuất PDF luyện tập
```

Suggested flow:

```text
Deck
  -> Generate PDF worksheet
  -> Choose worksheet template
  -> Choose source fields
  -> Configure layout/options
  -> Preview
  -> Generate PDF
  -> Download / Print
```

The generator must work from the current Deck data and should not require users to manually copy content into another screen.

---

## Field mapping

Do not hard-code field names such as `Expression`, `Kanji`, `Word`, etc.

The user must be able to choose the Note fields used by a template.

Example:

```text
Template: Kanji handwriting practice

Kanji source field:
[ Expression ▼ ]

Reading field (optional):
[ Reading ▼ ]

Meaning field (optional):
[ Meaning ▼ ]
```

If a selected field contains a word such as:

```text
勉強する
```

the Kanji worksheet pipeline should be able to extract the supported Kanji characters:

```text
勉
強
```

and generate handwriting practice content for them.

The extraction behavior must be compatible with the existing/planned Kanji/Hanzi stroke-diagram provider architecture instead of creating a second unrelated stroke-data implementation.

---

## Template 1 — Kanji handwriting practice

Research and design a printable Kanji practice sheet inspired by standard Japanese handwriting / school practice sheets.

Each Kanji block should support a configurable combination of:

- Large reference Kanji.
- Stroke-order diagram.
- Faint/tracing Kanji.
- Empty practice squares.
- Grid styles such as plain square / cross guidelines / Japanese manuscript-style guides.
- Reading if mapped.
- Meaning if mapped.
- Source vocabulary if useful.

Possible structure:

```text
漢字      Stroke order        Trace       Practice

勉        [stroke diagram]     勉          □ □ □ □ □

Reading: べん
Meaning: diligence / study
```

Or compact multi-row mode suitable for printing many characters per page.

### Required research

Research established Kanji handwriting worksheet patterns before fixing the layout, including:

- Number and size of practice boxes.
- Use of center/cross guide lines.
- Trace-first -> copy -> blank progression.
- Placement of stroke-order diagrams.
- A4 print readability.
- Appropriate margins for home/school printers.

Do not simply render the existing web card UI into PDF.

---

## Template 2 — Vocabulary / word writing table

Provide a generic worksheet for writing words repeatedly.

The user chooses one or more Deck fields as table columns.

Example configuration:

```text
Column 1: Vocabulary
Column 2: Reading
Column 3: Meaning
Column 4: Writing area
```

Example output:

```text
| Word | Reading | Meaning | Practice                     |
|------|---------|---------|------------------------------|
| 勉強 | べんきょう | study   | ____________________________ |
| 学校 | がっこう   | school  | ____________________________ |
```

Support templates such as:

- Word + blank writing area.
- Word + reading + blank writing area.
- Reading/meaning prompt with hidden word for recall practice.
- Multiple repeated writing boxes.

The user should be able to decide which Note field is used for each visible column.

---

## Template 3 — Generic field-based worksheet

Create an extensible generic template where the user can select fields from the Deck's Note Types.

Possible options:

```text
Visible columns:
[x] Expression
[x] Reading
[x] Meaning
[ ] Example

Practice column:
[x] Blank writing area

Rows per page:
[ 10 ]
```

Research whether this should be implemented as:

```text
WorksheetTemplate
  + field mappings
  + layout config
```

rather than separate hard-coded PDF functions for every new worksheet.

---

## Decks containing multiple Note Types

A Deck may contain notes from different Note Types with different schemas.

The UI must handle this explicitly.

Research one of these approaches:

1. User selects a Note Type first, then maps its fields.
2. Show compatible/common fields across selected notes.
3. Allow separate mappings per Note Type.

Do not silently assume every note in a Deck has identical fields.

---

## Selecting content

Allow the user to choose what is included in the generated worksheet.

Potential options:

- Entire Deck.
- Current subdeck.
- Selected notes/cards.
- First N items.
- Random N items.
- Filter by tags.

For large Decks, do not attempt to render thousands of rows in the browser without limits or pagination safeguards.

---

## PDF page configuration

At minimum support:

- A4 portrait.
- A4 landscape where appropriate.
- Configurable page margins.
- Page number optional.
- Worksheet title.
- Deck name optional.
- User-defined title optional.
- Date optional.

Research whether additional paper formats are worth supporting later, but A4 should be the initial default because the primary target is printable study material.

---

## Preview

Before generating/downloading the final PDF, provide a preview or sufficiently accurate page preview.

The user should be able to see:

- Selected template.
- Field mapping.
- Approximate page layout.
- Number of generated pages.

Changing settings should not require generating a permanent stored file each time.

---

## Architecture research

Research whether PDF generation should happen:

### Option A — server-side

```text
Frontend config
 -> API
 -> worksheet renderer
 -> PDF
```

Advantages to evaluate:

- Deterministic rendering.
- Better font control.
- Easier reuse from other clients/MCP later.
- Avoid browser differences.

### Option B — client-side

Evaluate browser PDF libraries only if they can reliably handle:

- Japanese/CJK fonts.
- SVG stroke diagrams.
- Page breaks.
- Printable layout.
- Large Decks.

The task should make an explicit technical decision after research instead of choosing a library only because it is easy to install.

---

## CJK fonts

PDF output must render Japanese/Chinese characters correctly.

Research:

- Font embedding/subsetting.
- Licensing of the selected font.
- File-size impact.
- Fallback behavior for unsupported characters.

Do not rely on the user's local OS fonts for generated server-side PDFs.

---

## Kanji stroke diagrams

For Kanji handwriting templates, reuse the planned Flama stroke-data abstraction where possible.

Expected conceptual dependency:

```text
Deck PDF Worksheet Generator
        |
        -> Kanji/Hanzi Stroke Diagram Pipeline
```

Avoid fetching arbitrary third-party images during PDF rendering.

Stroke assets should be deterministic, sanitized and reusable/cached.

The locale distinction from the stroke task (`ja`, `zh-CN`, `zh-TW`) must be respected if this feature later supports Hanzi worksheets.

---

## Suggested template model

Research a model similar to:

```text
WorksheetTemplate
- id
- name
- type
- supported_content
- page_layout
- field_slots
- options_schema

WorksheetGenerationRequest
- deck_id
- note_type_id
- template_id
- field_mapping
- item_selection
- layout_options
- locale
```

Example field mapping:

```json
{
  "kanji": "Expression",
  "reading": "Reading",
  "meaning": "Meaning"
}
```

Do not store raw PDF-specific coordinates inside user Deck data.

---

## Initial template catalog

Design at least these first-party templates:

1. **Kanji Stroke Practice**
   - Reference Kanji.
   - Stroke order.
   - Trace boxes.
   - Blank practice boxes.

2. **Kanji Compact Practice**
   - Multiple Kanji per page.
   - Smaller stroke diagram.
   - More writing boxes.

3. **Vocabulary Writing Practice**
   - Configurable Word / Reading / Meaning columns.
   - Writing area.

4. **Recall Worksheet**
   - Show reading/meaning as prompt.
   - Hide target word/Kanji.
   - Blank answer area.

5. **Generic Deck Table**
   - User-selected fields as columns.
   - Suitable for printing reference lists or exercises.

Research additional useful worksheet formats before implementation, but keep the initial system small and extensible.

---

## UI/UX

The generator UI should not expose PDF implementation details.

Prefer a wizard/configurator:

```text
1. Chọn mẫu
2. Chọn dữ liệu/field
3. Tùy chỉnh bố cục
4. Xem trước
5. Xuất PDF
```

For each template, explain briefly what it is intended for.

Example:

```text
Kanji Stroke Practice
Luyện viết Kanji theo thứ tự nét với ô tô chữ và ô viết trống.
```

---

## Error handling

Handle explicitly:

- Field does not exist anymore.
- Empty field values.
- Unsupported Kanji/Hanzi.
- No supported characters extracted from selected field.
- Missing stroke data.
- Mixed Note Types.
- Deck with no notes.
- PDF generation failure.
- Excessive generation size.

For unsupported stroke characters, the system should define graceful fallback behavior rather than failing the entire PDF.

---

## Security and limits

- Validate Deck access/ownership/installation permissions before reading notes for PDF generation.
- Do not allow arbitrary HTML/CSS injection through field values or template configuration.
- Sanitize rendered rich text.
- Apply reasonable limits to note count / page count / generation jobs.
- Do not expose private Deck data through publicly guessable PDF URLs.
- If generated PDFs are temporarily stored, define expiration and access control.

---

## Testing

Add tests for:

- Field mapping.
- Mixed Note Types.
- Kanji extraction from strings such as `勉強する`.
- Unsupported characters.
- Stroke asset rendering.
- Japanese font rendering.
- Pagination and page breaks.
- A4 portrait/landscape layouts.
- Empty Deck.
- Large Deck limits.
- Access control.
- Deterministic generation for the same input/config.

Where possible, test the generated document structure or rendered output deterministically rather than only checking that a PDF file exists.

---

## Acceptance criteria

- User can start PDF worksheet generation from a Deck.
- User can select a worksheet template.
- User can map Note fields to template inputs.
- Kanji template can extract Kanji from the selected field and render stroke-order practice content where data exists.
- Vocabulary templates support user-selected columns/fields.
- At least the initial first-party templates are available.
- Output is printable A4 PDF with correct Japanese/CJK rendering.
- User can preview/configure before final generation.
- Mixed Note Types and unsupported characters are handled safely.
- PDF generation is reusable/extensible for future worksheet templates.
- Tests cover field mapping, rendering, pagination and permission boundaries.

## Dependency / related task

Coordinate this task with the existing Kanji/Hanzi stroke diagram pipeline task. Do not create a duplicate stroke-data implementation specifically for PDF generation.
