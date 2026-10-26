"""Public AI Search & Documentation MCP Tools for external AI agents.

Enforces strict privacy boundaries (published marketplace items only),
anti-scraping sample preview limits (strictly 3-5 cards max), and pagination bounds.
"""

from __future__ import annotations

import logging
import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy import or_

from app.repositories.deck_tree_query import collect_subtree_ids
from app.services.common.mcp_response import (
    compact_description,
    wrap_tool_error,
    wrap_tool_result,
)
from app.services import marketplace_taxonomy_service
from app.services.marketplace.hub.helpers import _infer_market_levels
from app.validators.flashcard_input import RequestValidationError
from models import db
from models.deck import Deck
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note import Note

logger = logging.getLogger(__name__)

# Constants & Anti-scraping guardrails
MAX_PAGE_LIMIT = 20
DEFAULT_PAGE_LIMIT = 10
MIN_PAGE_LIMIT = 1
MAX_PREVIEW_SAMPLES = 5  # Anti-scraping hard limit: strictly 3 to 5 sample cards
DEFAULT_PREVIEW_SAMPLES = 3

FLAMA_DOCUMENTATION_TOPICS: dict[str, dict[str, str]] = {
    "note-type-authoring": {
        "title": "MCP NoteType and reusable template workflow (2026-10-27)",
        "markdown": """# MCP authoring workflow

Private tools require note-type:read or note-type:write. Listing is for discovery;
only owned resources can be changed. IDs are references, never authorization.

1. list_note_types, then get_note_type_schema to inspect field names, field_type,
   required and identity_role. include_templates=true includes stable field IDs,
   application IDs, source and input bindings for authoring.
2. create_note_type with a name and fields [{name,field_type,required,identity_role}].
   Supported types: text, richtext, markdown, image, audio, diagram, array.
   Primary identity is optional, unique, text-only and required. Omitted fields
   use Word/Meaning; omitted templates create a default presentation.
3. list_card_templates (search/group/page/page_size) finds reusable templates.
   get_card_template(include_source=true) returns HTML/CSS, typed input_schema
   [{key,label,type,required}], current_version_id and active applications.
4. preview_note_type_template with explicit input_schema, front_html, back_html,
   shared_css and sample_values checks a raw candidate without saving. Input keys
   are template variable names; labels are display text. Check valid, checks and
   diagnostics. Invalid preview content is a normal validation report (valid=false),
   so connectors preserve structured diagnostics. Mutations still return isError
   on failure. Authentication/authorization and service failures remain errors.
5. create_card_template saves a reusable definition. update_card_template renames
   it or edits inputs/source through the versioned library. Send template_id and
   expected_current_version_id from get_card_template to protect against stale edits.
   Definition edits affect its active applications; inspect usages before editing.
6. attach_card_template with note_type_id, template_id and input_bindings maps
   input keys to that NoteType's FieldDef IDs. Example: {"prompt":"<Word field ID>"}.
   Returns application_id. update_template_application changes the binding map,
   display_name, position or is_default for just that occurrence. Binding maps
   replace the previous map; include every mapping you want to keep.
7. Preview the attached occurrence using note_type_id + application_id and explicit
   samples keyed by source field name. Browser/interaction checks stay not_run;
   review appearance and behavior in the Study sandbox client.
8. create_deck(default_note_type_id=...) and create_note/batch_create_notes finish
   the flow; read back with get_note/get_card. To retire an unwanted default
   presentation, preview_note_type_update then update_note_type with
   templates={"removed":["<application_id>"]}; at least one presentation must remain.

## Updating NoteTypes and fields
Use preview_note_type_update, inspect its impact, then update_note_type with the
same changes and preview_id. Rename the NoteType with name. Prefer field deltas:
fields={"added":[{"name":"Example","field_type":"markdown"}],
"renamed":[{"old_name":"Meaning","new_name":"Definition"}],
"modified":[{"name":"Reading","required":true,"position":1}]}.
Renaming retains field identity and note data. Full field/template lists replace
their collections; omitted fields are removed and omitted presentations retired.
Removing populated fields requires a fresh preview and explicit user confirmation
before confirm=true. Published shared schemas can return
SHARED_SCHEMA_VERSIONING_REQUIRED: use the version-aware authoring UI instead.

Arrays and existing data retain their current contract; this workflow does not
migrate values or change rendering. See template-authoring for Mustache, media,
sandbox and legacy array details. A passing preview does not prove browser behavior.
""",
    },
    "template-authoring": {
        "title": "Card Template Authoring Contract v1 (2026-10-26)",
        "markdown": """# Card Template Authoring v1 — 2026-10-26

Use preview_note_type_template before applying a candidate. It checks Mustache,
field binding and inline JavaScript syntax without executing JavaScript. Checks
include javascript_syntax. Browser behavior and appearance are for user review;
study_browser and interaction remain not_run. A passed syntax check is not a
claim about runtime behavior, correct answers or visual quality.
It returns small diagnostics and candidate_hash; Study artifacts are delivered
only to the UI through result _meta by default. Request include_preview=true for
model-visible artifacts or include_server_render=true for legacy HTML debugging.
Preview validation errors return valid=false with checks and diagnostics as a
normal tool result, so connectors do not replace the report with an exception.
Mutation failures still return isError. Each diagnostic has code, severity, stage, source_part, line, column,
hint and suggestions. Unknown positions are null, not fabricated coordinates.
An MCP App can display the sandbox and, after user action, send a bounded report
to chat. The model cannot automatically click or inspect the preview DOM.

get_note_type_schema returns metadata without HTML/CSS or field/binding IDs by
default. Request include_templates=true only when source is needed. An optional
application_id selects one owned occurrence in source mode. Create/update return
compact metadata, not a copy of the submitted HTML/CSS. Only necessary target
references are returned; IDs never grant permission. The server enforces scopes,
ownership and published-release visibility even when an ID is known.

## Syntax and arrays
- Mustache sections: {{#options}}<li>{{.}}</li>{{/options}}.
- Inverted sections: {{^explanation}}No explanation provided.{{/explanation}}.
- Indexed access: {{options.0}} and {{correct_answers.0}} use zero-based lookup.
- {{options}} prints comma-joined text. Native array storage is JSON lists of
  strings or nested lists. Numeric/object items are rejected. Legacy newline
  strings are still readable but are not automatically converted to lists.
- {{@index}}, {{index}} item methods, Handlebars #each/#if and external partials
  are unsupported. To number options, iterate rendered DOM nodes with index + 1.
- Text {{field}} is escaped; {{{field}}} is sanitized rich markup. Richtext,
  Markdown and typed media use their normal renderer preparation.
- {{FrontSide}} on back includes the rendered front without its scripts; it is
  empty on front. Use a separate back initializer if interactions are required.

## Context and script lifecycle
HTML and inline <style> participate in Mustache interpolation. shared_css is
static and never interpolates note values. Study extracts template-authored
inline scripts before interpolation; {{tokens}} in those scripts remain literal.
Field content never gains script provenance. Read rendered DOM or
FlamaCard.getContext().fieldValues instead of inserting raw values into scripts.

Scripts run only in the existing opaque-origin iframe sandbox="allow-scripts".
Reactivating an unchanged face retains its document and local interaction state.
A new card, source or context causes a render or patch; script initialization
runs when a fresh document is rendered, rather than on every reactivation.
Initialize from DOM after markup and use FlamaCard.onReveal(callback) for every
show. Also available: FlamaCard.getConfig(), FlamaCard.getContext(),
FlamaCard.notifyHeight(), and FlamaCard.playAudio(ref) when needed.
Do not request allow-same-origin or external scripts. Media remains constrained
by renderer CSP and the existing proxy/allowlist model.

## Preview targets
Raw: input_schema [{key,type,required}], front_html, back_html and sample_values
are explicit. Samples are ephemeral. Attached: note_type_id + application_id
select a directly owned occurrence and its actual field bindings. Samples then
use source field names. template_id alone is ambiguous and unsupported. Installed
or another author's pinned contexts must use a separately resolved/exported raw
candidate; this tool does not substitute an author's live draft for a release.

Apply still uses preview_note_type_update then update_note_type with existing
confirmation/token semantics. Candidate hashes identify evidence, not permission.
""",
    },
    "quiz-template": {
        "title": "Sandbox Quiz Recipe v1 (2026-10-26)",
        "markdown": """# Sandbox Quiz Recipe v1 — 2026-10-26

Inputs: question (Markdown), options (array), correct_answers (array), explanation
(optional Markdown). correct_answers contains unique 1-based string positions,
e.g. ["1", "3"]. Use profile="quiz" in preview to validate nonempty flat options,
nonempty unique answers and range. Generic arrays have no quiz-specific rules.
Reordering options requires updating answer positions at the same time.

The recipe shows Select N answers, waits for exactly N selected, then grades.
Changing selections recalculates feedback. Revealing the back shows correct
answers and explanation, with an explicit missing-explanation fallback. This
feedback does not submit scheduler ratings or modify progress.

The JSON below is a candidate for preview_note_type_template, not instructions
to mutate a NoteType. Browser fixture checks are separate from server analysis.
""",
    },
    "overview": {
        "title": "Flama Platform Overview",
        "markdown": """# Flama Platform Overview (Flama.vn)

Flama is an advanced, full-stack Japanese language learning platform designed to streamline the journey from beginner (JLPT N5) to native fluency (JLPT N1+).

## Core Capabilities
1. **Intelligent Spaced Repetition (SRS)**: FSRS and SM-2 scheduling algorithms optimized for long-term memory retention and zero study burnout.
2. **Flama Connect & 1-Click Mining**: Yomitan protocol bridge on port 4790 allowing instant sentence, audio, and definition mining while reading Japanese media.
3. **Local Text-to-Speech Companion**: Flama Audio running VoiceVox and Kokoro TTS on port 4791 for pitch-accent-accurate pronunciation.
4. **Community Marketplace & Overlay Cloning**: Zero-copy clone architecture allowing learners to study shared decks while receiving upstream author updates without mutating personal progress.

Website: https://flama.vn
Marketplace: https://flama.vn/marketplace
Documentation: https://flama.vn/docs
""",
    },
    "srs": {
        "title": "Spaced Repetition System (SRS)",
        "markdown": """# Flama Spaced Repetition System (SRS)

Flama's SRS engine combines the best elements of FSRS (Free Spaced Repetition Scheduler) and modified SuperMemo SM-2 algorithms to maximize Japanese retention.

## Features
- **Day-Boundary Alignment**: Reviews roll over at configurable local timezone day boundaries (default 04:00 AM) to prevent split-day fatigue.
- **Difficulty & Stability Tracking**: Cards maintain independent stability and difficulty factors, adjusting review intervals from minutes to years.
- **4-Button Grading**: Again (fail), Hard (struggle), Good (standard recall), Easy (instant recall).
- **Anti-Leech Management**: Automatically flags cards with excessive lapses for targeted mnemonics or restructuring.
- **Study Authority Fence**: Ensures strictly deterministic scheduling without race conditions across mobile and web.
""",
    },
    "yomitan": {
        "title": "Yomitan Mining Bridge & Flama Connect",
        "markdown": """# Flama Connect & Yomitan 1-Click Mining

Flama Connect acts as a high-performance local protocol bridge (compatible with AnkiConnect protocol v6) running on port 4790.

## Workflow
1. Browse Japanese manga, novels, subtitles, or web articles in Google Chrome, Brave, or Firefox.
2. Hover over any unknown Japanese term using the Yomitan browser extension.
3. Click the '+' button: Yomitan calls Flama Connect (`/v1/mcp` or `/api/connect`).
4. Flama automatically creates the vocabulary note with:
   - Kanji term, furigana reading, bilingual definitions.
   - Context sentence with sentence audio capture.
   - Target deck placement and tag taxonomy.
""",
    },
    "tts": {
        "title": "Local Japanese TTS Engine (VoiceVox & Kokoro)",
        "markdown": """# Local Japanese TTS Engine (Flama Audio)

Flama features a dedicated offline desktop audio companion (`flama-audio/`) running as a lightweight .NET 8 WPF background service on port 4791.

## Supported TTS Engines
- **VoiceVox**: High-fidelity Japanese native neural voices (Zundamon, Shikoku Metan, WhiteCUL) with expressive pitch accent reproduction.
- **Kokoro-82M**: Ultra-fast, lightweight neural speech synthesis with exceptional clarity and natural phrasing.
- **Zero Cloud Latency**: Audio is synthesized locally with GPU/CPU acceleration, eliminating subscription costs and network delays.
""",
    },
    "marketplace": {
        "title": "Marketplace & JLPT Decks",
        "markdown": """# Flama Marketplace & JLPT Decks

The Flama Marketplace enables community authors and educators to publish curated Japanese flashcard decks, complete courses, and specialized vocabulary collections.

## JLPT Roadmaps
- **JLPT N5 & N4**: Essential kana, basic grammar structures, and core 1,500 beginner vocabulary.
- **JLPT N3**: Bridging the gap with intermediate reading, daily conversation expressions, and kanji compounds.
- **JLPT N2 & N1**: Advanced newspaper reading, professional expressions, academic terminology, and nuanced grammar.

## Clone Overlay Architecture
Unlike legacy Anki where sharing requires copying entire decks into personal databases, Flama uses an immutable clone overlay model:
- Students install decks with zero duplicate note storage.
- Authors push deck release updates (`DeckRelease`) which seamlessly flow to students.
- Student personal review schedules, intervals, and custom notes are stored in an independent overlay layer without mutating source decks.
""",
    },
    "faq": {
        "title": "Frequently Asked Questions (FAQ)",
        "markdown": """# Frequently Asked Questions (FAQ)

### Q: Is Flama free to use?
A: Yes! Flama provides generous free tier access for personal deck creation, SRS study, Yomitan word mining, and public marketplace decks.

### Q: Can I import my existing Anki decks?
A: Absolutely. Flama supports direct `.apkg` deck import with full preservation of card templates, audio, images, and review scheduling histories.

### Q: How does MCP search protect user privacy?
A: Flama's Model Context Protocol (MCP) public endpoint queries strictly published community decks (`publish_status == 'published'`). Personal user vocabulary, study logs, and unpublished draft cards are completely isolated behind authentication barriers.

### Q: Why does MCP only return 3-5 preview cards?
A: Flama implements strict anti-scraping guardrails to protect community deck creators from mass data scraping. AI agents receive rich metadata and a representative sample preview (3 to 5 cards max) to answer queries without dumping full deck databases.
""",
    },
}

TOPIC_ALIASES: dict[str, str] = {
    "note-type-authoring": "note-type-authoring",
    "note_type_authoring": "note-type-authoring",
    "template-authoring": "template-authoring",
    "template_authoring": "template-authoring",
    "quiz-template": "quiz-template",
    "quiz_template": "quiz-template",
    "overview": "overview",
    "general": "overview",
    "srs": "srs",
    "srs_spaced_repetition": "srs",
    "srs-spaced-repetition": "srs",
    "spaced_repetition": "srs",
    "spaced-repetition": "srs",
    "yomitan": "yomitan",
    "yomitan_connect": "yomitan",
    "yomitan-connect": "yomitan",
    "mining": "yomitan",
    "tts": "tts",
    "local_tts": "tts",
    "local-tts": "tts",
    "voicevox": "tts",
    "kokoro": "tts",
    "marketplace": "marketplace",
    "marketplace_jlpt": "marketplace",
    "marketplace-jlpt": "marketplace",
    "jlpt": "marketplace",
    "faq": "faq",
    "help": "faq",
}


def _resolve_topic(raw_topic: str | None) -> str:
    cleaned = str(raw_topic or "overview").strip().lower()
    return TOPIC_ALIASES.get(cleaned, "overview")


def _matches_jlpt_level(deck_item: DeckMarketplaceItem, requested_level: str | None) -> bool:
    if not requested_level or requested_level.strip().lower() in ("all", "", "any"):
        return True
    req = requested_level.strip().upper()
    meta = deck_item.taxonomy_metadata if isinstance(deck_item.taxonomy_metadata, dict) else {}
    framework_level = str(meta.get("framework_level") or meta.get("level") or "").strip().upper()
    if req in framework_level:
        return True
    inferred = _infer_market_levels(
        deck_item.title,
        deck_item.description,
        deck_item.primary_category,
        tags=deck_item.tags or [],
    )
    return any(req == lvl.upper() for lvl in inferred)


def _resolve_deck_jlpt_level(deck_item: DeckMarketplaceItem) -> str:
    meta = deck_item.taxonomy_metadata if isinstance(deck_item.taxonomy_metadata, dict) else {}
    if meta.get("framework_level"):
        return str(meta["framework_level"])
    inferred = _infer_market_levels(
        deck_item.title,
        deck_item.description,
        deck_item.primary_category,
        tags=deck_item.tags or [],
    )
    for lvl in ("N5", "N4", "N3", "N2", "N1"):
        if lvl in inferred:
            return lvl
    return inferred[0] if inferred else "All"


def _extract_field_text(field_values: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        if key in field_values and field_values[key] is not None:
            text = str(field_values[key]).strip()
            if text:
                return text
    return ""


def _extract_preview_samples(
    deck_item: DeckMarketplaceItem,
    max_samples: int = MAX_PREVIEW_SAMPLES,
) -> list[dict[str, Any]]:
    """Extract strictly at most 3 to 5 preview sample cards from published deck.

    Enforces the anti-scraping policy: output is hard-capped at MAX_PREVIEW_SAMPLES (5).
    """
    clamped_limit = max(1, min(max_samples, MAX_PREVIEW_SAMPLES))
    samples: list[dict[str, Any]] = []

    if deck_item.current_release_id:
        from app.services import marketplace_query_service
        from models.deck_release import DeckRelease

        release = db.session.get(DeckRelease, deck_item.current_release_id)
        if release is None or release.deck_item_id != deck_item.id or release.status != "published":
            return []
        # A cache is public only for the current immutable release. Reconstruct
        # from release memberships/deltas on a miss, never from working Notes.
        raw_samples = marketplace_query_service._cached_release_samples(
            deck_item, limit=clamped_limit, schema_version=1,
        )
        if raw_samples is None:
            raw_samples = marketplace_query_service.build_release_sample_cache_from_release(
                deck_item, release, limit=clamped_limit,
            )
        return [
            {key: str(sample.get(key) or "") for key in ("word", "reading", "meaning")}
            for sample in raw_samples[:clamped_limit]
        ]

    # 1. Try precomputed sample cache
    if isinstance(deck_item.preview_samples_json, list) and deck_item.preview_samples_json:
        for raw in deck_item.preview_samples_json[:clamped_limit]:
            if isinstance(raw, dict):
                word = str(raw.get("word") or raw.get("term") or raw.get("Word") or "").strip()
                reading = str(raw.get("reading") or raw.get("Reading") or raw.get("kana") or "").strip()
                meaning = str(raw.get("meaning") or raw.get("Meaning") or "").strip()
                if word:
                    samples.append({
                        "word": word,
                        "reading": reading,
                        "meaning": meaning,
                    })
        if samples:
            return samples[:MAX_PREVIEW_SAMPLES]

    # Legacy listings without a release keep their deterministic, bounded
    # preview. Published releases above never fall back to working Notes.
    if deck_item.source_deck_id is not None:
        try:
            subtree_ids = collect_subtree_ids(deck_item.source_deck_id)
            if subtree_ids:
                note_query = Note.query.filter(
                    Note.deck_id.in_(subtree_ids),
                    Note.user_id == deck_item.owner_user_id,
                )
                live_notes = note_query.order_by(Note.id.asc()).limit(clamped_limit * 2).all()
                for note in live_notes:
                    fvals = note.field_values if isinstance(note.field_values, dict) else {}
                    word = _extract_field_text(fvals, ["Word", "word", "Term", "term", "Vocabulary", "vocabulary"])
                    if not word:
                        for v in fvals.values():
                            if v:
                                word = str(v).strip()
                                break
                    if word:
                        reading = _extract_field_text(fvals, ["Reading", "reading", "Kana", "kana", "Yomigana", "yomigana"])
                        meaning = _extract_field_text(fvals, ["Meaning", "meaning", "Meaning_VI", "meaning_vi", "Translation_VI"])
                        samples.append({
                            "word": word,
                            "reading": reading,
                            "meaning": meaning,
                        })
                    if len(samples) >= clamped_limit:
                        break
        except Exception:
            logger.warning("Failed to extract live notes for deck_item_id=%s", deck_item.id, exc_info=True)

    return samples[:MAX_PREVIEW_SAMPLES]


def _count_published_deck_cards(deck_item: DeckMarketplaceItem) -> int:
    """Safely resolve total card count for a published deck."""
    if deck_item.sample_cards_count and deck_item.sample_cards_count > 0:
        return int(deck_item.sample_cards_count)
    if deck_item.source_deck_id is not None:
        try:
            subtree_ids = collect_subtree_ids(deck_item.source_deck_id)
            if subtree_ids:
                return Note.query.filter(
                    Note.deck_id.in_(subtree_ids),
                    Note.user_id == deck_item.owner_user_id,
                ).count()
        except Exception:
            pass
    return 0


# ===========================================================================
# Tool Implementations
# ===========================================================================

def search_marketplace_decks(
    query: str = "",
    jlpt_level: str = "All",
    category: str = "",
    pricing_mode: str = "all",
    sort_by: str = "popular",
    limit: int = DEFAULT_PAGE_LIMIT,
    offset: int = 0,
    *,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Search public published flashcard decks on the Flama Marketplace.

    Strictly queries published decks (publish_status == 'published').
    Enforces anti-scraping limits: sample_preview contains at most 3 to 5 cards,
    and pagination is bounded (max 20 decks per request).
    """
    del user_id  # Public search is unauthenticated / guest

    bounded_limit = max(MIN_PAGE_LIMIT, min(int(limit or DEFAULT_PAGE_LIMIT), MAX_PAGE_LIMIT))
    bounded_offset = max(0, int(offset or 0))

    # STRICT PRIVACY: Query ONLY published marketplace decks
    query_base = DeckMarketplaceItem.query.filter_by(publish_status="published")

    all_items = query_base.order_by(DeckMarketplaceItem.updated_at.desc()).all()

    # Filter by query keyword
    clean_q = str(query or "").strip().lower()
    filtered: list[DeckMarketplaceItem] = []
    for item in all_items:
        if clean_q:
            title_text = str(item.title or "").lower()
            desc_text = str(item.description or "").lower()
            cat_text = str(item.primary_category or "").lower()
            tags_text = " ".join(str(t).lower() for t in (item.tags or []))
            if not (clean_q in title_text or clean_q in desc_text or clean_q in cat_text or clean_q in tags_text):
                continue

        # Filter by category
        if category and str(category).strip():
            cat_filter = str(category).strip().lower()
            if cat_filter != str(item.primary_category or "").strip().lower():
                continue

        # Filter by pricing mode
        if pricing_mode and str(pricing_mode).strip().lower() in ("free", "paid"):
            if str(item.pricing_mode or "free").lower() != str(pricing_mode).strip().lower():
                continue

        # Filter by JLPT level
        if not _matches_jlpt_level(item, jlpt_level):
            continue

        filtered.append(item)

    # Sort
    sort_key = str(sort_by or "popular").strip().lower()
    if sort_key == "rating":
        filtered.sort(key=lambda d: (float(d.rating_avg or 0.0), int(d.rating_count or 0)), reverse=True)
    elif sort_key == "newest":
        filtered.sort(key=lambda d: d.created_at or d.updated_at, reverse=True)
    elif sort_key == "card_count":
        filtered.sort(key=lambda d: int(d.sample_cards_count or 0), reverse=True)
    else:  # popular
        filtered.sort(
            key=lambda d: (int(d.install_count or 0), float(d.rating_avg or 0.0)),
            reverse=True,
        )

    total = len(filtered)
    paged = filtered[bounded_offset : bounded_offset + bounded_limit]

    result_items: list[dict[str, Any]] = []
    for item in paged:
        author_name = item.owner.username if item.owner else "Flama Community"
        deck_cards_count = _count_published_deck_cards(item)
        preview_samples = _extract_preview_samples(item, max_samples=MAX_PREVIEW_SAMPLES)
        jlpt = _resolve_deck_jlpt_level(item)

        result_items.append({
            "id": str(item.id),
            "title": str(item.title),
            "description": compact_description(item.description, max_length=300) or "",
            "primary_category": str(item.primary_category or "General"),
            "jlpt_level": jlpt,
            "total_cards": deck_cards_count,
            "rating_avg": round(float(item.rating_avg or 0.0), 2),
            "rating_count": int(item.rating_count or 0),
            "pricing_mode": str(item.pricing_mode or "free"),
            "author_username": author_name,
            "canonical_url": f"https://flama.vn/marketplace/decks/{item.id}",
            "sample_preview": preview_samples,
        })

    return {
        "items": result_items,
        "total": total,
        "limit": bounded_limit,
        "offset": bounded_offset,
        "has_more": (bounded_offset + len(result_items) < total),
        "anti_scraping_guardrail": {
            "max_page_limit": MAX_PAGE_LIMIT,
            "max_preview_samples_per_deck": MAX_PREVIEW_SAMPLES,
            "notice": "Sample preview capped at 5 cards per deck. Full card extraction is restricted.",
        },
    }


def lookup_public_vocabulary(
    query: str,
    jlpt_level: str = "All",
    limit: int = DEFAULT_PAGE_LIMIT,
    offset: int = 0,
    *,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Search Japanese vocabulary words, kana readings, and definitions across published marketplace decks.

    STRICT PRIVACY: Searches only the fixed public preview samples of published
    marketplace items. Owner working values and non-sample content stay private.
    """
    del user_id  # Public search is unauthenticated / guest

    clean_query = str(query or "").strip().lower()
    bounded_limit = max(MIN_PAGE_LIMIT, min(int(limit or DEFAULT_PAGE_LIMIT), MAX_PAGE_LIMIT))
    bounded_offset = max(0, int(offset or 0))

    if not clean_query:
        return {
            "matches": [],
            "total": 0,
            "limit": bounded_limit,
            "offset": bounded_offset,
            "has_more": False,
        }

    # 1. Fetch published marketplace items ONLY
    published_items = DeckMarketplaceItem.query.filter_by(publish_status="published").all()
    if jlpt_level and jlpt_level.strip().lower() not in ("all", "", "any"):
        published_items = [it for it in published_items if _matches_jlpt_level(it, jlpt_level)]

    if not published_items:
        return {
            "matches": [],
            "total": 0,
            "limit": bounded_limit,
            "offset": bounded_offset,
            "has_more": False,
        }

    matches: list[dict[str, Any]] = []
    seen_terms: set[tuple[str, str]] = set()  # (deck_id, word)

    for item in published_items:
        jlpt = _resolve_deck_jlpt_level(item)
        canonical_url = f"https://flama.vn/marketplace/decks/{item.id}"
        # The same fixed sample set serves previews and searches. Querying
        # live Notes (or filtering before the cap) would expose owner drafts
        # and let repeated searches/pagination reconstruct the entire deck.
        for sample in _extract_preview_samples(item, max_samples=MAX_PREVIEW_SAMPLES):
            word, reading, meaning = (sample[key] for key in ("word", "reading", "meaning"))
            if not any(clean_query in value.lower() for value in (word, reading, meaning)):
                continue
            dedup_key = (str(item.id), word.lower())
            if dedup_key in seen_terms:
                continue
            seen_terms.add(dedup_key)
            matches.append({
                "term": word,
                "word": word,
                "reading": reading,
                "meaning": meaning,
                "deck_id": str(item.id),
                "deck_title": str(item.title),
                "canonical_url": canonical_url,
                "jlpt_level": jlpt,
            })

    total = len(matches)
    paged_matches = matches[bounded_offset : bounded_offset + bounded_limit]

    return {
        "matches": paged_matches,
        "total": total,
        "limit": bounded_limit,
        "offset": bounded_offset,
        "has_more": (bounded_offset + len(paged_matches) < total),
    }


def get_public_deck_preview(
    deck_item_id: str,
    *,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Get metadata and a limited sample preview (strictly at most 3 to 5 cards) for a published marketplace deck.

    Validates publish_status == 'published'. Rejects private or unlisted decks with DECK_NOT_PUBLIC.
    Capped at 5 cards max to enforce anti-scraping policy.
    """
    del user_id  # Public search is unauthenticated / guest

    clean_id = str(deck_item_id or "").strip()
    if not clean_id:
        raise RequestValidationError(
            "deck_item_id là bắt buộc.",
            field="deck_item_id",
            status=400,
            code="INVALID_PARAMS",
        )

    item = DeckMarketplaceItem.query.filter_by(id=clean_id).first()
    if item is None or item.publish_status != "published":
        raise RequestValidationError(
            f"Deck '{clean_id}' không tồn tại hoặc không ở trạng thái công khai.",
            field="deck_item_id",
            status=404,
            code="DECK_NOT_PUBLIC",
        )

    author_name = item.owner.username if item.owner else "Flama Community"
    deck_cards_count = _count_published_deck_cards(item)
    preview_samples = _extract_preview_samples(item, max_samples=MAX_PREVIEW_SAMPLES)
    jlpt = _resolve_deck_jlpt_level(item)

    return {
        "id": str(item.id),
        "title": str(item.title),
        "description": str(item.description or ""),
        "primary_category": str(item.primary_category or "General"),
        "jlpt_level": jlpt,
        "tags": list(item.tags or []),
        "total_cards": deck_cards_count,
        "rating_avg": round(float(item.rating_avg or 0.0), 2),
        "rating_count": int(item.rating_count or 0),
        "pricing_mode": str(item.pricing_mode or "free"),
        "author_username": author_name,
        "canonical_url": f"https://flama.vn/marketplace/decks/{item.id}",
        "sample_preview": preview_samples,
        "anti_scraping_guardrail": {
            "is_sample_preview_only": True,
            "max_allowed_samples": MAX_PREVIEW_SAMPLES,
            "message": "Full deck content cannot be dumped via MCP. Only 3 to 5 sample preview cards are provided to protect author content.",
        },
    }


def get_flama_documentation(
    topic: str = "overview",
    *,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Reference authoritative documentation on Flama features (SRS, Yomitan, Local TTS, Marketplace, FAQ)."""
    del user_id  # Public documentation is unauthenticated

    resolved_key = _resolve_topic(topic)
    doc_info = FLAMA_DOCUMENTATION_TOPICS.get(resolved_key, FLAMA_DOCUMENTATION_TOPICS["overview"])

    return {
        "topic": resolved_key,
        "title": doc_info["title"],
        "content": _documentation_markdown(resolved_key, doc_info),
        "canonical_url": f"https://flama.vn/docs/{resolved_key}",
        "available_topics": list(FLAMA_DOCUMENTATION_TOPICS.keys()),
    }


# ===========================================================================
# MCP Resources Helpers (flama://docs/...)
# ===========================================================================

def _documentation_markdown(topic, doc_info):
    if topic == "quiz-template":
        # Fixed packaged recipe only: never map a caller-supplied URI to disk.
        recipe_path = Path(__file__).resolve().parent / "recipes" / "quiz.json"
        if recipe_path.is_file():
            recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
            return doc_info["markdown"] + "\n```json\n" + json.dumps(recipe, ensure_ascii=False, indent=2) + "\n```\n"
    return doc_info["markdown"]


def list_documentation_resources() -> list[dict[str, Any]]:
    """Return catalog of public flama://docs/... documentation resources."""
    resources: list[dict[str, Any]] = []
    for topic_key, doc_info in FLAMA_DOCUMENTATION_TOPICS.items():
        resources.append({
            "uri": f"flama://docs/{topic_key}",
            "name": doc_info["title"],
            "description": f"Official documentation for {doc_info['title']} on Flama.vn",
            "mimeType": "text/markdown",
        })
    return resources


def read_documentation_resource(uri: str) -> dict[str, Any] | None:
    """Read a specific flama://docs/<topic> documentation resource."""
    cleaned_uri = str(uri or "").strip()
    match = re.match(r"^flama://docs/([^/?#]+)$", cleaned_uri)
    if not match:
        return None
    raw_topic = match.group(1).lower()
    resolved_topic = TOPIC_ALIASES.get(raw_topic)
    if not resolved_topic or resolved_topic not in FLAMA_DOCUMENTATION_TOPICS:
        return None
    doc_info = FLAMA_DOCUMENTATION_TOPICS[resolved_topic]
    return {
        "uri": cleaned_uri,
        "mimeType": "text/markdown",
        "text": _documentation_markdown(resolved_topic, doc_info),
    }


# ===========================================================================
# Argument Validators for MCP Registry
# ===========================================================================

def validate_search_marketplace_decks_arguments(arguments: Any) -> dict[str, Any]:
    payload = arguments if isinstance(arguments, dict) else {}
    return {
        "query": str(payload.get("query") or "").strip(),
        "jlpt_level": str(payload.get("jlpt_level") or "All").strip(),
        "category": str(payload.get("category") or "").strip(),
        "pricing_mode": str(payload.get("pricing_mode") or "all").strip(),
        "sort_by": str(payload.get("sort_by") or "popular").strip(),
        "limit": int(payload.get("limit") or DEFAULT_PAGE_LIMIT),
        "offset": int(payload.get("offset") or 0),
    }


def validate_lookup_public_vocabulary_arguments(arguments: Any) -> dict[str, Any]:
    payload = arguments if isinstance(arguments, dict) else {}
    query = str(payload.get("query") or "").strip()
    if not query:
        raise RequestValidationError(
            "query là bắt buộc.",
            field="query",
            status=400,
            code="INVALID_PARAMS",
        )
    return {
        "query": query,
        "jlpt_level": str(payload.get("jlpt_level") or "All").strip(),
        "limit": int(payload.get("limit") or DEFAULT_PAGE_LIMIT),
        "offset": int(payload.get("offset") or 0),
    }


def validate_get_public_deck_preview_arguments(arguments: Any) -> dict[str, Any]:
    payload = arguments if isinstance(arguments, dict) else {}
    deck_item_id = str(payload.get("deck_item_id") or "").strip()
    if not deck_item_id:
        raise RequestValidationError(
            "deck_item_id là bắt buộc.",
            field="deck_item_id",
            status=400,
            code="INVALID_PARAMS",
        )
    return {
        "deck_item_id": deck_item_id,
    }


def validate_get_flama_documentation_arguments(arguments: Any) -> dict[str, Any]:
    payload = arguments if isinstance(arguments, dict) else {}
    return {
        "topic": str(payload.get("topic") or "overview").strip(),
    }
