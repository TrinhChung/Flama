# Master Execution Report: Phase 1 & Phase 2 Database & Template Modernization

**Document ID**: `FLAMA-AUDIT-EXEC-20261023`  
**Report Version**: 1.0.0 (Master Execution Report)  
**Execution Timestamp Window**: `2026-10-23T16:20:00Z` – `2026-10-23T17:15:00Z`  
**Author**: Worker M3 (`teamwork_preview_worker_m3`)  
**Target Database**: MySQL 8.0.40 (`nihongo` database, `localhost:3306`, principal `root@localhost`)  
**Execution Environment**: Python 3.12 (`.\.venv\Scripts\python.exe`), PyMySQL 1.1.1, SQLAlchemy 2.0.35  
**Core Architectural Mandate**: Flama Native Array Model (`AGENTS.md`), No Anki Export, Overlay-Only Clones, Zero Data Loss  

---

## Table of Contents

1. [Executive Summary & Global Invariants](#1-executive-summary--global-invariants)
2. [Phase 1 Modernization of 14 Presentation Templates](#2-phase-1-modernization-of-14-presentation-templates)
3. [Phase 2 Bracket-Shielding Multi-Value Array Migration](#3-phase-2-bracket-shielding-multi-value-array-migration)
4. [Quantitative Before vs After Verification Matrix](#4-quantitative-before-vs-after-verification-matrix)
5. [Automated Test Qualification Matrix](#5-automated-test-qualification-matrix)
6. [Security, Zero Data Loss & Rollback Guarantee Sign-Off](#6-security-zero-data-loss--rollback-guarantee-sign-off)

---

## 1. Executive Summary & Global Invariants

### 1.1 Mission Overview & Execution Scope
This document serves as the authoritative, forensic execution report for the full production deployment of **Phase 1** (Modernization of 14 Incompatible Presentation Templates) and **Phase 2** (Bracket-Shielding Multi-Value Array Normalization on 2,112 notes across 675 decks) within the Flama learning platform database.

Following the initial comprehensive audit documented in `docs/audit/MASTER_DECK_NATIVE_ARRAY_AUDIT_REPORT.md`, two distinct systemic flaws were targeted:
1. **Phase 1 (Presentation Templates)**: 14 card templates exhibited critical rendering bugs in study sessions, including unclosed `<div>` tags triggering DOM breakage and layout collapse on 5 Grammar templates, flat string coercion on array fields (`{{Field}}` rendering concatenated with commas), and absence of client-side array unwrapping scripts.
2. **Phase 2 (Content Normalization)**: Exactly 2,112 notes across 675 decks stored multi-value array fields as "fake 1-element arrays" (e.g., `["Đạt đến mức tối đa; Chinh phục"]`), trapping distinct lexical items inside a single string because legacy Anki/TSV import routines failed to split punctuated delimiters outside protected parentheses.

Both phases were executed against the live local MySQL 8.0 database (`nihongo`) under strict transactional chunking ($\le 250$ notes/transaction), with full cryptographic preimage snapshots stored both in dedicated MySQL tables and immutable JSON manifests.

### 1.2 Global Database Invariant Verification
Direct empirical verification against MySQL 8.0.40 confirms 100% preservation of database structural and content invariants:

| Metric | Pre-Migration Baseline | Post-Phase 1 State | Post-Phase 2 State | Net Delta | Verification Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Total System Notes** | **41,544** | **41,544** | **41,544** | **0** | **100.00% Preserved (Zero Deletion)** |
| **Total System Decks** | **5,577** | **5,577** | **5,577** | **0** | **100.00% Preserved** |
| Active Decks ($\ge 1$ note) | 1,544 | 1,544 | 1,544 | 0 | 100.00% Preserved |
| Empty Structural / Overlay Decks | 4,033 | 4,033 | 4,033 | 0 | 100.00% Preserved |
| Note Types Scanned | 38 | 38 | 38 | 0 | Fully Reconciled |
| Card Templates in Database | 39 | 39 | 39 | 0 | Modernized in Place |
| Active Study Applications | 38 | 38 | 38 | 0 | Fully Reconciled |

### 1.3 Key Architectural Achievements
- **Zero Data Loss Guarantee**: All 41,544 notes and 5,577 decks remain intact. Not a single note, deck, or card was dropped or orphaned.
- **Defects Eradicated to Zero**:
  - Incompatible presentation templates: **14 $\rightarrow$ 0** (100% eradicated).
  - Decks impacted by broken templates: **34 $\rightarrow$ 0** (100% eradicated).
  - Cards impacted by broken templates: **321 $\rightarrow$ 0** (100% eradicated).
  - Fake 1-element array notes: **2,112 $\rightarrow$ 0** (100% eradicated).
  - Decks containing fake 1-element arrays: **675 $\rightarrow$ 0** (100% eradicated).
- **Phonetic & Semantic Protection**: 100% of English for Everyone (En4Everyone) International Phonetic Alphabet (IPA) slashes (`/.../`) and bracketed parenthetical glosses (`(...)`, `（...）`, `[...]`, `【...】`, `「...」`, `{...}`) were shielded from improper splitting.
- **Cryptographic Preimage Snapshots**: Dual-storage rollback snapshots (MySQL table `notes_migration_preimages` + JSON manifest `docs/audit/snapshots/preimage_wave_r1_20261023.json`) record SHA-256 signatures for every modified entity before modification.
- **Rollback Readiness**: Both Phase 1 and Phase 2 rollback engines (`rollback_r2_templates.py` and `rollback_array_wave.py`) were verified in dry-run and live tests, proving complete bi-directional idempotency.

---

## 2. Phase 1 Modernization of 14 Presentation Templates

### 2.1 Scope & Inventory of Modernized Templates
Phase 1 addressed 14 presentation templates identified by AST audit engine `audit_r2_templates.py`. Each template was analyzed for tag balance, section iteration, and CSS responsiveness, then upgraded with full historical tracking in `template_versions`:

| # | Template ID | Template Name | Owner | Pre-Version | Post-Version | Affected Decks | Affected Notes | Issues Resolved |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| 1 | `0a86851a-843e-48b5-8275-66f244c595b7` | Grammar & Literary Quotes Card | 1 | v1 (`c1fa7f3d`) | **v2** (`f71ffce4`) | 19 | 92 | Unclosed `<div>`, rigid 100vh, dot iteration, runtime script |
| 2 | `0d62d4a3-d309-4da6-98e6-ac7dc8f89536` | Front | 1 | v3 (`7768aad6`) | **v4** (`234e424a`) | 1 | 10 | Dot iteration, runtime script injection |
| 3 | `266cbc84-dd0e-443b-9fbe-1d5a49cee753` | Thẻ 1 (Grammar) | 1 | v1 (`227bdd1c`) | **v2** (`2d8f6371`) | 4 | 139 | Unclosed `<div>`, rigid 100vh, dot iteration, runtime script |
| 4 | `273a92a1-4378-4d61-904a-e7582daca5e4` | Thẻ 1 | 1 | v1 (`34a841ef`) | **v2** (`97db8ae9`) | 0 | 0 | Dot iteration, runtime script injection |
| 5 | `36aad069-2991-45a6-8e39-4d89443fa47e` | Sentence | 1 | v1 (`ac967207`) | **v2** (`07064b45`) | 1 | 1 | Dot iteration, runtime script injection |
| 6 | `48a17d92-39bc-48b8-b7ab-745c487b3e1c` | Thẻ 1 (Grammar) | 1 | v1 (`3a1f8930`) | **v2** (`8a701b31`) | 0 | 0 | Unclosed `<div>`, rigid 100vh, dot iteration, runtime script |
| 7 | `4f184341-1fcc-4949-9edd-c798c5770131` | Card 1 [TechKeyword] | 1 | v1 (`381a65d2`) | **v2** (`48ba309f`) | 6 | 68 | Dot iteration on Meaning/Usage, runtime script injection |
| 8 | `55c18e42-a792-4d83-82a6-e33ec3537140` | Card 1 [JapTest] | 1 | v1 (`6b6587e2`) | **v2** (`5aad9d13`) | 2 | 3 | Dot iteration on Meaning/Sentence, runtime script injection |
| 9 | `62daa743-6408-460f-9f13-23c40c95fee6` | Thẻ Kanji tối giản | 1 | v1 (`63b11d1c`) | **v2** (`1bea03d8`) | 0 | 0 | Dot iteration on Back, runtime script injection |
| 10 | `76efe654-7b8b-45fd-8f73-34f6fb2eda33` | Default Quiz Flashcard | 1 | v1 (`ad16dab6`) | **v2** (`9ee7f1d8`) | 1 | 8 | Dot iteration on correct_answer, runtime script injection |
| 11 | `9379dde5-0d73-4a6a-bc6e-90b6d81dae9e` | Grammar Card | 1 | v1 (`efa87084`) | **v2** (`5063f012`) | 0 | 0 | Dot iteration, runtime script injection |
| 12 | `a7f1a1cd-0388-4a64-a712-6ecd92e6ac4f` | Thẻ Kanji tối giản | 1 | v1 (`d2f34469`) | **v2** (`99df3d56`) | 0 | 0 | Dot iteration on Back, runtime script injection |
| 13 | `c51dc3ba-37a6-4245-b61e-6261f367ad24` | Thẻ 1 (Grammar) | 1 | v1 (`184c67d2`) | **v2** (`e2bb80e6`) | 0 | 0 | Unclosed `<div>`, rigid 100vh, dot iteration, runtime script |
| 14 | `d81c0a0a-9d31-4a5a-a91c-46f57ec0923e` | Thẻ 1 (Grammar) | 1 | v1 (`eb48fe76`) | **v2** (`b1baefce`) | 0 | 0 | Unclosed `<div>`, rigid 100vh, dot iteration, runtime script |

*Total Active Scope*: 34 unique decks, 321 active notes.

### 2.2 DOM Structure & Tag Balance Repairs (The 5 Grammar Templates)
The 5 Grammar templates (`0a86851a`, `266cbc84`, `48a17d92`, `c51dc3ba`, `d81c0a0a`) suffered from severe DOM nesting defects:
1. **Unclosed `<div>` at Header**: An outer `<div style='display: flex; flex-direction: column; ...'>` opened immediately after `{{#name}}` was missing a closing `</div>` before `{{/name}}`.
2. **Orphaned `</div>` at Additional Example**: A dangling `</div>` was placed outside `{{#additional_example}}`, causing invalid HTML parsing when `additional_example` was empty or missing.
3. **Rigid Viewport Height**: `height: 100vh;` in Front HTML caused layout clipping and overflow on mobile devices.

#### Verbatim Code Repair Diff (Back HTML):
```diff
--- Baseline Back HTML (v1)
+++ Modernized Back HTML (v2)
@@ -1,13 +1,14 @@
     <!-- Ví dụ: Hiển thị lại từ vựng (nếu muốn) -->
     {{#name}}
 <div style='
     display: flex;
     flex-direction: column;
     justify-content: flex-start;
     text-align: start;
     padding-left: 20px;
     font-family: "Arial"; 
     font-size: 18px;'
 >
     <div style='
         font-family: "Arial"; 
         font-size: 36px; 
@@ -19,10 +20,11 @@
     >
         {{name}}
 {{#Audio}}
   <audio id="custom-audio" src="{{Audio_url}}"></audio>
   <button onclick="document.getElementById('custom-audio').play()">🔊</button>
 {{/Audio}}
     </div>
+</div>
     {{/name}}

     <!-- Ngữ nghĩa / Cấu trúc (nếu muốn lặp lại) -->
@@ -49,12 +51,12 @@
     <div style='display: flex; padding-top: 10px; color: #3367d6; font-weight: bold;'>
         ◆ Ví dụ khác:
     </div>
 <div style='display: flex; flex-direction: column; padding-top: 10px;'>
     <div style="font-size: 20px; display: flex; align-items: center;">
-        {{{additional_example}}}
+        {{#additional_example}}<div class="array-item">{{{.}}}</div>{{/additional_example}}
 {{#Example_Audio}}
   <audio id="example-audio" src="{{Example_Audio_url}}"></audio>
   <button onclick="document.getElementById('example-audio').play()">🔊</button>
 {{/Example_Audio}}
     </div>
-    {{/additional_example}}
 </div>
+    {{/additional_example}}
```

#### Verbatim Code Repair Diff (Front HTML & Shared CSS):
```diff
--- Baseline Front HTML & CSS (v1)
+++ Modernized Front HTML & CSS (v2)
- <div style='height:100vh;text-align:center;display:flex;justify-content:center;align-items:center;font-size:70px;font-weight:bold;color:#e53c20'>
+ <div style='min-height:100vh;text-align:center;display:flex;justify-content:center;align-items:center;font-size:70px;font-weight:bold;color:#e53c20'>
  {{name}}
  </div>

  .card {
      font-family: arial;
      font-size: 20px;
      text-align: center;
      color: black;
      background-color: white;
+     flex-wrap: wrap;
  }
```

### 2.3 Mustache Dot Iteration (`{{{.}}}`) Syntax Upgrade
In accordance with Flama's Native Array Policy (`AGENTS.md`), array-typed fields stored as JSON lists must be iterated via Mustache sections using dot iteration (`{{{.}}}`) instead of flat string coercion.

The modernizing engine replaced flat placeholder references:
- **Card 1 [TechKeyword] (`4f184341`)**:
  - `{{{Meaning}}}` $\rightarrow$ `{{#Meaning}}<span class="array-item">{{{.}}}</span>{{/Meaning}}`
  - `{{{Usage}}}` $\rightarrow$ `{{#Usage}}<div class="array-item">{{{.}}}</div>{{/Usage}}`
  - `{{{AdditionalContent}}}` $\rightarrow$ `{{#AdditionalContent}}<div class="array-item">{{{.}}}</div>{{/AdditionalContent}}`
- **Card 1 [JapTest] (`55c18e42`)**:
  - `{{{Meaning}}}` $\rightarrow$ `{{#Meaning}}<div class="array-item">{{{.}}}</div>{{/Meaning}}`
  - `{{{Sentence}}}` $\rightarrow$ `{{#Sentence}}<div class="array-item">{{{.}}}</div>{{/Sentence}}`
- **Default Quiz Flashcard (`76efe654`)**:
  - `{{correct_answer}}` $\rightarrow$ `{{#correct_answer}}<span class="array-item">{{{.}}}</span>{{/correct_answer}}`
- **Front (`0d62d4a3`)**:
  - `{{Reading}}` $\rightarrow$ `{{#Reading}}<span class="array-item">{{{.}}}</span>{{/Reading}}`
- **Sentence (`36aad069`)**:
  - `{{{Definition}}}` $\rightarrow$ `{{#Definition}}<div class="array-item">{{{.}}}</div>{{/Definition}}`
- **Thẻ Kanji tối giản (`62daa743`, `a7f1a1cd`)**:
  - `{{{Back}}}` $\rightarrow$ `{{#Back}}<div class="array-item">{{{.}}}</div>{{/Back}}`

### 2.4 Flama Native Arrays Runtime Script (`flama-native-arrays.v1`)
To ensure bulletproof client-side rendering even in legacy webviews or embedded iframe contexts, each modernized template was injected with the `flama-native-arrays.v1` runtime script at the end of `back_html`:

```html
<!-- Flama Native Array Client Unwrapper v1 -->
<script data-flama-runtime="native-arrays.v1">
(function() {
  if (window.__flama_native_arrays_initialized) return;
  window.__flama_native_arrays_initialized = true;
  document.querySelectorAll('.array-item').forEach(function(el) {
    if (el.textContent && el.textContent.startsWith('["') && el.textContent.endsWith('"]')) {
      try {
        var items = JSON.parse(el.textContent);
        if (Array.isArray(items)) {
          el.innerHTML = items.map(function(item) {
            return '<span class="native-array-val">' + item + '</span>';
          }).join(', ');
        }
      } catch(e) {}
    }
  });
})();
</script>
```

### 2.5 Historical Versioning & Snapshot Trail
- **SQLAlchemy `Session.before_commit` Hook**: All template updates were executed using Flama's ORM model with `mark_template_version(...)`. This created 14 new immutable rows in `template_versions` with incremented `version_no` (13 templates from v1 $\rightarrow$ v2; template `0d62d4a3` from v3 $\rightarrow$ v4) and updated `templates.current_version_id`.
- **Preimage Snapshot**: Saved to `docs/audit/snapshots/preimage_templates_phase1.json` (66,086 bytes) capturing full pre-migration `front_html`, `back_html`, `shared_css`, `input_schema`, and cryptographic SHA-256 hashes for all 14 templates.

---

## 3. Phase 2 Bracket-Shielding Multi-Value Array Migration

### 3.1 Population Demographics & Root Cause
The R1 audit engine discovered that out of 41,544 total notes in the database:
- **2,112 notes** across **675 active decks** contained array fields erroneously formatted as single-element lists containing punctuated text (e.g. `["Item 1; Item 2 / Item 3"]`).
- **Root Cause**: The original Anki TSV importer treated entire lines as a single string and wrapped them in `[raw_string]`. Because delimiters were never parsed into genuine multi-item JSON arrays, frontend renderers and mobile cards displayed ugly raw semicolons and slashes.

#### Distribution by Field Definition:
| NoteType ID | NoteType Name | Target Field Def ID | Field Name | Notes Affected | Primary Delimiters |
| :--- | :--- | :--- | :--- | :---: | :--- |
| `e2f310a8-ecb3-4446-8a93-4c258e52b132` | Flama Standard Vocabulary | `e71ec494-dbfb-41b2-8b89-1e3584d6aeaf` | `translation_vi` | 1,939 | `;`, `/`, `、`, `,` |
| `e2f310a8-ecb3-4446-8a93-4c258e52b132` | Flama Standard Vocabulary | `cfe0d506-f625-4db3-b249-960126870f51` | `reading` | 19 | `$`, `;`, `/` |
| `6b2a8fec-f04b-4b2e-a52c-46132049d5ef` | English for Everyone | `89d816fb-ec47-49f9-aa2b-b6d19dcfe334` | `Meaning` | 137 | `;`, `/`, `,` |
| `6b2a8fec-f04b-4b2e-a52c-46132049d5ef` | English for Everyone | `e2a0b1c9-75a8-4e89-8d54-1b0d778d9122` | `Antonym_VI` | 4 | `;`, `/` |
| `0bece587-6e6e-44c1-9c60-e41c09b6860f` | Kanji_N3 | `1ecf9453-cf85-4521-8278-f7b55db56f18` | `Nghĩa` | 14 | `;`, `,` |
| `db5c9ec6-89c5-4ceb-8c8f-287714be0ba2` | Gõ chép chính tả | `44883907-735a-4b0d-9b51-789a7f3408ec` | `Answer` | 3 | `/`, `;` |
| **Total Target Scope** | **6 Distinct NoteTypes** | **6 Target Field Definitions** | — | **2,112 notes** | **2,116 field instances** |

### 3.2 The `split_outside_brackets_v2` Bracket-Shielding Algorithm
A naive `string.split(';')` or `string.split('/')` causes catastrophic data loss by cutting through parenthetical glosses, e.g.:
- `tướng mạo (khẩu ngữ cổ)` $\rightarrow$ Naive split on `/` $\rightarrow$ `["tướng mạo (khẩu ngữ", "cổ)"]` (BROKEN).
- `Được (mọi người/ai đó) gọi là / mệnh danh là gì.` $\rightarrow$ Naive split $\rightarrow$ `["Được (mọi người", "ai đó) gọi là", "mệnh danh là gì."]` (CORRUPTED).

#### Algorithm Architecture:
The `split_outside_brackets_v2` engine executes a multi-pass tokenization with zero external regex race conditions:
1. **Balanced Bracket Stack Pre-Scanning**: Tracks nesting depth across 6 canonical bracket pairs:
   - ASCII round `()` and full-width round `（）`
   - ASCII square `[]` and full-width square `［］`
   - Lenticular black brackets `【】`
   - Japanese quotation brackets `「」` and `『』`
   - Curly braces `{}` and full-width curly braces `｛｝`
2. **HTML Tag & Entity Protection**: Pre-scans and shields `<...>` tags (including attributes) and `&...;` entities.
3. **URL & URI Protection**: Pre-scans `https?://[^\s]+` strings so forward slashes in web addresses are never split.
4. **En4Everyone IPA Slash Isolation**:
   - For English for Everyone (`6b2a8fec`), pronunciation and phonetic fields (`IPA_FIELD_RE`) strictly remove `/` and `／` from the delimiter set (`IPA_PROTECTED_DELIMITERS`).
   - Standalone `/.../` IPA transcriptions (e.g. `/ˌkɒnvəˈseɪʃn/`) are recognized as atomic phonetic tokens.
5. **Unmatched / Broken Bracket Guard**: Only syntactically closed bracket pairs create shielded spans. In unclosed colloquial notes (e.g. Chinese grammar `(ai/gì/đâu`), unclosed opening parentheses do not shield delimiters, allowing clean separation into `["(ai", "gì", "đâu"]`.

#### Empirical Normalization Examples from Live Database:
- **Note `00ac5baa-856e-45d3-b177-3755a51a9e9f` (Deck 1388)**:
  - *Before*: `["nhân tài; người tài; vóc dáng/tướng mạo (khẩu ngữ cổ)"]`
  - *After*: `["nhân tài", "người tài", "vóc dáng", "tướng mạo (khẩu ngữ cổ)"]`
  - *Result*: Parenthetical gloss `(khẩu ngữ cổ)` completely preserved!
- **Note `00eb9dea-7101-44ca-a61f-f4f1cdff354b` (Deck 3966)**:
  - *Before*: `["Được (mọi người/ai đó) gọi là / mệnh danh là gì."]`
  - *After*: `["Được (mọi người/ai đó) gọi là", "mệnh danh là gì."]`
  - *Result*: Internal slash `(mọi người/ai đó)` shielded; outer slash `/` split cleanly!
- **Note `00005ce9-9dff-496a-a6b6-15871d41c950` (Deck 1388)**:
  - *Before*: `["Đạt đến mức tối đa; Chinh phục"]`
  - *After*: `["Đạt đến mức tối đa", "Chinh phục"]`
  - *Result*: Normalized to 2 distinct array elements!

### 3.3 Transactional Chunking & InnoDB Concurrency Safety
Updating 2,112 JSON rows in MySQL 8.0 InnoDB poses concurrency risks: table locking, undo log bloat, and deadlock contention with background study workers.

To eliminate all locking hazards:
1. **Deterministic Slicing**: Target note IDs were sorted deterministically (`ORDER BY id ASC`) before batching.
2. **Chunk Sizing**: Chunks were capped at 200 notes per transaction (strictly $\le 250$ max).
3. **Optimistic CAS (Compare-And-Swap)**: Updates checked `WHERE id = :id AND content_revision = :expected_rev` and applied `content_revision = content_revision + 1, updated_at = NOW()`.
4. **Execution Performance Log**:
   - Total Chunks: **11 chunks**
   - Average Chunk Latency: **324.5 ms**
   - Total Wall-Clock Execution Time: **6.37 seconds**
   - Rollback / Undo Log Contention: **0 deadlocks, 0 lock wait timeouts**

| Chunk Index | Notes Processed | Cumulative Progress | Execution Duration | Status | Commit Verification |
| :---: | :---: | :---: | :---: | :---: | :---: |
| `Chunk 01/11` | 200 notes | 9.5% | 388.4 ms | COMMITTED | Verified in DB |
| `Chunk 02/11` | 200 notes | 18.9% | 276.5 ms | COMMITTED | Verified in DB |
| `Chunk 03/11` | 200 notes | 28.4% | 285.9 ms | COMMITTED | Verified in DB |
| `Chunk 04/11` | 200 notes | 37.9% | 385.0 ms | COMMITTED | Verified in DB |
| `Chunk 05/11` | 200 notes | 47.3% | 435.6 ms | COMMITTED | Verified in DB |
| `Chunk 06/11` | 200 notes | 56.8% | 313.6 ms | COMMITTED | Verified in DB |
| `Chunk 07/11` | 200 notes | 66.3% | 271.7 ms | COMMITTED | Verified in DB |
| `Chunk 08/11` | 200 notes | 75.8% | 280.8 ms | COMMITTED | Verified in DB |
| `Chunk 09/11` | 200 notes | 85.2% | 311.9 ms | COMMITTED | Verified in DB |
| `Chunk 10/11` | 200 notes | 94.7% | 410.7 ms | COMMITTED | Verified in DB |
| `Chunk 11/11` | 112 notes | 100.0% | 208.9 ms | COMMITTED | Verified in DB |
| **TOTAL** | **2,112 notes** | **100.0%** | **6.37 s** | **ALL COMMITTED** | **41,544 Total Notes Intact** |

### 3.4 Preimage Cryptographic Durability
Before updating any note, a complete preimage snapshot was stored in two independent media:
1. **MySQL Table `notes_migration_preimages`**:
   - Columns: `batch_id varchar(64)`, `note_id varchar(36)`, `deck_id int`, `note_type_id varchar(36)`, `content_revision bigint`, `original_field_values_by_id json`, `sha256_hash varchar(64)`, `created_at datetime`.
   - Populated with exactly **2,112 rows** under batch `wave_r1_20261023`.
2. **Filesystem JSON Manifest**:
   - Path: `docs/audit/snapshots/preimage_wave_r1_20261023.json` (73,475 lines, 6,444,367 bytes).
   - Cryptographic Manifest Hash: `f003b49668a6d8595c16b28d06f3700a0b0f5512098b45635dcc75cd06796a49`.

---

## 4. Quantitative Before vs After Verification Matrix

The following matrices synthesize the exact quantitative shift across the entire Flama database resulting from the Phase 1 and Phase 2 executions:

### 4.1 Phase 1 — Presentation Templates Metrics
| Audit Metric | Baseline Before Phase 1 | Post-Phase 1 | Post-Phase 2 | Net Reduction | Target Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Incompatible Templates** | **14** | **0** | **0** | **-14 (-100.0%)** | **MET (Zero Defect)** |
| Fully Compatible Templates | 13 | 27 | 27 | +14 (+107.7%) | Substantially Improved |
| Partially Compatible Templates | 12 | 12 | 12 | 0 | Unchanged |
| **Active Decks Affected by Incompatible Templates** | **34** | **0** | **0** | **-34 (-100.0%)** | **MET (Zero Defect)** |
| **Active Notes Affected by Incompatible Templates** | **321** | **0** | **0** | **-321 (-100.0%)** | **MET (Zero Defect)** |
| Templates with Unclosed HTML Tags (`<div>`) | 5 | 0 | 0 | -5 (-100.0%) | Completely Repaired |
| Templates Missing Runtime Script | 14 | 0 | 0 | -14 (-100.0%) | 100% Injected |
| Templates Missing Dot Iteration on Arrays | 14 | 0 | 0 | -14 (-100.0%) | 100% Modernized |

### 4.2 Phase 2 — Multi-Value Array Content Metrics
| Audit Metric | Baseline Before Phase 2 | Post-Phase 1 | Post-Phase 2 | Net Reduction | Target Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Total Fake 1-Element Array Notes** | **2,112** | **2,112** | **0** | **-2,112 (-100.0%)** | **MET (Zero Defect)** |
| **Active Decks with Fake 1-Element Arrays** | **675** | **675** | **0** | **-675 (-100.0%)** | **MET (Zero Defect)** |
| Decks with Raw Scalar Delimiters | 1,533 | 1,533 | 1,533 | 0 | Untouched (Future Waves) |
| Pristine Clean Active Decks | 9 | 9 | 11 | +2 (+22.2%) | Improved |
| Total Active Notes Scanned | 41,544 | 41,544 | 41,544 | 0 | 100.00% Preserved |
| Total Active Decks Scanned | 1,544 | 1,544 | 1,544 | 0 | 100.00% Preserved |

### 4.3 Delimiter Breakdown Elimination in Array Fields
| Delimiter Type | Baseline Fake Array Notes | Post-Migration Fake Array Notes | Elimination Rate |
| :--- | :---: | :---: | :---: |
| Semicolon (`;`, `；`) | 1,733 | **0** | **100.00%** |
| Slash (`/`, `／`) | 344 | **0** | **100.00%** |
| Comma (`,`, `，`, `、`) | 32 | **0** | **100.00%** |
| Dollar Sign (`$`) (phonetic) | 7 | **0** | **100.00%** |
| **Total Fake Array Occurrences** | **2,116** | **0** | **100.00%** |

---

## 5. Automated Test Qualification Matrix

### 5.1 Verification Methodology & Suite Disambiguation
During Phase 3 verification, the testing matrix was evaluated across two distinct automated suites:
1. **Core Domain Unit Tests (58 Test Cases)**: Specifically covers the fundamental behavioral domains mandated by the user's acceptance criteria: `test_field_array_split.py` (bracket-shielding splitting), `test_field_array_conversion.py` (native array type conversion), `test_native_array_cleanup.py` (array whitespace and sanitization), `test_anki_scheduler.py` (Anki SM-2 scheduler integrity), and `test_template_formatters.py` (Mustache token rendering).
2. **Audit Adversarial Verification Suites**:
   - **Phase 1 & Phase 2 Post-Migration Adversarial Suite (59 Test Cases)**: Specifically constructed by empirical challengers to verify that the modernized templates render cleanly, preimages match with 100% cryptographic parity, and rollback tools function flawlessly.
   - **Baseline Proof-of-Defect Suite (58 Test Cases)**: Constructed during the initial audit phase to empirically prove that bugs *existed* in the pre-migration baseline (e.g. asserting that 14 incompatible templates exist, 2,112 fake arrays exist, and 5 templates have unclosed `<div>` tags). In the post-migration database, these defect-assertion tests fail precisely because the defects have been eliminated, and pass when rollback is simulated.

### 5.2 Core Domain Unit Tests (58/58 PASS)
- **Command**:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests/test_field_array_split.py tests/test_field_array_conversion.py tests/test_native_array_cleanup.py tests/test_anki_scheduler.py tests/test_template_formatters.py
  ```
- **Execution Timestamp**: `2026-10-23T17:18:13Z`
- **Duration**: 8.599 seconds
- **Pass Rate**: **58 / 58 (100.00% PASS)**
- **Verbatim Output**:
  ```text
  ..........................................................
  ----------------------------------------------------------------------
  Ran 58 tests in 8.599s

  OK
  ```
- **Test File Distribution Breakdown**:
  - `tests/test_field_array_split.py`: **17 tests** (Bracket-shielding splitting, nested bracket pairs, HTML entity shielding, IPA delimiter isolation) — PASS.
  - `tests/test_field_array_conversion.py`: **14 tests** (Native array type transitions, stored JSON lists, codec conversion) — PASS.
  - `tests/test_native_array_cleanup.py`: **15 tests** (Array whitespace normalization, empty item pruning, deduplication) — PASS.
  - `tests/test_anki_scheduler.py`: **8 tests** (Anki SM-2 scheduler algorithm, intervals, ease factors, fuzzing, day boundaries) — PASS.
  - `tests/test_template_formatters.py`: **4 tests** (Mustache token formatting, field interpolation, empty state rendering) — PASS.

### 5.3 Phase 1 & Phase 2 Post-Migration Adversarial Suite (59/59 PASS)
- **Commands & Results**:
  1. `tests/test_challenger_m2_2_adversarial_phase2.py`:
     - Command: `.\.venv\Scripts\python.exe -m unittest tests/test_challenger_m2_2_adversarial_phase2.py`
     - Tests: **7 tests** (2,112 preimages in table & JSON, 100% SHA-256 match, En4Everyone IPA protection, CAS revision increment) — **7/7 PASS (3.142s)**.
  2. `tests/test_challenger_m1_2_adversarial_templates.py`:
     - Command: `.\.venv\Scripts\python.exe -m unittest tests/test_challenger_m1_2_adversarial_templates.py`
     - Tests: **15 tests** (Tag balance stack validation, dot iteration execution, CSS responsiveness) — **15/15 PASS (15.401s)**.
  3. `tests/test_challenger_m1_1_adversarial_templates.py`:
     - Command: `.\.venv\Scripts\python.exe -m unittest tests/test_challenger_m1_1_adversarial_templates.py`
     - Tests: **13 tests** (Template syntax parsing, HTML sanitizer boundaries) — **13/13 PASS (0.620s)**.
  4. `tests/test_challenger_m2_1_adversarial.py`:
     - Command: `.\.venv\Scripts\python.exe -m unittest tests/test_challenger_m2_1_adversarial.py`
     - Tests: **16 tests** (Multi-value boundary conditions, unicode punctuation) — **16/16 PASS (0.220s)**.
  5. `tests/test_adversarial_poc_harness.py`:
     - Command: `.\.venv\Scripts\python.exe -m unittest tests/test_adversarial_poc_harness.py`
     - Tests: **8 tests** (Proof-of-concept harness, chunk isolation) — **8/8 PASS (2.358s)**.
  - **Total Adversarial Tests Passed**: **59 / 59 (100.00% PASS)**.

### 5.4 Template Versioning & Token Regression Suite (32/32 PASS)
- **Command**:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest tests/test_template_versions.py tests/test_template_tokens.py
  ```
- **Duration**: 2.967 seconds
- **Pass Rate**: **32 / 32 (100.00% PASS)**
- **Verbatim Output**:
  ```text
  ................................
  ----------------------------------------------------------------------
  Ran 32 tests in 2.967s

  OK
  ```

### 5.5 CLI Audit Tools & Check Flag Verifications
1. **Presentation Templates Audit (`audit_r2_templates.py --check`)**:
   - Command: `.\.venv\Scripts\python.exe scripts/audit/audit_r2_templates.py --check`
   - Exit Code: **0**
   - Output: `PASSED: 0 incompatible templates found.`
2. **Multi-Value Arrays Audit (`audit_r1_multi_value.py`)**:
   - Command: `.\.venv\Scripts\python.exe scripts/audit/audit_r1_multi_value.py`
   - Exit Code: **0**
   - Manifest Metrics: `fake_array_decks_count: 0`, `total_fake_array_notes: 0`.
3. **Master Audit Orchestrator (`run_comprehensive_audit.py`)**:
   - Command: `.\.venv\Scripts\python.exe scripts/audit/run_comprehensive_audit.py`
   - Exit Code: **0**
   - Total Execution Time: **7.618 seconds**
   - Result: All 3 engines (`R1 Multi-Value`, `R2 Templates`, `R3 Semantics`) reported **PASS**.

---

## 6. Security, Zero Data Loss & Rollback Guarantee Sign-Off

### 6.1 Zero Data Loss Forensic Attestation
We hereby certify under the strict Integrity Mandate of the Flama engineering standard:
1. **Total Preservation of Rows**: No row was deleted, truncated, or dropped from `notes` (count exactly 41,544) or `decks` (count exactly 5,577).
2. **Preservation of Inner-Bracket Content**: The bracket-shielding engine inspected and shielded 100% of substrings enclosed within `()`, `（）`, `[]`, `［］`, `【】`, `「」`, `『』`, and `{}`. No parenthetical annotations, translations, or context glosses were split.
3. **Preservation of Phonetic Notation**: All phonetic slashes `/.../` in English for Everyone (`6b2a8fec`) were completely preserved.
4. **Historical Provenance Preservation**: All template upgrades generated immutable rows in `template_versions` with sequential version numbers and user provenance.

### 6.2 Preimage Snapshot Storage & Rollback Runbook
In the unlikely event that an emergency rollback is requested, the system provides two automated rollback engines backed by dual preimage stores:

#### 1. Phase 1 Template Rollback Runbook:
- **Preimage Snapshot**: `docs/audit/snapshots/preimage_templates_phase1.json` (14 templates).
- **Dry-Run Simulation**:
  ```powershell
  .\.venv\Scripts\python.exe scripts/migrations/rollback_r2_templates.py --dry-run
  ```
  *Verified Output*: Scans all 14 templates, confirms `Status: NEEDS_RESTORE`, matches live version with preimage version, and executes 0 mutations.
- **Live Rollback Execution**:
  ```powershell
  .\.venv\Scripts\python.exe scripts/migrations/rollback_r2_templates.py
  ```
  Restores `front_html`, `back_html`, `shared_css`, and `current_version_id` to exact pre-migration state and purges post-migration versions.

#### 2. Phase 2 Content Rollback Runbook:
- **Preimage Stores**: MySQL table `notes_migration_preimages` (2,112 rows) and filesystem manifest `docs/audit/snapshots/preimage_wave_r1_20261023.json` (SHA-256: `f003b49668a6d8595c16b28d06f3700a0b0f5512098b45635dcc75cd06796a49`).
- **Dry-Run Simulation**:
  ```powershell
  .\.venv\Scripts\python.exe scripts/migrations/rollback_array_wave.py --dry-run
  ```
  *Verified Output*: Validates all 2,112 notes against stored SHA-256 hashes in 0.17s. Confirms 2,112 notes ready for restoration with 0 database writes.
- **Live Rollback Execution**:
  ```powershell
  .\.venv\Scripts\python.exe scripts/migrations/rollback_array_wave.py
  ```
  Restores `field_values_by_id`, decrements `content_revision`, and updates timestamps in 11 safe transaction chunks $\le 250$ notes/tx.
- **Live Rollback Empirical Proof**:
  Worker M2 executed live rollback during testing, confirming 2,112 notes restored in 2.49s, verified `audit_r1_multi_value.py` reported 2,112 fake arrays, and successfully re-migrated to 0 in 7.05s.

### 6.3 Final Sign-Off & Verification Receipts
- **Database Engine**: MySQL 8.0.40 on `localhost:3306` (`nihongo`)
- **Final Notes Row Count**: **41,544**
- **Final Decks Row Count**: **5,577**
- **Incompatible Templates**: **0**
- **Fake 1-Element Array Notes**: **0**
- **Core Domain Unit Tests**: **58 / 58 PASS (100%)**
- **Post-Migration Adversarial Tests**: **59 / 59 PASS (100%)**
- **Template Regression Tests**: **32 / 32 PASS (100%)**
- **Comprehensive Audit Status**: **ALL 3 ENGINES PASS (0 ERRORS)**

*Signed and Certified by*: Worker M3 (`teamwork_preview_worker_m3`), Final Verification & Master Report Specialist  
*Date of Sign-Off*: `2026-10-23T17:25:00Z`
