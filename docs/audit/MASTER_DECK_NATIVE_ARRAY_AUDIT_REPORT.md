# Master Deck Native Array & Template Audit Report

**Report Version**: 1.0.0  
**Generated Timestamp**: `2026-10-23T14:32:16.776135+00:00`  
**Target Database**: MySQL 8.0.40 (`nihongo` database, localhost:3306)  
**Audit Execution Mode**: `STRICT_READ_ONLY` (Zero Database Mutations)  
**Total System Decks**: 5,577  
**Active Decks with Notes**: 1,544 (100.00% Coverage)  
**Empty Structural / Clone Decks**: 4,033  
**Total Active Notes Scanned**: 41,544  
**NoteTypes Audited**: 38  
**Card Templates Audited**: 39 (38 Active Study Applications)  
**Core Architectural Policy**: Flama Native Array Policy (`AGENTS.md`), No Anki Export, Overlay-Only Clones  

---

## Table of Contents

1. [Executive Summary & Global Dataset Metrics](#1-executive-summary--global-dataset-metrics)
2. [5-Tier Master Deck Health Matrix & Distribution](#2-5-tier-master-deck-health-matrix--distribution)
3. [Deep-Dive Audit Findings](#3-deep-dive-audit-findings)
4. [Master Deck Inventory & Evidence Index](#4-master-deck-inventory--evidence-index)
5. [Concrete 3-Phase Zero-Data-Loss Upgrade Roadmap](#5-concrete-3-phase-zero-data-loss-upgrade-roadmap)
6. [Audit Verification & Read-Only Integrity Attestation](#6-audit-verification--read-only-integrity-attestation)

---

## 1. Executive Summary & Global Dataset Metrics

### 1.1 Audit Scope & Dataset Reconciliation
This master report delivers an exhaustive, evidence-backed evaluation of the Flama production database across 100% of its decks, notes, note types, and card templates. The audit was conducted strictly off offline JSON manifests produced by read-only extraction engines (R1 Multi-Value & Delimiters, R2 Presentation Templates, and R3 Semantic Integrity & Schema Drift).

Under Flama's architecture, educational content transitions to a **Native Array model** (`notes.field_values_by_id` using codec `field-id.v1`). The platform operates on a strict **No Anki Export** rule, meaning notes imported from legacy flat-text sources can be safely split and structured into native JSON arrays without backwards compatibility constraints with Anki's single-line limits.

### 1.2 Global Metrics Summary Table

| Global Metric                            | Value   | % of Active Scope | Description / Provenance                                              |
| :--------------------------------------- | ------: | ----------------: | :-------------------------------------------------------------------- |
| Total System Decks                       |   5,577 |                 — | Total rows in MySQL `decks` table                                     |
| Active Decks with Notes                  |   1,544 |           100.00% | Decks containing $\ge 1$ note                                         |
| Empty Structural / Clone Decks           |   4,033 |                 — | Tree folders & marketplace clone overlays ($notes = 0$)               |
| Total Active Notes                       |  41,544 |           100.00% | Total rows in MySQL `notes` table                                     |
| NoteTypes Audited                        |      38 |           100.00% | Distinct note types in active use                                     |
| Card Templates Audited                   |      39 |           100.00% | Distinct card templates across all study applications                 |
| Active Study Applications                |      38 |           100.00% | Active template attachments to note types                             |
| Incompatible Templates                   |      14 |            35.90% | Templates with unclosed tags, flat string coercion, or no array loops |
| Decks Impacted by Incompatible Templates |      34 |             2.20% | Active decks attached to incompatible templates                       |
| Notes Impacted by Incompatible Templates |     321 |             0.77% | Cards failing to render properly in study runner                      |
| Decks with Fake 1-Element Arrays         |     675 |            43.72% | Array fields stored as single delimited strings (`["a; b"]`)          |
| Notes with Fake 1-Element Arrays         |   2,112 |             5.08% | Notes requiring bracket-shielded array splitting                      |
| Decks with Raw Scalar Delimiters         |   1,533 |            99.29% | Plain text fields containing punctuation separators                   |
| Total Raw Delimiter Fields Detected      | 209,972 |                 — | Punctuation/delimiter instances across all fields                     |
| Semantic Anomaly Instances               |   1,130 |                 — | Total linguistic inversion defect instances                           |
| Notes Affected by Semantic Anomalies     |     972 |             2.34% | Notes with inverted readings, Hanviet, or words                       |
| Decks Affected by Semantic Anomalies     |     195 |            12.63% | Decks containing semantic anomalies                                   |
| Schema Extras Overflow Notes             |       4 |             0.01% | Notes with data leaking into `field_values_extras`                    |
| Decks with Schema Extras Overflow        |       2 |             0.13% | Decks 6857 & 6858                                                     |
| Unmapped FieldDef Keys                   |       0 |             0.00% | 100% field definition schema alignment across 41,544 notes            |

### 1.3 Executive Remediation Matrix

| Remediation Phase                      | Target Scope                 | Active Decks | Active Notes | Risk Level   | Primary Action                                                         |
| :------------------------------------- | :--------------------------- | -----------: | -----------: | :----------- | :--------------------------------------------------------------------- |
| **Phase 1: Template Modernization**    | 14 Incompatible Templates    |           34 |          321 | Zero DB Risk | Deploy drop-in HTML/CSS/Mustache template updates (zero DB write)      |
| **Phase 2: Array Field Normalization** | Fake 1-Element Arrays        |          675 |        2,112 | Medium       | Run transactional bracket-shielded array splitting with rollback guard |
| **Phase 3: Semantic Curation**         | Extras Overflow & Inversions |          195 |          972 | Low          | Remap extras fields in 6857/6858 + script-assisted dictionary curation |
| **Optional Normalization**             | Pure Scalar Text Delimiters  |          741 |       26,300 | Very Low     | Cosmetic punctuation cleanup or leave as narrative prose               |
| **No Action Required**                 | Pristine Active + Structural |        4,036 |            6 | None         | 100% compliant with Flama production standards                         |

---

## 2. 5-Tier Master Deck Health Matrix & Distribution

### 2.1 Canonical Severity Priority Cascade (Model 1 — MECE)
Standalone component audits reveal that 229 decks exhibit multiple concurrent defect types (e.g., decks with both fake arrays and semantic inversions). To establish an actionable triage hierarchy, Model 1 classifies every deck according to its **highest operational severity**:

$$\text{Critical Template/Schema Failure (Tier 4)} > \text{Semantic Inversions (Tier 3)} > \text{Fake Arrays (Tier 2)} > \text{Scalar Delimiters (Tier 1)} > \text{Pristine (Tier 0)}$$

This ensures that every deck is assigned to exactly one tier ($\sum_{i=0}^4 |T_i| = 1,544$ active decks).

| Health Tier | Classification Description            | Active Decks | % Decks     | Total Notes | % Notes     | Primary Remediation Action                        |
| :---------- | :------------------------------------ | -----------: | ----------: | ----------: | ----------: | :------------------------------------------------ |
| **Tier 4**  | Critical / Structural Incompatibility |           36 |       2.33% |         325 |       0.78% | Phase 1 Template drop-ins & Phase 3 extras repair |
| **Tier 3**  | Semantic & Linguistic Inversions      |          189 |      12.24% |       5,518 |      13.28% | Phase 3 field relocation & linguistic curation    |
| **Tier 2**  | Fake 1-Element Arrays                 |          575 |      37.24% |       9,395 |      22.61% | Phase 2 bracket-shielded native array splitting   |
| **Tier 1**  | Minor Formatting / Scalar Delimiters  |          741 |      47.99% |      26,300 |      63.31% | Cosmetic delimiter normalization (optional)       |
| **Tier 0**  | Pristine Active Decks                 |            3 |       0.19% |           6 |       0.01% | Fully compliant; zero migration required          |
| **Tier 0**  | Empty Structural / Clone Decks        |        4,033 |           — |           0 |       0.00% | Category folders & marketplace clone overlays     |
| **Total**   | **All Active Decks ($\sum T_i$)**     |        1,544 | **100.00%** |      41,544 | **100.00%** | **Strict MECE Disjoint Partition**                |
| **Total**   | **All System Decks**                  |        5,577 |           — |      41,544 |           — | **Complete Database Inventory**                   |

### 2.2 Alternative Structural Array Priority Cascade (Model 2)
Model 2 evaluates an alternative migration strategy where **Native Array data migration** is prioritized directly below Tier 4, treating all 675 fake-array decks as a single unfragmented cohort (including the 100 decks that also exhibit semantic anomalies):

| Tier (Model 2) | Cohort Description                    | Active Decks | Active Notes | Rationale / Difference vs Model 1                                              |
| :------------- | :------------------------------------ | -----------: | -----------: | :----------------------------------------------------------------------------- |
| **Tier 4**     | Critical / Structural Incompatibility |           36 |          325 | Identical to Model 1 (34 incompatible templates + 2 extras overflow)           |
| **Tier 2**     | All Fake 1-Element Arrays             |          675 |       10,542 | Consolidates all 675 fake-array decks for single-wave array migration          |
| **Tier 3**     | Semantic-Only Inversions              |           89 |        4,371 | Decks with semantic anomalies that do NOT contain fake arrays (189 - 100 = 89) |
| **Tier 1**     | Minor Scalar Delimiters               |          741 |       26,300 | Identical to Model 1 (scalar-only punctuation)                                 |
| **Tier 0**     | Pristine Active Decks                 |            3 |            6 | Identical to Model 1 (Decks 347, 4564, 6860)                                   |
| **Tier 0**     | Empty Structural / Clone Decks        |        4,033 |            0 | Identical to Model 1 (Category tree and clone overlay containers)              |
| **Total**      | **All Active Decks**                  |        1,544 |       41,544 | **Strict MECE Property Preserved**                                             |

### 2.3 Non-MECE Issue Footprint Matrix
The raw distribution of each defect across the active deck dataset prior to MECE cascade resolution:

| Issue Condition                  | Total Decks | % of 1,544 Scope | Standalone Manifest Source  | Operational Impact                                        |
| :------------------------------- | ----------: | ---------------: | :-------------------------- | :-------------------------------------------------------- |
| Incompatible Card Template       |          34 |            2.20% | R2 Template Manifest        | Cards fail to render safely or overflow screen            |
| Schema Extras Overflow           |           2 |            0.13% | R3 Semantic Manifest        | Data leaks into `field_values_extras`, unindexed          |
| Semantic Anomaly (Any Category)  |         195 |           12.63% | R3 Semantic Manifest        | Linguistic inversion, audio TTS failure, mining error     |
| Fake 1-Element Array             |         675 |           43.72% | R1 Multi-Value Manifest     | Badge/pill list rendering collapses into single text blob |
| Raw Scalar Delimiters            |       1,533 |           99.29% | R1 Multi-Value Manifest     | Punctuation artifacts in plain text fields                |
| R1 Isolated Zero-Delimiter Decks |           9 |            0.58% | R1 Multi-Value Manifest     | 6 decks disqualified by template/extras defects           |
| True Multi-Engine Pristine Decks |           3 |            0.19% | Multi-Manifest Intersection | 100% compliant across R1, R2, and R3 audits               |

### 2.4 Health Tier Definitions & Triage Criteria
- **Tier 4 (Critical / Structural Incompatibility)**: Decks bound to card templates with broken HTML markup (unclosed tags causing DOM tree corruption), rigid `100vh` viewport overflow on mobile devices, flat string coercion of array variables, or decks with data leaking into `field_values_extras`. These decks fail study runner rendering and require immediate Phase 1 template replacement and Phase 3 schema remapping.
- **Tier 3 (Semantic & Linguistic Inversions)**: Decks with structurally compatible templates, but whose content has suffered linguistic inversion during Anki/text import (Kanji or Katakana stored in `hanviet`, Vietnamese meanings or placeholders stored in `reading`, Latin acronyms stored in Japanese `word`). These corrupt TTS audio, Yomitan mining, and search queries.
- **Tier 2 (Fake 1-Element Arrays)**: Decks where multi-value fields (meanings, examples, collocations, readings) are declared as arrays but stored as single-element strings containing raw delimiters (`["item1; item2"]`). They require Phase 2 bracket-shielded splitting into valid JSON arrays `["item1", "item2"]`.
- **Tier 1 (Minor Formatting & Scalar Delimiters)**: Decks whose scalar text fields contain punctuation marks (`;`, `$`, `、`, `/`, `
`, `①`). Rendering is completely functional; normalization is optional.
- **Tier 0 (Pristine Active & Structural Decks)**: Decks with 0 defects across all audit dimensions (Decks 347, 4564, 6860), plus the 4,033 structural tree and marketplace clone containers.

### 2.5 Structural & Marketplace Clone Decks Architecture (The 4,033 Decks)
A critical finding of this audit is reconciling why 4,033 of the 5,577 total decks in MySQL contain zero direct notes:
1. **Hierarchical Tree Nodes (~2,150 decks)**: In Flama, top-level decks (e.g. `JLPT N1`, `Minna no Nihongo`, `Kanji Look and Learn`) serve exclusively as organizational categories. Cards belong strictly to child lesson decks.
2. **Marketplace Clone Overlays (~1,680 decks)**: Under Flama's `DeckInstall` overlay architecture (`CLONE_CUTOVER_REPORT.md`), installing a shared deck creates a container record. Cards are **never duplicated**; study reviews and edits point to source note IDs via overlay delta tables.
3. **Draft / Empty Shells (~203 decks)**: User-created decks that have not yet had cards imported.

All 4,033 decks are structurally clean and require zero database migration.

---

## 3. Deep-Dive Audit Findings

### 3.1 R1 Multi-Value & Delimiter Audit Findings
The R1 audit engine analyzed 41,544 notes and identified **209,972 raw delimiter instances** across scalar text and array fields. The table below provides the full breakdown by delimiter character class:

| Delimiter Name    | Symbol | Instances in Fake Arrays | Instances in Scalar Fields | Primary Field Context                     |
| :---------------- | :----: | -----------------------: | -------------------------: | :---------------------------------------- |
| Ascii Comma       |   ,    |                       28 |                          0 | `tags`, `synonym_list`                    |
| Circled Number    |  ①-⑳   |                        0 |                        670 | `definition_senses`, `numbered_examples`  |
| Dollar            |   $    |                        3 |                     57,769 | `reading`, `furigana`, `audio_markers`    |
| Japanese Comma    |   、    |                       95 |                     52,124 | `onyomi`, `kunyomi`, `compounds`, `notes` |
| Middle Dot        |   ・    |                        4 |                      4,235 | `kana_reading`, `sub_definitions`         |
| Newline           |   \n   |                        0 |                        740 | `explanation`, `story`, `usage`           |
| Relational Marker |   →    |                        1 |                        102 | `antonym`, `cross_reference`              |
| Semicolon         |   ;    |                      761 |                     66,772 | `example_jp`, `meaning_vi`, `notes`       |
| Slash             |   /    |                    1,247 |                     27,560 | `translation_vi`, `synonyms`, `reading`   |

#### The Fake 1-Element Array Phenomenon
In 675 decks (2,112 notes), fields declared as `array` in `FieldDef` contain a single string encapsulating multiple sub-values (e.g. `['tạo sân chơi/tạo nơi']` or `['① A; ② B']`). Because Chevron and Mustache treat a 1-element list as a single iteration step, badge loops render the entire raw string with all punctuation inside a single unwieldy pill, completely defeating the purpose of structured UI badges.

### 3.2 R2 Presentation Template Compatibility Audit Findings
The R2 audit engine tokenized and validated all 39 card templates against AST requirements. Out of 39 templates, **13 are Fully Compatible**, **12 are Partially Compatible**, and **14 are Incompatible**. The 14 incompatible templates affect **34 active decks** holding **321 notes**.

| Template Name                | Template ID   | Compatibility    | Dot Loop | Array Script | Decks | Notes  |
| :--------------------------- | :------------ | :--------------: | :------: | :----------: | ----: | -----: |
| Default Flama Flashcard      | `24646a7b...` |       FULL       |    ✓     |      ✓       |     0 |      0 |
| Default Flama Flashcard      | `28634386...` |       FULL       |    ✓     |      ✓       |     0 |      0 |
| Default Flama Flashcard      | `7e8daff8...` |       FULL       |    ✓     |      ✓       |     0 |      0 |
| Default Flama Flashcard      | `d4c6aaa3...` |       FULL       |    ✓     |      ✓       |     0 |      0 |
| Default Flama Flashcard      | `d941ec64...` |       FULL       |    ✓     |      ✓       |     0 |      0 |
| Default Flama Flashcard      | `ebf594ca...` |       FULL       |    ✓     |      ✓       |     1 |      1 |
| Default Flama Flashcard      | `f4b9d2cd...` |       FULL       |    ✓     |      ✓       |     0 |      0 |
| Default Flama Flashcard      | `f864d4ff...` |       FULL       |    ✓     |      ✓       |     0 |      0 |
| Gõ chép chính tả             | `fc011484...` |       FULL       |    ✓     |      ✓       |     1 |      6 |
| Gõ cách đọc                  | `5c460ccb...` |       FULL       |    ✓     |      ✓       |     1 |      2 |
| Gõ nghĩa                     | `ef8757fb...` |       FULL       |    ✓     |      ✓       |     1 |      2 |
| Gõ từ qua ảnh                | `633d3b27...` |       FULL       |    ✓     |      ✓       |     1 |      2 |
| Gõ đáp án (JS)               | `a37a3daa...` |       FULL       |    ✓     |      ✓       |     1 |      2 |
| Card 1                       | `4f184341...` | **INCOMPATIBLE** |    ✗     |      ✗       |     6 |     68 |
| Card 1                       | `55c18e42...` | **INCOMPATIBLE** |    ✗     |      ✗       |     2 |      3 |
| Default Quiz Flashcard       | `76efe654...` | **INCOMPATIBLE** |    ✗     |      ✗       |     1 |      8 |
| Front                        | `0d62d4a3...` | **INCOMPATIBLE** |    ✗     |      ✗       |     1 |     10 |
| Grammar & Literary Quotes... | `0a86851a...` | **INCOMPATIBLE** |    ✗     |      ✗       |    19 |     92 |
| Grammar Card                 | `9379dde5...` | **INCOMPATIBLE** |    ✗     |      ✗       |     0 |      0 |
| Sentence                     | `36aad069...` | **INCOMPATIBLE** |    ✗     |      ✗       |     1 |      1 |
| Thẻ 1                        | `266cbc84...` | **INCOMPATIBLE** |    ✗     |      ✗       |     4 |    139 |
| Thẻ 1                        | `273a92a1...` | **INCOMPATIBLE** |    ✗     |      ✗       |     0 |      0 |
| Thẻ 1                        | `48a17d92...` | **INCOMPATIBLE** |    ✗     |      ✗       |     0 |      0 |
| Thẻ 1                        | `c51dc3ba...` | **INCOMPATIBLE** |    ✗     |      ✗       |     0 |      0 |
| Thẻ 1                        | `d81c0a0a...` | **INCOMPATIBLE** |    ✗     |      ✗       |     0 |      0 |
| Thẻ Kanji tối giản           | `62daa743...` | **INCOMPATIBLE** |    ✗     |      ✗       |     0 |      0 |
| Thẻ Kanji tối giản           | `a7f1a1cd...` | **INCOMPATIBLE** |    ✗     |      ✗       |     0 |      0 |
| Advanced Vocabulary Card     | `f6d63262...` |     PARTIAL      |    ✓     |      ✓       |   143 |  4,125 |
| Card 1                       | `21a53f7b...` |     PARTIAL      |    ✓     |      ✓       |    13 |    790 |
| Default Flama Flashcard      | `187b3d10...` |     PARTIAL      |    ✓     |      ✓       |     0 |      0 |
| Default Flama Flashcard      | `6ebcb224...` |     PARTIAL      |    ✓     |      ✓       |     0 |      0 |
| Default Flama Flashcard      | `cad0cda8...` |     PARTIAL      |    ✓     |      ✓       |     0 |      0 |
| Default Flama Flashcard      | `e0cb18b2...` |     PARTIAL      |    ✓     |      ✓       | 1,305 | 35,114 |
| Default Flama Flashcard      | `ebf68caa...` |     PARTIAL      |    ✓     |      ✓       |     0 |      0 |
| Thẻ 1                        | `0ff348a2...` |     PARTIAL      |    ✓     |      ✓       |    43 |  1,179 |
| Thẻ 1                        | `79583825...` |     PARTIAL      |    ✓     |      ✓       |     0 |      0 |
| Thẻ 1                        | `d59eaec9...` |     PARTIAL      |    ✓     |      ✓       |     0 |      0 |
| Thẻ 1                        | `e38dd9f6...` |     PARTIAL      |    ✓     |      ✓       |     0 |      0 |
| Thẻ 1                        | `f0584f68...` |     PARTIAL      |    ✓     |      ✓       |     0 |      0 |

#### Root Causes of Template Incompatibility
1. **Absence of Mustache Dot Iteration**: Using flat `{{Field}}` instead of `{{#Field}}<tag>{{.}}</tag>{{/Field}}`.
2. **Flat String Coercion**: Passing native JSON arrays directly into Mustache, resulting in `String(array)` comma-separated dumps.
3. **Missing Client Runtime**: Omitting `flama-native-arrays.v1`, leaving arrays unformatted on the client.
4. **The Grammar Template Unclosed `<div>` Syntax Bug**: Templates `0a86851a`, `266cbc84`, `48a17d92`, `c51dc3ba`, and `d81c0a0a` contain a conditional container nesting bug in their back HTML. An outer layout `<div style='display:flex...'>` is opened inside `{{#name}}` but never closed before `{{/name}}`. Furthermore, an orphan `</div>` exists outside `{{#additional_example}}`. This causes DOM tree corruption, style bleed, and card clipping in 23 active decks (231 notes).

### 3.3 R3 Semantic & Schema Drift Audit Findings
The R3 audit engine scanned all 41,544 notes for linguistic inversions, schema misalignment, and extras overflow. A total of **1,130 semantic anomalies** were identified across **972 notes** in **195 decks**.

| Anomaly Category            | Instances | Notes Affected | Decks Affected | Severity | Representative Sample                                           |
| :-------------------------- | --------: | -------------: | -------------: | :------: | :-------------------------------------------------------------- |
| Kanji in `hanviet`          |       709 |            709 |            169 |   HIGH   | `hanviet='賛 辞 贈'` (Deck 424)                                    |
| Kana in `hanviet`           |       217 |            217 |             24 |  MEDIUM  | `hanviet='ジカン カセぐ'` (Deck 423)                                  |
| Vietnamese in `reading`     |       169 |            169 |             19 |   HIGH   | `reading='Chưa có dữ liệu'` / `'tình hình cục diện'` (Deck 516) |
| Latin Acronym in `word`     |        25 |             25 |              5 |   LOW    | `word='IP-VPN'`, `'WPA2'`, `'Yunyang'` (Deck 1820)              |
| Unparsed Kanji in `reading` |         6 |              6 |              4 |   HIGH   | `reading='じけんを葬る'` (Deck 455)                                   |
| Schema Extras Overflow      |         4 |              4 |              2 | CRITICAL | `extras={'Meaning': '...'}` (Decks 6857 & 6858)                 |
| **Total**                   | **1,130** |        **972** |        **195** |    —     | **Complete Semantic Inventory**                                 |

#### FieldDef Schema Alignment Analysis
Across all 41,544 notes, **zero unmapped FieldDef keys** were detected (`unmapped_fielddef_keys_count == 0`). Every field key in `field_values_by_id` corresponds to a valid `FieldDef.id` in `note_types.fields`.

#### Schema Extras Overflow Forensic Investigation (Decks 6857 & 6858)
Exactly 4 notes have data stored in `notes.field_values_extras` because imported field names did not match FieldDef schemas:
- **Deck 6857** (`Gõ nghĩa`, NoteType `f9912e3a`): Notes `7006c395` and `af292864` have `extras={'Meaning': 'ăn\năn uống'}`. The valid fields are `PromptText` and `Answer` (array); there is no field named `Meaning`.
- **Deck 6858** (`Gõ từ qua ảnh`, NoteType `9e80eb7b`): Notes `4933296b` and `72751cb5` have `extras={'Image': '...', 'Example': '...'}`. The schema specifies `PromptImage` instead of `Image`.

---

## 4. Master Deck Inventory & Evidence Index

### 4.1 Active Deck Inventory Schema & Field Definitions
Every active deck is cataloged with the following attributes:
- **Deck ID**: Numeric primary key in MySQL `decks` table.
- **Deck Name**: User-facing deck title.
- **NoteType Name (ID)**: Associated NoteType name and truncated UUID.
- **Notes**: Total number of cards/notes in deck.
- **Health Tier**: Model 1 Severity Priority Cascade tier (Tiers 4 to 0).
- **Issue Codes**: Standardized issue identifiers (`INCOMPATIBLE_TEMPLATE`, `EXTRAS_OVERFLOW`, `KANJI_IN_HANVIET`, `FAKE_1_ELEM_ARRAY`, `RAW_SCALAR_DELIM`, `PRISTINE`).
- **Representative Evidence Sample**: Verbatim data extract from manifests illustrating the defect.

### Tier 4: Critical & Structurally Incompatible Decks (Complete 36 Decks)

| Deck ID | Deck Name                           | NoteType Name (ID)                   | Notes | Health Tier | Issue Codes                    | Representative Evidence Sample                          |
| ------: | :---------------------------------- | :----------------------------------- | ----: | :---------: | :----------------------------- | :------------------------------------------------------ |
|     174 | Trac Nghiem Co Ban                  | Trắc nghiệm (`94e51bc4...`)          |     8 |    Tier 4   | INCOMPATIBLE_TEMPLATE          | Template missing native array dot loop or has unclos... |
|     348 | test                                | JapTest (`33fbb358...`)              |     1 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|     350 | D1                                  | JapTest (`33fbb358...`)              |     2 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1399 | Bài 01                              | 文法N1 (`4fc2eb8e...`)                 |     5 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1400 | Bài 02                              | 文法N1 (`4fc2eb8e...`)                 |     5 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1401 | Bài 03                              | 文法N1 (`4fc2eb8e...`)                 |     5 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1402 | Bài 04                              | 文法N1 (`4fc2eb8e...`)                 |     5 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1403 | Bài 05                              | 文法N1 (`4fc2eb8e...`)                 |     5 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1404 | Bài 06                              | 文法N1 (`4fc2eb8e...`)                 |     5 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1405 | Bài 07                              | 文法N1 (`4fc2eb8e...`)                 |     5 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1406 | Bài 08                              | 文法N1 (`4fc2eb8e...`)                 |     5 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1407 | Bài 09                              | 文法N1 (`4fc2eb8e...`)                 |     5 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1408 | Bài 10                              | 文法N1 (`4fc2eb8e...`)                 |     5 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1409 | Bài 11                              | 文法N1 (`4fc2eb8e...`)                 |     5 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1410 | Bài 12                              | 文法N1 (`4fc2eb8e...`)                 |     5 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1411 | Bài 13                              | 文法N1 (`4fc2eb8e...`)                 |     5 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1412 | Bài 14                              | 文法N1 (`4fc2eb8e...`)                 |     5 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1413 | Bài 15                              | 文法N1 (`4fc2eb8e...`)                 |     5 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1414 | Bài 16                              | 文法N1 (`4fc2eb8e...`)                 |     5 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1415 | Bài 17                              | 文法N1 (`4fc2eb8e...`)                 |     5 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1416 | Bài 18                              | 文法N1 (`4fc2eb8e...`)                 |     5 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    1820 | D1                                  | TechKeyword (`f2b1d212...`)          |    13 |    Tier 4   | INCOMPATIBLE_TEMPLATE, LATI... | Template missing native array dot loop or has unclos... |
|    4568 | Unit 1                              | 文法N1 (`35cef59f...`)                 |    31 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    4569 | Unit 2                              | 文法N1 (`35cef59f...`)                 |    70 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    4570 | Unit 3                              | 文法N1 (`35cef59f...`)                 |    22 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    4571 | Unit 4                              | 文法N1 (`35cef59f...`)                 |    16 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    6138 | D2                                  | TechKeyword (`f2b1d212...`)          |    19 |    Tier 4   | INCOMPATIBLE_TEMPLATE, LATI... | Template missing native array dot loop or has unclos... |
|    6139 | D3                                  | TechKeyword (`f2b1d212...`)          |    11 |    Tier 4   | INCOMPATIBLE_TEMPLATE, LATI... | Template missing native array dot loop or has unclos... |
|    6140 | D4                                  | TechKeyword (`f2b1d212...`)          |     3 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    6141 | D5                                  | TechKeyword (`f2b1d212...`)          |     3 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    6193 | D6                                  | TechKeyword (`f2b1d212...`)          |    19 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    6857 | 4. Luyện gõ - Gõ nghĩa (Meaning)    | Gõ nghĩa (`f9912e3a...`)             |     2 |    Tier 4   | EXTRAS_OVERFLOW                | extras=['Meaning']                                      |
|    6858 | 5. Luyện gõ - Gõ từ qua ảnh (Image) | Gõ từ qua ảnh (`9e80eb7b...`)        |     2 |    Tier 4   | EXTRAS_OVERFLOW                | extras=['Image', 'Example', 'Explanation', 'ExampleT... |
|    6861 | 8. 文法N1 (Grammar & Quotes)          | 文法N1 (`4fc2eb8e...`)                 |     2 |    Tier 4   | INCOMPATIBLE_TEMPLATE, RAW_... | Template missing native array dot loop or has unclos... |
|    6863 | Sentences                           | Sentence Card (`c1cef8d4...`)        |     1 |    Tier 4   | INCOMPATIBLE_TEMPLATE, LATI... | Template missing native array dot loop or has unclos... |
|    6864 | Shortcut probe 387277               | Shortcut probe 387277 (`96474be8.... |    10 |    Tier 4   | INCOMPATIBLE_TEMPLATE          | Template missing native array dot loop or has unclos... |

### Tier 3: Semantic & Linguistic Inversion Decks (189 Decks)

| Deck ID | Deck Name                    | NoteType Name (ID)                   | Notes | Health Tier | Issue Codes                    | Representative Evidence Sample |
| ------: | :--------------------------- | :----------------------------------- | ----: | :---------: | :----------------------------- | :----------------------------- |
|     423 | Bài 008                      | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 3   | KANA_IN_HANVIET, RAW_SCALAR... | hanviet=''                     |
|     424 | Bài 009                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     425 | Bài 010                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     434 | Bài 019                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     435 | Bài 020                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     436 | Bài 021                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     437 | Bài 022                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     438 | Bài 023                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|     439 | Bài 024                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|     440 | Bài 025                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     441 | Bài 026                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     444 | Bài 029                      | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|     446 | Bài 031                      | Flama Standard Vocabulary (`e2f31... |    58 |    Tier 3   | KANA_IN_HANVIET, RAW_SCALAR... | hanviet=''                     |
|     447 | Bài 032                      | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 3   | KANA_IN_HANVIET, RAW_SCALAR... | hanviet=''                     |
|     455 | Bài 040                      | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 3   | UNPARSED_KANJI_IN_READING, ... | reading=''                     |
|     459 | Bài 044                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     463 | Bài 048                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     464 | Bài 049                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     468 | Bài 053                      | Flama Standard Vocabulary (`e2f31... |    58 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     473 | Bài 058                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | VIETNAMESE_IN_READING, FAKE... | reading=''                     |
|     477 | Bài 062                      | Flama Standard Vocabulary (`e2f31... |    58 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     488 | Bài 073                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     489 | Bài 074                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     491 | Bài 076                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     493 | Bài 078                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     496 | Bài 081                      | Flama Standard Vocabulary (`e2f31... |    58 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     497 | Bài 082                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     498 | Bài 083                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     499 | Bài 084                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     500 | Bài 085                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     501 | Bài 086                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     503 | Bài 088                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     506 | Bài 091                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, VIETNAMES... | hanviet=''                     |
|     508 | Bài 093                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     510 | Bài 095                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     511 | Bài 096                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     512 | Bài 097                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | UNPARSED_KANJI_IN_READING, ... | reading=''                     |
|     516 | Bài 101                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | VIETNAMESE_IN_READING, RAW_... | reading=''                     |
|     517 | Bài 102                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     518 | Bài 103                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, VIETNAMES... | hanviet=''                     |
|     520 | Bài 105                      | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     523 | Bài 108                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     525 | Bài 110                      | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     526 | Bài 111                      | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     527 | Bài 112                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANA_IN_HANVIET, KANJI_IN_H... | hanviet=''                     |
|     528 | Bài 113                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     529 | Bài 114                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     531 | Bài 116                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANA_IN_HANVIET, RAW_SCALAR... | hanviet=''                     |
|     534 | Bài 119                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     535 | Bài 120                      | Flama Standard Vocabulary (`e2f31... |    58 |    Tier 3   | KANA_IN_HANVIET, RAW_SCALAR... | hanviet=''                     |
|     536 | Bài 121                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANA_IN_HANVIET, VIETNAMESE... | hanviet=''                     |
|     540 | Bài 125                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANA_IN_HANVIET, RAW_SCALAR... | hanviet=''                     |
|     542 | Bài 127                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANA_IN_HANVIET, RAW_SCALAR... | hanviet=''                     |
|     543 | Bài 128                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     544 | Bài 129                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     545 | Bài 130                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     548 | Bài 133                      | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     549 | Bài 134                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     550 | Bài 135                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANA_IN_HANVIET, RAW_SCALAR... | hanviet=''                     |
|     551 | Bài 136                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANA_IN_HANVIET, KANJI_IN_H... | hanviet=''                     |
|     553 | Bài 138                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANA_IN_HANVIET, KANJI_IN_H... | hanviet=''                     |
|     554 | Bài 139                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|     584 | Bài 169                      | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    1334 | Bài 01                       | Flama Standard Vocabulary (`e2f31... |    25 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    1335 | Bài 02                       | Flama Standard Vocabulary (`e2f31... |    30 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    1336 | Bài 03                       | Flama Standard Vocabulary (`e2f31... |    30 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    1377 | Bài 08                       | Flama Standard Vocabulary (`e2f31... |    51 |    Tier 3   | VIETNAMESE_IN_READING, RAW_... | reading=''                     |
|    1378 | Bài 09                       | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    3213 | KanjiN3                      | Kanji_N3 (`91f567ab...`)             |     1 |    Tier 3   | KANA_IN_HANVIET, VIETNAMESE... | Phiên âm=''                    |
|    3214 | Bài 1                        | Kanji_N3 (`91f567ab...`)             |   266 |    Tier 3   | KANA_IN_HANVIET, KANJI_IN_H... | Phiên âm=''                    |
|    3215 | Bài 10                       | Kanji_N3 (`91f567ab...`)             |    20 |    Tier 3   | KANA_IN_HANVIET, VIETNAMESE... | Phiên âm=''                    |
|    3216 | Bài 2                        | Kanji_N3 (`91f567ab...`)             |    69 |    Tier 3   | KANA_IN_HANVIET, UNPARSED_K... | Phiên âm=''                    |
|    3217 | Bài 3                        | Kanji_N3 (`91f567ab...`)             |    77 |    Tier 3   | KANA_IN_HANVIET, KANJI_IN_H... | Âm Hán Tự=''                   |
|    3218 | Bài 4                        | Kanji_N3 (`91f567ab...`)             |    51 |    Tier 3   | KANA_IN_HANVIET, KANJI_IN_H... | Âm Hán Tự=''                   |
|    3219 | Bài 5                        | Kanji_N3 (`91f567ab...`)             |    39 |    Tier 3   | KANA_IN_HANVIET, KANJI_IN_H... | Phiên âm=''                    |
|    3220 | Bài 6                        | Kanji_N3 (`91f567ab...`)             |    41 |    Tier 3   | KANA_IN_HANVIET, KANJI_IN_H... | Âm Hán Tự=''                   |
|    3221 | Bài 7                        | Kanji_N3 (`91f567ab...`)             |    44 |    Tier 3   | KANA_IN_HANVIET, VIETNAMESE... | Phiên âm=''                    |
|    3222 | Bài 8                        | Kanji_N3 (`91f567ab...`)             |    54 |    Tier 3   | KANA_IN_HANVIET, KANJI_IN_H... | Phiên âm=''                    |
|    3223 | Bài 9                        | Kanji_N3 (`91f567ab...`)             |    40 |    Tier 3   | KANA_IN_HANVIET, KANJI_IN_H... | Phiên âm=''                    |
|    3224 | Đồng nghĩa                   | Kanji_N3 (`91f567ab...`)             |    86 |    Tier 3   | KANA_IN_HANVIET, KANJI_IN_H... | Phiên âm=''                    |
|    3653 | Bài 5                        | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3654 | Bài 6                        | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3655 | Bài 7                        | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    3660 | Bài 12                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    3661 | Bài 13                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3662 | Bài 14                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3663 | Bài 15                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3664 | Bài 16                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3667 | Bài 19                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3669 | Bài 21                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3670 | Bài 22                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3672 | Bài 24                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3674 | Bài 26                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3675 | Bài 27                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3677 | Bài 29                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3679 | Bài 31                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3683 | Bài 1                        | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    3688 | Bài 6                        | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3689 | Bài 7                        | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3690 | Bài 8                        | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3696 | Bài 14                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3697 | Bài 15                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3699 | Bài 17                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3701 | Bài 19                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3702 | Bài 20                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3704 | Bài 22                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3706 | Bài 24                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3708 | Bài 26                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3709 | Bài 27                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3714 | Bài 32                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3715 | Bài 33                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3717 | Bài 35                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3718 | Bài 36                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3719 | Bài 37                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3722 | Bài 40                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3724 | Bài 42                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3726 | Bài 44                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3728 | Bài 46                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3730 | Bài 48                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3732 | Bài 50                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3735 | Bài 53                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3736 | Bài 54                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3771 | Bài 18                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    3773 | Bài 20                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3774 | Bài 21                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3785 | Bài 32                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3787 | Bài 34                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3808 | Bài 55                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3809 | Bài 56                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3819 | Bài 66                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3820 | Bài 67                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    3823 | Bài 70                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3824 | Bài 71                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3841 | Bài 88                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3915 | Bài 7                        | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3916 | Bài 8                        | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3917 | Bài 9                        | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3925 | Bài 17                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    3926 | Bài 18                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3928 | Bài 20                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3929 | Bài 21                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3930 | Bài 22                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3931 | Bài 23                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3932 | Bài 24                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3975 | Bài 67                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    3976 | Bài 68                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4005 | Bài 97                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4006 | Bài 98                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4012 | Bài 1                        | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    4013 | Bài 2                        | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    4014 | Bài 3                        | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    4024 | Bài 13                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4025 | Bài 14                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4026 | Bài 15                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    4031 | Bài 20                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4032 | Bài 21                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4043 | Bài 32                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4059 | Bài 48                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4060 | Bài 49                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4080 | Bài 69                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4081 | Bài 70                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4100 | Bài 89                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4101 | Bài 90                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4102 | Bài 91                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4107 | Bài 96                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4108 | Bài 97                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4115 | Bài 104                      | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4116 | Bài 105                      | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4176 | Bài 4                        | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4177 | Bài 5                        | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4178 | Bài 6                        | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4196 | Bài 24                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4197 | Bài 25                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4221 | Bài 49                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4222 | Bài 50                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4223 | Bài 51                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4234 | Bài 62                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    4235 | Bài 63                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    4236 | Bài 64                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4252 | Bài 80                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4253 | Bài 81                       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | KANJI_IN_HANVIET, FAKE_1_EL... | hanviet=''                     |
|    4254 | Bài 82                       | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    4389 | Bài 42                       | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    4403 | Bài 56                       | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    4431 | Bài 84                       | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    4440 | Bài 93                       | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    4454 | Bài 107                      | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 3   | KANJI_IN_HANVIET, RAW_SCALA... | hanviet=''                     |
|    4559 | Test                         | Flama Standard Vocabulary (`e2f31... |     8 |    Tier 3   | LATIN_IN_WORD, RAW_SCALAR_D... | word=''                        |
|    6855 | 2. Flama Standard Vocabulary | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 3   | VIETNAMESE_IN_READING, FAKE... | reading=''                     |

### Tier 2: Fake 1-Element Array Decks (575 Decks)

| Deck ID | Deck Name                            | NoteType Name (ID)                   | Notes | Health Tier | Issue Codes                    | Representative Evidence Sample                          |
| ------: | :----------------------------------- | :----------------------------------- | ----: | :---------: | :----------------------------- | :------------------------------------------------------ |
|     417 | Bài 002                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: tạo sân chơi/tạo nơi                    |
|     432 | Bài 017                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 負荷を見ながらパラメータを調整します。$打ち合わせの日程を調整してご連         |
|     467 | Bài 052                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | additional_note_vi: Gần nghĩa, 偏り.$Sắc thái, 偏向 thường  |
|     519 | Bài 104                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | reading: ふうしゃ$かざぐるま                                     |
|     539 | Bài 124                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 彼は努力の末、第一志望の試験に受かった。                        |
|     559 | Bài 144                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: まず計画のあらましを説明してから、詳細に入ります。                   |
|     562 | Bài 147                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 彼は飛んできたボールをしっかり受け止めた。$上司の指摘を前向きに受け止         |
|     564 | Bài 149                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 令和元年に入社した社員が、今年で五年目を迎えた。                    |
|     577 | Bài 162                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 裁判では、死刑制度の是非についても議論されました。                   |
|    1338 | Bài 05                               | Flama Standard Vocabulary (`e2f31... |    30 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 学生のうちから、ビジネスメールの書き方を練習しておくといい。              |
|    1341 | Bài 002                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: employ (v): tuyển dụng; employment         |
|    1343 | Bài 004                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: orchestra (n): dàn nhạc; orchestral        |
|    1345 | Bài 006                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: expert (n/adj): chuyên gia; experti        |
|    1347 | Bài 008                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Meaning: đồ nội thất sân vườn, bàn ghế ngoài            |
|    1350 | Bài 011                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: task (n): nhiệm vụ; task (v): giao         |
|    1370 | Bài 01                               | Flama Standard Vocabulary (`e2f31... |    52 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | additional_note_jp: 類語：見渡す、注意する                         |
|    1373 | Bài 04                               | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | meaning_jp: 範囲・エリア                                      |
|    1374 | Bài 05                               | Flama Standard Vocabulary (`e2f31... |    58 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | meaning_vi: Cảm giác bất lực/khó chịu                   |
|    1379 | Bài 10                               | Flama Standard Vocabulary (`e2f31... |    33 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | additional_note_jp: 「生き生き」は幅広く生命感・活気を表す。溌剌は特に若々しく元気な印象が |
|    1383 | Bài 03                               | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | usage_jp: 試験中、焦りは禁物だ                                    |
|    1387 | Bài 07                               | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Nghĩa tình; Mối quan hệ thân thích      |
|    1388 | Bài 08                               | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Đạt đến mức tối đa; Chinh phục          |
|    1392 | Bài 12                               | Flama Standard Vocabulary (`e2f31... |    57 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | additional_note_jp: 憂鬱：U uất, sầu muộn, tâm trạng buồn  |
|    1393 | Bài 13                               | Flama Standard Vocabulary (`e2f31... |    63 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | meaning_vi: ① Ấn, ép thứ gì đó vào bên trong ②          |
|    1421 | Bài 03                               | Flama Standard Vocabulary (`e2f31... |    85 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | meaning_vi: Kiềm chế cơn giận / Hạn chế chi tiê         |
|    1422 | Bài 04                               | Flama Standard Vocabulary (`e2f31... |    84 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | meaning_vi: Sơ đồ tổ chức công ty / Tổ chức côn         |
|    1424 | Bài 06                               | Flama Standard Vocabulary (`e2f31... |    81 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Làm đục; nói tránh                      |
|    1425 | Bài 07                               | Flama Standard Vocabulary (`e2f31... |    84 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Giám sát; huấn luyện viên; đạo diễn     |
|    1426 | Bài 08                               | Flama Standard Vocabulary (`e2f31... |    64 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: プロジェクトはいよいよ佳境に入り、最終調整が続いている。$あなたは、プ         |
|    1427 | Bài 09                               | Flama Standard Vocabulary (`e2f31... |    66 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Cảm khái / Phẫn nộ                      |
|    1428 | Bài 10                               | Flama Standard Vocabulary (`e2f31... |    75 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Làm màu mỡ; bồi dưỡng                   |
|    1429 | Bài 11                               | Flama Standard Vocabulary (`e2f31... |    64 |    Tier 2   | FAKE_1_ELEM_ARRAY              | translation_vi: Cây cung; vĩ đàn                        |
|    1430 | Bài 12                               | Flama Standard Vocabulary (`e2f31... |    52 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Trọng tài; phán xét                     |
|    1431 | Bài 13                               | Flama Standard Vocabulary (`e2f31... |    78 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Nóc nhà; tòa (đếm toà nhà)              |
|    1432 | Bài 14                               | Flama Standard Vocabulary (`e2f31... |    77 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 連日の長時間労働で、チーム全体が疲弊している。                     |
|    1433 | Bài 15                               | Flama Standard Vocabulary (`e2f31... |    82 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Sôi; bùng nổ                            |
|    1435 | Bài 17                               | Flama Standard Vocabulary (`e2f31... |    79 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 厳密に言えば、それは違う。                               |
|    1436 | Bài 18                               | Flama Standard Vocabulary (`e2f31... |    81 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Mũi nhọn tấn công; hướng công kích      |
|    1437 | Bài 19                               | Flama Standard Vocabulary (`e2f31... |    85 |    Tier 2   | FAKE_1_ELEM_ARRAY              | translation_vi: Nghiêm túc; kiếm thật                   |
|    1438 | Bài 20                               | Flama Standard Vocabulary (`e2f31... |   118 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Dính; kiên trì                          |
|    1453 | Bài 1                                | En4Everyone (`6b2a8fec...`)          |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: pad (n): miếng lót; pad (v): đệm; p        |
|    1458 | Bài 6                                | En4Everyone (`6b2a8fec...`)          |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: stair (n): bậc thang; stairs (n): c        |
|    1461 | Bài 1                                | En4Everyone (`6b2a8fec...`)          |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: wait (v): chờ; waiter (n): bồi bàn;        |
|    1464 | Bài 01                               | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: even (adj): đều; evenly (adv): đồng        |
|    1465 | Bài 02                               | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: workaround (n): giải pháp tạm; work        |
|    1467 | Bài 04                               | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: various (adj): đa dạng; vary (v): t        |
|    1468 | Bài 05                               | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Meaning: (IT) cơ chế phân phối dữ liệu ra nh            |
|    1471 | Bài 08                               | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: preserve (v): bảo tồn; preservation        |
|    1477 | 語彙徹底N1                               | Flama Standard Vocabulary (`395e5... |     1 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: hoa anh đào; cây anh đào                |
|    1879 | Bài 17                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: faculty (n.): 教員陣、学部; faculty membe        |
|    1881 | Bài 19                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Meaning: 課す、押しつける                                       |
|    1883 | Bài 21                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: craftspeople (n., plural): 職人たち; cr        |
|    1884 | Bài 22                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Meaning: 全国規模の、全国的な                                     |
|    1888 | Bài 26                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: avid (adj.): 熱心な；avidly (adv.): 熱心に        |
|    1890 | Bài 28                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Meaning: 水をやる、水を飲ませる                                    |
|    1892 | Bài 30                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Meaning: 天蓋、日よけ                                         |
|    1894 | Bài 32                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: travel agency (n.): 旅行会社; itinerary        |
|    2414 | Bài 22                               | En4Everyone (`6b2a8fec...`)          |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: regard (n/v): sự quan tâm, xem là;         |
|    2630 | Bài 06                               | Flama Standard Vocabulary (`e2f31... |     1 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 多少費用がかかっても、安全には代えられない。                      |
|    3319 | Bài 1 Chào bạn                       | Flama Standard Vocabulary (`e2f31... |    17 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 老师，您好！$请问，您是哪位？                             |
|    3327 | Bài 9 Con trai bạn làm việc ở đâu    | Flama Standard Vocabulary (`e2f31... |    13 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: mèo; con mèo                            |
|    3334 | Bài 1 Chào bạn                       | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 你好！$我很渴。$买水果。                               |
|    3337 | Bài 4 Cô ấy là giáo viên tiếng Tr... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: NẢ / NÉ                                        |
|    3338 | Bài 5 Con gái cô ấy năm nay 20 tuổi  | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 你今年多大了？$李老师多大了？$我二十岁了。                      |
|    3342 | Bài 9 Con trai bạn làm việc ở đâu    | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ... đâu rồi? / ... ở đâu? (hỏi vị t     |
|    3346 | Bài 13 Anh ấy đang học nấu món ăn... | Flama Standard Vocabulary (`e2f31... |     8 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: A-lô; Này; Ơi                           |
|    3347 | Bài 14 Cô ấy đã mua rất nhiều quầ... | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我去商店了。$他买了一本书。$你喝水了吗？                       |
|    3368 | Bài 9 Câu hỏi nhiều quá tôi chưa ... | Flama Standard Vocabulary (`e2f31... |    15 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: nhìn thấy; trông thấy                   |
|    3376 | Bài 2 Tôi thức dậy lúc 6 giờ mỗi ... | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 你多大？我十六岁。$王医生的儿子多高？$学校离这里有多远？               |
|    3377 | Bài 3 Cái màu đỏ bên trái là của tôi | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这本书是我的。$左边那个红色的是小王的杯子。$吃的东西我都准备好了。          |
|    3380 | Bài 6 Sao bạn không ăn nữa           | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: từng cái một đều... / mỗi... đều...     |
|    3381 | Bài 7 Nhà bạn cách công ty có xa ... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 八点了，他还在睡觉。$你怎么还没吃饭？$他还在教室学习呢。               |
|    3382 | Bài 8 Để tôi suy nghĩ rồi nói cho... | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我请你吃饭。$你让我再想想。$妈妈叫我去买苹果。                    |
|    3383 | Bài 9 Câu hỏi nhiều quá tôi chưa ... | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Thứ... / Đầu... (tiền tố chỉ số thứ     |
|    3384 | Bài 10 Đừng tìm nữa, điện thoại ở... | Flama Standard Vocabulary (`e2f31... |     2 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: BẤT YẾU LIỄU / BIỆT LIỄU                       |
|    3385 | Bài 11 Anh ấy lớn hơn tôi 3 tuổi     | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 哥哥没有姐姐高。$这个苹果没有那个大。$我今天没有昨天忙。               |
|    3386 | Bài 12 Bạn mặc ít áo quá             | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我住得不远，很近。$姐姐今天起得早不早？$你昨晚睡得好吗？               |
|    3387 | Bài 13 Cửa đang mở kìa               | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 门开着呢。$她穿着一件红色的衣服。$桌子上放着几本书。                 |
|    3390 | Bài 1 Cuối tuần bạn có dự định gì    | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ... xong / ... xong xuôi / ... ổn t     |
|    3391 | Bài 2 Khi nào anh ấy về              | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我们在楼上等你呢，你快上来吧。$他走进图书馆去了。$老师带了一本书来。         |
|    3392 | Bài 3 Trên bàn để rất nhiều đồ uống  | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: hoặc / hay là (lựa chọn)                |
|    3393 | Bài 4 Cô ấy luôn cười khi nói chu... | Flama Standard Vocabulary (`e2f31... |     2 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这个西瓜又大又甜。$外边又黑又冷，你别出去了。$这里的服务员又年轻又热         |
|    3395 | Bài 6 Sao đột nhiên lại không tìm... | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ...đâu rồi? / ...ở đâu?                 |
|    3396 | Bài 7 Tôi và cô ấy đều đã quen nh... | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 现在已经差一刻八点了，快起床吧！$现在是差五分十点。$差十分十二点我们         |
|    3397 | Bài 8 Bạn đi đâu tôi đi đó           | Flama Standard Vocabulary (`e2f31... |     2 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 他昨天来过，今天又来了。$我今天有点儿累，明天再去游泳吧。$你上午喝了         |
|    3398 | Bài 9 Tiếng Trung của cô ấy nói h... | Flama Standard Vocabulary (`e2f31... |     2 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: A giống B / A như B (về phương diện     |
|    3399 | Bài 10 Môn toán khó hơn môn lịch ... | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我每天学习一两个小时汉语。$你都喝了三四杯咖啡了，别再喝了！$从这里到         |
|    3401 | Bài 12 Hãy để những thứ quan trọn... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我早上五点就起床了。$坐飞机一个小时就到了。                      |
|    3402 | Bài 13 Tôi đi bộ về đấy              | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ... chết đi được / ... cực kỳ / ...     |
|    3404 | Bài 15 Những thứ khác đều không c... | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 周末你有没有什么打算？$你写得很好，没什么问题。                    |
|    3407 | Bài 18 Tôi tin rằng họ sẽ đồng ý     | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 只要经过一段时间，就会慢慢地习惯。$听到这个好消息，大家高兴地笑了。$         |
|    3409 | Bài 20 Tôi bị anh ấy ảnh hưởng rồi   | Flama Standard Vocabulary (`e2f31... |     2 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: chỉ khi... mới... / chỉ có... mới..     |
|    3413 | Bài 4 Cô ấy luôn cười khi nói chu... | Flama Standard Vocabulary (`e2f31... |    22 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: khách; khách hàng; khách khứa           |
|    3417 | Bài 8 Bạn đi đâu tôi đi đó           | Flama Standard Vocabulary (`e2f31... |    21 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 健康最重要，胖瘦没关系。$多吃水果蔬菜对健康好。$祝您身体健康，工作顺         |
|    3421 | Bài 12 Hãy để những thứ quan trọn... | Flama Standard Vocabulary (`e2f31... |    17 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我已经把我的照片放在你的包里了。$桌子上有一个黑色的包。$周末我们一起         |
|    3423 | Bài 14 Bạn mang hoa quả lại đây      | Flama Standard Vocabulary (`e2f31... |    21 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: thanh toán; tính tiền; trả tiền hóa     |
|    3431 | Bài 2 Người bạn thực sự              | Flama Standard Vocabulary (`e2f31... |     8 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 在工作中遇到问题，男人不喜欢说，而女人喜欢跟朋友聊。$我们应该多听别人         |
|    3432 | Bài 3 Giám đốc có ấn tượng rất tố... | Flama Standard Vocabulary (`e2f31... |     8 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: trước tiên... tiếp theo/thứ hai là.     |
|    3433 | Bài 4 Đừng quá sốt ruột kiếm tiền    | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: hóa ra / ban đầu vs vốn dĩ / đáng l     |
|    3434 | Bài 5 Chỉ mua đồ đúng, không mua ... | Flama Standard Vocabulary (`e2f31... |     7 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 他喜欢很多运动，尤其是踢足球。$这里的风景很美，尤其是秋天。$考试前要         |
|    3439 | Bài 10 Tiêu chuẩn của hạnh phúc      | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这件衣服样子很好看，不过价格有点儿贵。$对不起，先生，那种蛋糕卖完了，         |
|    3440 | Bài 11 Đọc sách hay, đọc cho hay,... | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: bất kể/bất luận... đều/cũng...          |
|    3441 | Bài 12 Dùng trái tim khám phá thế... | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: dù/cho dù... đi nữa cũng...             |
|    3445 | Bài 16 Cuộc sống có thể tốt đẹp hơn  | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 明天的会议恐怕要推迟了。$这个会议室的座位恐怕不够，换个大的吧。$那份         |
|    3446 | Bài 17 Con người và tự nhiên         | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: vì... mà... / để... mà...               |
|    3448 | Bài 19 Hương vị của cuộc sống        | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Được / lên (đạt được mục đích, kết      |
|    3449 | Bài 20 Cảnh đẹp trên đường           | Flama Standard Vocabulary (`e2f31... |     7 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 她讲着讲着自己就先笑了。$晚上躺在草地上看星星，有时候躺着躺着就睡着了         |
|    3468 | Bài 19 Hương vị của cuộc sống        | Flama Standard Vocabulary (`e2f31... |    33 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 图书馆里禁止大声讲话。$加油站内严禁抽烟。                       |
|    3471 | Bài 2 Để lại chùm chìa khóa cho c... | Flama Standard Vocabulary (`e2f31... |     7 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: cực kỳ / vô cùng / khủng khiếp / ch     |
|    3473 | Bài 4 Tử Lộ vác gạo                  | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 他顶着大风大雪在路上艰难地走着。$他们克服了重重困难，终于爬上了山顶。         |
|    3474 | Bài 5 Dòng suối Tế Nam               | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 他把平时省下来的钱都积蓄起来，准备买一套属于自己的房子。$刘丽知道自己         |
|    3475 | Bài 6 Nguồn gốc đêm Giao thừa        | Flama Standard Vocabulary (`e2f31... |     9 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Dò hỏi / hỏi thăm vs Hỏi han / tra      |
|    3477 | Bài 8 Ý nghĩa xưa và nay của Sáng... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: nếu không thì; hay là                   |
|    3479 | Bài 10 Kỳ tích từ tranh luận         | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 最新的调查结果显示，多数年轻人喜欢在线购物。$这次比赛充分显示了他的领         |
|    3480 | Bài 11 Tác hại của đồng hồ báo thức  | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 山水画所表现的是人与自然和谐共处的关系。$调查显示，随着经济发展，人们         |
|    3481 | Bài 12 Người dùng hải ngoại dùng ... | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这家公司正在大力发展海外业务。$方便快捷的交通网络是发展地方经济的基础         |
|    3483 | Bài 14 Tứ hợp viện ở Bắc Kinh        | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: bị / được ... làm cho (cấu trúc bị      |
|    3488 | Bài 19 Bánh củ cải quê hương         | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 萝卜饼要趁热吃，凉了就不好吃了。$趁现在天气晴朗，我们去公园散步吧。$         |
|    3489 | Bài 20 Quầy truyện tranh thiếu nhi   | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Có/không có đủ khả năng/điều kiện (     |
|    3490 | Bài 21 Chú Hán Tự Tình duyên của ... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ngẫu nhiên; tình cờ; bất ngờ            |
|    3491 | Bài 22 Đọc và tư duy                 | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Từ khi; kể từ                           |
|    3492 | Bài 23 Buông tay                     | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 据警方通报，犯罪嫌疑人李某已被依法拘留。$长期进行某方面的专业训练，能         |
|    3494 | Bài 25 Đổ đầy nước cho chính mình    | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 刘老师虽然看上去很严肃，但其实对人很友善。$会议室里的气氛十分严肃，大         |
|    3502 | Bài 33 Lấy tắc trị tắc Mẹo hay gi... | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 面对困难，他表现得非常冷静和坚强。$为了得到领导的赏识，他在会议上拼命         |
|    3503 | Bài 34 Thuật chăm sóc lông vũ của... | Flama Standard Vocabulary (`e2f31... |     9 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 他转过身来，微笑着向大家打招呼。$请把桌上的那本词典递过来。$听到这个         |
|    3505 | Bài 36 Lão Xá và thú trồng hoa       | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 只要大家齐心协力，就一定能应付眼前的困难。$他平时不努力，考试全凭临时         |
|    3507 | Bài 2 Để lại chùm chìa khóa cho c... | Flama Standard Vocabulary (`e2f31... |    46 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 假期里校园里冷冷清清的，几乎看不到学生。$这家餐厅生意不好，平日里总是         |
|    3508 | Bài 3 Đời người có lựa chọn, mọi ... | Flama Standard Vocabulary (`e2f31... |    56 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 公司必须严格把关，绝不能让不合格产品流入市场。$这款新产品一经推出，就         |
|    3509 | Bài 4 Tử Lộ vác gạo                  | Flama Standard Vocabulary (`e2f31... |    55 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: nhân tài; người tài; vóc dáng/tướng     |
|    3510 | Bài 5 Dòng suối Tế Nam               | Flama Standard Vocabulary (`e2f31... |    53 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 历代文人留下了许多赞美济南泉水的诗文。$他用动听的歌声赞美大自然的美好         |
|    3511 | Bài 6 Nguồn gốc đêm Giao thừa        | Flama Standard Vocabulary (`e2f31... |    48 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 传说“夕”是一种十分凶猛的怪兽，害怕巨大的声响。$在除夕这一天，一家人         |
|    3512 | Bài 7 Hai câu chuyện thành ngữ       | Flama Standard Vocabulary (`e2f31... |    58 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 在口语交流中，主语常常可以省略。$前面的背景大家都很清楚，后面这部分就         |
|    3513 | Bài 8 Ý nghĩa xưa và nay của Sáng... | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: sống chung; chung sống; qua lại; cư     |
|    3514 | Bài 9 Một Lỗ Tấn rất khác            | Flama Standard Vocabulary (`e2f31... |    56 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 她在这次考试中取得了突出的成绩。$这篇文章的主题不够突出，需要修改。$         |
|    3516 | Bài 11 Tác hại của đồng hồ báo thức  | Flama Standard Vocabulary (`e2f31... |    46 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 紧张的时候，做几次深呼吸有助于放松心情。$医生检查发现病人的呼吸十分微         |
|    3517 | Bài 12 Người dùng hải ngoại dùng ... | Flama Standard Vocabulary (`e2f31... |    61 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这是我的个人爱好，跟我学什么专业没有关系。$在处理集体利益与个人利益的         |
|    3519 | Bài 14 Tứ hợp viện ở Bắc Kinh        | Flama Standard Vocabulary (`e2f31... |    44 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 在各种各样的民居中，北京四合院最具有代表性。$我想代表全体员工，向经理         |
|    3520 | Bài 15 Bàn việc quân trên giấy       | Flama Standard Vocabulary (`e2f31... |    52 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 领导决定下个月将他调动到总公司工作。$老师想方设法调动学生们的学习积极         |
|    3522 | Bài 17 Rời đi vào khoảnh khắc đẹp... | Flama Standard Vocabulary (`e2f31... |    48 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 观众对这部电影的评价非常高。$我们要客观公正地评价每一个人的工作表现。         |
|    3526 | Bài 21 Chú Hán Tự Tình duyên của ... | Flama Standard Vocabulary (`e2f31... |    51 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 记者经过深入调查，终于揭开了事情的真相。$俗话说“有图有真相”，但他发         |
|    3528 | Bài 23 Buông tay                     | Flama Standard Vocabulary (`e2f31... |    55 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这孩子平时很乖，从不让父母操心。$ 自从吃了那次亏后，他也变得学乖了。         |
|    3531 | Bài 26 Bạn thuộc kiểu người bận r... | Flama Standard Vocabulary (`e2f31... |    48 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 一连三天，他们都很顺利地实现了原定的考察计划。$他一连加了几个星期的班         |
|    3541 | Bài 36 Lão Xá và thú trồng hoa       | Flama Standard Vocabulary (`e2f31... |    42 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: cây kéo; cái kéo                        |
|    3542 | Bài 1 Khơi gợi từ con trẻ            | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Ước gì; mong sao; nóng lòng muốn        |
|    3544 | Bài 3 Một hộp bánh Trung thu         | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 既然已经确立了目标，我们就非坚持到底不可。$这件事情太严重了，你今天非         |
|    3547 | Bài 6 Làm tốt vai trò người mới c... | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这次考试失败了不要紧，大不了从头再来。$太不像话了，明明是在故意刁难人         |
|    3548 | Bài 7 Cuộc đời tôi do tôi tự quyết   | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 他的粗心大意致使整个试验最终失败。$由于连日暴风雪，致使航班大面积延误         |
|    3549 | Bài 8 Gặp lại tôi của ngày xưa       | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Thành thật mà nói; nói thật với bạn     |
|    3550 | Bài 9 Những ngày không dùng điện ... | Flama Standard Vocabulary (`e2f31... |     7 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ... chết đi được; ... muốn chết; cự     |
|    3551 | Bài 10 Ẩm thực Trung Hoa trong tầ... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Cho dù; dù cho; ngay cả khi             |
|    3553 | Bài 12 Chúng ta đều thích tiếng ồ... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: xét thấy; căn cứ vào; bởi vì            |
|    3557 | Bài 16 Từ Kiện và các nhiếp ảnh g... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: bị... bởi... / được... bởi...           |
|    3559 | Bài 18 Dây mướp kỳ diệu              | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: cùng với / kể cả / lẫn                  |
|    3560 | Bài 19 Thế giới biển sâu không có... | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 尊老爱幼历来是中华民族的传统美德。$他做事一向认真负责，从来不推卸责任         |
|    3564 | Bài 23 Thời đại dữ liệu lớn          | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 枯燥晦涩的专业名词解释，往往会让门外汉和“科盲”们更加不知所云。$十一         |
|    3565 | Bài 24 Trải nghiệm kỳ lạ của các ... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 他明明知道这是商业机密，还故意向竞争对手透露消息。$法官最终认定被告在         |
|    3567 | Bài 26 Ánh sáng kỳ lạ                | Flama Standard Vocabulary (`e2f31... |     7 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 他因为上班迟到，今天又挨了一顿批评。$这家老字号餐厅服务周到，深受顾客         |
|    3570 | Bài 29 Bản ghi nhớ về tiếng cười     | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 那里一年四季都是旅游旺季，到那里去旅行一定要预先订好旅馆。$大家预先都         |
|    3574 | Bài 33 Hoài niệm cuộc sống chậm rãi  | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: tại hiện trường / trực tiếp vs ngay     |
|    3577 | Bài 36 Thư viện cổ xưa của Trung ... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Hết hạn; tính đến thời điểm... (dừn     |
|    3578 | Bài 37 Câu chuyện cảnh sát           | Flama Standard Vocabulary (`e2f31... |     7 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Để / Nhằm mục đích...                   |
|    3579 | Bài 38 Mắt tinh bắt trọn cơ hội k... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Căn cứ vào; dựa theo; căn cứ / cơ s     |
|    3581 | Bài 40 Siêu năng lực con người có... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 他们凭借顽强的毅力战胜了伤病，终于重返赛场。$运动员们在落后的情况下顽         |
|    3582 | Bài 1 Khơi gợi từ con trẻ            | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 公司向所有消费者郑重承诺，绝不销售假冒伪劣商品。$他郑重地收下了这份奖         |
|    3586 | Bài 5 Học một ngoại ngữ có cần lý... | Flama Standard Vocabulary (`e2f31... |    53 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 考上大学固然好，没考上也不是没出路。$这道题的方法固然巧妙，但并不适合         |
|    3588 | Bài 7 Cuộc đời tôi do tôi tự quyết   | Flama Standard Vocabulary (`e2f31... |    49 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 最近，小王正为工作的事伤脑筋。$孩子的教育问题一直让许多年轻父母感到伤         |
|    3591 | Bài 10 Ẩm thực Trung Hoa trong tầ... | Flama Standard Vocabulary (`e2f31... |    52 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这片原始森林里栖息着各种各样的飞禽走兽。$古代画卷中常常出现神仙与飞禽         |
|    3592 | Bài 11 Khi tôi vắng nhà, mèo làm gì  | Flama Standard Vocabulary (`e2f31... |    55 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 所有进入考场的人都必须出示准考证，任何人概不例外。$全家人都喜欢吃辣，         |
|    3593 | Bài 12 Chúng ta đều thích tiếng ồ... | Flama Standard Vocabulary (`e2f31... |    58 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 微风抚摸树叶，发出了极其温柔的沙沙声。$母亲温柔地抚摸着孩子的头，眼神         |
|    3594 | Bài 13 Nhìn thế sự đổi thay qua c... | Flama Standard Vocabulary (`e2f31... |    56 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 由于项目经费预算不足，部分研究计划不得不延期。$我们正在向相关部门申请         |
|    3599 | Bài 18 Dây mướp kỳ diệu              | Flama Standard Vocabulary (`e2f31... |    51 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 院子里种着几株罕见的名贵兰花。$经过精心栽培，那株幼苗终于结出了果实。         |
|    3601 | Bài 20 Tổ gà vàng                    | Flama Standard Vocabulary (`e2f31... |    62 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 身为国家公职人员，绝不敢贪污一分一毫的公款。$政府坚决打击贪污腐败行为         |
|    3602 | Bài 21 Cửa hàng tương lai            | Flama Standard Vocabulary (`e2f31... |    62 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 他在比赛中发挥出色，斩获了一枚金牌。$她小心翼翼地把这枚纪念邮票贴在信         |
|    3605 | Bài 24 Trải nghiệm kỳ lạ của các ... | Flama Standard Vocabulary (`e2f31... |    75 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这种只想赢球的心态和比赛精神南辕北辙。$如果学习方法不当，你的努力只会         |
|    3607 | Bài 26 Ánh sáng kỳ lạ                | Flama Standard Vocabulary (`e2f31... |    68 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 长时间对着电脑低头工作，容易导致颈椎酸痛。$他去医院检查后，医生诊断他         |
|    3610 | Bài 29 Bản ghi nhớ về tiếng cười     | Flama Standard Vocabulary (`e2f31... |    56 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: rõ ràng ngay trước mắt; nhìn qua là     |
|    3611 | Bài 30 Bạn ngủ ngon không            | Flama Standard Vocabulary (`e2f31... |    64 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 科技创新在国家综合实力竞争中占据着举足轻重的地位。$在这个跨国项目中，         |
|    3612 | Bài 31 Học vấn trong vận động        | Flama Standard Vocabulary (`e2f31... |    67 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 科学研究表明，大脑是人体衰退最慢的器官之一。$ 随着年龄的增长，他的记         |
|    3616 | Bài 35 Tiếp cận tranh Tết khắc gỗ    | Flama Standard Vocabulary (`e2f31... |    51 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 朱仙镇被誉为中国木版年画的故乡。$漫步在异国街头，他格外思念遥远的故乡         |
|    3617 | Bài 36 Thư viện cổ xưa của Trung ... | Flama Standard Vocabulary (`e2f31... |    62 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 老师亲自做出示范，规范学生的每一个实验步骤。$老一辈学者的严谨治学态度         |
|    3620 | Bài 39 Đời sống trong kỷ nguyên I... | Flama Standard Vocabulary (`e2f31... |    72 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 他的幽默发言瞬间打破了会议室里单调沉闷的气氛。$整天过着单调沉闷的生活         |
|    3621 | Bài 40 Siêu năng lực con người có... | Flama Standard Vocabulary (`e2f31... |    67 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 运动员必须接受正规科学的训练，才能有效避免运动损伤。$购买药品一定要通         |
|    3647 | Bài 8                                | Flama Standard Vocabulary (`e2f31... |    30 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 请问，你喜欢哪本书？这本还是那本？$他是哪国人？他是中国人还是美国人？         |
|    3649 | Bài 1                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 天黑了，我们快点儿回家吧。$现在天气不热了，很舒服。$我不想喝茶了，想         |
|    3650 | Bài 2                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我没有中国朋友，我想认识一个同学。$今天他没苹果，明天他去商店买。           |
|    3651 | Bài 3                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 明天下午我们一起去买水果吧。$他想去饭店吃中国菜。$下午我不忙，想去商         |
|    3656 | Bài 8                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 请问，您是李老师的学生吗？$明天你想和我一起去喝茶吗？$这里的中国菜很         |
|    3657 | Bài 9                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这本书不是我的，是我同学的。$桌子上的苹果是爸爸买的。$那件大衣服是哥         |
|    3658 | Bài 10                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 弟弟现在在房间里看书呢。$ 我们在听王老师说汉语呢。$ 爸爸和妈妈在客         |
|    3659 | Bài 11                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 大卫学汉语学了三个月了，说得很好。$王老师在那个学校教了十年书了。$妹         |
|    3665 | Bài 17                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 桌子上面有两本书和一个水杯。$我今天上午买了五个大苹果。$我们学校有八         |
|    3666 | Bài 18                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我每天下午都在家里看书、喝茶。$小明想去商店买新衣服和鞋子。$弟弟不喜         |
|    3668 | Bài 20                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我和同学在学校学了一个小时。$我哥哥在北京住了四年。$爸爸每天在医院工         |
|    3671 | Bài 23                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: HÒA / HẠP                                      |
|    3673 | Bài 25                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Không có chi / Đừng khách sáo (Đáp      |
|    3676 | Bài 28                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Biết / Có thể làm gì (thông qua học     |
|    3678 | Bài 30                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Xin mời / Mời / Làm ơn + Động từ (C     |
|    3680 | Bài 32                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我的小妹妹会做饭，她做的中国菜很好吃。$我现在不忙，能跟你一起去商店买         |
|    3681 | Bài 33                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 请问，你的汉语老师是哪国人？$我不认识他，不知道他是哪国人。              |
|    3682 | Bài 34                               | Flama Standard Vocabulary (`e2f31... |     2 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: không thể / không được ...              |
|    3684 | Bài 2                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 医生让我每天多喝温水、多休息。$今天工作太累了，你让我坐下休息一会儿。         |
|    3686 | Bài 4                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我们班里他的汉语说得最好，大家都喜欢他。$在所有水果里面，妹妹最喜欢吃         |
|    3687 | Bài 5                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 今天我生病了，你能帮我把这本书给王老师吗？$下课以后，请你帮我把这杯热         |
|    3691 | Bài 9                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 今天天气非常好，我们去外面走走吧。$请你尝尝这个苹果，看看甜不甜。$你         |
|    3693 | Bài 11                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: KỶ + SỐ TỪ HÀNG CHỤC/TRĂM/NGHÌN + L            |
|    3694 | Bài 12                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 星期天我想和姐姐一起去电影院看电影。$明天下午你愿意和我一起打篮球吗？         |
|    3695 | Bài 13                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: sắp... rồi / là... ngay                 |
|    3698 | Bài 16                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 明天是妈妈的生日，我想给她买一个新手表。$哥哥昨天下午去商店给朋友买生         |
|    3700 | Bài 18                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: một chút / một ít (cái gì đó)           |
|    3703 | Bài 21                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 桌子上放着我昨天下午新买的汉语书。$前面那个跑步的高个子男人是我的大学         |
|    3705 | Bài 23                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Thật là... / Rất... (Cấu trúc cảm t     |
|    3707 | Bài 25                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ... là / đúng là ...                    |
|    3710 | Bài 28                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 今天天气不太冷，我们一起去公园走走吧。$这门课有点儿难，我听得不太懂。         |
|    3711 | Bài 29                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ... xong chưa / ... đã ổn thỏa chưa     |
|    3712 | Bài 30                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: không thể / không được                  |
|    3713 | Bài 31                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: một chút / một lát / thử xem            |
|    3716 | Bài 34                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这件黑色的衣服不大也不小，正合适。$这几天的天气很好，不干也不湿。$今         |
|    3720 | Bài 38                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Chưa / Không (làm gì)                   |
|    3721 | Bài 39                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ... của / mà (kết cấu định ngữ biểu     |
|    3723 | Bài 41                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 桌子上有一本书和两杯热茶，请喝吧。$飞机上有很多人，大家都在安静地看书         |
|    3725 | Bài 43                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 你的生日是几月几号？我想送你一个礼物。$请问，王医生的办公室是在三层几         |
|    3729 | Bài 47                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 新开的中国饭馆离我们学校很近，走路五分钟就到了。$我现在住的地方离公司         |
|    3731 | Bài 49                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Tặng / cho [ai đó] [cái gì]             |
|    3733 | Bài 51                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 明天是星期天，我要去商店买水果。$现在很晚了，我们该准备要睡觉了。$哥         |
|    3734 | Bài 52                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: sao vẫn chưa…… / sao còn chưa……         |
|    3737 | Bài 55                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 今天外面的天气比昨天冷，你出门要多穿点衣服。$这个西瓜比那个大得多，而         |
|    3738 | Bài 56                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 哥哥喜欢看书，弟弟也很喜欢看书。$这家饭馆的菜很好吃，也很便宜。$爸爸         |
|    3739 | Bài 57                               | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 医生让我这个星期吃两次鱼。$王老师每个月去北京旅游一次。$我每天跑步一         |
|    3741 | Bài 2                                | Flama Standard Vocabulary (`e2f31... |    35 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 穿白衣服的女孩子跳舞跳得真好。$那个小女孩子正在公园里高兴地玩水。           |
|    3742 | Bài 3                                | Flama Standard Vocabulary (`e2f31... |    35 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我每天早上六点半起床去跑步。$明天有考试，你记得早一点儿起床。             |
|    3743 | Bài 4                                | Flama Standard Vocabulary (`e2f31... |    35 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 中国人很喜欢喝热茶。$请给我来一杯绿茶，谢谢。                     |
|    3748 | Bài 9                                | Flama Standard Vocabulary (`e2f31... |    35 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 今天是十月五号，也是我的生日。$请问你住在这栋楼的几号房间？              |
|    3752 | Bài 13                               | Flama Standard Vocabulary (`e2f31... |    35 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 中国人在新年的时候喜欢穿红色的衣服。$桌子上放着几个又大又红的苹果。          |
|    3754 | Bài 1                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: MỖI ... ĐÔ / ĐẤU ...                           |
|    3755 | Bài 2                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这次考试取得了好成绩，这件事情让他非常开心。$医生让他每天按时睡觉，不         |
|    3756 | Bài 3                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 小红每天都起得很早，把房间打扫得非常干净。$大卫说汉语说得非常流利，大         |
|    3757 | Bài 4                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我已经买好了明天去上海的火车票。$妈妈做好了晚饭，叫大家快来吃。$你先         |
|    3760 | Bài 7                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 除了学习汉语，我每天晚上还要去健身房锻炼身体。$这个水果店里除了苹果，         |
|    3762 | Bài 9                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Đi về hướng / đi về phía...             |
|    3763 | Bài 10                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Nhưng / nhưng mà...                     |
|    3764 | Bài 11                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Gặp mặt nhau một chút / gặp một cái     |
|    3765 | Bài 12                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: MỘT HỮU……GIÁ MA/NA MA……                        |
|    3766 | Bài 13                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Câu hỏi chính phản ghép dạng khẳng      |
|    3769 | Bài 16                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 今天是妈妈的生日，我想给她做一个大蛋糕。$晚上哥哥会给我们做几道好吃的         |
|    3775 | Bài 22                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Có sự nâng cao / tiến bộ...             |
|    3776 | Bài 23                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 医生说我的感冒已经好了，以后不用再天天吃药了。$外面的雨已经停了，我们         |
|    3777 | Bài 24                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 周末我们在家打扫打扫房间，洗洗衣服吧。$明天有听力考试，今天晚上你要好         |
|    3779 | Bài 26                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 外面下大雨，哥哥正在房间里听音乐呢。$老师正在办公室批改我们今天的听写         |
|    3780 | Bài 27                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 回家以后，你要先把手洗干净再去吃水果。$我们先把这个会议开完，然后再去         |
|    3781 | Bài 28                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: đã... / là... ngay / chỉ mất...         |
|    3782 | Bài 29                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 大家快坐好，电影马上就要开始了。$再等我两分钟，我马上就洗完了。            |
|    3783 | Bài 30                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 你到了北京以后，记得马上给妈妈打电话。$老师生病没来上课，班长准备给她         |
|    3784 | Bài 31                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 时间已经不早了，你别玩电脑游戏了，快去睡觉吧。$事情都已经解决了，你就         |
|    3786 | Bài 33                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我只需要两三天时间就能写完这个报告。$门外站着三四个学生，好像在找老师         |
|    3788 | Bài 35                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 从这个路口一直向前走，就能看到地铁站。$你向右边看一下，王老师就在那边         |
|    3789 | Bài 36                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 快起床吧，现在已经差十分八点了，要迟到了。$会议差一刻三点开始，请大家         |
|    3790 | Bài 37                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 妈妈笑着对我说：“明天我们一起去买新衣服。”$老师对大家说，下个星期一         |
|    3791 | Bài 38                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 今天外面下大雨了，所以我们不去踢足球了。$因为他生病发烧了，所以今天没         |
|    3792 | Bài 39                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 昨天晚上他加班到十二点才回宿舍睡觉。$这封信寄了很久，我到今天上午才收         |
|    3793 | Bài 40                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: TRỪ LIỄU... NGOẠI, DÃ / HOÀN...                |
|    3794 | Bài 41                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 请你把桌子上的牛奶喝完再睡觉。$妹妹已经把所有的房间都打扫干净了。           |
|    3795 | Bài 42                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ... xong là / thì ... liền              |
|    3796 | Bài 43                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这是我第一次来这个中国饭馆吃饭。$请大家打开书，翻到第三十五页。$小明         |
|    3797 | Bài 44                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: hơi / có một chút ...                   |
|    3798 | Bài 45                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这台新电脑比旧电脑快，工作起来很方便。$今天的苹果比昨天的甜，大家都很         |
|    3799 | Bài 46                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我一查词典才明白这个生词的具体意思。$大家一问才知道小王为什么今天没来         |
|    3800 | Bài 47                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: đến lúc... rồi / nên... rồi             |
|    3801 | Bài 48                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这个手机好看是好看，就是电池不太好。$学汉语难是难，就是非常有意思。          |
|    3802 | Bài 49                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 从我家到公司坐公共汽车要半个小时。$我们每天从早上八点学习到中午十二点         |
|    3805 | Bài 52                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 听说张老师下个月就要跟他大学时的同学结婚了。$他们认识五年了，决定今年         |
|    3806 | Bài 53                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 收拾好行李，我们明天说走就走。$刚才还是晴天，现在说下雨就下雨了。           |
|    3810 | Bài 57                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 在这个城市住久了，你慢慢地也就习惯了。$等问题解决了，大家心里的石头也         |
|    3811 | Bài 58                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 如果明天的天气很好，我们就一起去爬山。$如果你在学习上遇到困难，就可以         |
|    3812 | Bài 59                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: CĂN…… NHẤT DẠNG / BẤT NHẤT DẠNG                |
|    3814 | Bài 61                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这家餐厅的菜味道不错，但是价格有点儿贵。$我今天工作了一整天，现在感觉         |
|    3815 | Bài 62                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 外面天气非常好，我们吃完饭一起去公园走走，好不好？$这件事情等明天经理         |
|    3816 | Bài 63                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: CHÍNH / TẠI / CHÍNH TẠI …… (NI)                |
|    3817 | Bài 64                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 今天晚上你想吃米饭还是吃面条？$我们明天是坐火车去，还是坐飞机去？$你         |
|    3818 | Bài 65                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Làm gì đó thật tốt / cẩn thận / hết     |
|    3822 | Bài 69                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 今天外面的风很大，出门要多穿点衣服。$这个汉语考试虽然很难，但他准备得         |
|    3825 | Bài 72                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: làm gì đó nhiều hơn / nên... nhiều      |
|    3826 | Bài 73                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 姐姐每天起得很早，经常去公园跑步。$他说汉语说得很流利，大家都听得懂。         |
|    3827 | Bài 74                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: hơn / ngoài (ước lượng số lượng)        |
|    3828 | Bài 75                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 妈妈总是为在外地读大学的哥哥担心。$你放心去考试吧，不用为家里的事担心         |
|    3829 | Bài 76                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Ở dưới / Dưới...                        |
|    3830 | Bài 77                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Kết hôn với…… / Cưới……                  |
|    3831 | Bài 78                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 小华练习了一个月，现在汉字写得好多了。$吃了这门药以后，病人感觉好得多         |
|    3832 | Bài 79                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: bảo / để / cho phép / khiến cho……       |
|    3833 | Bài 80                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 如果你对历史感兴趣，明天我们还可以去参观博物馆。$如果大家觉得不累，下         |
|    3834 | Bài 81                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: bảo / để / cho phép / khiến ai làm      |
|    3835 | Bài 82                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 外面刮起了大风，看样子马上快下雨了。$你快点儿穿衣服，去火车站的出租车         |
|    3836 | Bài 83                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 经理现在还在开会，今天的工作还没结束。$已经八点了，他怎么还没起床去上         |
|    3837 | Bài 84                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 王老师正在给新来的外国留学生介绍这所大学。$我想给妹妹介绍一本非常好看         |
|    3838 | Bài 85                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 今天天气真好，公园里散步的人真多。$你穿这件黑色的衬衫真好看。$听到你         |
|    3839 | Bài 86                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 如果你对北京感兴趣，我们明天还可以去故宫看看。$要是你现在不累，我们还         |
|    3840 | Bài 87                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这个周末除了看电影，我还打算去图书馆看书。$王经理除了会说英语以外，还         |
|    3842 | Bài 89                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我站在三楼，看到小王慢慢走上来了。$这些行李太重了，服务员帮你搬上来了         |
|    3843 | Bài 90                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ảnh hưởng đến... / có ảnh hưởng đối     |
|    3844 | Bài 91                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 服务员找给我五块钱零钱。$生日那天，爸爸给我买了一辆自行车。$请把桌子         |
|    3847 | Bài 94                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: TRÌNH ĐỘ / TRẠNG THÁI BỔ NGỮ                   |
|    3849 | Bài 96                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 根据天气预报，我们可以知道明天下午会下大雨。$根据他发来的短信息，大家         |
|    3850 | Bài 97                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这件新买的外套大小刚好，不长也不短。$这杯绿茶的温度正好，不烫也不凉，         |
|    3851 | Bài 98                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: …… ĐÍCH THÌ HẬU / …… THÌ                       |
|    3852 | Bài 99                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 老师进教室的时候，同学们都在认真听讲。$外面在下大雨，你出门要记得带雨         |
|    3853 | Bài 100                              | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Và / Cùng với                           |
|    3858 | Bài 5                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 今天外面刮大风，你出门要多穿点衣服。$冬天的时候，这里经常刮风，特别冷         |
|    3864 | Bài 11                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 房间里放着一张很大的床。$ 医生刚才去病房看了八床的病人。               |
|    3871 | Bài 18                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我们俩的爱好完全不同，但关系很好。$ 每个人都有不同的想法，这很正常。         |
|    3894 | Bài 19                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 听力考试只是汉语水平测试中的一个组成部分。$这本小说的大部分内容都是根         |
|    3898 | Bài 23                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 动物园里有一只非常凶猛的野生老虎。$老虎是受到国家重点保护的动物。           |
|    3899 | Bài 24                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 很多外国朋友觉得用筷子吃饭很有趣。$请帮我拿一双干净的筷子，谢谢。           |
|    3909 | Bài 1                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Tiêm/Chích thuốc cho...                 |
|    3910 | Bài 2                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这家餐厅的服务态度很热情，环境也非常干净。$今天早上的空气很新鲜，让人         |
|    3911 | Bài 3                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 新租的这间公寓离地铁站非常近，出行很方便。$那家超级市场离我们小区只有         |
|    3912 | Bài 4                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 前面那个穿红衣服的是我们学校新来的汉语老师。$参加这次会议的都是来自各         |
|    3918 | Bài 10                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 在出门旅游之前，我们最好先查看一下天气预报。$在开会之前，请大家把手机         |
|    3919 | Bài 11                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 随着经济的快速发展，人们的生活水平有了明显提高。$随着气温逐渐升高，公         |
|    3920 | Bài 12                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: hoàn toàn / thực sự (không hề...)       |
|    3921 | Bài 13                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 身体健康往往与每天的饮食习惯有很大关系。$这个科学实验的结果与环境温度         |
|    3922 | Bài 14                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 小李很重视这次面试，提前准备了很久。$父母很担心一个人在国外生活的妹妹         |
|    3923 | Bài 15                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 爷爷的感冒已经完全好了，不用去医院了。$现在已经超过下午五点了，大家下         |
|    3924 | Bài 16                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 吃完午饭以后，我习惯在办公室休息半小时。$大学毕业以后，他选择留在大城         |
|    3927 | Bài 19                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 只要大家共同努力，我们就一定能按时完成这项任务。$只要你平时认真复习，         |
|    3933 | Bài 25                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 桌子上的牛奶被小猫打翻了，弄得地上都是。$由于路上严重堵车，经理被耽误         |
|    3934 | Bài 26                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 去外国旅游费用很高，光是往返的机票就要花八千块。$这篇长文章内容太复杂         |
|    3935 | Bài 27                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: thực ra không hề……; vốn không……         |
|    3937 | Bài 29                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 周末有空的时候，我打算给在老家的父母打个电话。$导游正在耐心地给外国游         |
|    3938 | Bài 30                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: vì……mà…… / để……mà……                     |
|    3939 | Bài 31                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: khiến cho / làm cho……                   |
|    3940 | Bài 32                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 李阿姨每天打扫房间，总是把客厅整理得干干净净。$妹妹听到通过考试的消息         |
|    3942 | Bài 34                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 由于航班因为暴风雨延误了，他没能按时赶上重要的签约仪式。$由于平时缺乏         |
|    3943 | Bài 35                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Sự/Cái... đối với...                    |
|    3944 | Bài 36                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 经过一段时间的复习，他的成绩比以前好多了。$坐高铁比乘长途汽车舒适多了         |
|    3945 | Bài 37                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Làm việc vì... / Làm việc cho...        |
|    3946 | Bài 38                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 大学毕业以后，他打算先去国外留学两年。$周末如果天气晴朗，我们打算去郊         |
|    3947 | Bài 39                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ... (làm gì) một cách / đến mức...      |
|    3948 | Bài 40                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 你顺着这条路一直往东走，就能看到地铁站了。$出了图书馆大门往右走，旁边         |
|    3949 | Bài 41                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Liên hệ với... / giữ liên lạc với..     |
|    3950 | Bài 42                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 除了会弹钢琴以外，她还会拉小提琴。$这家超市除了卖新鲜水果，还卖各种日         |
|    3951 | Bài 43                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 你不是昨天刚买过牛奶吗？怎么今天又要去买？$我们不是早就约好周末去爬山         |
|    3952 | Bài 44                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: tưởng là / cứ ngỡ là (thực tế khác      |
|    3953 | Bài 45                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 只有坚持每天锻炼身体，身体才会越来越好。$必须按时完成所有任务，经理才         |
|    3954 | Bài 46                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Dù có…… đến mấy/nữa thì cũng……          |
|    3955 | Bài 47                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Giới thiệu…… với/cho ai                 |
|    3956 | Bài 48                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这本关于中国文化的新书，正是我们现在需要的。$那个在讲台上发言的人，正         |
|    3957 | Bài 49                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: đành phải / buộc phải / không thể k     |
|    3958 | Bài 50                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: thương lượng với... / bàn bạc với..     |
|    3959 | Bài 51                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 只有保护好自然环境，人类才能拥有美好的未来。$只有经过长期的训练，演员         |
|    3960 | Bài 52                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 无论遇到什么困难，还是面对失败，他都不会放弃希望。$无论工作日还是节假         |
|    3961 | Bài 53                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 周末你想去哪儿玩，我们就一起去哪儿。$这个密码非常简单，办公室里谁都能         |
|    3962 | Bài 54                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 他今天没来开会，不是因为生病了，而是因为出差去上海了。$解决这个问题不         |
|    3963 | Bài 55                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: ĐƯƠNG / ĐÁNG                                   |
|    3964 | Bài 56                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 经常阅读可以丰富知识，使生活变得更加有趣。$互联网的发展使人们的沟通变         |
|    3965 | Bài 57                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我们不是专业演员，所以表演中难免会有一些缺点。$今天不是节假日，所以商         |
|    3966 | Bài 58                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 大熊猫因为数量稀少，被人们叫做中国的国宝。$由于气候四季如春，这座城市         |
|    3967 | Bài 59                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Làm thế nào để... / Làm sao...          |
|    3968 | Bài 60                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: NHƯỢNG / SỬ / KHIẾU                            |
|    3969 | Bài 61                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Chẳng lẽ... / Lẽ nào...                 |
|    3970 | Bài 62                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: khi / lúc……                             |
|    3971 | Bài 63                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 仔细检查了三遍后，他才放心地把试卷交上去。$回到家以后，我才发现手机落         |
|    3972 | Bài 64                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: cười không nổi / không cười nổi         |
|    3973 | Bài 65                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这座南方城市给我的感觉非常干净舒适。$新来的李老师给学生们的感觉既亲切         |
|    3974 | Bài 66                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 周末有空的话，我们一起去公园散步散步吧。$这个问题比较复杂，我们还需要         |
|    3977 | Bài 69                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 妹妹虽然年纪小，但是做事情比哥哥还要细心。$坐高铁比坐普通火车快得多，         |
|    3978 | Bài 70                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Nếu... / Nếu như...                     |
|    3979 | Bài 71                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: BẤT QUẢN …… ĐÔ/DÃ ……                           |
|    3980 | Bài 72                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 春风吹过之后，公园里的花草渐渐绿了起来。$听到了这个好消息，大家高兴地         |
|    3981 | Bài 73                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这种生长在南方的果树，在当地被叫做黄金果。$因为平时喜欢帮助邻居，那位         |
|    3982 | Bài 74                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Căn cứ vào / Dựa theo...                |
|    3983 | Bài 75                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Gây ra / tạo ra ảnh hưởng... đối vớ     |
|    3984 | Bài 76                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Sao mà... thế / Làm sao mà... được      |
|    3985 | Bài 77                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这项跨国合作任务可不轻松，需要我们全力以赴。$在这么短的时间内学好两门         |
|    3986 | Bài 78                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Có cần... không / có muốn... không?     |
|    3987 | Bài 79                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: ……TIỀN / ……CHI TIỀN                            |
|    3988 | Bài 80                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 你不是答应过今天要陪我去图书馆看书了吗？$那份翻译材料我不是早上就发到         |
|    3989 | Bài 81                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我们可以从这次失败的经历中吸取宝贵的教训。$孩子们从丰富的课外活动中学         |
|    3991 | Bài 83                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 王老师除了教我们中文以外，周末还在图书馆教留学生书法。$这家咖啡馆除了         |
|    3992 | Bài 84                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Khác nhau / Từng cái đều không giốn     |
|    3993 | Bài 85                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 南方夏天的气温虽然很高，但是北方的冬天比南方冷得多。$坐高铁去上海比坐         |
|    3994 | Bài 86                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 想掌握一门外语，我们不能光背语法规则，还要经常练习口语。$解决生活中的         |
|    3995 | Bài 87                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Tuy / mặc dù ... nhưng lại ...          |
|    3997 | Bài 89                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Không... thì... / Chưa... đã...         |
|    3998 | Bài 90                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: NHƯỢNG / SỬ... ĐÍCH THỊ                        |
|    3999 | Bài 91                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 麻烦你帮我把这份材料打印两份，谢谢。$办这个手续需要很多证明文件，确实         |
|    4004 | Bài 96                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这件裙子腰部太紧了，师傅帮我改宽了一点儿。$工人们花了三个月时间，终于         |
|    4007 | Bài 99                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Và; cùng; với                           |
|    4008 | Bài 100                              | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Nếu như... vậy thì / thì...             |
|    4009 | Bài 101                              | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Càng... hơn / ... hơn nữa               |
|    4010 | Bài 102                              | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Mỗi... đều... / Cứ mỗi... lại...        |
|    4011 | Bài 103                              | Flama Standard Vocabulary (`e2f31... |     1 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Không... lắm / Không quá...             |
|    4015 | Bài 4                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: vì/do... mà...                          |
|    4016 | Bài 5                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ... sẽ... mà / ... chắc chắn sẽ...      |
|    4017 | Bài 6                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: trên phương diện/về mặt...              |
|    4018 | Bài 7                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Xem ra / Có vẻ như                      |
|    4019 | Bài 8                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Nếu... / Nếu như...                     |
|    4020 | Bài 9                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Hơn nữa / Mà còn                        |
|    4021 | Bài 10                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ở cùng với... / bên cạnh...             |
|    4022 | Bài 11                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 因为突降暴雨，所以原定的户外拓展活动推迟了。$他因为经常坚持运动，所以         |
|    4027 | Bài 16                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: CƯƠNG / TỰU                                    |
|    4028 | Bài 17                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: TÁC VI / CHI NHẤT                              |
|    4029 | Bài 18                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: BỊ / MIÊU TẢ VI                                |
|    4030 | Bài 19                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 经常熬夜对身体非常不好，容易导致免疫力下降。$王老师对待学生一向很好，         |
|    4033 | Bài 22                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 因为平时注重体育锻炼，所以他的身体素质一直很好。$他这次能够提前完成任         |
|    4034 | Bài 23                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: CHỈ YẾU... DÃ/TỰU...                           |
|    4035 | Bài 24                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 那位应聘者的出色表现，给面试官留下了极好的印象。$这次云南之旅给所有游         |
|    4036 | Bài 25                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 经过多方考察后，公司最终决定在这个城市投资建厂。$吃完午饭后，稍微休息         |
|    4037 | Bài 26                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 双方管理层目前还在就合作细节进行深入协商。$对于是否接受这份跨国工作，         |
|    4039 | Bài 28                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 虽然筹备时间很紧迫，但今天的开幕式办得挺成功的。$这份调查报告的数据挺         |
|    4040 | Bài 29                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 医生建议他每天坚持慢跑半小时，以增强体质。$鉴于目前的市场竞争，我不建         |
|    4044 | Bài 33                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Làm gì có... / Đâu có...                |
|    4045 | Bài 34                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 充分听取了各方专家的意见之后，项目组做出了最终决定。$在经历了无数次的         |
|    4046 | Bài 35                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Tương tự với... / Giống với...          |
|    4047 | Bài 36                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Căn cứ vào / dựa vào / theo...          |
|    4048 | Bài 37                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Từ trong... / qua...                    |
|    4049 | Bài 38                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Đâu có ngờ / nào ngờ / ai ngờ đâu       |
|    4050 | Bài 39                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 关于这个合作项目，双方早就达成了共识。$气象部门早就预报了今天会有强降         |
|    4051 | Bài 40                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: HƯỚNG ... TÁ / TÁC ...                         |
|    4052 | Bài 41                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 他成功的关键不是运气有多好，而是多年如一日的坚持。$这次会议讨论的不是         |
|    4053 | Bài 42                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: mất niềm tin vào... / mất tự tin đố     |
|    4054 | Bài 43                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ... lại / nhưng lại...                  |
|    4055 | Bài 44                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Tưởng rằng... / Cứ ngỡ là...            |
|    4056 | Bài 45                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 除了具备专业知识以外，优秀的领导者还需要具备亲和力。$这家书店除了出售         |
|    4057 | Bài 46                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Có hứng thú với... / Nảy sinh niềm      |
|    4058 | Bài 47                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 保护自然生态环境，是实现社会可持续发展的重要任务之一。$睡眠不足是导致         |
|    4063 | Bài 52                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 办理登机手续时，他特意申请和妻子坐一起。$为了方便讨论课题，老师安排班         |
|    4064 | Bài 53                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 受到这次惨痛的教训后，他再也不敢酒后驾车了。$自从搬离那座城市，我再也         |
|    4065 | Bài 54                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Có ảnh hưởng/tác động đến...            |
|    4066 | Bài 55                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ... có nghĩa là gì? / Ý của... là g     |
|    4067 | Bài 56                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这片神秘的原始森林依然保留着未被人类破坏的生态系统。$专家指出，该提案         |
|    4068 | Bài 57                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 他并没有放弃理想，而是选择换一种方式继续努力。$这次失败并不是坏事，而         |
|    4069 | Bài 58                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: trong vòng...; trong phạm vi...         |
|    4070 | Bài 59                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 只要大家齐心协力，困难便能迎刃而解。$太阳刚升起，山间的浓雾便渐渐散去         |
|    4071 | Bài 60                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: điểm...; chỗ... (chỉ đặc điểm, khía     |
|    4072 | Bài 61                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: bày kín / xếp đầy                       |
|    4073 | Bài 62                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: CHÍ HỮU / TẤT TU……TÀI……                        |
|    4074 | Bài 63                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: bận rộn với / bận... (việc gì)          |
|    4075 | Bài 64                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: nếu / nếu như……                         |
|    4076 | Bài 65                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: hướng về / về phía (làm hành động g     |
|    4077 | Bài 66                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这部经典电影取材于真实历史事件，深受观众喜爱。$作者的新作取材于日常生         |
|    4078 | Bài 67                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Bay tới / Bay về phía / Bay sang (đ     |
|    4079 | Bài 68                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Chỉ cần... là/thì...                    |
|    4082 | Bài 71                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 老师把全班同学分成五个小组来讨论这个商业案例。$为了提高工作效率，我们         |
|    4083 | Bài 72                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Hễ là... / Phàm là... thì đều...        |
|    4084 | Bài 73                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: nếu như... thì đương nhiên/tất nhiê     |
|    4085 | Bài 74                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 每天坚持慢跑半小时，对身体健康有很大帮助。$多阅读经典文学作品，对提高         |
|    4086 | Bài 75                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 一个人的性格形成往往与家庭教育环境有密切关系。$这次实验的成功与全体团         |
|    4087 | Bài 76                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Đành phải…… / Buộc phải…… / Không t     |
|    4088 | Bài 77                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Nếu như... thì hoàn toàn không / th     |
|    4089 | Bài 78                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: NẢ PHÁ…… DÃ/ĐÃN……                              |
|    4090 | Bài 79                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Giá mà / Nếu như... thì tốt rồi         |
|    4092 | Bài 81                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 虽然创业初期面临巨大的资金压力，但他始终没有放弃梦想。$虽然这款新手机         |
|    4093 | Bài 82                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Làm thế nào cũng... / Dù thế nào cũ     |
|    4094 | Bài 83                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Đã làm cho... / Khiến cho...            |
|    4096 | Bài 85                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 无论是工作日还是节假日，这位医生都会按时去病房查房。$无论刮风还是下雨         |
|    4098 | Bài 87                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: nói/kể/cho... biết cái gì               |
|    4103 | Bài 92                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这部小说的篇幅虽然很短，却蕴含着极为深刻的人生哲理。$他虽然在这个行业         |
|    4104 | Bài 93                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 从长远发展的角度来说，企业必须重视科技研发和人才培养。$从节能环保的标         |
|    4105 | Bài 94                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: LIÊN... ĐÔ/DÃ...                               |
|    4106 | Bài 95                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Có hại cho... / Có hại đối với...       |
|    4109 | Bài 98                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 关于明天的学术报告，大家已经商量好具体的发言顺序。$出行前请务必收拾好         |
|    4110 | Bài 99                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 虽然入职已经一个月了，但他还没完全熟悉内部业务流程。$关于是否接受该岗         |
|    4111 | Bài 100                              | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 面对突发的市场变化，对新员工来说确实是个巨大的挑战。$掌握两门外语，对         |
|    4112 | Bài 101                              | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ... trở lên / từ... trở lên             |
|    4114 | Bài 103                              | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: THẬM CHÍ LIÊN……ĐÔ / DÃ……                       |
|    4117 | Bài 106                              | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 听到这个令人激动的消息，大家忍不住大声欢呼起来。$会议室里原本很安静，         |
|    4118 | Bài 107                              | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 母亲亲手做的炸酱面味道非常香，全家人吃得津津有味。$那位经验丰富的老技         |
|    4135 | Bài 17                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 会议结束后，主办方安排了丰盛的午餐。$ 我们一起去附近的餐厅吃午餐吧。         |
|    4138 | Bài 20                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 我们在做决定前必须全面考虑各种因素。$学校非常重视学生德智体美劳的全面         |
|    4140 | Bài 22                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 他对古代军事历史有着浓厚的兴趣。$这个地区建有一座规模巨大的军事基地。         |
|    4146 | Bài 28                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 除夕之夜，全家人都会聚在一起吃热热闹闹的热汤圆。$ 考试前夕，同学们都         |
|    4151 | Bài 33                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 看外语电影时，我习惯参考中文字幕。$这段视频没有字幕，听起来有点吃力。         |
|    4159 | Bài 41                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这位作家花了两年的时间才完成这部长篇小说。$阅读长篇小说能够培养我们的         |
|    4162 | Bài 44                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 年轻人往往对新鲜事物充满好奇心和探索欲望。$我们应该全面地看待任何客观         |
|    4173 | Bài 1                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Hoàn toàn không / Thực sự không hề      |
|    4174 | Bài 2                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 许多珍稀野生动物因栖息地遭受破坏而濒临灭绝。$这家老字号餐厅因服务周到         |
|    4175 | Bài 3                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Có giúp ích / Có lợi ích đối với...     |
|    4179 | Bài 7                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: căn cứ vào / dựa trên... để quy hoạ     |
|    4180 | Bài 8                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这份文件的核心机密等级极高，别说基层员工，就是部门主管也无权查阅。$连         |
|    4181 | Bài 9                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: mắt thấy... sắp sửa... đến nơi rồi      |
|    4182 | Bài 10                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: vừa không... cũng không... / không.     |
|    4183 | Bài 11                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 在方案正式提交之前，我们需要再次进行全方位的论证。$在经济危机爆发之前         |
|    4184 | Bài 12                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 现代远程教育不同于传统课堂教学，它赋予了学生更高的自主性。$这家初创企         |
|    4185 | Bài 13                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Không bận tâm/để ý... mà bận tâm/để     |
|    4186 | Bài 14                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Mấu chốt nằm ở chỗ... / Điểm cốt lõ     |
|    4187 | Bài 15                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Nằm ở / Chính là / Tùy thuộc vào        |
|    4188 | Bài 16                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 本次国际学术研讨会的所有组织流程，均由该研究院负责。$这个高科技创新项         |
|    4189 | Bài 17                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Cho / Làm gì cho ai / Hướng đến đối     |
|    4190 | Bài 18                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这项全新科研成果的转化率比预估的高出许多。$如今数字技术的普及速度远比         |
|    4191 | Bài 19                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这本科普图册是专门给初学者看的启蒙读物。$该艺术展览并非专门给专业学者         |
|    4192 | Bài 20                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 长期处于高度紧张的状态下，人们很容易产生焦虑情绪。$这类概念十分抽象，         |
|    4193 | Bài 21                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: TÙNG …… KHAI THỦY / THÂN THƯỢNG                |
|    4194 | Bài 22                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 研究员必须把采集到的水质样本妥善封存，以免破坏微量元素的平衡。$组委会         |
|    4195 | Bài 23                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Ngoài... ra thì chỉ toàn là...; Hết     |
|    4198 | Bài 26                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 如果方案已经获得董事会批准，就要尽可能缩短落实周期。$企业如果要实现品         |
|    4199 | Bài 27                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 人口老龄化加剧对社会保障体系的可持续性产生了深远影响。$汇率剧烈波动对         |
|    4200 | Bài 28                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 跨国企业在制定海外经营策略时，必须充分尊重当地的文化习俗。$面对激烈的         |
|    4201 | Bài 29                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Nếu... vậy thì... / Nếu... thế thì.     |
|    4202 | Bài 30                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 除了学术研究之外，他还积极投身于公益环保事业。$除了张教授之外，大家都         |
|    4203 | Bài 31                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Bị khống chế bởi; chịu sự chi phối/     |
|    4204 | Bài 32                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 只要大家能齐心协力，任何艰难险阻都终将被克服。$只要恪守诚信底线，不论         |
|    4205 | Bài 33                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Có ý nghĩa/giá trị... đối với...        |
|    4206 | Bài 34                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: ĐỐI……HỮU DỤNG / TRỌNG YẾU                      |
|    4207 | Bài 35                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ... lại là... / ... nhưng thực tế l     |
|    4208 | Bài 36                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 政府加强了对高新技术产业的扶持力度。$企业应当重视对客户反馈意见的收集         |
|    4209 | Bài 37                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这个问题太复杂，连资深专家都感到棘手。$山路异常险峻，连最有经验的向导         |
|    4210 | Bài 38                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 因为市场调研不够充分，所以产品投放后并未引起预期反响。$因为双方在核心         |
|    4211 | Bài 39                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Có phải là... đâu / Đâu phải là...      |
|    4212 | Bài 40                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这项跨学科科研成果是由青年团队历时三年自主研发完成的。$他们是在充分听         |
|    4213 | Bài 41                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 市场上的理财产品一类保本但收益偏低，另一类高收益却伴随高风险。$现代小         |
|    4215 | Bài 43                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: đợi đến lúc/khi……                       |
|    4216 | Bài 44                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这项举措不但稳定了就业局势，而且拉动了周边区域的消费。$现代医学不但注         |
|    4218 | Bài 46                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 数字技术的普及给边远地区的教育带来了革命性变革。$贸易保护主义的抬头给         |
|    4219 | Bài 47                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 倘若没有持之以恒的毅力，任何宏伟的计划就只能沦为空想。$在关键时刻倘若         |
|    4220 | Bài 48                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 组委会将参赛作品按类别进行了细致整理，随后呈送评委审阅。$我们必须将理         |
|    4224 | Bài 52                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: dẫn đến / đến nỗi                       |
|    4225 | Bài 53                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: làm theo...; dựa theo...; theo như.     |
|    4226 | Bài 54                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: người mà...; những người...             |
|    4227 | Bài 55                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: theo... thấy; theo quan điểm của...     |
|    4228 | Bài 56                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: CHỈ HỮU …… TÀI …… / NHƯ QUẢ …… TÀI             |
|    4229 | Bài 57                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 企业如果想在竞争中生存，就必须不断进行技术创新。$如果你想彻底掌握这门         |
|    4230 | Bài 58                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 尽管方案得到了批准，但由于资金短缺，执行也遇阻。$尽管天气十分恶劣，但         |
|    4231 | Bài 59                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 学者总结了前人的失败教训，以此作为改进实验的依据。$公司设立了严格的质         |
|    4232 | Bài 60                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 任何成功都没有捷径可走，更没有不劳而获的奇迹。$这场风波中他没有任何推         |
|    4233 | Bài 61                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Nhằm / Để mà / Bằng cách...             |
|    4237 | Bài 65                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Hướng về / đối với / từ / cho...        |
|    4238 | Bài 66                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Không nhất thiết / chưa chắc / khôn     |
|    4239 | Bài 67                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 提高全民环保意识，既需要法律制度的硬性约束，也离不开宣传教育的引导。$         |
|    4240 | Bài 68                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Há chẳng phải là... sao / Chẳng phả     |
|    4241 | Bài 69                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Viết cho / gửi tặng cho...              |
|    4242 | Bài 70                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 审计报告得出的核心数据与财务部门提供的台账完全一致。$这一学术假说的验         |
|    4243 | Bài 71                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: ĐỐI ... MÃN Ý / BẤT MÃN Ý                      |
|    4244 | Bài 72                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这位老学者曾发表过多篇在国际学术界具有深远影响的论文。$该企业曾面临严         |
|    4245 | Bài 73                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Làm thế nào mới có thể... / Phải nh     |
|    4246 | Bài 74                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 他除了负责公司的战略规划外，还直接兼任海外项目的总指挥。$这项举措除了         |
|    4247 | Bài 75                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: ... vô cùng / ... hết sức / cực kỳ.     |
|    4248 | Bài 76                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Được ấn định vào / Dự kiến diễn ra      |
|    4249 | Bài 77                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | hanviet: TƯỢNG …… NHẤT DẠNG / TỰ ĐỊA                    |
|    4250 | Bài 78                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 与其在这里盲目等待，不如主动出击寻找新的商业机遇。$在实际操作经验方面         |
|    4251 | Bài 79                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 科研团队通过长达数年的对比实验，最终得出了这一科学结论。$学者通过对大         |
|    4265 | Bài 11                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 夫妻之间产生分歧很正常，但尽量不要当面吵架。$ 他们俩刚才还在大声吵架         |
|    4273 | Bài 19                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 最近几年，这座沿海小城市发生了巨大的变化。$由于沟通不足，双方在合作过         |
|    4299 | Bài 45                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 工人用铁锤将坚硬的石头彻底砸碎。$由于准备不足，他把这次重要的面试彻底         |
|    4303 | Bài 49                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 养成每天坚持读书的好习惯能开阔视野并提升素养。$ 无论生活多么艰难，父         |
|    4305 | Bài 51                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 登机前工作人员会仔细核对行李的实际重量。$新型轻质材料在减轻重量的同时         |
|    4306 | Bài 52                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 明明不是他的错却挨了批评，他心里感到非常委屈。$ 招待所条件简陋，今天         |
|    4348 | Bài 1                                | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 警方经过缜密调查，终于破获了这起跨国诈骗案件。$法院将于下周公开审理这         |
|    4361 | Bài 14                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 进图书馆之前，读者需将随身大件物品存放在存包柜中。$易燃易爆危险品严禁         |
|    4363 | Bài 16                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 该博物馆安装了最先进的防盗报警系统。$未经许可，严禁盗用他人名义发表言         |
|    4370 | Bài 23                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 主人准备了一桌丰盛的宴席款待远道而来的贵宾。$除夕之夜，全家人围坐在一         |
|    4378 | Bài 31                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 他们夫妻俩勤劳朴实，精打细算，把日子过得红红火火。$ 结婚之后就得踏踏         |
|    4384 | Bài 37                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 两位学者的深度交流碰撞出了智慧的火花。$电流短路瞬间迸发出耀眼的火花。         |
|    4386 | Bài 39                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这座纪念馆内陈列着该科学家生前使用过的大量手稿与实验仪器。$为了弘扬革         |
|    4390 | Bài 43                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 集合训练结束后，教官下达了原地解散的指令。$由于成员志向不合，这支成立         |
|    4394 | Bài 47                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 在制作蛋糕糊时，必须将面粉与牛奶充分搅拌均匀，避免产生颗粒。$病人经过         |
|    4400 | Bài 53                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 她一手拎着沉重的手提箱，一手拿着登机牌匆忙赶往登机口。$爷爷每天清晨都         |
|    4417 | Bài 70                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 这种新型面料触感极其柔软，透气性也很强。$瑜伽练习有助于保持身体的柔软         |
|    4420 | Bài 73                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 企业必须严格把控产品质量，切不可为了短期利益而损害长久积累的商业声誉。         |
|    4426 | Bài 79                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 演员通过细腻入微的表演，在荧幕上成功塑造了一位深明大义的英雄母亲。$家         |
|    4430 | Bài 83                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 由于具有极佳的导电性，铜被广泛应用于电气与通讯工程中。$这件商周时期的         |
|    4433 | Bài 86                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | example_jp: 该银行在全国拥有上万个营业网点，方便客户办理业务。$为了提高物流效率，         |
|    4452 | Bài 105                              | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | translation_vi: Hội chợ triển lãm; cuộc triển lãm       |
|    6145 | Bài 002                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: industry (n): ngành công nghiệp/lĩn        |
|    6147 | Bài 004                              | En4Everyone (`13ff54d7...`)          |    19 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: (enough) (det/adv): đủ; sufficientl        |
|    6149 | Bài 006                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: ready (adj): sẵn sàng; readiness (n        |
|    6151 | Bài 008                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: eco-friendliness (n): tính thân thi        |
|    6154 | Bài 011                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: surprised (adj): ngạc nhiên; surpri        |
|    6167 | Bài 01                               | En4Everyone (`13ff54d7...`)          |    30 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: sample (n): mẫu; sample (v): lấy mẫ        |
|    6168 | Bài 02                               | En4Everyone (`13ff54d7...`)          |    30 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: retain (v): giữ lại; retention (n):        |
|    6170 | Bài 04                               | En4Everyone (`13ff54d7...`)          |    30 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: exponent (n): số mũ; exponentiation        |
|    6171 | Bài 05                               | En4Everyone (`13ff54d7...`)          |    30 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: complaint (n): lời/phần khiếu nại;         |
|    6174 | Bài 08                               | En4Everyone (`13ff54d7...`)          |    30 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Meaning: tư thế/mức độ an ninh tổng thể (tìn            |
|    6182 | Bài 1                                | En4Everyone (`13ff54d7...`)          |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: pencil (n): bút chì; pencil (v): vi        |
|    6187 | Bài 6                                | En4Everyone (`13ff54d7...`)          |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: stair (n): bậc thang; stairs (n): c        |
|    6190 | Bài 1                                | En4Everyone (`13ff54d7...`)          |    40 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Word Family: associate (n): cộng sự/nhân viên; a        |
|    6859 | 6. Luyện gõ - Gõ chép chính tả (D... | Gõ chép chính tả (`bb5f70a3...`)     |     6 |    Tier 2   | FAKE_1_ELEM_ARRAY, RAW_SCAL... | Answer: Last Saturday, I visited the local              |

### Tier 1: Minor Formatting & Scalar Delimiter Decks (741 Decks)

| Deck ID | Deck Name                            | NoteType Name (ID)                   | Notes | Health Tier | Issue Codes      | Representative Evidence Sample                          |
| ------: | :----------------------------------- | :----------------------------------- | ----: | :---------: | :--------------- | :------------------------------------------------------ |
|       2 | ChungBechN1__言葉__Bài 01              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 当面の課題は、対立する両者の関係を調整すること。                    |
|     383 | Bài 1                                | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: schedule (n): 予定; schedule (v): 予定を        |
|     416 | Bài 001                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | meaning_jp: 害虫・害獣を取り除くこと                                |
|     418 | Bài 003                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | meaning_vi: bố cục tranh/chụp                           |
|     419 | Bài 004                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | usage_jp: 技術・経営・行政で一般的。                                 |
|     420 | Bài 005                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | additional_note_jp: 応募する・申し込むとほぼ同じ意味で、ややカジュアルな響き        |
|     421 | Bài 006                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | usage_jp: 口座・契約・名義変更など法律や事務処理で多用される                     |
|     422 | Bài 007                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | additional_note_vi: So sánh nhanh: 散布 là rải/phun rộng, |
|     426 | Bài 011                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | meaning_vi: Tính/ hành vi thô bạo, nguy hiểm.           |
|     427 | Bài 012                              | Flama Standard Vocabulary (`e2f31... |    58 |    Tier 1   | RAW_SCALAR_DELIM | additional_note_jp: 比較: 説明は一般, 釈明は疑い・非難を受けたとき。          |
|     428 | Bài 013                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | additional_note_vi: So sánh nhanh: 犯人 là thủ phạm, 悪者 l |
|     429 | Bài 014                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 心臓の移植手術が成功した。$このアプリをLinux向けに移植した。           |
|     430 | Bài 015                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | meaning_jp: 他とは違う、その組織や人だけのやり方であること。                    |
|     431 | Bài 016                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 年月を隔てて、ようやく当時の真相が分かった。                      |
|     433 | Bài 018                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 古い船が少しずつ沈下していきました。$大雨の後、地盤が沈下しました。          |
|     442 | Bài 027                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | additional_note_vi: Đồng nghĩa gần: 却下する。So sánh nhanh: |
|     443 | Bài 028                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | meaning_jp: 物価が継続的に下落し、景気が停滞しやすい状態。                     |
|     445 | Bài 030                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | additional_note_jp: 類義: 無駄遣い$対義: 節約                     |
|     448 | Bài 033                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | additional_note_jp: 類: 人の姿, 人通り／比較: 人通りは人の往来の多さ。        |
|     449 | Bài 034                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 大雨で川が氾濫しました。$ネット上には偽情報が氾濫しています。             |
|     450 | Bài 035                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | usage_jp: ホチキスで綴じる・製本して綴じる                              |
|     451 | Bài 036                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 手続きを簡略し、申請時間を短縮しました。                        |
|     452 | Bài 037                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 紙を半分に折り返してください。$予定より早く折り返して会社に戻りました         |
|     453 | Bài 038                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | usage_jp: 名/サ変, 格闘する, 格闘技, 問題と格闘する                      |
|     454 | Bài 039                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | meaning_vi: Việc đảm nhiệm điều hành tiến trình         |
|     456 | Bài 041                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 淡いピンクの花が咲いていました。$淡い期待を抱いて待っています。            |
|     457 | Bài 042                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: ご尽力いただき、誠にありがとうございます。                       |
|     458 | Bài 043                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 彼女はかろやかな足取りで階段を上った。$問題が解決して気持ちがかろやか         |
|     460 | Bài 045                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | meaning_jp: ある人の目の前、またはその場にいるところ。                       |
|     461 | Bài 046                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 規約違反が確認された場合、制裁を科します。                       |
|     462 | Bài 047                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 庭の花を少し摘んで飾った。$細かいミスを摘まれると作業が進まない。           |
|     465 | Bài 050                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 不運が重なり、計画が延期になりました。                         |
|     466 | Bài 051                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 報告書の付録に参考資料をまとめました。$雑誌の付録が目当てで購入しまし         |
|     469 | Bài 054                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 音声はアナログ信号として扱われます。$アナログな管理だとミスが増えやす         |
|     470 | Bài 055                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | meaning_jp: 講演や演説、音楽などを聞くために集まった人々。                     |
|     471 | Bài 056                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: このシステムは設定の融通が利くので使いやすい。$急な出費があり、友人に         |
|     472 | Bài 057                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: この植物から有効成分を抽出します。$条件に合う顧客データだけを抽出して         |
|     474 | Bài 059                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: ボールが床で高く弾んだ。$旅行の話を聞くと心が弾む。$久しぶりに会った         |
|     475 | Bài 060                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 必要に応じて、資料を適宜修正してください。                       |
|     476 | Bài 061                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 問題の原因を理解するには、まず内部機構を知る必要がある。                |
|     478 | Bài 063                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | usage_jp: 「体調を崩す」と近いが、「調子を崩す」は成績やペースにも使える。              |
|     479 | Bài 064                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 試験が終わったとたんに気が緩んで、風邪をひいてしまった。                |
|     480 | Bài 065                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | meaning_jp: 相手を怒らせたり、行動を起こさせたりするために、わざと刺激すること。          |
|     481 | Bài 066                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 知っているくせに, 彼はとぼけて何も知らないふりをした。$祖父は最近少         |
|     482 | Bài 067                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 薬を飲んだら, しばらくして頭痛が治まった。$名君のもとで国はよく治ま         |
|     483 | Bài 068                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | additional_note_jp: 「質」よりも、商品やサービスの評価として使われやすい。         |
|     484 | Bài 069                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | meaning_jp: 上下や優劣がなく、互いに同じ立場で向き合う関係。                    |
|     485 | Bài 070                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 手っ取り早く確認したいなら、まず公式サイトを見るのがいい。               |
|     486 | Bài 071                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 無理をしたせいで、けがの症状が悪化した。                        |
|     487 | Bài 072                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 約束を守れず, 皆の前で面目を失った。$このたびはご迷惑をおかけして,         |
|     490 | Bài 075                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 彼は怪力の持ち主で、重い荷物も一人で運べる。                      |
|     492 | Bài 077                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | additional_note_jp: 「愛を深める」より、少しずつ大切に育てる感じが強い。          |
|     494 | Bài 079                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 彼は時間にルーズなので、待ち合わせではいつも困ります。                 |
|     495 | Bài 080                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | meaning_jp: 変化が少なく、同じような状態が続くこと。                        |
|     502 | Bài 087                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 朝早かったので、駅前を歩く人はまだまばらだった。                    |
|     504 | Bài 089                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 作業を分担したおかげで、予定より早く終わった。                     |
|     505 | Bài 090                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | additional_note_jp: 類義表現は契約を結ぶ、協定は組織間の取り決めに多い。          |
|     507 | Bài 092                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | meaning_vi: làm cho thứ đang tiếp diễn bị ngắt          |
|     509 | Bài 094                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 初心者にはありがちなミスなので、あまり気にしなくていい。                |
|     513 | Bài 098                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 不安に駆られて、何度も家族に連絡した。                         |
|     514 | Bài 099                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | meaning_jp: はっきりしていて、あいまいさがないこと。                        |
|     515 | Bài 100                              | Flama Standard Vocabulary (`e2f31... |    58 |    Tier 1   | RAW_SCALAR_DELIM | usage_vi: Nghĩa 1 dùng cho đồ vật, dáng vẻ.$N           |
|     521 | Bài 106                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | meaning_jp: 構造や立場などが弱く、外からの影響を受けやすいこと。                  |
|     522 | Bài 107                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: この映画の主題歌は、今でも多くの人に愛される名曲です。                 |
|     524 | Bài 109                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 締切寸前になって、重大なミスが見つかりました。                     |
|     530 | Bài 115                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 障害発生時に備えて、監視態勢を整えています。                      |
|     532 | Bài 117                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 彼は新しい制度に強く抵抗した。$この部品の抵抗値を測定してください。          |
|     533 | Bài 118                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | additional_note_jp: 類語: 探求、検討。模索は不確かな中で探る感じが強い。         |
|     537 | Bài 122                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 決勝点が入った瞬間、観客は大きく興奮した。                       |
|     538 | Bài 123                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 遠くのビルの上で、赤い光が瞬いていた。                         |
|     541 | Bài 126                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: プログラムでは、変更しない値を定数として定義しておくと管理しやすい。          |
|     546 | Bài 131                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 会議の前に少し雑談して、場の空気を和らげた。                      |
|     547 | Bài 132                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 彼は厳しい質問を受けても、微動だにしませんでした。                   |
|     552 | Bài 137                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 社員には、業務上知った情報を守る義務があります。                    |
|     555 | Bài 140                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 事故の後、警察が周辺道路で検問を行った。                        |
|     556 | Bài 141                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | meaning_jp: 高い能力、学歴、地位などを持つ選ばれた人々。                      |
|     557 | Bài 142                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 後半に二点を取り、チームは逆転勝利を収めた。                      |
|     558 | Bài 143                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 小さな木片が、夕方の海で波に漂っていた。                        |
|     560 | Bài 145                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 台風は明日の朝、九州に上陸する見込みです。$海外で人気のサービスが、つ         |
|     561 | Bài 146                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 物語の最後で、主人公は悪人を懲らしめました。                      |
|     563 | Bài 148                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: ログの内容から、障害の原因をある程度推測できる。                    |
|     565 | Bài 150                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 新人でも、能動的に質問する姿勢が評価されます。                     |
|     566 | Bài 151                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 講師は参加者に、働く意味について問いかけました。                    |
|     567 | Bài 152                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 就業時間中は、私用の電話を控えてください。                       |
|     568 | Bài 153                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 北海道では酪農が盛んで、新鮮な牛乳が多く生産されている。                |
|     569 | Bài 154                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 会社は次世代のリーダーを養成するため、研修制度を整えた。                |
|     570 | Bài 155                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 彼は健康上の理由で、社長の座を退いた。                         |
|     571 | Bài 156                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: ログには、不可解なエラーが繰り返し記録されていた。                   |
|     572 | Bài 157                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 店では日本酒を木の升に入れて出してくれた。$祖母は一升の米を丁寧に量っ         |
|     573 | Bài 158                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 所用のため、本日の会議には出席できません。                       |
|     574 | Bài 159                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 彼女は弁論大会で、環境問題について力強く主張した。                   |
|     575 | Bài 160                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: この祭りは、この地域特有の伝統行事です。                        |
|     576 | Bài 161                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: この製品は独自の技術で、従来品と一線を画している。                   |
|     578 | Bài 163                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 彼は上司の言葉を何度も反芻し、自分の課題を考え直した。                 |
|     579 | Bài 164                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 忙しくて、午前中は新しい資料作成に手をつけられなかった。                |
|     580 | Bài 165                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 報告書から重要な部分を抜粋して、会議資料に載せた。                   |
|     581 | Bài 166                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 何度も挑戦したので、今回はようやく諦めがついた。                    |
|     582 | Bài 167                              | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 丘の上に立つと、町全体の見晴らしがよかった。                      |
|     583 | Bài 168                              | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 大雨の影響で、一部の電車が運行を見合わせています。                   |
|     585 | Bài 170                              | Flama Standard Vocabulary (`e2f31... |    51 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 彼は用心深いので、契約書を何度も確認してから署名する。                 |
|    1337 | Bài 04                               | Flama Standard Vocabulary (`e2f31... |    30 |    Tier 1   | RAW_SCALAR_DELIM | meaning_jp: 規則、理論、条件、形式などを具体的な対象Bに適用することを表す。            |
|    1340 | Bài 001                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: refreshness (n): sự tươi mới; fresh        |
|    1342 | Bài 003                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: prohibition (n): sự cấm; prohibited        |
|    1344 | Bài 005                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: collect (v): thu thập; collective (        |
|    1346 | Bài 007                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: arbitrariness (n): tính tùy tiện; a        |
|    1348 | Bài 009                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: In TOEIC, material often means “tra        |
|    1349 | Bài 010                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: social (adj): xã hội; media (n): ph        |
|    1351 | Bài 012                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: expire (v): hết hạn; expiration (n)        |
|    1352 | Bài 013                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: profession (n): nghề nghiệp; profes        |
|    1353 | Bài 014                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: researcher (n): nhà nghiên cứu; res        |
|    1354 | Bài 015                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Example: Please place the label on the right            |
|    1355 | Bài 016                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Example: Please add your signature at the bo            |
|    1356 | Bài 017                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: operation (n): sự vận hành; operato        |
|    1357 | Bài 018                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: spacious (adj): rộng rãi; spacing (        |
|    1358 | Bài 019                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: product (n): sản phẩm; production (        |
|    1359 | Bài 020                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: machine (v): gia công bằng máy; mac        |
|    1360 | Bài 021                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Example: The software can perform complex ca            |
|    1361 | Bài 022                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Example: We received an order for 200 units.            |
|    1362 | Bài 023                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: describe (v): mô tả; description (n        |
|    1363 | Bài 024                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: final (adj/n): cuối cùng, vòng chun        |
|    1364 | Bài 025                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: average (v): tính trung bình; avera        |
|    1365 | Bài 026                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: upward (adj/adv): hướng lên; upward        |
|    1366 | Bài 027                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: review (n/v): sự xem xét, xem xét;         |
|    1367 | Bài 028                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: ease (n/v): sự dễ dàng, làm giảm; e        |
|    1368 | Bài 029                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: change (n/v): sự thay đổi, thay đổi        |
|    1371 | Bài 02                               | Flama Standard Vocabulary (`e2f31... |    48 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 平素は格別のご高配を賜り、厚く御礼申し上げます。                    |
|    1372 | Bài 03                               | Flama Standard Vocabulary (`e2f31... |    56 |    Tier 1   | RAW_SCALAR_DELIM | meaning_jp: 極端な例を挙げて、それさえも同じであることを示す                    |
|    1375 | Bài 06                               | Flama Standard Vocabulary (`e2f31... |    59 |    Tier 1   | RAW_SCALAR_DELIM | meaning_jp: 沈むこと、下がること                                  |
|    1376 | Bài 07                               | Flama Standard Vocabulary (`e2f31... |    61 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 彼は若い頃、小説を読み漁っていた。                           |
|    1381 | Bài 01                               | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: オリンピックに触発され、スポーツ用品を買う消費者が増える。               |
|    1382 | Bài 02                               | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | additional_note_jp: 合：強制労働、強制送還。自発的の対義語。                |
|    1384 | Bài 04                               | Flama Standard Vocabulary (`e2f31... |    61 |    Tier 1   | RAW_SCALAR_DELIM | meaning_jp: 機械などを用いて、隠されているものを探す。                       |
|    1385 | Bài 05                               | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 公正な裁判のおかげで、人権が守られる。                         |
|    1386 | Bài 06                               | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | additional_note_jp: 放置：Bỏ mặc không xử lý dù biết có vấ |
|    1389 | Bài 09                               | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 肉が柔らかく煮込んであり、口に入れるととろけるようだ。; 彼女の甘い言         |
|    1390 | Bài 10                               | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | meaning_jp: 思ったより簡単ですぐ終わり、つまらない                         |
|    1391 | Bài 11                               | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 合格するかもと淡い期待を抱いたが、やはり不合格だった。                 |
|    1394 | Bài 14                               | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | meaning_vi: ① Thẫn thờ, đầu óc trống rỗng. <br>         |
|    1395 | Bài 15                               | Flama Standard Vocabulary (`e2f31... |    60 |    Tier 1   | RAW_SCALAR_DELIM | meaning_vi: ① Tiếng sột soạt khi vật khô chạm n         |
|    1396 | Bài 16                               | Flama Standard Vocabulary (`e2f31... |    61 |    Tier 1   | RAW_SCALAR_DELIM | meaning_vi: ① Nói nhỏ, khó nghe <br>② Thức ăn k         |
|    1397 | Bài 17                               | Flama Standard Vocabulary (`e2f31... |    41 |    Tier 1   | RAW_SCALAR_DELIM | meaning_vi: ① Thẳng. <br>② Không pha trộn. <br>         |
|    1419 | Bài 01                               | Flama Standard Vocabulary (`e2f31... |    94 |    Tier 1   | RAW_SCALAR_DELIM | additional_note_jp: <ul><li><div><strong>Đồng nghĩa / g |
|    1420 | Bài 02                               | Flama Standard Vocabulary (`e2f31... |    84 |    Tier 1   | RAW_SCALAR_DELIM | meaning_jp: Nに劣る → より弱い、比較で使う                           |
|    1423 | Bài 05                               | Flama Standard Vocabulary (`e2f31... |    95 |    Tier 1   | RAW_SCALAR_DELIM | meaning_jp: 試合に勝ち、雪辱を果たす                                |
|    1434 | Bài 16                               | Flama Standard Vocabulary (`e2f31... |    57 |    Tier 1   | RAW_SCALAR_DELIM | additional_note_jp: 償う：Bồi thường, đền bù, chuộc lại lỗ |
|    1440 | Bài 1                                | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: vacant (adj): trống; vacancy (n): v        |
|    1441 | Bài 2                                | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: satisfy (v): làm hài lòng; satisfie        |
|    1442 | Bài 3                                | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Example: The software is affordable; further            |
|    1443 | Bài 4                                | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: reinforce (v): củng cố; reinforceme        |
|    1444 | Bài 5                                | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: resign (v): từ chức; resignation (n        |
|    1445 | Bài 6                                | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: reveal (v): tiết lộ; revelation (n)        |
|    1446 | Bài 7                                | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: take over (v): tiếp quản; takeover         |
|    1449 | Family                               | En4Everyone (`6b2a8fec...`)          |    25 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: parent (n): cha mẹ; parental (adj):        |
|    1452 | Bài 1                                | En4Everyone (`6b2a8fec...`)          |    65 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: parrot (n): vẹt; parrotlike (adj):         |
|    1454 | Bài 2                                | En4Everyone (`6b2a8fec...`)          |    40 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: nappie (n): tã; napery (n): khăn bà        |
|    1455 | Bài 3                                | En4Everyone (`6b2a8fec...`)          |    40 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: stool (n): stool; barstool (n): bar        |
|    1456 | Bài 4                                | En4Everyone (`6b2a8fec...`)          |    40 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: back (n): lưng; pack (v): đóng gói;        |
|    1457 | Bài 5                                | En4Everyone (`6b2a8fec...`)          |    40 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: sell (v): bán; sales (n): doanh số,        |
|    1459 | Bài 7                                | En4Everyone (`6b2a8fec...`)          |    40 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: draw (v): kéo; drawer unit (n): tủ         |
|    1460 | Bài 8                                | En4Everyone (`6b2a8fec...`)          |    28 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: exit (v): thoát ra/rời đi; exiting         |
|    1462 | Bài 2                                | En4Everyone (`6b2a8fec...`)          |    22 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: judge (v): phán xét; judgment (n):         |
|    1466 | Bài 03                               | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: use case (n): trường hợp sử dụng; u        |
|    1469 | Bài 06                               | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: concern (n/v): lo ngại/liên quan; c        |
|    1470 | Bài 07                               | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: circumstance (n): hoàn cảnh; circum        |
|    1472 | Bài 09                               | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: circumstance (n): hoàn cảnh; circum        |
|    1473 | Bài 10                               | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: calibration (n): sự hiệu chỉnh cali        |
|    1474 | Bài 2                                | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: in person (adv. phrase): 直接; person        |
|    1475 | Bài 3                                | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: quite a few (quantifier): かなり多くの; f        |
|    1476 | Bài 4                                | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: author (n./v.): 著者; 執筆する; authorshi        |
|    1822 | Bài 8                                | En4Everyone (`6b2a8fec...`)          |    29 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: bracket (v): xếp nhóm; bracket (n):        |
|    1823 | Bài 9                                | En4Everyone (`6b2a8fec...`)          |    29 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: appear (v): xuất hiện hoặc có vẻ; a        |
|    1824 | Bài 10                               | En4Everyone (`6b2a8fec...`)          |    29 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: hesitate (v): do dự; hesitation (n)        |
|    1825 | Bài 11                               | En4Everyone (`6b2a8fec...`)          |    29 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: commission (n): hoa hồng hoặc ủy ba        |
|    1826 | Bài 12                               | En4Everyone (`6b2a8fec...`)          |    29 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: cord (n): dây; corded (adj): có dây        |
|    1827 | Bài 13                               | En4Everyone (`6b2a8fec...`)          |    32 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: act (v): hành động; action (n): hàn        |
|    1828 | Bài 14                               | En4Everyone (`6b2a8fec...`)          |    29 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: desire (n/v): mong muốn; desirable         |
|    1829 | Bài 15                               | En4Everyone (`6b2a8fec...`)          |    29 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: land (n/v): đất hoặc hạ cánh; landf        |
|    1830 | Bài 16                               | En4Everyone (`6b2a8fec...`)          |    33 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: shell (n): vỏ; shellfish (n): hải s        |
|    1831 | Bài 17                               | En4Everyone (`6b2a8fec...`)          |    31 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: project (v): dự báo hoặc trình chiế        |
|    1832 | Bài 18                               | En4Everyone (`6b2a8fec...`)          |    32 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: precise (adj): chính xác; precisely        |
|    1833 | Bài 19                               | En4Everyone (`6b2a8fec...`)          |    31 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: discretion (n): quyền tự quyết; dis        |
|    1835 | Bài 1                                | En4Everyone (`6b2a8fec...`)          |    10 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: educate (v); educational (adj); edu        |
|    1836 | Bài 2                                | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: achievement (n); achievable (adj)          |
|    1837 | Bài 3                                | En4Everyone (`6b2a8fec...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: evaluation (n); evaluative (adj)           |
|    1838 | Bài 030                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: limit (n/v): giới hạn, hạn chế; lim        |
|    1839 | Bài 031                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: drop (v/n): làm rơi, sự giảm; drop-        |
|    1840 | Bài 032                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: receive (v): nhận; recipient (n): n        |
|    1841 | Bài 033                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: respect (n/v): sự tôn trọng, tôn tr        |
|    1842 | Bài 034                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: cater (v): cung cấp đồ ăn; catering        |
|    1843 | Bài 035                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: infuse (v): truyền vào, pha; infusi        |
|    1844 | Bài 036                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: astound (v): làm kinh ngạc; astound        |
|    1845 | Bài 037                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: metric (adj): thuộc hệ mét; ton (n)        |
|    1846 | Bài 038                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: external (adj): bên ngoài; external        |
|    1847 | Bài 039                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: survey (n/v): khảo sát, khảo sát; s        |
|    1848 | Bài 040                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: reimburse (v): hoàn trả; reimbursem        |
|    1849 | Bài 041                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Example: The new unit is energy-efficient; f            |
|    1850 | Bài 042                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: detail (n/v): chi tiết, mô tả chi t        |
|    1851 | Bài 043                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: money (n): tiền; back (adv/adj/n):         |
|    1852 | Bài 044                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: escape (n/v): sự thoát, thoát khỏi;        |
|    1853 | Bài 045                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: ski (n/v): môn trượt tuyết, trượt t        |
|    1854 | Bài 046                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: adhere (v): tuân thủ, bám dính; adh        |
|    1855 | Bài 047                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: high (adj/adv): cao; light (n/v): á        |
|    1856 | Bài 048                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: wrinkle (n/v): nếp nhăn, làm nhăn;         |
|    1857 | Bài 049                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: encourage (v): khuyến khích; encour        |
|    1858 | Bài 050                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: deflate (v): làm xẹp; deflation (n)        |
|    1859 | Bài 051                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: grant (n/v): khoản tài trợ, cấp; gr        |
|    1860 | Bài 052                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: prime (adj/n/v): hàng đầu, số nguyê        |
|    1861 | Bài 053                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: promote (v): quảng bá, thăng chức;         |
|    1862 | Bài 054                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: reduce (v): giảm; reduced (adj): đư        |
|    1863 | Bài 055                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: trigger (n/v): yếu tố kích hoạt, kí        |
|    1864 | Bài 056                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: decade (n): thập kỷ; decade-long (a        |
|    1865 | Bài 057                              | En4Everyone (`6b2a8fec...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: item (n): mục, món hàng; itemize (v        |
|    1866 | Bài 058                              | En4Everyone (`6b2a8fec...`)          |    22 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: afford (v): có khả năng chi trả; af        |
|    1867 | Bài 5                                | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: display (n/v): 表示・展示する; displayed (        |
|    1868 | Bài 6                                | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: lead (n/v): 主導・導く; leader (n): 指導者;        |
|    1869 | Bài 7                                | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: distribute (v): 配布する; distribution         |
|    1870 | Bài 8                                | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: temporary (adj.): 一時的な; temporarily        |
|    1871 | Bài 9                                | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: former (adj.): 以前の・前者の; formerly (a        |
|    1872 | Bài 10                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: obtain (v.): 得る; obtainable (adj.):        |
|    1873 | Bài 11                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: solve (v.): 解決する; solution (n.): 解決        |
|    1874 | Bài 12                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: preserve (v.): 保存・保護する; preservatio        |
|    1875 | Bài 13                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: paper (n.): 紙・書類; paperwork (n.): 書        |
|    1876 | Bài 14                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: store (v.): 保管する；storage (n.): 保管、収        |
|    1877 | Bài 15                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: profile (n./v.): プロフィール／人物を紹介する；pro        |
|    1878 | Bài 16                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: conservation (n.): 保全／節約；conserve (        |
|    1880 | Bài 18                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: situated (adj.): 位置している; situate (v        |
|    1882 | Bài 20                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: stable (adj.): 安定した; stability (n.)        |
|    1885 | Bài 23                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: bid (n./v.): 入札・入札する; bidder (n.):         |
|    1886 | Bài 24                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: aspire (v.): 熱望する; aspiring (adj.):        |
|    1887 | Bài 25                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: compatible (adj.): 互換性のある；compatibi        |
|    1889 | Bài 27                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: meticulously (adv.): 綿密に；meticulous        |
|    1891 | Bài 29                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: pot (n.): 鍋・鉢; potted (adj.): 鉢植えの;        |
|    1893 | Bài 31                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: present (v.): 提示する; presentation (n        |
|    1895 | Bài 33                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: ambassador (n.): 大使; ambassadorial         |
|    1896 | Bài 34                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Example: The software is reliable; moreover,            |
|    1897 | Bài 35                               | En4Everyone (`6b2a8fec...`)          |    39 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: hold (v./n.): 持つ・開催する・保留; holder (n        |
|    1898 | Bài 36                               | En4Everyone (`6b2a8fec...`)          |    41 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: delivery (n.): 配達・話し方; deliver (v.)        |
|    2412 | Bài 20                               | En4Everyone (`6b2a8fec...`)          |    35 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: familiar (adj): quen thuộc; familia        |
|    2413 | Bài 21                               | En4Everyone (`6b2a8fec...`)          |    40 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: diverse (adj): đa dạng; diversity (        |
|    3320 | Bài 2 Cảm ơn bạn                     | Flama Standard Vocabulary (`e2f31... |     9 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们一起读。$我和他一起去学校。$我们一起学汉语吧。                  |
|    3321 | Bài 3 Bạn tên là gì                  | Flama Standard Vocabulary (`e2f31... |    13 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我是美国人。$他不是美国人。$她是我的美国朋友。                    |
|    3322 | Bài 4 Cô ấy là giáo viên tiếng Tr... | Flama Standard Vocabulary (`e2f31... |    12 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 李月是我的老师。$这是谁的书？是我的。                         |
|    3323 | Bài 5 Con gái cô ấy năm nay 20 tuổi  | Flama Standard Vocabulary (`e2f31... |    19 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我爷爷今年七十岁。$这是我爷爷。                            |
|    3324 | Bài 6 Tôi biết nói tiếng Trung       | Flama Standard Vocabulary (`e2f31... |    16 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 中国菜很好吃。$这个菜不好吃。                             |
|    3325 | Bài 7 Hôm nay là ngày mấy            | Flama Standard Vocabulary (`e2f31... |    14 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 今天9月1号。$今天星期几？                              |
|    3326 | Bài 8 Tôi muốn uống trà              | Flama Standard Vocabulary (`e2f31... |    15 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这个杯子多少钱？$我想买一个杯子。$那个杯子很漂亮。                  |
|    3328 | Bài 10 Tôi có thể ngồi đây không     | Flama Standard Vocabulary (`e2f31... |    16 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 桌子上有什么？$书在椅子上。                              |
|    3329 | Bài 11 Bây giờ là mấy giờ            | Flama Standard Vocabulary (`e2f31... |    12 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 现在是六点三十分。$ 还有十分钟。                           |
|    3330 | Bài 12 Ngày mai thời tiết thế nào    | Flama Standard Vocabulary (`e2f31... |    16 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 天气太热了，我不爱吃饭。$妹妹很爱吃苹果。                       |
|    3331 | Bài 13 Anh ấy đang học nấu món ăn... | Flama Standard Vocabulary (`e2f31... |    16 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 大卫在看书。$大卫也在看书吗？$他是大卫，他是美国人。                 |
|    3332 | Bài 14 Cô ấy đã mua rất nhiều quầ... | Flama Standard Vocabulary (`e2f31... |    20 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 她买了不少衣服。$我想去买一件新衣服。$这件衣服太漂亮了！               |
|    3333 | Bài 15 Tôi đi máy bay đến            | Flama Standard Vocabulary (`e2f31... |    10 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 很高兴认识您！$我不认识那个汉字。                           |
|    3335 | Bài 2 Cảm ơn bạn                     | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: A: 谢谢你！ B: 不客气！$A: 谢谢老师！ B: 不客气，请坐。         |
|    3336 | Bài 3 Bạn tên là gì                  | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 李月是老师。$我不是美国人，我是中国人。$他是我的好朋友。               |
|    3339 | Bài 6 Tôi biết nói tiếng Trung       | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 中国菜很好吃。$今天天气不冷。$她很高兴。                       |
|    3340 | Bài 7 Hôm nay là ngày mấy            | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我的汉语老师33岁。$明天星期三。$今天9月1号。                   |
|    3341 | Bài 8 Tôi muốn uống trà              | Flama Standard Vocabulary (`e2f31... |     7 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 三个老师$五个学生$一个杯子                              |
|    3343 | Bài 10 Tôi có thể ngồi đây không     | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 请喝茶。$请坐，老师马上来。$请不要说话。                       |
|    3344 | Bài 11 Bây giờ là mấy giờ            | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我星期一去北京。$李老师上午八点去学校。$妈妈六点做饭。                |
|    3345 | Bài 12 Ngày mai thời tiết thế nào    | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 你的汉语怎么样？$你妈妈身体怎么样？$明天天气怎么样？                 |
|    3348 | Bài 15 Tôi đi máy bay đến            | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 明天是2014年5月11号。$今天是九月十日，星期五。$2023年8月         |
|    3360 | Bài 1 Đi Bắc Kinh du lịch vào thá... | Flama Standard Vocabulary (`e2f31... |    14 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 下午我们一起去踢足球吧。$我哥哥最喜欢踢足球。                     |
|    3361 | Bài 2 Tôi thức dậy lúc 6 giờ mỗi ... | Flama Standard Vocabulary (`e2f31... |    16 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 你怎么知道这么多啊？$我不知道明天要考试。                       |
|    3362 | Bài 3 Cái màu đỏ bên trái là của tôi | Flama Standard Vocabulary (`e2f31... |    21 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这本书太有趣了，我看了爱不释手。$他对这个新手机爱不释手，天天拿着玩。         |
|    3363 | Bài 4 Công việc này là do anh ấy ... | Flama Standard Vocabulary (`e2f31... |    16 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 电话是谁打的？$我想给妈妈打电话。                           |
|    3364 | Bài 5 Cứ mua chiếc này đi            | Flama Standard Vocabulary (`e2f31... |    18 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这两天有点儿累，不去打球了。$今天天气有点儿冷，多穿点儿衣服吧。$这件         |
|    3365 | Bài 6 Sao bạn không ăn nữa           | Flama Standard Vocabulary (`e2f31... |    19 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 因为他每天跑步，所以身体很好。 $ 身体不舒服，今天不能去跑步。            |
|    3366 | Bài 7 Nhà bạn cách công ty có xa ... | Flama Standard Vocabulary (`e2f31... |    13 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 走几分钟就到了。$我家离学校很近，我每天走路去。$太晚了，我该走了。          |
|    3367 | Bài 8 Để tôi suy nghĩ rồi nói cho... | Flama Standard Vocabulary (`e2f31... |    11 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 你等等我，好吗？$我每天在学校门口等你。$请等一下，老师马上来。            |
|    3369 | Bài 10 Đừng tìm nữa, điện thoại ở... | Flama Standard Vocabulary (`e2f31... |    12 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 医生说吃药后两个小时不要喝茶。$你生病了，一定要按时吃药。$我已经吃药         |
|    3370 | Bài 11 Anh ấy lớn hơn tôi 3 tuổi     | Flama Standard Vocabulary (`e2f31... |    13 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 左边这个看报纸的女孩子是你姐姐吗？$这个小孩子真可爱。$王老师有两个孩         |
|    3371 | Bài 12 Bạn mặc ít áo quá             | Flama Standard Vocabulary (`e2f31... |    13 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 早睡早起身体好。$医生让我每天早睡早起。$他从小就养成了早睡早起的好习         |
|    3372 | Bài 13 Cửa đang mở kìa               | Flama Standard Vocabulary (`e2f31... |    13 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 那个手里拿着铅笔的是谁？$我买了两支铅笔。$考试的时候请用铅笔写。           |
|    3373 | Bài 14 Bạn đã xem bộ phim đó chưa    | Flama Standard Vocabulary (`e2f31... |    13 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们周末一起去北京玩儿玩儿吧。$孩子们正在房间里玩儿玩具。               |
|    3374 | Bài 15 Năm mới sắp đến rồi           | Flama Standard Vocabulary (`e2f31... |     8 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 今天是12月20日。$ 明天是我的生日，你来吗？                    |
|    3375 | Bài 1 Đi Bắc Kinh du lịch vào thá... | Flama Standard Vocabulary (`e2f31... |     8 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我想买几本书。$车上有十几个人。$学校里有几十个老师。                 |
|    3378 | Bài 4 Công việc này là do anh ấy ... | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这本书是我买的。$晚饭是妈妈做的。$电话不是他打的，是我打的。             |
|    3379 | Bài 5 Cứ mua chiếc này đi            | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这件衣服颜色还可以，就是有点儿大。$这家饭馆菜很好吃，就是有点儿贵。$         |
|    3388 | Bài 14 Bạn đã xem bộ phim đó chưa    | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我看过两次这个电影。$他来过我家三次。$我们坐过一次飞机。               |
|    3389 | Bài 15 Năm mới sắp đến rồi           | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 1   | RAW_SCALAR_DELIM | hanviet: KHOÁI YẾU / KHOÁI / TỰU YẾU / YẾU L            |
|    3394 | Bài 5 Dạo này tôi càng ngày càng béo | Flama Standard Vocabulary (`e2f31... |     2 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我现在不那么忙了。$天气冷了，你要多穿衣服。$我喜欢吃辣的了。             |
|    3400 | Bài 11 Đừng quên tắt điều hòa        | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 你可以把空调关了吗？$我今天太累了，没把作业做完。$你别把这件事告诉他         |
|    3403 | Bài 14 Bạn mang hoa quả lại đây      | Flama Standard Vocabulary (`e2f31... |     2 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我把衣服洗干净了。$请同学们把书拿出来。$你先把这杯热牛奶喝完吧。           |
|    3405 | Bài 16 Bây giờ tôi mệt đến mức ta... | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 弟弟高兴得跳了起来。$孩子们玩儿得不想回家。$他忙得连饭都没时间吃。          |
|    3406 | Bài 17 Ai cũng có cách chữa khỏi ... | Flama Standard Vocabulary (`e2f31... |     2 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他是新来的，有时间你帮助帮助他吧。$太累了，我们去公园休息休息吧。$这         |
|    3408 | Bài 19 Bạn không nhìn ra sao         | Flama Standard Vocabulary (`e2f31... |     7 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 那位老人看上去只有五十多岁。$这件衣服看上去很漂亮，你试一下吧。$他看         |
|    3410 | Bài 1 Cuối tuần bạn có dự định gì    | Flama Standard Vocabulary (`e2f31... |    25 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 水果、面包、茶都准备好了。$明天要考试，你准备好了吗？                 |
|    3411 | Bài 2 Khi nào anh ấy về              | Flama Standard Vocabulary (`e2f31... |    25 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 那边树多，我们过去坐一下吧。$公园里种了很多高大的树。                 |
|    3412 | Bài 3 Trên bàn để rất nhiều đồ uống  | Flama Standard Vocabulary (`e2f31... |    23 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这件衬衫怎么样？$他今天穿了一件白衬衫。$这件衬衫有点贵，320元一件         |
|    3414 | Bài 5 Dạo này tôi càng ngày càng béo | Flama Standard Vocabulary (`e2f31... |    20 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 你最喜欢哪个季节？——当然是春天。$下周的朋友聚会，你来吗？——当然来         |
|    3415 | Bài 6 Sao đột nhiên lại không tìm... | Flama Standard Vocabulary (`e2f31... |    20 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我离不开眼镜，不戴就看不清楚。$这副眼镜是你新买的吗？                 |
|    3416 | Bài 7 Tôi và cô ấy đều đã quen nh... | Flama Standard Vocabulary (`e2f31... |    16 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 以前她在哪儿工作？$来中国以前，我就开始学习汉语了。$睡觉以前喝一杯热         |
|    3418 | Bài 9 Tiếng Trung của cô ấy nói h... | Flama Standard Vocabulary (`e2f31... |    19 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们可以从中间这条路过去。$我就坐在这两个人中间。$这三本书里，中间的         |
|    3419 | Bài 10 Môn toán khó hơn môn lịch ... | Flama Standard Vocabulary (`e2f31... |    20 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 大小没关系，主要是环境。$我们今天的主要任务是打扫房间。$他迟到的主要         |
|    3420 | Bài 11 Đừng quên tắt điều hòa        | Flama Standard Vocabulary (`e2f31... |    24 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 那我们今天喝点儿啤酒吧。$天气太热了，我想喝一杯冰啤酒。                |
|    3422 | Bài 13 Tôi đi bộ về đấy              | Flama Standard Vocabulary (`e2f31... |    19 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 等了这么久，你终于回来了！$经过努力，他终于考完试了。$这道题我想了很         |
|    3424 | Bài 15 Những thứ khác đều không c... | Flama Standard Vocabulary (`e2f31... |    28 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这个地方每年夏天都要举行一次啤酒节。$学校下个星期将举行足球比赛。           |
|    3425 | Bài 16 Bây giờ tôi mệt đến mức ta... | Flama Standard Vocabulary (`e2f31... |    19 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 跑步的时候最好穿运动鞋。$我昨天买了一双新的运动鞋。$这双运动鞋穿着非         |
|    3426 | Bài 17 Ai cũng có cách chữa khỏi ... | Flama Standard Vocabulary (`e2f31... |    20 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们要选择“对”的时间去运动。$这道选择题的答案是A还是B？$两件衣服         |
|    3427 | Bài 18 Tôi tin rằng họ sẽ đồng ý     | Flama Standard Vocabulary (`e2f31... |    21 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 关于这个工作，还有什么问题吗？$这是一本关于中国历史的书。               |
|    3428 | Bài 19 Bạn không nhìn ra sao         | Flama Standard Vocabulary (`e2f31... |    23 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 她小时候很喜欢留短头发。$会议的时间很短，只有十分钟。                 |
|    3429 | Bài 20 Tôi bị anh ấy ảnh hưởng rồi   | Flama Standard Vocabulary (`e2f31... |    18 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 你有几张信用卡？$请问这里可以刷信用卡吗？$我用信用卡买了一台电脑。          |
|    3430 | Bài 1 Tình yêu giản đơn              | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 老张开会从来不迟到。$虽然我们认识很久了，但我从来没见他生过气。            |
|    3435 | Bài 6 Tiền nào của nấy               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这个歌最近很流行，你竟然没听过？$来这家饭馆吃饭的人竟然这么多，排队都         |
|    3436 | Bài 7 Bác sĩ tốt nhất là chính mình  | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 今天来不及开会了，明天我们再讨论吧。$快点儿走吧，要不然就来不及赶火车         |
|    3437 | Bài 8 Cuộc sống không thiếu cái đẹp  | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: A: 没想到咱们毕业都已经十年了。 B: 可不是！时间过得太快了。$A         |
|    3438 | Bài 9 Ánh dương luôn ở sau giông bão | Flama Standard Vocabulary (`e2f31... |     8 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 经过多方调查，警察终于找到了小偷。$每天上班我都会经过那家咖啡店。$小         |
|    3442 | Bài 13 Vừa uống trà vừa xem Kinh ... | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 大家请注意，十分钟后会议继续进行。$专家们正在对这个问题进行深入调查。         |
|    3443 | Bài 14 Bảo vệ mẹ Trái Đất            | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 医生提醒我们，每天一般睡够八小时就可以了。$行李箱已经够重的了，不用再         |
|    3444 | Bài 15 Nghệ thuật dạy con            | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 搬家的时候小心点儿，别把电脑弄坏了。$晚饭我已经弄好了，你们快过来吃吧         |
|    3447 | Bài 18 Khoa học kỹ thuật và thế giới | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这本书我不知道她是否能读懂。$婚姻是否幸福跟长相没有关系。$请告诉我你         |
|    3450 | Bài 1 Tình yêu giản đơn              | Flama Standard Vocabulary (`e2f31... |    39 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 虽然认识的时间不长，但我从来没这么快乐过。$他工作很有原则，从来不迟到         |
|    3451 | Bài 2 Người bạn thực sự              | Flama Standard Vocabulary (`e2f31... |    37 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 朋友可以丰富我们的生活。$王老师有多年的教学工作经验，经验非常丰富。          |
|    3452 | Bài 3 Giám đốc có ấn tượng rất tố... | Flama Standard Vocabulary (`e2f31... |    36 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这会给面试者留下一个好的印象。$今天天气不好，你还是留在家里吧。$我们         |
|    3453 | Bài 4 Đừng quá sốt ruột kiếm tiền    | Flama Standard Vocabulary (`e2f31... |    36 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 按原来的计划应该是两周，但我们可以提前完成。$我还以为是谁敲门呢，原来         |
|    3454 | Bài 5 Chỉ mua đồ đúng, không mua ... | Flama Standard Vocabulary (`e2f31... |    31 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这家餐厅的菜味道应该不错，很多人排队。$这碗面不仅闻起来香，味道也很好         |
|    3455 | Bài 6 Tiền nào của nấy               | Flama Standard Vocabulary (`e2f31... |    37 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这个行李箱不管从价格还是质量看，都是值得考虑的。$花再多时间把这道题弄         |
|    3456 | Bài 7 Bác sĩ tốt nhất là chính mình  | Flama Standard Vocabulary (`e2f31... |    35 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 只有身体和精神都健康，才算是真正的健康。$他今天穿了一身新西服，看起来         |
|    3457 | Bài 8 Cuộc sống không thiếu cái đẹp  | Flama Standard Vocabulary (`e2f31... |    29 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 喜欢穿浅色衣服的女孩子性格通常比较阳光。$清晨的阳光洒在房间里，让人感         |
|    3458 | Bài 9 Ánh dương luôn ở sau giông bão | Flama Standard Vocabulary (`e2f31... |    38 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 几个月坚持运动下来，减肥的效果很不错。$这种感冒药的效果非常明显，吃完         |
|    3459 | Bài 10 Tiêu chuẩn của hạnh phúc      | Flama Standard Vocabulary (`e2f31... |    35 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 在父母眼里，我们永远长不大。$我永远不会忘记你的帮助。                 |
|    3460 | Bài 11 Đọc sách hay, đọc cho hay,... | Flama Standard Vocabulary (`e2f31... |    37 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他是我们班最优秀的学生之一。$会议结束之后，请大家留下来打扫教室。           |
|    3461 | Bài 12 Dùng trái tim khám phá thế... | Flama Standard Vocabulary (`e2f31... |    36 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这件事在网上引起了很大的讨论。$不清楚的表达可能会引起误会。              |
|    3462 | Bài 13 Vừa uống trà vừa xem Kinh ... | Flama Standard Vocabulary (`e2f31... |    36 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 运动已经成了我生活里不可缺少的一部分。$这本书的前一部分写得很有意思。         |
|    3463 | Bài 14 Bảo vệ mẹ Trái Đất            | Flama Standard Vocabulary (`e2f31... |    33 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 汽车以极快的速度向前开去。$为了按时完成任务，我们必须加快速度。            |
|    3464 | Bài 15 Nghệ thuật dạy con            | Flama Standard Vocabulary (`e2f31... |    35 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他每天晚上都要练习弹钢琴。$我妹妹从小就喜欢弹钢琴。                  |
|    3465 | Bài 16 Cuộc sống có thể tốt đẹp hơn  | Flama Standard Vocabulary (`e2f31... |    37 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 拒绝正好说明你对朋友负责。$王老师工作非常认真负责，深受学生喜爱。$这         |
|    3466 | Bài 17 Con người và tự nhiên         | Flama Standard Vocabulary (`e2f31... |    35 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们小时候都听过美人鱼的故事。$这部电影讲述了一个美人鱼和人类的爱情故         |
|    3467 | Bài 18 Khoa học kỹ thuật và thế giới | Flama Standard Vocabulary (`e2f31... |    37 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 警察在火车站抓住了一个小偷。$ 机会来了就要好好抓住，千万别错过。           |
|    3469 | Bài 20 Cảnh đẹp trên đường           | Flama Standard Vocabulary (`e2f31... |    39 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 湖南菜的特点就是辣，吃起来非常过瘾。$虽然这道菜很辣，但我还是忍不住多         |
|    3470 | Bài 1 Chi tiết của tình yêu          | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他累得靠在沙发上睡着了。$在家靠父母，出门靠朋友。$我想买一张靠窗的飞         |
|    3472 | Bài 3 Đời người có lựa chọn, mọi ... | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 汉语技能教学包括听、说、读、写四个方面。$我们班所有人都参加了比赛，包         |
|    3476 | Bài 7 Hai câu chuyện thành ngữ       | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这棵大树的根已经深深扎进了泥土里。$小女孩手里拿着一根漂亮的棒棒糖。          |
|    3478 | Bài 9 Một Lỗ Tấn rất khác            | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我把这个小阳台作为每晚读书的地方。$作为一名医生，救死扶伤是我的职责。         |
|    3482 | Bài 13 Cưa bỏ đáy giỏ cuộc đời       | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 楼下就有小超市，你何必跑去学校外面买呢？$既然他已经拒绝了，你何必还要         |
|    3484 | Bài 15 Bàn việc quân trên giấy       | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 1   | RAW_SCALAR_DELIM | hanviet: ĐẮC / BẤT QUÁ                                  |
|    3485 | Bài 16 Cân nặng và ăn kiêng          | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 老师针对他薄弱的基础进行了个别辅导。$除了个别偏远地区以外，全国大部分         |
|    3486 | Bài 17 Rời đi vào khoảnh khắc đẹp... | Flama Standard Vocabulary (`e2f31... |     7 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们要以积极的心态面对工作中的各种挑战。$我们每天坚持锻炼身体，以保持         |
|    3487 | Bài 18 Nghệ thuật trừu tượng có đ... | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 怎么只有你们两个人？其余的同学呢？$先解决这几个紧急问题，其余的以后再         |
|    3493 | Bài 24 Chiến dịch dạy học tình ng... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 保护环境是每个公民应尽的责任和义务。$学校有义务保障学生在校期间的安全         |
|    3495 | Bài 26 Bạn thuộc kiểu người bận r... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我喜欢上海，一来上大学时在那里住过几年，二来我太太也是上海人。$他不想         |
|    3496 | Bài 27 Đánh cờ                       | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 买了这么贵的新衣服，她平时根本舍不得穿。$马上就要毕业了，大家都舍不得         |
|    3497 | Bài 28 Sinh viên tốt nghiệp được ... | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他喝了这种药后，身体出现了过敏反应。$老王决定把社区的卫生问题反映给物         |
|    3498 | Bài 29 Bồi dưỡng đối thủ             | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 求人不如求己。$三家的营业额加起来还不如他一家高。$周末去爬山太累了，         |
|    3499 | Bài 30 Cạnh tranh giúp thị trường... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 听了她的演奏，大家觉得她的确很有音乐天赋。$这部电影的情节的确非常吸引         |
|    3500 | Bài 31 Hiệu ứng bước một chân qua... | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 嗯！你的房间为什么这么冷？$嗯！你怎么还没走啊？大家都等你呢。             |
|    3501 | Bài 32 Bảo vệ môi trường quanh ta    | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 汽车尾气排放与空气质量密切相关。$医生正在密切关注病人的体温变化。$两         |
|    3504 | Bài 35 Cây cối cũng biết toát mồ hôi | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 因为跟蒸腾作用有关，这种特殊的提升力就被称为“蒸腾拉力”。$今天天气特         |
|    3506 | Bài 1 Chi tiết của tình yêu          | Flama Standard Vocabulary (`e2f31... |    48 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 火车快到的时候你喊我一声。$外面太吵了，他不得不大声地喊。$清晨，妈妈         |
|    3515 | Bài 10 Kỳ tích từ tranh luận         | Flama Standard Vocabulary (`e2f31... |    53 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 双方围绕人工智能的发展前景进行了激烈的辩论。$他代表学校参加了这次全国         |
|    3518 | Bài 13 Cưa bỏ đáy giỏ cuộc đời       | Flama Standard Vocabulary (`e2f31... |    49 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这位年轻的运动员打破了男子百米比赛的世界纪录。$他一直保持着这项比赛的         |
|    3521 | Bài 16 Cân nặng và ăn kiêng          | Flama Standard Vocabulary (`e2f31... |    51 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 她胃很不舒服，恶心想吐。$孩子因为吃坏了东西，晚上吐了好几次。$他晕车         |
|    3523 | Bài 18 Nghệ thuật trừu tượng có đ... | Flama Standard Vocabulary (`e2f31... |    51 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 她是当代最受欢迎的电影明星之一。$许多年轻人喜欢花时间和精力去追明星。         |
|    3524 | Bài 19 Bánh củ cải quê hương         | Flama Standard Vocabulary (`e2f31... |    46 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 高手往往把面擀得薄如白纸。$今天天气转凉，穿这么薄的衣服容易感冒。$这         |
|    3525 | Bài 20 Quầy truyện tranh thiếu nhi   | Flama Standard Vocabulary (`e2f31... |    44 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 互联网对现代青少年的生活和学习方式产生了深远的影响。$ 社会各界都应当         |
|    3527 | Bài 22 Đọc và tư duy                 | Flama Standard Vocabulary (`e2f31... |    44 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 买书的时候我一般会先看看前面的目录。$请把这些资料保存在新建的目录下。         |
|    3529 | Bài 24 Chiến dịch dạy học tình ng... | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 老师让他站起来，朗读自己的作文。$每天早晨大声朗读课文，有助于提高口语         |
|    3530 | Bài 25 Đổ đầy nước cho chính mình    | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 在工作中不能做一天和尚撞一天钟，必须有长远的规划。$ 他总是抱着做一天         |
|    3532 | Bài 27 Đánh cờ                       | Flama Standard Vocabulary (`e2f31... |    49 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我父亲是一位经验丰富的象棋教练。$教练正在耐心地指导队员们练习防守技巧         |
|    3533 | Bài 28 Sinh viên tốt nghiệp được ... | Flama Standard Vocabulary (`e2f31... |    51 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 无论在哪个行业，最缺乏的永远都是专注的人。$他工作时非常专注，外界的声         |
|    3534 | Bài 29 Bồi dưỡng đối thủ             | Flama Standard Vocabulary (`e2f31... |    41 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 买大件家电一定要货比三家，才能买到性价比最高的产品。$网购时不妨货比三         |
|    3535 | Bài 30 Cạnh tranh giúp thị trường... | Flama Standard Vocabulary (`e2f31... |    45 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 年轻人大多精力旺盛，能够承担高强度的工作。$这些鱼群在刺激下保持了旺盛         |
|    3536 | Bài 31 Hiệu ứng bước một chân qua... | Flama Standard Vocabulary (`e2f31... |    29 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 那位舞蹈演员的身段非常优美。$当你放低身段时，会缩短与人的距离。$作为         |
|    3537 | Bài 32 Bảo vệ môi trường quanh ta    | Flama Standard Vocabulary (`e2f31... |    39 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 工厂增加了环保设施，以减少污染物排放。$这个小区的公共设施非常完善，生         |
|    3538 | Bài 33 Lấy tắc trị tắc Mẹo hay gi... | Flama Standard Vocabulary (`e2f31... |    51 |    Tier 1   | RAW_SCALAR_DELIM | hanviet: CHIÊU / CHIÊU NHI                              |
|    3539 | Bài 34 Thuật chăm sóc lông vũ của... | Flama Standard Vocabulary (`e2f31... |    36 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 下过雨后，路上出现了很多浅水坑。$工人们正在路边挖坑准备栽种树木。$这         |
|    3540 | Bài 35 Cây cối cũng biết toát mồ hôi | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 走累了，我们坐在石阶上歇一会儿吧。$ 这几天工作太紧张，周末我想好好歇         |
|    3543 | Bài 2 Tình yêu của cha mẹ            | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他工作忙的时候，恨不得一个人干两个人的活儿。$他累极了，恨不得倒在床上         |
|    3545 | Bài 4 Thắng lợi hoàn hảo             | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这次出差去北京，我们可以乘机游览一下长城。$犯罪分子往往乘机钻法律的空         |
|    3546 | Bài 5 Học một ngoại ngữ có cần lý... | Flama Standard Vocabulary (`e2f31... |     7 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这道题的做法固然巧妙，可是计算过程太繁琐了。$考上名校固然好，没考上也         |
|    3552 | Bài 11 Khi tôi vắng nhà, mèo làm gì  | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他把抽屉里的旧信件和照片统统清理了出去。$他平时不爱交际，什么舞会、酒         |
|    3554 | Bài 13 Nhìn thế sự đổi thay qua c... | Flama Standard Vocabulary (`e2f31... |     6 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 科普文章应该写得简明易懂，便于读者理解。$为了便于管理，学校将新生按专         |
|    3555 | Bài 14 Cõng nồi cơm điện chụp ảnh... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 每次回想起当时惊险的情景，他的心情依然难以平静。$你编造的借口漏洞百出         |
|    3556 | Bài 15 Tác phẩm điêu khắc trên dã... | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我国幅员辽阔，拥有极其丰富的水电与矿产资源。$这项重大的科技突破，具有         |
|    3558 | Bài 17 Thế giới chậm rãi trong mắ... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 大家如果都不遵守交通规则，势必会导致严重的交通拥堵。$人口盲目过度增长         |
|    3561 | Bài 20 Tổ gà vàng                    | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这套房子交通方便，况且房租又不贵，真是再合适不过了。$路途这么远，况且         |
|    3562 | Bài 21 Cửa hàng tương lai            | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他嫌这道菜太咸，一口都没吃。$既然你不嫌麻烦，那就请你帮我这个忙吧。$         |
|    3563 | Bài 22 Ô tô năm 2050 sẽ như thế nào  | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他最近工作压力太大，动不动就对同事发脾气。$这台旧电脑动不动就死机，严         |
|    3566 | Bài 25 Thuyền cỏ mượn tên            | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 虽然我们来自不同的省份，但童年的成长经历大致相同。$这篇调查报告我大致         |
|    3568 | Bài 27 Trả ngọc nguyên vẹn về nướ... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 秦王对着和氏璧左看右看，爱不释手。$左思右想之后，他终于决定放弃这次出         |
|    3569 | Bài 28 Núi cao nước chảy gặp tri âm  | Flama Standard Vocabulary (`e2f31... |     8 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他把心爱的琴摔了个粉碎。$张总一张嘴，大家就会笑个不停。$我们一定能够         |
|    3571 | Bài 30 Bạn ngủ ngon không            | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 在原则问题上，公司绝不会容忍任何欺骗行为。$他那种傲慢无礼的态度，实在         |
|    3572 | Bài 31 Học vấn trong vận động        | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 运动健身归根到底是自己的事，胡乱对付其实是在欺骗自己。$技术固然重要，         |
|    3573 | Bài 32 Đôi khi đau buồn cũng chẳn... | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 没有理想，人生就如荒漠，没有生气；没有理想，人生就如黑夜，没有光明；没         |
|    3575 | Bài 34 Người sinh ra vì di vật vă... | Flama Standard Vocabulary (`e2f31... |     3 |    Tier 1   | RAW_SCALAR_DELIM | hanviet: ĐƯƠNG / ĐÁNG                                   |
|    3576 | Bài 35 Tiếp cận tranh Tết khắc gỗ    | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 有了纸，书写就需要墨；有了墨，印章就开始流行；有了印章，人们便想到了印         |
|    3580 | Bài 39 Đời sống trong kỷ nguyên I... | Flama Standard Vocabulary (`e2f31... |     4 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 大学阶段学业尚未完成，经济上也尚未独立。$该项研究成果的临床效果尚未得         |
|    3583 | Bài 2 Tình yêu của cha mẹ            | Flama Standard Vocabulary (`e2f31... |    66 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 在医生面前，患者不应该隐瞒自己的真实病情。$他选择向家人隐瞒投资失败的         |
|    3584 | Bài 3 Một hộp bánh Trung thu         | Flama Standard Vocabulary (`e2f31... |    58 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 哥哥嫂子结婚多年，感情一直十分融洽。$昨天去同事家做客，嫂子热情地招待         |
|    3585 | Bài 4 Thắng lợi hoàn hảo             | Flama Standard Vocabulary (`e2f31... |    51 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 猎豹奔跑时的速度极快，像子弹一样冲了出去。$一颗子弹擦伤了他的手臂，幸         |
|    3587 | Bài 6 Làm tốt vai trò người mới c... | Flama Standard Vocabulary (`e2f31... |    64 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 新任总统在首都发表了慷慨激昂的就职演说。$ 我们俩是同一天就职的，所以         |
|    3589 | Bài 8 Gặp lại tôi của ngày xưa       | Flama Standard Vocabulary (`e2f31... |    53 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 器官捐献能够为许多绝望中的病人带来重生的希望。$随着年龄的增长，人体的         |
|    3590 | Bài 9 Những ngày không dùng điện ... | Flama Standard Vocabulary (`e2f31... |    47 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 她生病胃口不好，母亲特意为她熬了一碗热气腾腾的白粥。$厨房里弥漫着小米         |
|    3595 | Bài 14 Cõng nồi cơm điện chụp ảnh... | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 她身穿一套时髦的衣裳，显得格外优雅大方。$ 节日里，孩子们都换上了崭新         |
|    3596 | Bài 15 Tác phẩm điêu khắc trên dã... | Flama Standard Vocabulary (`e2f31... |    57 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 中国是一个拥有数千年悠久历史与灿烂文化的文明古国。$人类拥有惊人的创造         |
|    3597 | Bài 16 Từ Kiện và các nhiếp ảnh g... | Flama Standard Vocabulary (`e2f31... |    55 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这项科考成果填补了我国在深海生物研究领域的空白。$考察队拍下了珍贵照片         |
|    3598 | Bài 17 Thế giới chậm rãi trong mắ... | Flama Standard Vocabulary (`e2f31... |    49 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 看似渺小的苍蝇能敏捷地躲过人类的攻击。$ 站在浩瀚的大海面前，每个人都         |
|    3600 | Bài 19 Thế giới biển sâu không có... | Flama Standard Vocabulary (`e2f31... |    64 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 雄鹰在广阔的天空中自由自在地翱翔。$这项前沿科技在未来的医疗领域有着极         |
|    3603 | Bài 22 Ô tô năm 2050 sẽ như thế nào  | Flama Standard Vocabulary (`e2f31... |    69 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们在设计方案时力求做到尽善尽美。$公司力求实现今年既定的销售目标。          |
|    3604 | Bài 23 Thời đại dữ liệu lớn          | Flama Standard Vocabulary (`e2f31... |    64 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 在我们这家跨国公司里，大家公认他非常敬业。$他是国际学术界公认的人工智         |
|    3606 | Bài 25 Thuyền cỏ mượn tên            | Flama Standard Vocabulary (`e2f31... |    56 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 各项准备工作均已安排妥当，请领导放心。$这种处理方式似乎有些欠妥当，需         |
|    3608 | Bài 27 Trả ngọc nguyên vẹn về nướ... | Flama Standard Vocabulary (`e2f31... |    68 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 只要我们没有做错事，就可以理直气壮地表达自己的诉求。$面对不合理的指责         |
|    3609 | Bài 28 Núi cao nước chảy gặp tri âm  | Flama Standard Vocabulary (`e2f31... |    70 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 暴风雨来临前，渔船纷纷驶入了平静的港湾。$无论在外遇到多大挫折，家庭永         |
|    3613 | Bài 32 Đôi khi đau buồn cũng chẳn... | Flama Standard Vocabulary (`e2f31... |    70 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他为了个人利益而背叛朋友，最终落得众叛亲离的下场。$我们绝不能背叛自己         |
|    3614 | Bài 33 Hoài niệm cuộc sống chậm rãi  | Flama Standard Vocabulary (`e2f31... |    57 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 为期三天的假期，我和好友结伴去西安旅行。$这次为期两周的国际研讨会圆满         |
|    3615 | Bài 34 Người sinh ra vì di vật vă... | Flama Standard Vocabulary (`e2f31... |    64 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 经过多年的积累，这所图书馆的藏书数量十分可观。$这家网店上个月的利润相         |
|    3618 | Bài 37 Câu chuyện cảnh sát           | Flama Standard Vocabulary (`e2f31... |    62 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 她出门前总是要花半个小时化妆。$那位正在化妆的女士突然听到了敲门声。          |
|    3619 | Bài 38 Mắt tinh bắt trọn cơ hội k... | Flama Standard Vocabulary (`e2f31... |    36 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 公司决定在今年进一步扩充海外业务。$这所学校不断扩充师资力量，提升教学         |
|    3640 | Bài 1                                | Flama Standard Vocabulary (`e2f31... |    30 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 爸爸在打电话。$ 我想给妈妈打电话。$ 他每天都给我打电话。              |
|    3641 | Bài 2                                | Flama Standard Vocabulary (`e2f31... |    30 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 星期六晚上我们去看电影吧。$这家电影院看电影很好。$我不常看电影，我喜         |
|    3642 | Bài 3                                | Flama Standard Vocabulary (`e2f31... |    30 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他在学校里认真学习汉语。 $ 学习外语需要天天练习。 $ 我们班的同学         |
|    3643 | Bài 4                                | Flama Standard Vocabulary (`e2f31... |    30 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 学校前面有一家很大的商店。$我在商店里买了一件漂亮衣服。                |
|    3644 | Bài 5                                | Flama Standard Vocabulary (`e2f31... |    30 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 妈妈在厨房里做饭。$你在做什么工作？$我想做几道好吃的菜。               |
|    3645 | Bài 6                                | Flama Standard Vocabulary (`e2f31... |    30 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 去火车站太远了，我们坐出租车吧。$他在北京开出租车已经五年了。             |
|    3646 | Bài 7                                | Flama Standard Vocabulary (`e2f31... |    30 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们星期二下午有汉语课。 $ 他的房间号是二零八。 $ 二加八等于十。         |
|    3648 | Bài 9                                | Flama Standard Vocabulary (`e2f31... |     1 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他身体不太好，下午要去医院看医生。$我生病了，明天想去看医生。$爸爸今         |
|    3652 | Bài 4                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 你看一下，今天晚上的北京天气怎么样？$我们明天中午一起去吃中国菜，怎么         |
|    3685 | Bài 3                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 哥哥送给妹妹一只非常可爱的小白狗。$这件黑色的新衣服是朋友送给我的。$         |
|    3692 | Bài 10                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我的小猫已经三岁了。$现在太晚了，公共汽车已经没有了。$哥哥已经去学校         |
|    3727 | Bài 45                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 学校旁边有一家很大的书店。$坐在我旁边的那个同学是日本人。$你可以把自         |
|    3740 | Bài 1                                | Flama Standard Vocabulary (`e2f31... |    35 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 妈妈让我今天早点儿睡觉。$在公交车上，我们要给老人让座。                |
|    3744 | Bài 5                                | Flama Standard Vocabulary (`e2f31... |    35 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我家就在前面那个车站旁边。$ 走在前面的那个人是王老师。                |
|    3745 | Bài 6                                | Flama Standard Vocabulary (`e2f31... |    35 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我今年二十岁，正在北京读大学。$今年冬天的天气比去年冷很多。$你打算今         |
|    3746 | Bài 7                                | Flama Standard Vocabulary (`e2f31... |    35 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我每天早上都去公园跑步。$跑步对身体非常好。$他喜欢晚上一个人跑步。          |
|    3747 | Bài 8                                | Flama Standard Vocabulary (`e2f31... |    35 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这本书不是我的，是我同桌的。$ 他不是中国人，他是学汉语的留学生。           |
|    3749 | Bài 10                               | Flama Standard Vocabulary (`e2f31... |    35 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 长时间坐着对身体不太好。$我们有很长时间没见面了。                   |
|    3750 | Bài 11                               | Flama Standard Vocabulary (`e2f31... |    35 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 今天天气是阴天，非常凉快。$ 天阴了，出门记得带一把伞。$ 阴天的时候         |
|    3751 | Bài 12                               | Flama Standard Vocabulary (`e2f31... |    35 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 请问，医院的洗手间在哪里？$ “你汉语说得真好！”“哪里，还要多学呢。         |
|    3753 | Bài 14                               | Flama Standard Vocabulary (`e2f31... |    11 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我已经在网上买好了下周去北京的机票。$去机场以前，请检查你的机票和护照         |
|    3758 | Bài 5                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他昨天晚上复习功课，夜里一点才睡觉。$坐了两个小时的公共汽车，我才到学         |
|    3759 | Bài 6                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 你在楼下等我五分钟，我马上就下楼。$听完了这段音乐，大家就高兴地跳起舞         |
|    3761 | Bài 8                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 你别太担心，医生说明天病人的情况就会好起来的。$只要我们认真复习，这次         |
|    3767 | Bài 14                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 妹妹每天都起得很早，去公园跑步锻炼。$他汉字写得非常漂亮，大家都喜欢看         |
|    3768 | Bài 15                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 外面的雨下得很大，你今天最好别出门了。$生病了就要多喝水，你最好马上去         |
|    3770 | Bài 17                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 请问今天的报纸上有没有关于天气的消息？$你快去前台问问服务员，还有没有         |
|    3772 | Bài 19                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 晚上我想去超市买点儿新鲜水果。$这双鞋太小了，有没有大点儿的？             |
|    3778 | Bài 25                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 过生日那天，朋友送我一本很有趣的书。$他送给老师一束非常漂亮的新鲜花。         |
|    3803 | Bài 50                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 听李医生说，多吃新鲜水果对身体很有好处。$我听小王说，那家新开的咖啡馆         |
|    3804 | Bài 51                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 今天工作很累，晚上我想早点儿回家洗洗澡休息。$吃完晚饭以后，我们全家人         |
|    3807 | Bài 54                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 除了踢足球，我周末还喜欢去游泳。$他除了会说英语，还会说一点儿汉语。          |
|    3813 | Bài 60                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们吃完午饭再去图书馆借书也来得及。$盘子里的菜大家都吃完了，看来大家         |
|    3821 | Bài 68                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 坐飞机去南方旅游比坐火车快多了。$吃了医生开的药，我现在觉得舒服多了。         |
|    3845 | Bài 92                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 走出校门后一直向东走，就能看到地铁站。$汽车向右拐进了一条小路。$遇到         |
|    3846 | Bài 93                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 电影马上就要开始了，我们快点儿进去吧。$外面的天阴了，刮着大风，好像要         |
|    3848 | Bài 95                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我也想去旅行，问题是现在手头没有钱。$这个计划很好，问题是谁来负责完成         |
|    3854 | Bài 1                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 过马路的时候，一定要注意看红绿灯。$天气越来越冷了，出门要多穿衣服，注         |
|    3855 | Bài 2                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我经常用电子词典查生词的发音。$这部电子词典的功能很多，非常方便。           |
|    3856 | Bài 3                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这件衣服不仅好看，而且价格很便宜。$老板，如果我买两件，能便宜一点儿吗         |
|    3857 | Bài 4                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我想去图书馆借几本中文小说。$你可以借我用一下你的铅笔吗？$他把车借给         |
|    3859 | Bài 6                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 开学第一天，校长在会上发表了讲话。$ 我们校长对每位老师和学生都很关心         |
|    3860 | Bài 7                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我想去附近的银行换一些零钱。$这家银行下午五点关门，你快去吧。             |
|    3861 | Bài 8                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 她是一个既聪明又能干的年轻女人。$那个女人手里拿着一本书，正在安静地等         |
|    3862 | Bài 9                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 每年春节，全家人都会聚在一起吃年夜饭。$春节期间火车站的人特别多。$祝         |
|    3863 | Bài 10                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 运动以后，请记得喝一杯温水。$桌子上放着一瓶干净的矿泉水。               |
|    3865 | Bài 12                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们上午有两节汉语课，下午没有课。$明天上午八点我们在校门口集合。           |
|    3866 | Bài 13                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他因为牙疼，今天一天都没怎么吃东西。$如果你总是牙疼，应该早点儿去医院         |
|    3867 | Bài 14                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 为了不迟到，他每天早上六点就起床了。$今天是周末，我想多睡一会儿，不想         |
|    3868 | Bài 15                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 抬头看天空，蓝天上漂浮着几朵白云。$天边的乌云越来越多，马上就要下大雨         |
|    3869 | Bài 16                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他是我的大学同学，学习非常努力。$如果你看见他，请让他给我打个电话。$         |
|    3870 | Bài 17                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 为了身体健康，你一定要按时吃早饭。$妈妈每天早上六点起床给我们做早饭。         |
|    3872 | Bài 19                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 周末我和爸爸一起去看望爷爷奶奶。$爷爷奶奶非常喜欢在公园里散步。            |
|    3873 | Bài 20                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我给远方的朋友写了一封长信。$他说的话都是真的，你一定要信他。             |
|    3874 | Bài 21                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 周末的电影票我已经买好了。$上车前请大家准备好车票。$去北京的飞机票现         |
|    3875 | Bài 22                               | Flama Standard Vocabulary (`e2f31... |     1 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这家餐馆的菜做得很不错，味道很好。$我已经准备好了，随时可以出发。           |
|    3876 | Bài 1                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 为了准备期末考试，他整天都待在图书馆里。$在图书馆看书时，请大家保持安         |
|    3877 | Bài 2                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 在做出决定之前，我们需要先对市场进行全面调查。$这次满意度调查的结果表         |
|    3878 | Bài 3                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他在大学毕业后找到了一份非常理想的工作。$不管做什么工作，都需要有强烈         |
|    3879 | Bài 4                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这里的居民对外国游客非常友好。$我们应该用友好的态度对待新同事。$两国         |
|    3880 | Bài 5                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 老师把这个舞蹈动作又示范了一遍。$他的动作非常标准，看起来很专业。           |
|    3881 | Bài 6                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 夏天一边吃烤肉一边喝冰镇啤酒，感觉真舒服。$ 医生建议他为了身体健康，         |
|    3882 | Bài 7                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 在实验室里，必须严格按照规定使用仪器。$这款软件的使用方法很简单，一看         |
|    3883 | Bài 8                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 喝了一杯热茶后，我感觉身体舒服多了。$我对这份新工作有一种非常亲切的感         |
|    3884 | Bài 9                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这件衣服太小了，请给我换另外一件。$今天会议就到这里，另外，大家别忘了         |
|    3885 | Bài 10                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们必须快点出发，否则就赶不上火车了。$ 你要按时吃药，否则病情会变得         |
|    3886 | Bài 11                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 外面快要下雨了，出门时记得带上一把雨伞。$他一边打着雨伞，一边快步向地         |
|    3887 | Bài 12                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这部电影拍得确实精彩，值得多看几次。$最近的工作任务确实很重，大家都辛         |
|    3888 | Bài 13                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 无论多忙，他每天都坚持锻炼一个小时。$参加社会实践活动能锻炼我们的交流         |
|    3889 | Bài 14                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 妈妈熬的鱼汤一点儿也不腥，味道特别鲜。$菜市场上有很多刚刚采摘的新鲜蔬         |
|    3890 | Bài 15                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我家住在五层，平时我都喜欢爬楼梯。$刚擦完的桌子上又落了一层厚厚的灰。         |
|    3891 | Bài 16                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 年轻人在第一份工作中，应该努力积累经验。$学好一门外语需要长期的词汇积         |
|    3892 | Bài 17                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 你放心去出差吧，家里的一切有我照顾。$听到手术成功的消息，家人终于放心         |
|    3893 | Bài 18                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 凭学生证购买门票可以享受半价优惠。$商场里的冬装现在都开始半价出售了。         |
|    3895 | Bài 20                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 明天早上八点我们在校门口集合。$老师吹了一声哨子，同学们马上集合了。          |
|    3896 | Bài 21                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 因为超额完成了销售任务，经理拿到了丰厚的奖金。$年底的时候，公司会根据         |
|    3897 | Bài 22                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 新来的汉语老师性格很好，大家挺喜欢她。$虽然每天工作挺忙的，但他觉得很         |
|    3900 | Bài 25                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 周末爸爸喜欢在家看足球赛。$ 这场足球赛吸引了很多观众。                |
|    3901 | Bài 26                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 甜食通常含有很高的热量，吃多了容易发胖。$运动是消耗身体多余热量最好的         |
|    3902 | Bài 27                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 现在的年轻人很喜欢通过社交软件交友。$参加志愿活动不仅能帮助他人，也是         |
|    3903 | Bài 28                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这本关于中国历史的书深受读者喜爱。$ 他的精彩故事让在场的所有观众深受         |
|    3904 | Bài 29                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 你遇到困难，我当然会尽全力帮助你。$学好外语当然需要付出很多时间和努力         |
|    3905 | Bài 30                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 多吃新鲜水果对保护皮肤很有帮助。$超市里的水果不仅品种丰富，而且价格便         |
|    3906 | Bài 31                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 关于这个计划，大家有什么看法？$ 这是一本关于中国历史的书。              |
|    3907 | Bài 32                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 姐姐在商店里看上了一条漂亮的裙子。$他第一眼就看上了那辆红色的自行车。         |
|    3908 | Bài 33                               | Flama Standard Vocabulary (`e2f31... |     7 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他生病刚出院，今天还不能去学校上课。$只要努力练习，你一定能考过这次汉         |
|    3913 | Bài 5                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 电影马上就要开始了，大家快找座位坐下吧。$天空中乌云密布，看样子马上要         |
|    3914 | Bài 6                                | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 茶几上放着两本书和一杯新鲜的果汁。$他在工作上非常认真，经常主动帮助新         |
|    3936 | Bài 28                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 张老师对每一个学生都非常热情，大家都很喜欢他。$多吃新鲜蔬菜和水果对我         |
|    3941 | Bài 33                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 当你在异国遇到困难的时候，朋友的鼓励会给你巨大的勇气。$当春天到来的时         |
|    3990 | Bài 82                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 外面现在风刮得特别大，你出门前最好多穿一件外套。$周末去这家饭馆吃饭的         |
|    3996 | Bài 88                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 明天就要公布考试成绩了，小李紧张得整夜都睡不着觉。$晚上喝了浓咖啡以后         |
|    4000 | Bài 92                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 邻居们平时相处得非常好，大家都把彼此当成了家人。$因为长得太像，很多新         |
|    4001 | Bài 93                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 请问这种新鲜的苹果怎么卖，可以便宜一点儿吗？$这个汉字我没见过，你可以         |
|    4002 | Bài 94                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 周末有空的话，我想与李老师聊聊出国留学的计划。$下班后，他喜欢与邻居聊         |
|    4003 | Bài 95                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他是你的亲哥哥，你怎么可以对他发这么大的脾气呢？$这么重要的会议，你作         |
|    4023 | Bài 12                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 请你把桌上的会议文件整理好后送到办公室。$他粗心大意地把手机落在了出租         |
|    4038 | Bài 27                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们相信新产品能够满足广大消费者的多元化需求。$经过长期的刻苦训练，他         |
|    4041 | Bài 30                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 参加这次国际交流活动，大家最好穿得正式点儿。$明天早上有重要考试，你今         |
|    4042 | Bài 31                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 经理让他负责筹备下个星期的产品发布会。$这次考试取得优异成绩，让他的父         |
|    4061 | Bài 50                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 看把这孩子高兴的，手里拿着新玩具跑来跑去不肯停下。$跑完全程马拉松之后         |
|    4062 | Bài 51                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 为了提高生产效率，工程师把零件装配时间缩短到了十分钟。$老师要求大家修         |
|    4091 | Bài 80                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 通过分析这份财务报表，我们可以掌握公司近期的运营状况。$通过长期坚持阅         |
|    4095 | Bài 84                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 你打算乘坐高铁去北京，还是直接坐飞机去？$周末你喜欢在家里安静地看书，         |
|    4097 | Bài 86                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这所大学拥有雄厚的师资力量，除此之外，硬件设施也极为完善。$公司为员工         |
|    4099 | Bài 88                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 与其在这里无休止地抱怨环境，不如静下心来提升自己的核心竞争力。$周末与         |
|    4113 | Bài 102                              | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | hanviet: BỈ……CANH / YẾU……                               |
|    4119 | Bài 1                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 在推出新产品之前，我们必须做好充分的市场调研。$专家团队下周将前往农村         |
|    4120 | Bài 2                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 为了庆祝毕业，我们在学校附近的饭店聚餐。$这家五星级饭店为客人提供接送         |
|    4121 | Bài 3                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 生病后，很多人喜欢通过看中医来调理身体。$这位老中医拥有几十年的临床经         |
|    4122 | Bài 4                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 服务员礼貌地对顾客说：“请您稍等，菜马上就来。”$经理现在正在开会，请         |
|    4123 | Bài 5                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 天气变化无常，平时要注意保暖，别感冒了。$他因为受了风寒，不仅感冒而且         |
|    4124 | Bài 6                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 北方一到冬天就会频繁下雪，到处白茫茫一片。$因为外面正在下雪，路面结冰         |
|    4125 | Bài 7                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们应该养成垃圾分类的好习惯。$手机里每天都会收到很多没用的垃圾信息。         |
|    4126 | Bài 8                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 风太大了，吹得沙子迷了路人的眼睛。$孩子们在海滩上用沙子堆起了一座漂亮         |
|    4127 | Bài 9                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 在做出最后决定之前，我们需要全面考虑各种因素。$请你认真考虑一下这份工         |
|    4128 | Bài 10                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 很多外国留学生对中国京剧产生了浓厚的兴趣。$他从小跟随著名的京剧演员学         |
|    4129 | Bài 11                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 做人需要诚实，做生意也是如此。$ 运动需要坚持，学习一门外语也是如此。         |
|    4130 | Bài 12                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 经过多年的刻苦学习，他终于成为了一名翻译官。$随着科技的飞速发展，这个         |
|    4131 | Bài 13                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他口袋里装着一串钥匙，走起路来叮当作响。$听完这个好消息，她兴奋地说了         |
|    4132 | Bài 14                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 爷爷平时最大的爱好就是收集名家字画儿。$ 他在书房里挂了几幅很有意境的         |
|    4133 | Bài 15                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 公司对新入职的员工有非常明确的专业要求。$老师要求大家在下周五之前提交         |
|    4134 | Bài 16                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他带上照相机，记录下旅行途中的美丽风景。$这台专业照相机的镜头可以根据         |
|    4136 | Bài 18                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 裁判员必须保持客观，确保比赛的公平。$在职场中，每个人都希望获得公平的         |
|    4137 | Bài 19                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 听轻音乐是缓解工作压力的好方法。$吃完医生开的药后，他的头痛得到了明显         |
|    4139 | Bài 21                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 每年端午节，河两岸都会聚集大批观看赛龙舟的群众。$村里组织了一支年轻队         |
|    4141 | Bài 23                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 冬天在室外待久了，他的双手变得冷冰冰的。$她总是一副冷冰冰的表情，让人         |
|    4142 | Bài 24                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 实在抱歉，路上堵车严重，让您久等了。$他在雨中久等不来，只好先回家了。         |
|    4143 | Bài 25                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这部科幻小说情节曲折，一出版就受到了年轻人的喜爱。$他利用业余时间创作         |
|    4144 | Bài 26                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这次国际艺术展览会吸引了成千上万的观众。$公司决定派两名代表去北京参加         |
|    4145 | Bài 27                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 科学技术是推动社会创造财富的重要力量。$ 丰富的阅历和健康的身体是人生         |
|    4147 | Bài 29                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 虽然遇到了很多困难，但他并未放弃希望。$事实证明，传闻中的事情并未真正         |
|    4148 | Bài 30                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 公司业务扩展迅速，需要再雇几位工程师。$为了打赢这场官司，他特意雇了一         |
|    4149 | Bài 31                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 主持人点头示意，让下一位选手上台发言。$他悄悄用眼神示意我不要当众揭穿         |
|    4150 | Bài 32                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 董事会决定邀请他出任公司的首席执行官。$他受邀出任国家足球队的主教练。         |
|    4152 | Bài 34                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 请把修改后的文件发到我的电子信箱。$为了方便接收通知，你需要先申请一个         |
|    4153 | Bài 35                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他的钱包不小心从口袋里掉落到了地上。$树上的成熟果实随着微风纷纷掉落。         |
|    4154 | Bài 36                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 遇到不懂的问题要及时请教，千万不要因为怕丢脸而装懂。$在公共场合大吵大         |
|    4155 | Bài 37                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 桂林山水甲天下，因此赢得了许多美好的美称。$他医术高明，在当地获得了“         |
|    4156 | Bài 38                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 移动支付为现代人的日常生活提供了快捷的服务。$高铁的开通让两地之间的往         |
|    4157 | Bài 39                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 老师的教诲，我将永远铭记在心中。$ 无论遇到多大的困难，父母永远是我们         |
|    4158 | Bài 40                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 地面太滑，走路时要小心，别摔倒了。$老人出门时要注意安全，防止意外摔倒         |
|    4160 | Bài 42                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 为了了解消费者的需求，公司组织了一次市场调查。$警方正在对事故的具体原         |
|    4161 | Bài 43                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他在人际交往中总是表现得十分诚恳大方。$他们两个人交往已经好几年了，准         |
|    4163 | Bài 45                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 出门前，母亲再三叮嘱我路上一定要注意安全。$经过再三考虑，他最终决定放         |
|    4164 | Bài 46                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们应该摆事实讲道理，而不是对他人进行人身攻击。$这家公司的核心数据库         |
|    4165 | Bài 47                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 会议期间，双方代表就合作项目充分交换了意见。$孩子们常常在节日时互相交         |
|    4166 | Bài 48                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 李经理多年来一直掌管着公司核心部门的财务工作。$既然把这个重要任务交给         |
|    4167 | Bài 49                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 新学期即将开始，大家都做好了充分的准备。$这个学期他的中文水平有了明显         |
|    4168 | Bài 50                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 为了方便周围居民的生活，小区门口新开了一家商店。$这家文具商店里陈列着         |
|    4169 | Bài 51                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 出门在外，大家一定要注意人身和财产安全。$只有遵守交通规则，才能保证自         |
|    4170 | Bài 52                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 国际市场上石油价格的变动会直接影响全球经济。$这家大型企业主要从事石油         |
|    4171 | Bài 53                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 优秀的科学家通常对大自然的一切事物保持着强烈的好奇心。$老师善于提出有         |
|    4172 | Bài 54                               | Flama Standard Vocabulary (`e2f31... |    26 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 随着经济的发展，村民们的生活越来越富裕了。$他虽然出生在一个富裕的家庭         |
|    4214 | Bài 42                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 坚持晨跑不仅能强健体魄，因为促进了代谢，还能有效缓解精神压力。$采用新         |
|    4217 | Bài 45                               | Flama Standard Vocabulary (`e2f31... |     5 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这份调研报告的精准数据让评审委员会深感震动。$持续不断的创新突破让这家         |
|    4255 | Bài 1                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 无论面对怎样刁钻的客户，前台接待人员始终彬彬有礼。$他性格沉稳，待人接         |
|    4256 | Bài 2                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 保持乐观的心态是很多百岁老人长寿的秘诀。$合理的饮食和适量的运动有助于         |
|    4257 | Bài 3                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 年轻时为了谋生，他曾在许多城市做过各种临时工。$掌握一门实用的技术，是         |
|    4258 | Bài 4                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 打折促销的消息一传出，货架上的商品就被抢购一空。$几场暴风雨过后，原本         |
|    4259 | Bài 5                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 深夜的街道上空无一人，显得格外寂静。$走进会议室，他惊讶地发现里面居然         |
|    4260 | Bài 6                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 坚持体育锻炼能够有效提高人体的免疫力。$我们要增强心理免疫力，不被外界         |
|    4261 | Bài 7                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 虽然在决赛中遗憾失利，但队员们展现了顽强的拼搏精神。$这次商业谈判失利         |
|    4262 | Bài 8                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 松烟制墨是中国古代一项非常精湛的传统技艺。$这款高档书法墨汁正是采用优         |
|    4263 | Bài 9                                | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 柜子里陈列着几件做工极其精致的古代瓷器。$她喜欢在闲暇时把生活打理得十         |
|    4264 | Bài 10                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 夫妻俩含辛茹苦多年，终于把儿子培养成才。$他对待儿子十分严格，但内心充         |
|    4266 | Bài 12                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们可以乘坐机场穿梭巴士直达市中心酒店。$这种双层巴士深受观光游客的喜         |
|    4267 | Bài 13                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 许多中小企业在突如其来的经济危机中宣告破产。$政府采取了积极的财政政策         |
|    4268 | Bài 14                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 落叶缓缓浮在平静的水面上，随波荡漾。$听到那个好消息后，他的脸上浮现出         |
|    4269 | Bài 15                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 请你提出具体的改进措施，不要只谈空洞的理论。$面对复杂局面，我们需要结         |
|    4270 | Bài 16                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他利用业余时间去学校专门学习西餐烹饪技巧。$精湛的烹饪手艺让普通的食材         |
|    4271 | Bài 17                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 能受邀参加这次国际学术研讨会，我深感荣幸。$能够与这位著名学者当面交流         |
|    4272 | Bài 18                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 只有经历过失败，才能有切身的体会。$环境保护直接关系到每个人的切身利益         |
|    4274 | Bài 20                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 凡事预则立，不预则废，提前规划至关重要。$他为人谨慎，凡事都要经过深思         |
|    4275 | Bài 21                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 现代通信网络将世界紧密联系成一个地球村。$生活在地球村的居民应当共同应         |
|    4276 | Bài 22                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 价格昂贵的名牌商品，质量不见得比普通品牌的更好。$大家都赞同的观点，不         |
|    4277 | Bài 23                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 古代帝王常在秋冬季节组织规模庞大的围猎活动。$警方周密部署，对藏匿在深         |
|    4278 | Bài 24                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 充足的睡眠有助于促进青少年的骨骼发育。$技术创新是促进企业持续发展的核         |
|    4279 | Bài 25                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 良好的家庭氛围对孩子的性格养成至关重要。$合理的投资能够有效降低普通家         |
|    4280 | Bài 26                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 青少年应当积极参与体育运动，铸就强健的体魄。$良好的心理素质往往依赖于         |
|    4281 | Bài 27                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 漏洞虽然造成了损失，但现在亡羊补牢依然还来得及。$公司及时撤换了问题产         |
|    4282 | Bài 28                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 工程师们耗时三个月才完成了这幅施工图纸的绘制。$科研人员利用卫星数据精         |
|    4283 | Bài 29                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 政府出台多项税收优惠政策以鼓励青年自主创业。$缺乏充足的流动资金是许多         |
|    4284 | Bài 30                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这家出版社每年都会推出大量优质的学术著作。$他的新书已经交给出版社进行         |
|    4285 | Bài 31                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 深呼吸有助于快速调节紧张的心情。$市场机制能够自动调节商品的供求关系。         |
|    4286 | Bài 32                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 每位员工都应当尽职尽责，做好自己的本职工作。$他不仅立足本职，还积极参         |
|    4287 | Bài 33                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 该城市依托优越的地理位置大力发展跨境贸易。$科技创新应当依托实体经济才         |
|    4288 | Bài 34                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这部电影上映后获得了评论家们的一致好评。$作为独立评论家，他的言辞一向         |
|    4289 | Bài 35                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 燕子低飞通常是天要下雨的征兆。$头晕恶心可能是身体发出的危险征兆。           |
|    4290 | Bài 36                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这把刚磨过的手术刀非常锋利，使用时须格外小心。$记者提出了几个言辞锋利         |
|    4291 | Bài 37                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 年终绩效考核直接关系到员工的奖金发放。$科学的管理模式有助于大幅提升团         |
|    4292 | Bài 38                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 事已至此，我们不如将错就错，看看能否有意外的收获。$既然台词说错了，演         |
|    4293 | Bài 39                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他不想把宝贵的精力白白浪费在无谓的生活琐事上。$这对年轻夫妇常常因为一         |
|    4294 | Bài 40                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 在做出决定之前，你必须先搞清楚具体原因。$ 我们花了两天时间，终于搞清         |
|    4295 | Bài 41                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这两款手机在外观设计上有着许多相似之处。$我们俩的家庭背景相似，因此交         |
|    4296 | Bài 42                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 久坐之后，站起来舒展一下身体会舒服很多。$听到这个好消息，他紧锁的眉头         |
|    4297 | Bài 43                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 专家通常利用心理测量工具来评估求职者的职业倾向。$学校定期为学生进行心         |
|    4298 | Bài 44                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 部门经理在晨会上向大家传达了董事会的最新决定。$这幅画作准确地传达出了         |
|    4300 | Bài 46                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 由于缺乏阅读，他的写作语言显得十分贫乏。$这个地区虽然自然资源贫乏，但         |
|    4301 | Bài 47                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 经常熬夜和过度劳累会导致人的记忆力明显减退。$他拥有惊人的记忆力，能够         |
|    4302 | Bài 48                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 企业唯有不断创新，才能在市场中领先于竞争对手。$知己知彼才能制定出有效         |
|    4304 | Bài 50                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 由于突发恶劣天气，考察团不得不临时调整接下来的行程。$这次出差的行程安         |
|    4307 | Bài 53                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 专家根据现场留下的痕迹推测出了事故原因。$从目前掌握的数据来看，这只是         |
|    4308 | Bài 54                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 写作者需要从纷繁的生活素材中选取最具代表性的细节。$该实验选取了不同年         |
|    4309 | Bài 55                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 新政策一经出台，市民们便纷纷发表自己对此举的看法。$秋风吹过，金黄的树         |
|    4310 | Bài 56                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 刚出门就踩了一脚泥，他觉得自己今天真晦气。$遇到这种不讲理的人，大家只         |
|    4311 | Bài 57                               | Flama Standard Vocabulary (`e2f31... |    40 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这种鸟类的生活习性与气候变化密切相关。$ 饲养野生动物前必须深入了解其         |
|    4312 | Bài 58                               | Flama Standard Vocabulary (`e2f31... |     2 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 合理规划作息能有效缓解疲劳，从而提高工作效率。$科技创新降低了生产成本         |
|    4349 | Bài 2                                | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 传说很多探险家曾深入亚马逊雨林，寻找失落的黄金宝藏。$民间口头文学是一         |
|    4350 | Bài 3                                | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们要严惩那些打击报复举报人的违法犯罪行为。$盲目地采取报复手段不仅解         |
|    4351 | Bài 4                                | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 小女孩今天扎了一对俏皮的羊角辫子。$工作中一定要遵章守纪，免得被竞争对         |
|    4352 | Bài 5                                | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这座现代建筑的外观融合了传统园林元素，整体构思别具匠心。$展厅内的灯光         |
|    4353 | Bài 6                                | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 从近期的经济数据中，不难看出该行业正在逐步复苏。$通过双方的交涉细节，         |
|    4354 | Bài 7                                | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 春天一到，茶农们便上山采摘明前茶。$他在舞台上展现出了非凡的艺术风采。         |
|    4355 | Bài 8                                | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他神色慌张，但极力掩饰，普通人很难察觉出异样。$凭借多年的职业敏感，记         |
|    4356 | Bài 9                                | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们应该趁年轻多学一些本领，积累经验。$这道菜要趁热吃才能品尝出最地道         |
|    4357 | Bài 10                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 因为昨晚加班错过了球赛直播，他今天特意观看了重播。$这部经典电视剧深受         |
|    4358 | Bài 11                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 该队因核心球员受伤而在半决赛中惨遭出局。$企业若不加快技术革新，很快就         |
|    4359 | Bài 12                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 博物馆里的展品多数是不允许观众触摸的。$走进古城，你仿佛能触摸到岁月的         |
|    4360 | Bài 13                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这几位所谓的评论家在媒体上互相吹捧，令人生厌。$下属对他的极力吹捧，反         |
|    4362 | Bài 15                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 绿色低碳产业在新一轮科技革命中大有可为。$青年一代在乡村振兴的广阔舞台         |
|    4364 | Bài 17                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 评委对每位选手的现场表现都进行了极其专业而中肯的点评。$著名学者受邀在         |
|    4365 | Bài 18                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 每逢周末，他都喜欢去郊外的湖边静心钓鱼。$广大网民要提高警惕，切勿点击         |
|    4366 | Bài 19                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | hanviet: ĐẤU / ĐẨU                                      |
|    4367 | Bài 20                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 通缉犯在偏远山村里躲藏了数月，最终还是落入了法网。$小女孩和同伴玩捉迷         |
|    4368 | Bài 21                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他在公众场合情绪失控，竟然当众扇了对方一个耳光。$现实的残酷数据给那些         |
|    4369 | Bài 22                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 网络社交平台上虚假广告泛滥成灾，严重损害了消费者的合法权益。$夏季暴雨         |
|    4371 | Bài 24                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 绿色低碳出行已成为越来越多现代都市人所践行的新风尚。$ 尊老爱幼不仅是         |
|    4372 | Bài 25                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 在社区人员的帮助下，他决心改邪归正，重新做人。$法律不仅惩罚罪犯，也致         |
|    4373 | Bài 26                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我找了半天，敢情钥匙就在你兜里。$你要是能帮我这个忙，那敢情好！            |
|    4374 | Bài 27                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 市民如有线索，请立即与当地市公安局联系。$他前往公安局出入境管理处办理         |
|    4375 | Bài 28                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他因严重违纪被依法开除党籍和公职。$依法履行公职的人员应当自觉接受社会         |
|    4376 | Bài 29                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 由于项目工期极其紧张，大家连吃饭都顾不上了。$情况万分紧急，他顾不上个         |
|    4377 | Bài 30                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 该案件涉及跨境纠纷，两地法院在管辖权上存在争议。$这片海域属于该国领海         |
|    4379 | Bài 32                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 第二次世界大战给整个人类文明带来了一场空前的浩劫。$森林大火使数以万计         |
|    4380 | Bài 33                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 做生意讲究“和气生财”，态度恶劣只会赶走客户。$虽在观点上各抒己见，但         |
|    4381 | Bài 34                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这篇文章首尾呼应，结构十分严谨。$两支部队在战场上紧密呼应，迅速击溃了         |
|    4382 | Bài 35                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 相比于天天打车，买一辆二手车代步显然更划算。$促销期购买年卡非常划算，         |
|    4383 | Bài 36                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他的论点缺乏足够的数据支撑，换言之，其结论并不可信。$资源是有限的，换         |
|    4385 | Bài 38                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 科学家通过基因编辑技术成功培育出抗旱作物品种。$创新已经深深植根于这家         |
|    4387 | Bài 40                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 适度的户外运动是都市白领减压的绝佳方式。$深海潜水员升井时必须在减压舱         |
|    4388 | Bài 41                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这座国家级自然保护区坐落于多省交界的原始森林中。$两国交界处的边境贸易         |
|    4391 | Bài 44                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 两国领导人就深化双边经贸合作达成了重要共识。$本次跨国经贸洽谈会吸引了         |
|    4392 | Bài 45                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 护士用医用酒精对伤口周围进行了消毒处理。$警方在路口严厉查处酒后驾驶，         |
|    4393 | Bài 46                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 安理会一致通过了关于维持地区和平的最新决议。$大会以绝大多数赞成票形成         |
|    4395 | Bài 48                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 孩子在楼梯上不小心摔倒，把膝盖磕破了。$一家人围坐在客厅里，一边闲聊一         |
|    4396 | Bài 49                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 李白的诗歌中大量运用了夸张的修辞手法，具有极强的浪漫主义色彩。$他的表         |
|    4397 | Bài 50                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 该公司连续三年出现严重亏损，面临退市风险。$经过一系列改革，这家国有企         |
|    4398 | Bài 51                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这双鞋的鞋带勒得太紧，把脚背都勒出了一道红印。$在困难时期，大家咬紧牙         |
|    4399 | Bài 52                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 在数学计算中，求一个数的立方即将其自乘三次。$这个水库的有效蓄水量可达         |
|    4401 | Bài 54                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他每天早晨都要快速浏览一下当天的国际财经新闻。$这项功能支持用户在没有         |
|    4402 | Bài 55                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这家研究机构广泛搜罗各领域的青年学者。$由于缺乏创新，这家老店门可罗雀         |
|    4404 | Bài 57                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 开封后的茶叶应当放在干燥阴凉处密封保存，以免受潮变质。$航天器舱门必须         |
|    4405 | Bài 58                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这座古庙依山而建，历经数百年风雨依然完好。$每逢初一十五，许多信徒都会         |
|    4406 | Bài 59                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 经过十几个小时的颠簸，考察团队终于安全抵达了目的地。$作为全球知名的旅         |
|    4407 | Bài 60                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 无论路途多么遥远，游子们都会赶回家吃年夜饭。$除夕之夜，全家人围坐在一         |
|    4408 | Bài 61                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 虽然离家多年，他一张口依然带着浓重的乡音。$这幅油画使用了浓重的暗色调         |
|    4409 | Bài 62                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 如果实验数据存在严重偏差，整个研究结论的可靠性都会受到质疑。$执行政策         |
|    4410 | Bài 63                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们虽是萍水相逢，却一见如故，谈得十分投机。$在旅途中与萍水相逢的陌生         |
|    4411 | Bài 64                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我们要高举科技创新的旗帜，加快构建现代化产业体系。$鲁迅先生是中国现代         |
|    4412 | Bài 65                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 两国元首在峰会结束后共同签署了联合公报。$双方经过数月的谈判，终于正式         |
|    4413 | Bài 66                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这项社保改革方案关系到广大劳动者的切身利益。$ 只有经历过挫折的人，才         |
|    4414 | Bài 67                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 出国前夕，许多亲友纷纷前来为他饯行。$在亲友们的共同见证下，两位新人庄         |
|    4415 | Bài 68                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 官方媒体今日受权发布了该项联合声明的全文。$如果想深入了解该研究的论据         |
|    4416 | Bài 69                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 选拔干部不仅要考察业务能力，更要看其人品如何。$他一向为人谦逊正直，人         |
|    4418 | Bài 71                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 成年子女依法对丧失劳动能力的父母负有赡养义务。$他不顾工作繁忙，始终悉         |
|    4419 | Bài 72                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 该报今日发表社论，呼吁各方保持克制。$这篇社论深刻剖析了当前的经济形势         |
|    4421 | Bài 74                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 青少年应当学会尊敬师长、关爱同伴。$在校期间，他虚心接受师长的教诲，取         |
|    4422 | Bài 75                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 警方迅速采取果断措施，防止事态进一步恶化。$目前该地区的事态发展引起了         |
|    4423 | Bài 76                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 数千名投资者在这起特大金融诈骗案中受害。$持续的干旱天气导致当地农作物         |
|    4424 | Bài 77                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 唯有秉持开放包容的心态，才能在经贸摩擦中寻求双赢的解决方案。$校企合作         |
|    4425 | Bài 78                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 顺着这条林荫小道一直往前走，就能看到湖泊。$他现在正在气头上，你最好先         |
|    4427 | Bài 80                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 做生意应当恪守诚信底线，绝不能干损人利己的勾当。$这种损人利己的做法最         |
|    4428 | Bài 81                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 为了扶持这个公益项目，他不惜自掏腰包投入了数万元启动资金。$消费者往往         |
|    4429 | Bài 82                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这个孩子平时非常听话，从不让父母操心。$你要做个听话的员工，才能尽快融         |
|    4432 | Bài 85                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 我现在手头事务繁多，实在难以脱身参加会议。$他凭借机智勇敢，最终从歹徒         |
|    4434 | Bài 87                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他的供词与警方的调查结果完全吻合。$实验数据与理论模型的预测高度吻合。         |
|    4435 | Bài 88                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 雷达屏幕上突然出现了一个高速移动的不明物体。$光线照射在不透明的物体上         |
|    4436 | Bài 89                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 本刊将在下期对该热点学术争议进行深入专题探讨。$关于这项资金的具体分配         |
|    4437 | Bài 90                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这项政策的推行打破了该领域以往的陈规，开创了先例。$法官在审理此案时，         |
|    4438 | Bài 91                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 他不仅长相酷似父亲，连性格也极为相像。$像这样重大的战略决策，必须经过         |
|    4439 | Bài 92                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 警方行动之前，绝对不能泄露任何风声。$未经允许泄露他人个人信息属于违法         |
|    4441 | Bài 94                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 看到朋友陷入困境，我们绝不能袖手旁观。$面对损害公共利益的行为，每个公         |
|    4442 | Bài 95                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 学者穷其一生，只为在浩瀚典籍中寻觅历史的真相。$青年艺术家漫步在古城街         |
|    4443 | Bài 96                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 长期重复单调的流水线工作让他深感厌倦。$她早已厌倦了都市名利场上的虚伪         |
|    4444 | Bài 97                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 政府出台了多项政策，以确保养老金按时足额发放。$个人养老金制度的实施为         |
|    4445 | Bài 98                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 商务谈判中，得体的仪表能给对方留下良好的第一印象。$飞行员需时刻密切关         |
|    4446 | Bài 99                               | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 作为公众人物，她的一举一动都处于媒体和舆论的严密监督之下。$在严格的安         |
|    4447 | Bài 100                              | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 这种治疗方案的效果往往因人而异，需要个体化评估。$教育应当遵循因材施教         |
|    4448 | Bài 101                              | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 著名学者应邀出席了本届国际汉学论坛并致辞。$他应邀担任该项国际赛事的决         |
|    4449 | Bài 102                              | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 诈骗分子常以“高额回报”为诱饵，诱骗缺乏风险意识的老人投资。$警方巧妙         |
|    4450 | Bài 103                              | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 很多语言词汇的搭配并没有严密逻辑，而是约定俗成的结果。$春节贴春联这一         |
|    4451 | Bài 104                              | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 她身着一袭素雅的旗袍，举手投足间尽显东方女性的古典韵味。$这首古诗语言         |
|    4453 | Bài 106                              | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 选择一个高度适中的枕头有助于改善颈椎健康和睡眠质量。$她把头深深埋进枕         |
|    4455 | Bài 108                              | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 值此新春佳节之际，我谨向全体员工致以最诚挚的节日祝福。$由于连日暴雨引         |
|    4456 | Bài 109                              | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 新产品的发布会预计将于下月中旬正式举行。$四月中旬，这里的樱花将进入盛         |
|    4457 | Bài 110                              | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 本次研讨会为所有参会专家统一提供免费住宿。$旅游旺季期间，景区的住宿价         |
|    4458 | Bài 111                              | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 政府将着力解决中低收入群体的住房问题。$企业转型期应着力提升自主研发与         |
|    4459 | Bài 112                              | Flama Standard Vocabulary (`e2f31... |    50 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 退休后，他在乡下过着自由自在的田园生活。$海鸥在碧蓝的天空中自由自在地         |
|    4460 | Bài 113                              | Flama Standard Vocabulary (`e2f31... |    28 |    Tier 1   | RAW_SCALAR_DELIM | example_jp: 做生意不仅需要敏锐的市场洞察力，更要讲求诚信为本。$经过多年打拼，他在         |
|    6144 | Bài 001                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: open (v): mở; opening (n): sự mở đầ        |
|    6146 | Bài 003                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: perfect (v): hoàn thiện; perfection        |
|    6148 | Bài 005                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: issue (v): phát hành/cấp; issuer (n        |
|    6150 | Bài 007                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: spite (n): sự thù hằn; spiteful (ad        |
|    6152 | Bài 009                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: shallowness (n): sự nông cạn; shall        |
|    6153 | Bài 010                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: honor (v): tôn vinh; honorable (adj        |
|    6155 | Bài 012                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: destine (v): định sẵn; destined (ad        |
|    6156 | Bài 013                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: sign (v/n): ký; signup (n): sự đăng        |
|    6157 | Bài 014                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: indeed (adv): thật vậy; real (adj):        |
|    6158 | Bài 015                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: cover (v): bao phủ/đưa tin; covered        |
|    6159 | Bài 016                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: suggest (v): gợi ý; suggestion (n):        |
|    6160 | Bài 017                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: gather (v): tập hợp; gathered (adj)        |
|    6161 | Bài 018                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: internationalize (v): quốc tế hóa;         |
|    6162 | Bài 019                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: yielding (adj): dễ uốn; yielder (n)        |
|    6163 | Bài 020                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: locally (adv): tại địa phương; loca        |
|    6164 | Bài 021                              | En4Everyone (`13ff54d7...`)          |    20 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: modal (adj): thuộc chế độ; modality        |
|    6169 | Bài 03                               | En4Everyone (`13ff54d7...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: represents (v): (ngôi 3); represent        |
|    6172 | Bài 06                               | En4Everyone (`13ff54d7...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: sufficient (adj): đủ; insufficient         |
|    6173 | Bài 07                               | En4Everyone (`13ff54d7...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: adhere (v): tuân thủ; adhering (v-i        |
|    6175 | Bài 09                               | En4Everyone (`13ff54d7...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: grain (n): hạt granularity (n): mức        |
|    6176 | Bài 10                               | En4Everyone (`13ff54d7...`)          |    30 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: impair (v): làm suy giảm impairment        |
|    6178 | Family                               | En4Everyone (`13ff54d7...`)          |    25 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: spousal (adj): thuộc vợ chồng; marr        |
|    6181 | Bài 1                                | En4Everyone (`13ff54d7...`)          |    65 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: polar (adj): thuộc cực; bear (n): g        |
|    6183 | Bài 2                                | En4Everyone (`13ff54d7...`)          |    40 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: cook (v): nấu; top (n): mặt trên; c        |
|    6184 | Bài 3                                | En4Everyone (`13ff54d7...`)          |    40 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: construct (v): construct; construct        |
|    6185 | Bài 4                                | En4Everyone (`13ff54d7...`)          |    40 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: vehicular (adj): thuộc về xe cộ; ve        |
|    6186 | Bài 5                                | En4Everyone (`13ff54d7...`)          |    40 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: retail (n/adj): bán lẻ; retailer (n        |
|    6188 | Bài 7                                | En4Everyone (`13ff54d7...`)          |    40 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: mini (adj): nhỏ; bar (n): quầy đồ u        |
|    6189 | Bài 8                                | En4Everyone (`13ff54d7...`)          |    28 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: curbside (adj): bên lề đường; curbi        |
|    6191 | Bài 2                                | En4Everyone (`13ff54d7...`)          |    22 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: police (n): lực lượng cảnh sát; pol        |
|    6192 | Bài 23                               | En4Everyone (`6b2a8fec...`)          |    35 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: economy (n): nền kinh tế; economic         |
|    6854 | 1. En4Everyone (Advanced Vocabulary) | En4Everyone (`6b2a8fec...`)          |     5 |    Tier 1   | RAW_SCALAR_DELIM | Word Family: pandemic (n): đại dịch; pandemic (a        |
|    6856 | 3. Luyện gõ - Gõ cách đọc (Reading)  | Gõ cách đọc (`0b9a37e5...`)          |     2 |    Tier 1   | RAW_SCALAR_DELIM | Example: <p>毎日、朝ご飯を食べます。</p>                            |

### Tier 0: Pristine Active Decks (3 Decks)

| Deck ID | Deck Name                            | NoteType Name (ID)                   | Notes | Health Tier | Issue Codes | Representative Evidence Sample |
| ------: | :----------------------------------- | :----------------------------------- | ----: | :---------: | :---------- | :----------------------------- |
|     347 | Bài 1                                | Flama Standard Vocabulary (`e2f31... |     2 |    Tier 0   | PRISTINE    | Pristine (0 defects detected)  |
|    4564 | bài 1                                | Kanji_N3 (`91f567ab...`)             |     2 |    Tier 0   | PRISTINE    | Pristine (0 defects detected)  |
|    6860 | 7. Luyện gõ - Gõ đáp án JS (Basic... | Gõ đáp án (`a3048e55...`)            |     2 |    Tier 0   | PRISTINE    | Pristine (0 defects detected)  |

### Tier 0: Structural & Marketplace Clone Index (4,033 Decks)
The 4,033 decks with 0 direct notes comprise:
- **2,150 Hierarchical Parent Decks**: Organizational tree categories in `decks` table.
- **1,680 Marketplace Clone Overlay Records**: Container records under `DeckInstall` pointing to source notes.
- **203 Draft / Empty Decks**: User decks awaiting imports.

All 4,033 empty decks are fully accounted for, structurally intact, and require zero database modification.

---

## 5. Concrete 3-Phase Zero-Data-Loss Upgrade Roadmap

### 5.1 Roadmap Overview & Phase Sequence
The remediation roadmap establishes a strictly ordered 3-phase execution sequence to achieve 100% Native Array compliance:

```
+-----------------------------------------------------------------------------------+
|               PHASE 1: PRESENTATION TEMPLATE MODERNIZATION                        |
|  - Zero DB mutation required. Safe drop-in HTML/CSS/JS template upgrades.         |
|  - Fix unclosed <div> bug in 5 grammar templates (0a86851a, 266cbc84, etc.).      |
|  - Upgrade 14 Incompatible Templates to support Mustache dot loops & runtime.     |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|               PHASE 2: ARRAY FIELD DATA NORMALIZATION                             |
|  - Zero data loss: Bracket-Shielding Algorithm never splits inside (), [], 【】, 「」.|
|  - IPA Slash Protection: 100% preservation of phonemic /.../ in En4Everyone.      |
|  - Safe migration engine: 250-note transactional chunks, dry-run mode, preimage   |
|    snapshots (SHA-256), and automated instant rollback on failure.                |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|               PHASE 3: SEMANTIC ANOMALY QUARANTINE & CURATION                     |
|  - Quarantine protocol for 4 field_values_extras notes (Decks 6857 & 6858).       |
|  - Automated Unihan/Hán-Việt dictionary lookup for 709 Kanji-in-hanviet notes.    |
|  - Phonetic kana relocation for 217 Kana-in-hanviet notes.                         |
|  - Transposition reversal for 169 Vietnamese-in-reading notes.                    |
+-----------------------------------------------------------------------------------+
```

### 5.2 Phase 1: Presentation Template Modernization (Zero DB Mutation)
All 14 incompatible templates are upgraded via drop-in template code updates. No database writes are required.

#### Complete Upgrade Specifications for Key Templates

##### Template 1: Grammar & Literary Quotes Card (`0a86851a-843e-48b5-8275-66f244c595b7`)
- **Decks Affected**: 19 Decks (Decks 1399–1416, 6861; 92 Notes)
- **Associated NoteType**: `文法N1` (`4fc2eb8e-16ba-4c6b-b323-a5f66bc41cd8`)
- **Fix Description**: Repaired outer `<div style='display:flex...'>` tag nesting, eliminated orphan `</div>`, replaced fixed `100vh` with responsive CSS clamp, and embedded `flama-native-arrays.v1` runtime.

```html
<!-- DROP-IN UPGRADE: Front HTML -->
<div class="card grammar-card-front">
  <div class="grammar-title-large">{{name}}</div>
</div>
```

```html
<!-- DROP-IN UPGRADE: Back HTML (Balanced Divs & Array-Aware) -->
<div class="card grammar-card-back">
  {{#name}}
  <div class="grammar-header">
    <div class="grammar-name">{{name}}</div>
    {{#Audio}}
    <div class="audio-btn-wrapper">
      <audio id="custom-audio" src="{{Audio_url}}"></audio>
      <button class="audio-btn" type="button" onclick="document.getElementById('custom-audio').play()">🔊</button>
    </div>
    {{/Audio}}
  </div>
  {{/name}}

  {{#meaning}}
  <div class="grammar-section">
    <div class="grammar-meaning">{{{meaning}}}</div>
    {{#structure}}<div class="grammar-structure">{{structure}}</div>{{/structure}}
  </div>
  {{/meaning}}

  {{#additional_example}}
  <div class="grammar-section">
    <div class="section-title">◆ Ví dụ khác:</div>
    <div class="example-box">
      <div class="example-jp">{{{additional_example}}}</div>
      {{#example_vi}}<div class="example-vi">{{{example_vi}}}</div>{{/example_vi}}
    </div>
  </div>
  {{/additional_example}}

  {{#notes}}
  <div class="grammar-section">
    <div class="section-title">◆ Ghi chú:</div>
    <span data-native-array-guard="notes" style="display:contents">
      {{#notes}}<span data-native-array-presence hidden></span>{{/notes}}
      <span data-native-array-value>{{#notes}}<div class="note-item">{{.}}</div>{{/notes}}</span>
    </span>
  </div>
  {{/notes}}
</div>

<script>
// flama-native-arrays.v1 runtime
(function () {
  'use strict';
  document.querySelectorAll('[data-native-array-guard]').forEach(function (guard) {
    var present = Array.from(guard.children).filter(function (child) { return child.hasAttribute('data-native-array-presence'); });
    if (!present.length) { guard.remove(); return; }
    present.forEach(function (child) { child.remove(); });
    var content = document.createDocumentFragment();
    while (guard.firstChild) content.appendChild(guard.firstChild);
    guard.replaceWith(content);
  });
})();
</script>
```

##### Template 2: 文法N1 Thẻ 1 (`266cbc84-dd0e-443b-9fbe-1d5a49cee753`)
- **Decks Affected**: 4 Decks (Decks 4568–4571; 139 Notes)
- Shares the identical balanced markup and CSS as Template 1, curing all 139 notes in Decks 4568–4571.

##### Template 3: TechKeyword (`4f184341-1fcc-4949-9edd-c798c5770131`)
- **Decks Affected**: 6 Decks (Decks 1820, 6138–6141, 6193; 68 Notes)
- **Fix Description**: Replaced flat string coercion of `Meaning`, `Usage`, and `AdditionalContent` with native dot iteration loops `{{#Meaning}}<div class="item">{{{.}}}</div>{{/Meaning}}`.

##### Template 4: JapTest (`55c18e42-a792-4d83-82a6-e33ec3537140`)
- **Decks Affected**: 2 Decks (Decks 348, 350; 3 Notes)
- **Fix Description**: Upgraded `Pronounce` to flex-wrap badge pills and `Meaning` to multi-block containers.

### 5.3 Phase 2: Array Field Data Normalization (Zero Data Loss)
#### Bracket-Shielding Splitting Algorithm (`split_outside_brackets`)
Naive splitting on commas or semicolons corrupts explanatory notes (e.g. `"số tấm (giấy, ảnh), vật mỏng"` or `"おくりもの【贈り物, 贈物】、プレゼント"`). The Bracket-Shielding Algorithm maintains a character nesting depth vector across 6 enclosure types and only executes splits when bracket depth equals 0:

$$\text{is\_splittable}(c, i) = \left( c \in \text{Delimiters} \right) \land \left( \sum_{k} d_k = 0 \right) \land \neg \text{is\_escaped}(i)$$

##### Supported Bracket Enclosures:
1. Parentheses: `(` $\leftrightarrow$ `)` and `（` $\leftrightarrow$ `）`
2. Square Brackets: `[` $\leftrightarrow$ `]` and `［` $\leftrightarrow$ `］`
3. Lenticular Brackets: `【` $\leftrightarrow$ `】`
4. Corner Quotes: `「` $\leftrightarrow$ `」` and `『` $\leftrightarrow$ `』`
5. Curly Braces: `{` $\leftrightarrow$ `}`
6. HTML Tags: `<` $\leftrightarrow$ `>`

```python
# Reference Implementation of Bracket-Shielded Splitter
def split_outside_brackets(text: str, delimiters: tuple[str, ...] = (',', '，', '、', ';', '；', '$', '\n')) -> list[str]:
    bracket_map = {'(': ')', '（': '）', '[': ']', '［': '］', '【': '】', '「': '」', '『': '』', '{': '}'}
    close_to_open = {v: k for k, v in bracket_map.items()}
    open_brackets = set(bracket_map.keys())
    close_brackets = set(bracket_map.values())
    tokens, current, stack, in_html = [], [], [], False
    i, n = 0, len(text)
    while i < n:
        char = text[i]
        if char == '<' and not in_html: in_html = True; current.append(char); i += 1; continue
        elif char == '>' and in_html: in_html = False; current.append(char); i += 1; continue
        if not in_html:
            if char in open_brackets: stack.append(char); current.append(char); i += 1; continue
            elif char in close_brackets:
                if stack and stack[-1] == close_to_open[char]: stack.pop()
                current.append(char); i += 1; continue
            if len(stack) == 0 and char in delimiters:
                t = ''.join(current).strip()
                if t: tokens.append(t)
                current = []; i += 1; continue
        current.append(char); i += 1
    if current: tokens.append(''.join(current).strip())
    return tokens
```

#### IPA Slash Protection Algorithm
English learning decks (`En4Everyone`, NoteType `6b2a8fec`, 5,304 Notes) store phonemic transcriptions enclosed in slashes (e.g. `"/ˌrek.əɡˈnaɪz/"` or `"/rɪˈkɔːl/, /ˌriːˈkɔːl/"`). The migration engine strictly protects fields in `{'pronunciation', 'ipa', 'phonetic', 'phatam'}` from slash splitting, splitting only on commas while preserving enclosing boundary slashes intact.

#### Transactional Production Protocol
- **Batch Size**: 250 notes per transaction with consistent snapshot.
- **Optimistic Locking**: Enforce `revision = expected_revision` on every row update.
- **Preimage Snapshots**: Save original JSON and SHA-256 hash in `notes_migration_preimages` before modification.
- **Automated Rollback**: Rollback script (`scripts/migrations/rollback_array_wave.py`) restores snapshots instantly if needed.

### 5.4 Phase 3: Semantic Anomaly Quarantine & Curation
- **Decks 6857 & 6858 Schema Extras Remapping**: Repatriate the 4 notes in `field_values_extras` by writing `Meaning` to `Answer` in Deck 6857, and mapping `Image` to `PromptImage` while archiving explanatory text in `DefinitionHint` for Deck 6858.
- **709 Kanji in `hanviet`**: Automated Unihan dictionary lookup script generates capitalized Sino-Vietnamese readings (e.g. `賛 辞 贈` $\rightarrow$ `"TÁN TỪ TẶNG"`).
- **217 Kana in `hanviet`**: Move Katakana reading into `reading` array field, then generate true Sino-Vietnamese reading from headword.
- **169 Vietnamese in `reading`**: Relocate Vietnamese definitions to `meaning_vi` array, then regenerate Japanese Hiragana readings via MeCab.

---

## 6. Audit Verification & Read-Only Integrity Attestation

### 6.1 Database Read-Only Invariant Attestation
All data and metrics presented in this report were gathered under strict read-only execution modes (`SET TRANSACTION READ ONLY`). Zero INSERT, UPDATE, DELETE, ALTER, or DROP statements were executed against the MySQL production database. Row counts, column structures, and revision numbers remained perfectly invariant throughout the entire audit.

- **Notes Table Count**: Exactly **41,544 rows** (0 rows added, 0 rows deleted).
- **Notes Revision Maximum**: Exactly **1** (0 rows mutated).
- **Checksum Status**: Invariant across all tables.

### 6.2 Mathematical Identity Proofs
The 5-Tier Health Classification satisfies strict set-theoretic partition invariants:
$$\sum_{i=0}^4 |T_i| = 36 + 189 + 575 + 741 + 3 = 1,544 \text{ Active Decks (100.00% Coverage)}$$
$$\sum_{i=0}^4 \text{Notes}(T_i) = 325 + 5,518 + 9,395 + 26,300 + 6 = 41,544 \text{ Notes (100.00% Coverage)}$$
$$1,544 \text{ Active Decks} + 4,033 \text{ Structural Decks} = 5,577 \text{ Total System Decks (100.00% Coverage)}$$
$$\text{Unmapped FieldDef Keys} = 0 \quad (100\% \text{ Schema Alignment})$$

### 6.3 Verification Command & Reproducibility Runbook
To independently verify report freshness, manifest integrity, and dataset invariants:

```powershell
# Run automated verification check
.venv\Scripts\python.exe scripts/audit/generate_master_audit_matrix.py --check

# Run unit test suite
.venv\Scripts\python.exe -m unittest tests/test_master_audit_matrix.py
```
