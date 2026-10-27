r"""Wave 7 Migration: Grammar Practice Recovery (ChungBech N1 & Derivatives).

Scope & Actions:
1. Bracket-Shielded Label Splitting:
   - Shields 9 bracket pairs: (), （）, [], ［］, {}, ｛｝, 【】, 「」, 『』
   - Shields quotes and math expressions
   - Splits on grammar labels strictly outside shielded brackets:
     - usage_vi: 'Cấu trúc:', 'Nghĩa:', 'Ý nghĩa:', 'Sắc thái:', 'Tình huống:', 'Hạn chế:', 'Cụm từ hay dùng:', 'Lưu ý:'
     - usage_jp: '接続:', '接续:', '意味:', '意义:', 'ニュアンス:', '语气/语感:', '使用場面:', '制約:', '限制:', '常见搭配:'
     - additional_note_vi: 'So sánh nhanh:' / 'Mẹo nhớ:' (normalizes to single \n between sections)
     - additional_note_jp: '比較:' / '注意:' (normalizes to single \n between sections)
2. Target Scope (172 unique notes):
   - ChungBech N1 文法練習: Decks 1334 (25 notes), 1335 (30 notes), 1336 (30 notes), 1337 (30 notes), 1338 (30 notes), 2630 (1 note) = 146 notes.
   - Derivative grammar decks: Decks 3653 (4 notes; skipping clean note e89ab1ce), 3654 (5 notes), 4051 (1 grammar note: 86a98dbe), 4052 (5 notes), 4053 (5 notes), 4250 (5 notes), 4252 (1 grammar note: b192b449) = 26 notes.
   - Total: 146 + 26 = 172 notes.
3. Modernize Presentation Template:
   - Template e0cb18b2-881d-4b46-a567-dc5db14d661f (Default Flama Flashcard):
     - Adds display: flex; flex-direction: column; gap: 4px; to usage_jp and usage_vi containers.
     - Adds display: flex; flex-direction: column; gap: 4px; white-space: pre-wrap; to additional_note_jp and additional_note_vi containers.
     - Adds .flama-array-item { line-height: 1.45; } to shared_css.
     - Validates 100% AST tag-balance via TagBalanceValidator.
     - Marks template version history via mark_template_version.
4. Preimage Snapshot:
   - Captured at docs/audit/snapshots/wave7_preimage_grammar_practice_recovery.json
   - Canonical SHA-256 computed on JSON payload excluding 'preimage_sha256'.
   - Atomic write using .tmp replacement.
5. Invariants & Guardrails:
   - 100% non-whitespace character conservation.
   - Global note count (41,870) and deck count (5,610) preserved.
   - Exactly 172 notes modified in live database.
6. CLI Flags:
   - --dry-run: Simulate migration without committing changes
   - --rollback: Roll back changes from authentic preimage snapshot
   - --verify: Verify live database state and invariants
   - --snapshot: Capture and save preimage snapshot without modifying notes
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from sqlalchemy.orm.attributes import flag_modified

from app import create_app
from app.services.template_version_service import mark_template_version
from models import db
from models.deck import Deck
from models.note import Note
from models.template import Template


class TagBalanceValidator(HTMLParser):
    """HTML tag stack validator that detects unclosed tags and hierarchy mismatches."""

    VOID_TAGS = frozenset({
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"
    })

    def __init__(self) -> None:
        super().__init__()
        self.stack: List[str] = []
        self.errors: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        t = tag.lower()
        if t not in self.VOID_TAGS:
            self.stack.append(t)

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in self.VOID_TAGS:
            return
        if not self.stack:
            self.errors.append(f"Unexpected closing tag </{t}> without matching open tag")
            return
        if self.stack[-1] == t:
            self.stack.pop()
        else:
            if t in self.stack:
                idx = len(self.stack) - 1 - self.stack[::-1].index(t)
                unclosed = self.stack[idx + 1 :]
                self.errors.append(f"Unclosed tag(s) <{', '.join(unclosed)}> before </{t}>")
                self.stack = self.stack[:idx]
            else:
                self.errors.append(f"Mismatched closing tag </{t}>, expected </{self.stack[-1]}>")

CHUNK_SIZE = 200
PREIMAGE_FILE = ROOT / "docs" / "audit" / "snapshots" / "wave7_preimage_grammar_practice_recovery.json"

TMPL_FLAMA_DEF_ID = "e0cb18b2-881d-4b46-a567-dc5db14d661f"

# Target Fields in Flama Standard Vocabulary
FID_USAGE_VI = "b694faab-5492-40ee-a85a-e2e3684731e1"
FID_USAGE_JP = "ee54985b-62ac-47ad-b4b4-95d7b3d509c9"
FID_ADD_NOTE_VI = "f3abea0b-ebe5-4342-b2dd-ecdd191b7e08"
FID_ADD_NOTE_JP = "8d3c5d61-a516-4d47-9e1a-4af4b4617d24"

VI_LABELS = [
    "Cấu trúc:",
    "Nghĩa:",
    "Ý nghĩa:",
    "Sắc thái:",
    "Tình huống:",
    "Hạn chế:",
    "Giới hạn:",
    "Cụm từ hay dùng:",
    "Lưu ý:",
]

JP_LABELS = [
    "接続:",
    "接续:",
    "意味:",
    "意义:",
    "ニュアンス:",
    "语气/语感:",
    "使用場面:",
    "制約:",
    "限制:",
    "常见搭配:",
]

OPEN_BRACKETS = {'(': ')', '（': '）', '[': ']', '［': '］', '【': '】', '「': '」', '『': '』', '{': '}', '｛': '｝'}
CLOSE_BRACKETS = {v: k for k, v in OPEN_BRACKETS.items()}


def find_label_split_indices(text: str, labels: List[str]) -> List[Tuple[int, str]]:
    """Finds indices of labels that occur at depth 0 (strictly outside brackets)."""
    depth = 0
    stack: List[str] = []
    matches: List[Tuple[int, str]] = []

    i = 0
    n = len(text)
    while i < n:
        char = text[i]

        if depth == 0:
            matched_lbl = None
            for lbl in labels:
                if text.startswith(lbl, i):
                    if i == 0 or text[i - 1] in " \t\n\r。.;；,，":
                        matched_lbl = lbl
                        break
            if matched_lbl:
                matches.append((i, matched_lbl))
                i += len(matched_lbl)
                continue

        if char in OPEN_BRACKETS:
            stack.append(char)
            depth += 1
        elif char in CLOSE_BRACKETS:
            if stack and stack[-1] == CLOSE_BRACKETS[char]:
                stack.pop()
                depth = max(0, depth - 1)
        i += 1

    return matches


def split_by_labels(text: str, labels: List[str]) -> List[str]:
    """Splits text on label occurrences that reside outside shielded brackets."""
    if not text:
        return []
    matches = find_label_split_indices(text, labels)
    if not matches:
        return [text.strip()] if text.strip() else []

    items = []
    for idx, (start_pos, lbl) in enumerate(matches):
        end_pos = matches[idx + 1][0] if idx + 1 < len(matches) else len(text)
        chunk = text[start_pos:end_pos].strip()
        if chunk:
            items.append(chunk)

    if matches and matches[0][0] > 0:
        prefix = text[:matches[0][0]].strip()
        if prefix:
            items.insert(0, prefix)

    return items


def normalize_additional_notes(text: Optional[str], first_label: str, second_label: str) -> Optional[str]:
    """Normalizes separation between first_label and second_label to a single newline (\n).

    Guarantees:
    1. If already separated by \n\n (or multiple newlines), collapses to single \n.
    2. Strips trailing whitespace on the first line and leading whitespace on the second line.
    3. If unseparated (raw preimage text with 0 newlines), splits at second_label outside brackets.
    4. If text has only one label or neither label, preserves text untouched.
    5. Zero Data Loss: non-whitespace character sequence is 100% conserved.
    """
    if not text or not isinstance(text, str):
        return text
    if first_label not in text or second_label not in text:
        return text
    if "\n" in text:
        return re.sub(r"[ \t]*\n+[ \t]*", "\n", text).strip()
    matches = find_label_split_indices(text, [second_label])
    if not matches:
        return text
    split_pos, _ = matches[0]
    prefix = text[:split_pos].rstrip()
    suffix = text[split_pos:].lstrip()
    return f"{prefix}\n{suffix}"


# Backward compatibility alias
split_additional_notes = normalize_additional_notes


def transform_note_wave7(field_values_by_id: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Transforms usage and additional note fields for a single note."""
    new_fv = dict(field_values_by_id)
    changed = False

    # 1. usage_vi
    u_vi = new_fv.get(FID_USAGE_VI)
    if isinstance(u_vi, list):
        if any(isinstance(s, str) and sum(1 for k in VI_LABELS if k in s) >= 2 for s in u_vi):
            new_items = []
            for s in u_vi:
                new_items.extend(split_by_labels(s, VI_LABELS))
            new_fv[FID_USAGE_VI] = new_items
            changed = True
    elif isinstance(u_vi, str) and sum(1 for k in VI_LABELS if k in u_vi) >= 2:
        new_fv[FID_USAGE_VI] = split_by_labels(u_vi, VI_LABELS)
        changed = True

    # 2. usage_jp
    u_jp = new_fv.get(FID_USAGE_JP)
    if isinstance(u_jp, list):
        if any(isinstance(s, str) and sum(1 for k in JP_LABELS if k in s) >= 2 for s in u_jp):
            new_items = []
            for s in u_jp:
                new_items.extend(split_by_labels(s, JP_LABELS))
            new_fv[FID_USAGE_JP] = new_items
            changed = True
    elif isinstance(u_jp, str) and sum(1 for k in JP_LABELS if k in u_jp) >= 2:
        new_fv[FID_USAGE_JP] = split_by_labels(u_jp, JP_LABELS)
        changed = True

    # 3. additional_note_vi
    an_vi = new_fv.get(FID_ADD_NOTE_VI)
    if isinstance(an_vi, str):
        new_an_vi = normalize_additional_notes(an_vi, "So sánh nhanh:", "Mẹo nhớ:")
        if new_an_vi != an_vi:
            new_fv[FID_ADD_NOTE_VI] = new_an_vi
            changed = True

    # 4. additional_note_jp
    an_jp = new_fv.get(FID_ADD_NOTE_JP)
    if isinstance(an_jp, str):
        new_an_jp = normalize_additional_notes(an_jp, "比較:", "注意:")
        if new_an_jp != an_jp:
            new_fv[FID_ADD_NOTE_JP] = new_an_jp
            changed = True

    return new_fv, changed


def non_ws_string(val: Any) -> str:
    """Extracts all non-whitespace characters from string or list of strings."""
    if isinstance(val, list):
        val = "".join(str(x) for x in val)
    return re.sub(r"\s+", "", str(val or ""))


def get_target_notes() -> List[Note]:
    """Retrieves all 172 target notes across ChungBech N1 and derivative grammar decks."""
    cb_decks = [1334, 1335, 1336, 1337, 1338, 2630]
    derivative_full_decks = [3653, 3654, 4052, 4053, 4250]
    specific_note_ids = [
        "86a98dbe-6f66-41cd-acae-907f2636ec60",  # Deck 4051 grammar note
        "b192b449-ba43-408e-a7a5-8c5c08d8aa79",  # Deck 4252 grammar note
    ]
    skip_clean_note_id = "e89ab1ce-a9f3-49e4-83bf-bf640c123f1b"  # Deck 3653 already clean

    all_notes = []
    for did in cb_decks + derivative_full_decks:
        notes = Note.query.filter_by(deck_id=did).order_by(Note.id).all()
        for n in notes:
            if n.id == skip_clean_note_id:
                continue
            all_notes.append(n)

    for nid in specific_note_ids:
        n = db.session.get(Note, nid)
        if n:
            all_notes.append(n)

    # De-duplicate while preserving order
    seen: Set[str] = set()
    deduped = []
    for n in all_notes:
        if n.id not in seen:
            seen.add(n.id)
            deduped.append(n)

    return deduped


MODERNIZED_BACK_HTML = """<div class="flama-vocab-card">
    <!-- Hiển thị từ vựng -->
    <div style='
        font-family: "Arial";
        font-size: 36px;
        font-weight: bold;
        display: flex;
        align-items: center;
        color: #e53c20;
        padding-top: 20px;'
    >
        {{{word}}}

{{#word_audio}}
  <audio id="custom-audio" style="display: none" src="{{{word_audio_url}}}"></audio>
  <button onclick="document.getElementById('custom-audio').play()">🔊</button>
{{/word_audio}}
    </div>

    <!-- Hiển thị cách đọc -->
    <div style='
        display: flex;
        font-weight: bold;
        font-family: "Arial";
        font-size: 20px;
        flex-direction: column;
        text-transform: uppercase;'
    >
        <div data-field="reading" style='font-family: "Arial";'>
            {{reading}}{{#hanviet}} 「{{hanviet}}」{{/hanviet}}
        </div>

        <span data-native-array-guard="translation_vi" style="display:contents">
            {{#translation_vi}}<span data-native-array-presence hidden></span>{{/translation_vi}}
            <div data-array-field="translation_vi" style='color: green; padding-bottom: 10px'>
                {{#translation_vi}}<div class="flama-array-item">{{{.}}}</div>{{/translation_vi}}
            </div>
        </span>
    </div>

    <!-- Hiển thị giải thích -->
    <span data-native-array-guard="meaning_jp" style="display:contents">
        {{#meaning_jp}}<span data-native-array-presence hidden></span>{{/meaning_jp}}
        <div style='display: flex; padding-top: 20px; color: #3367d6'>
            <div style="font-weight: bold; margin-right: 6px;">◆</div>
            <div style="display: flex; flex-direction: column; gap: 4px;">
                {{#meaning_jp}}<div class="flama-array-item">{{{.}}}</div>{{/meaning_jp}}
            </div>
        </div>
    </span>

    <span data-native-array-guard="meaning_vi" style="display:contents">
        {{#meaning_vi}}<span data-native-array-presence hidden></span>{{/meaning_vi}}
        <div style='display: flex; flex-direction: column; padding-top: 10px; gap: 4px;'>
            {{#meaning_vi}}<div class="flama-array-item">{{{.}}}</div>{{/meaning_vi}}
        </div>
    </span>

    <!-- Ảnh minh hoạ stroke order -->
    {{#image}}
      {{{image}}}
    {{/image}}
    {{#diagram}}
      {{{diagram}}}
    {{/diagram}}

    <!-- Hiển thị cách sử dụng -->
    <span data-native-array-guard="usage_jp" style="display:contents">
        {{#usage_jp}}<span data-native-array-presence hidden></span>{{/usage_jp}}
        <div style='display: flex; padding-top: 20px; color: #3367d6; font-weight: bold;'>
            ◆ Cách sử dụng:
        </div>

        <div style='display: flex; flex-direction: column; padding-top: 10px; gap: 4px;'>
            <div style="font-size: 20px; display: flex; flex-direction: column; gap: 4px; white-space: pre-wrap; line-height: 1.45;">
                {{#usage_jp}}<div class="flama-array-item">{{{.}}}</div>{{/usage_jp}}
            </div>

            <span data-native-array-guard="usage_vi" style="display:contents">
                {{#usage_vi}}<span data-native-array-presence hidden></span>{{/usage_vi}}
                <div style="font-size: 16px; color: gray; margin-left: 10px; display: flex; flex-direction: column; gap: 4px; white-space: pre-wrap; line-height: 1.45;">
                    {{#usage_vi}}<div class="flama-array-item">{{{.}}}</div>{{/usage_vi}}
                </div>
            </span>
        </div>
    </span>

    <!-- Hiển thị ví dụ -->
    <span data-native-array-guard="example_jp" style="display:contents">
        {{#example_jp}}<span data-native-array-presence hidden></span>{{/example_jp}}
        <div style='display: flex; padding-top: 20px; color: #3367d6; font-weight: bold;'>
            ◆ Câu ví dụ:
        </div>

        <div style='display: flex; flex-direction: column; padding-top: 10px; gap: 4px;'>
            <div style="font-size: 20px; display: flex; align-items: center;">
                <div style="display: flex; flex-direction: column; gap: 4px;">
                    {{#example_jp}}<div class="flama-array-item">{{{.}}}</div>{{/example_jp}}
                </div>

                {{#example_audio}}
                <audio
                    id="example-audio"
                    style="display: none"
                    src="{{{example_audio_url}}}">
                </audio>

                <button onclick="document.getElementById('example-audio').play()">🔊</button>
                {{/example_audio}}
            </div>

            <span data-native-array-guard="example_vi" style="display:contents">
                {{#example_vi}}<span data-native-array-presence hidden></span>{{/example_vi}}
                <div style="font-size: 16px; color: gray; margin-left: 10px; display: flex; flex-direction: column; gap: 4px;">
                    {{#example_vi}}<div class="flama-array-item">{{{.}}}</div>{{/example_vi}}
                </div>
            </span>
        </div>
    </span>

    <!-- Hiển thị ghi chú -->
    {{#additional_note_jp}}
    <div style='
        display: flex;
        padding-top: 20px;
        font-family: "Arial";
        color: #3367d6;'
    >
        ◆ Ghi chú:
    </div>

    <div style='display: flex; flex-direction: column; gap: 4px; padding-top: 10px; white-space: pre-wrap; line-height: 1.45;'>{{{additional_note_jp}}}</div>
    {{/additional_note_jp}}

    {{#additional_note_vi}}
    <div style='display: flex; flex-direction: column; gap: 4px; padding-top: 10px; font-family: "Arial"; color: gray; font-size: 16px; white-space: pre-wrap; line-height: 1.45;'>{{{additional_note_vi}}}</div>
    {{/additional_note_vi}}
</div>

<!-- Script phát âm từ vựng và ví dụ -->
<script>
// flama-native-arrays.v1: template-owned formatting, before its interaction scripts.
(function () {
  'use strict';
  document.querySelectorAll('[data-native-array-guard]').forEach(function (guard) {
    var present = Array.from(guard.children).filter(function (child) {
      return child.hasAttribute('data-native-array-presence');
    });
    if (!present.length) { guard.remove(); return; }
    present.forEach(function (child) { child.remove(); });
    var content = document.createDocumentFragment();
    while (guard.firstChild) content.appendChild(guard.firstChild);
    guard.replaceWith(content);
  });
})();

(() => {
    const wordAudio = document.getElementById("custom-audio");
    const exampleAudio = document.getElementById("example-audio");

    if (wordAudio) {
        wordAudio.play().catch(err => {
            console.warn("Autoplay:", err);
        });

        const autoPlayExampleOnce = () => {
            setTimeout(() => {
                if (exampleAudio) {
                    exampleAudio.play().catch(err => console.warn(err));
                }
            }, 500);

            wordAudio.removeEventListener("ended", autoPlayExampleOnce);
        };

        wordAudio.addEventListener("ended", autoPlayExampleOnce);
    }
})();
</script>"""

SHARED_CSS_RULE = """
.flama-array-item {
  line-height: 1.45;
  white-space: pre-wrap;
}
"""


def compute_canonical_sha256(payload: Dict[str, Any]) -> str:
    """Computes SHA-256 over deterministic JSON representation omitting 'preimage_sha256'."""
    clean = {k: v for k, v in payload.items() if k != "preimage_sha256"}
    canonical = json.dumps(clean, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def capture_preimage_snapshot(captured_at: Optional[str] = None) -> Dict[str, Any]:
    """Captures preimage snapshot of the 172 notes and template e0cb18b2."""
    app = create_app()
    with app.app_context():
        total_notes = Note.query.count()
        total_decks = Deck.query.count()

        t = db.session.get(Template, TMPL_FLAMA_DEF_ID)
        if not t:
            raise RuntimeError(f"Template {TMPL_FLAMA_DEF_ID} not found!")

        template_data = {
            "id": t.id,
            "name": t.name,
            "back_html": t.back_html,
            "shared_css": t.shared_css,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }

        target_notes = get_target_notes()
        notes_data = [
            {
                "id": n.id,
                "deck_id": n.deck_id,
                "note_type_id": n.note_type_id,
                "content_revision": n.content_revision,
                "field_values_by_id": n.field_values_by_id,
                "updated_at": n.updated_at.isoformat() if n.updated_at else None,
            }
            for n in target_notes
        ]

    payload: Dict[str, Any] = {
        "schema_version": "wave7-preimage.v1",
        "batch_id": "wave7_grammar_practice_recovery",
        "target_database": "mysql_8_0_nihongo",
        "captured_at": captured_at or datetime.now(timezone.utc).isoformat(),
        "baseline_metrics": {
            "total_notes": total_notes,
            "total_decks": total_decks,
            "target_notes_count": len(notes_data),
        },
        "template": template_data,
        "notes": notes_data,
    }

    payload["preimage_sha256"] = compute_canonical_sha256(payload)
    return payload


def save_preimage_atomic(payload: Dict[str, Any]) -> None:
    """Saves preimage snapshot atomically using .tmp file replacement."""
    PREIMAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = PREIMAGE_FILE.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp_path.replace(PREIMAGE_FILE)
    print(f"[PREIMAGE] Saved authentic preimage snapshot to {PREIMAGE_FILE} (SHA-256: {payload['preimage_sha256'][:16]}...)")


def execute_migration(dry_run: bool = False) -> Dict[str, Any]:
    """Executes Wave 7 migration with dry-run protection, chunking, and full invariant validation."""
    app = create_app()

    print("=" * 70)
    print("STARTING WAVE 7 MIGRATION EXECUTION")
    print(f"Mode: {'DRY RUN (simulation only)' if dry_run else 'LIVE COMMIT'}")
    print("=" * 70)

    # 1. Capture or verify preimage
    preimage = None
    if PREIMAGE_FILE.exists():
        try:
            with open(PREIMAGE_FILE, "r", encoding="utf-8") as f:
                preimage = json.load(f)
            rec_sha = preimage.get("preimage_sha256")
            comp_sha = compute_canonical_sha256(preimage)
            if rec_sha != comp_sha:
                print(f"[WARNING] Existing preimage corrupted! Re-capturing fresh preimage...")
                preimage = None
            else:
                print(f"[PREIMAGE] Authentic preimage already exists (SHA-256: {rec_sha[:16]}...)")
        except Exception as e:
            print(f"[WARNING] Could not read existing preimage: {e}. Re-capturing fresh preimage...")
            preimage = None

    if preimage is None:
        print("[PREIMAGE] Capturing fresh preimage snapshot...")
        preimage = capture_preimage_snapshot()
        if not dry_run:
            save_preimage_atomic(preimage)
        else:
            print(f"[PREIMAGE DRY RUN] Snapshot computed (SHA-256: {preimage['preimage_sha256'][:16]}...), skipping disk write in dry-run.")

    with app.app_context():
        # Validate baseline invariants
        base_notes = Note.query.count()
        base_decks = Deck.query.count()
        expected_base_notes = preimage.get("baseline_metrics", {}).get("total_notes", base_notes)
        expected_base_decks = preimage.get("baseline_metrics", {}).get("total_decks", base_decks)
        print(f"\n--- BASELINE CHECK: {base_notes} notes, {base_decks} decks ---")
        if base_notes != expected_base_notes or base_decks != expected_base_decks:
            raise RuntimeError(f"Unexpected baseline: notes={base_notes} (expected {expected_base_notes}), decks={base_decks} (expected {expected_base_decks})")

        # Step 1: Presentation Template Modernization
        print("\n--- STEP 1: TEMPLATE MODERNIZATION ---")
        # Validate HTML tag balance
        validator = TagBalanceValidator()
        validator.feed(MODERNIZED_BACK_HTML)
        validator.close()
        if validator.errors or validator.stack:
            raise ValueError(f"TagBalanceValidator failed on MODERNIZED_BACK_HTML: {validator.errors}, stack: {validator.stack}")
        print("[TEMPLATE VALIDATOR] HTML AST 100% tag-balanced (stack clean at EOF).")

        t = db.session.get(Template, TMPL_FLAMA_DEF_ID)
        if not t:
            raise RuntimeError(f"Template {TMPL_FLAMA_DEF_ID} not found!")

        t.back_html = MODERNIZED_BACK_HTML
        if ".flama-array-item" not in (t.shared_css or ""):
            t.shared_css = (t.shared_css or "").rstrip() + "\n" + SHARED_CSS_RULE.strip() + "\n"
        t.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        mark_template_version(
            t,
            origin="update",
            change_note="Wave 7: Flex column gap, pre-wrap modernization, and inline additional_note wrapping",
            force=True,
        )
        db.session.flush()
        print(f"[TEMPLATE] Modernized Template {t.id[:8]} ({t.name}) with flex column gap and pre-wrap.")

        # Step 2: Note Transformations
        print("\n--- STEP 2: NOTE TRANSFORMATIONS (CHUNK_SIZE = 200) ---")
        target_notes = get_target_notes()
        print(f"Loaded {len(target_notes)} target notes (expected 172).")
        if len(target_notes) != 172:
            raise RuntimeError(f"Expected exactly 172 target notes, found {len(target_notes)}!")

        chunks = [target_notes[i:i + CHUNK_SIZE] for i in range(0, len(target_notes), CHUNK_SIZE)]
        total_changed = 0

        for chunk_idx, chunk in enumerate(chunks, 1):
            for n in chunk:
                fv = n.field_values_by_id or {}
                # Verify non-whitespace character conservation before and after
                before_ws = "".join(non_ws_string(fv.get(fid)) for fid in [FID_USAGE_VI, FID_USAGE_JP, FID_ADD_NOTE_VI, FID_ADD_NOTE_JP])

                new_fv, changed = transform_note_wave7(fv)
                if changed:
                    after_ws = "".join(non_ws_string(new_fv.get(fid)) for fid in [FID_USAGE_VI, FID_USAGE_JP, FID_ADD_NOTE_VI, FID_ADD_NOTE_JP])
                    if before_ws != after_ws:
                        raise ValueError(f"Non-whitespace character conservation failed for note {n.id}!")

                    total_changed += 1
                    n.field_values_by_id = new_fv
                    flag_modified(n, "field_values_by_id")
                    n.content_revision = (n.content_revision or 1) + 1
                    n.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.session.flush()
            print(f"  Processed chunk {chunk_idx}/{len(chunks)} ({total_changed} notes modified so far)")

        print(f"[NOTES COMPLETE] Scanned {len(target_notes)} target notes ({total_changed} modified in this run).")

        # Step 3: Validate Invariants
        print("\n--- STEP 3: VALIDATING INVARIANTS ---")
        final_notes = Note.query.count()
        final_decks = Deck.query.count()
        if final_notes != base_notes or final_decks != base_decks:
            raise RuntimeError(f"Global invariant violation: notes={final_notes} (expected {base_notes}), decks={final_decks} (expected {base_decks})")

        # Verify no remaining multi-label concatenation in target notes
        remaining_concat = 0
        for n in target_notes:
            fv = n.field_values_by_id or {}
            for fid, lbls in [(FID_USAGE_VI, VI_LABELS), (FID_USAGE_JP, JP_LABELS)]:
                val = fv.get(fid)
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, str) and sum(1 for k in lbls if k in item) >= 2:
                            remaining_concat += 1
                elif isinstance(val, str) and sum(1 for k in lbls if k in val) >= 2:
                    remaining_concat += 1
        if remaining_concat > 0:
            raise RuntimeError(f"Verification failure: {remaining_concat} concatenated multi-label fields remain!")

        print(f"[INVARIANTS PASS] Global note count ({final_notes}), deck count ({final_decks}), and 0 concatenated items verified.")

        if dry_run:
            db.session.rollback()
            db.session.remove()
            print("\n[DRY RUN ROLLED BACK] Simulation complete. Database rolled back cleanly.")
            return {
                "status": "DRY_RUN_PASSED",
                "preimage_sha256": preimage.get("preimage_sha256"),
                "total_changed": total_changed,
            }
        else:
            db.session.commit()
            db.session.remove()
            print("\n" + "=" * 70)
            print("[SUCCESS] WAVE 7 MIGRATION COMMITTED TO LOCAL MYSQL 8.0.")
            print("=" * 70)
            return {
                "status": "MIGRATION_COMMITTED",
                "preimage_sha256": preimage.get("preimage_sha256"),
                "total_changed": total_changed,
            }


def rollback_migration(dry_run: bool = False) -> Dict[str, Any]:
    """Rolls back Wave 7 migration using authentic preimage snapshot."""
    app = create_app()
    print("=" * 70)
    print("STARTING WAVE 7 ROLLBACK EXECUTION")
    print(f"Mode: {'DRY RUN (simulation only)' if dry_run else 'LIVE COMMIT'}")
    print("=" * 70)

    if not PREIMAGE_FILE.exists():
        raise FileNotFoundError(f"Cannot rollback: Preimage file not found at {PREIMAGE_FILE}")

    with open(PREIMAGE_FILE, "r", encoding="utf-8") as f:
        preimage = json.load(f)

    recorded_sha256 = preimage.get("preimage_sha256")
    computed_sha256 = compute_canonical_sha256(preimage)
    if recorded_sha256 != computed_sha256:
        raise ValueError(f"Preimage cryptographic integrity failure! Recorded: {recorded_sha256}, Computed: {computed_sha256}")
    print(f"[PREIMAGE] Cryptographic integrity verified (SHA-256: {recorded_sha256[:16]}...)")

    with app.app_context():
        # Restore template
        tmpl_data = preimage.get("template")
        if tmpl_data:
            tmpl_upd = datetime.fromisoformat(tmpl_data["updated_at"]).replace(tzinfo=None) if tmpl_data.get("updated_at") else None
            if not dry_run:
                with db.engine.begin() as conn:
                    conn.execute(
                        text("UPDATE templates SET back_html = :b, shared_css = :c, updated_at = :u WHERE id = :id"),
                        {
                            "id": tmpl_data["id"],
                            "b": tmpl_data["back_html"],
                            "c": tmpl_data["shared_css"],
                            "u": tmpl_upd,
                        }
                    )
            print(f"[ROLLBACK TEMPLATE] Restored Template {tmpl_data['id'][:8]} ({tmpl_data.get('name')}) to preimage state.")

        # Restore notes
        preimage_notes = preimage.get("notes", [])
        print(f"\n--- RESTORING {len(preimage_notes)} NOTES (CHUNK_SIZE = {CHUNK_SIZE}) ---")
        chunks = [preimage_notes[i:i + CHUNK_SIZE] for i in range(0, len(preimage_notes), CHUNK_SIZE)]

        if not dry_run:
            with db.engine.begin() as conn:
                for chunk_idx, chunk in enumerate(chunks, 1):
                    for r in chunk:
                        note_upd = datetime.fromisoformat(r["updated_at"]).replace(tzinfo=None) if r.get("updated_at") else None
                        conn.execute(
                            text("UPDATE notes SET field_values_by_id = :fv, content_revision = :rev, updated_at = :upd WHERE id = :id"),
                            {
                                "id": r["id"],
                                "fv": json.dumps(r["field_values_by_id"], ensure_ascii=False),
                                "rev": r["content_revision"],
                                "upd": note_upd,
                            }
                        )
                    print(f"  Restored chunk {chunk_idx}/{len(chunks)} ({len(chunk)} notes)")
        else:
            for chunk_idx, chunk in enumerate(chunks, 1):
                print(f"  [DRY RUN] Would restore chunk {chunk_idx}/{len(chunks)} ({len(chunk)} notes)")

        total_notes = Note.query.count()
        total_decks = Deck.query.count()
        expected_notes = preimage.get("baseline_metrics", {}).get("total_notes", total_notes)
        expected_decks = preimage.get("baseline_metrics", {}).get("total_decks", total_decks)
        if total_notes != expected_notes or total_decks != expected_decks:
            raise RuntimeError(f"Rollback invariant failure: notes={total_notes} (expected {expected_notes}), decks={total_decks} (expected {expected_decks})")

        if dry_run:
            print("\n[ROLLBACK DRY RUN] Simulation complete. Preimage verified, rollback tested cleanly.")
            return {"status": "DRY_RUN_ROLLED_BACK", "preimage_sha256": recorded_sha256}
        else:
            # Cryptographic confirmation against authentic preimage
            current = capture_preimage_snapshot(captured_at=preimage.get("captured_at"))
            current_sha = compute_canonical_sha256(current)
            if current_sha != recorded_sha256:
                raise RuntimeError(
                    f"Post-rollback cryptographic verification failure! "
                    f"Recorded: {recorded_sha256}, Actual restored DB: {current_sha}"
                )
            print(f"[ROLLBACK CRYPTO VERIFIED] Restored live database matches authentic preimage SHA-256 (100% bit-for-bit).")
            print("\n" + "=" * 70)
            print("[SUCCESS] WAVE 7 ROLLBACK COMMITTED TO LOCAL MYSQL 8.0.")
            print("=" * 70)
            return {"status": "ROLLBACK_COMMITTED", "preimage_sha256": recorded_sha256}


def verify_migration() -> bool:
    """Verifies all post-migration database invariants and conditions on live MySQL."""
    app = create_app()
    print("=" * 70)
    print("STARTING WAVE 7 VERIFICATION")
    print("=" * 70)

    with app.app_context():
        # 1. Total Notes & Decks
        expected_notes = None
        expected_decks = None
        if PREIMAGE_FILE.exists():
            try:
                with open(PREIMAGE_FILE, "r", encoding="utf-8") as f:
                    pre_data = json.load(f)
                expected_notes = pre_data.get("baseline_metrics", {}).get("total_notes")
                expected_decks = pre_data.get("baseline_metrics", {}).get("total_decks")
            except Exception:
                pass

        total_notes = Note.query.count()
        total_decks = Deck.query.count()
        print(f"Total Notes: {total_notes} (Target: {expected_notes or '>=41870'})")
        print(f"Total Decks: {total_decks} (Target: {expected_decks or '>=5610'})")
        if expected_notes is not None:
            assert total_notes == expected_notes, f"Notes invariant violated: {total_notes} vs expected {expected_notes}"
        else:
            assert total_notes >= 41870, f"Notes invariant violated: {total_notes}"
        if expected_decks is not None:
            assert total_decks == expected_decks, f"Decks invariant violated: {total_decks} vs expected {expected_decks}"
        else:
            assert total_decks >= 5610, f"Decks invariant violated: {total_decks}"

        # 2. Template verification
        t = db.session.get(Template, TMPL_FLAMA_DEF_ID)
        assert 'display: flex; flex-direction: column; gap: 4px;' in t.back_html, "Template missing column flex for usage!"
        assert 'white-space: pre-wrap;' in t.back_html, "Template missing white-space: pre-wrap in back_html!"
        assert 'line-height: 1.45;' in t.back_html, "Template missing line-height: 1.45 in back_html!"
        assert '.flama-array-item' in (t.shared_css or ''), "Template missing .flama-array-item CSS rule!"
        assert 'line-height: 1.45;' in (t.shared_css or ''), "Template shared_css missing line-height: 1.45!"
        assert '>{{{additional_note_jp}}}</div>' in t.back_html, "Template additional_note_jp has whitespace padding before tag!"
        assert '>{{{additional_note_vi}}}</div>' in t.back_html, "Template additional_note_vi has whitespace padding before tag!"
        validator = TagBalanceValidator()
        validator.feed(t.back_html)
        validator.close()
        assert not validator.errors and not validator.stack, f"Template HTML tag imbalance: {validator.errors}"
        print("[VERIFY TEMPLATE] Template e0cb18b2 has column flex, pre-wrap, line-height 1.45, CSS rules, tight tag wrapping, and 100% tag balance.")

        # 3. Target Notes verification
        target_notes = get_target_notes()
        assert len(target_notes) == 172, f"Target notes count mismatch: {len(target_notes)}"

        concat_count = 0
        unseparated_additional_notes = 0
        double_newline_additional_notes = 0
        single_newline_vi_count = 0
        single_newline_jp_count = 0
        for n in target_notes:
            fv = n.field_values_by_id or {}
            for fid, lbls in [(FID_USAGE_VI, VI_LABELS), (FID_USAGE_JP, JP_LABELS)]:
                val = fv.get(fid)
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, str) and sum(1 for k in lbls if k in item) >= 2:
                            concat_count += 1
                elif isinstance(val, str) and sum(1 for k in lbls if k in val) >= 2:
                    concat_count += 1

            an_vi = fv.get(FID_ADD_NOTE_VI)
            if isinstance(an_vi, str) and "So sánh nhanh:" in an_vi and "Mẹo nhớ:" in an_vi:
                if "\n\n" in an_vi:
                    double_newline_additional_notes += 1
                if "\n" not in an_vi:
                    unseparated_additional_notes += 1
                else:
                    single_newline_vi_count += 1

            an_jp = fv.get(FID_ADD_NOTE_JP)
            if isinstance(an_jp, str) and "比較:" in an_jp and "注意:" in an_jp:
                if "\n\n" in an_jp:
                    double_newline_additional_notes += 1
                if "\n" not in an_jp:
                    unseparated_additional_notes += 1
                else:
                    single_newline_jp_count += 1

        assert concat_count == 0, f"Found {concat_count} notes with remaining concatenated usage labels!"
        assert unseparated_additional_notes == 0, f"Found {unseparated_additional_notes} additional notes without newline separation!"
        assert double_newline_additional_notes == 0, f"Found {double_newline_additional_notes} additional notes with double newlines (\\n\\n)!"
        assert single_newline_vi_count == 145, f"Expected 145 single-newline VI notes, found {single_newline_vi_count}!"
        assert single_newline_jp_count == 145, f"Expected 145 single-newline JP notes, found {single_newline_jp_count}!"
        print(f"[VERIFY NOTES] All 172 target notes verified: 0 concatenated usage items, 0 unseparated, 0 double newlines, 145 single-newline notes in VI & JP.")

        # 4. Preimage file verification
        if PREIMAGE_FILE.exists():
            with open(PREIMAGE_FILE, "r", encoding="utf-8") as f:
                preimage = json.load(f)
            rec_sha = preimage.get("preimage_sha256")
            comp_sha = compute_canonical_sha256(preimage)
            assert rec_sha == comp_sha, f"Preimage SHA-256 hash mismatch: {rec_sha} vs {comp_sha}"
            print(f"[VERIFY PREIMAGE] Authentic preimage SHA-256 matches: {rec_sha[:16]}...")

        print("\n" + "=" * 70)
        print("[VERIFICATION PASS] ALL WAVE 7 POST-MIGRATION INVARIANTS VERIFIED!")
        print("=" * 70)
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Wave 7 Grammar Practice Recovery Migration")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration or rollback without committing")
    parser.add_argument("--rollback", action="store_true", help="Roll back migration using authentic preimage snapshot")
    parser.add_argument("--verify", action="store_true", help="Verify live database state and invariants")
    parser.add_argument("--snapshot", action="store_true", help="Capture and save authentic preimage snapshot only")
    args = parser.parse_args()

    if args.verify:
        verify_migration()
    elif args.snapshot:
        preimage = capture_preimage_snapshot()
        save_preimage_atomic(preimage)
    elif args.rollback:
        rollback_migration(dry_run=args.dry_run)
    else:
        execute_migration(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
