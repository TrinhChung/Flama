"""Public AI Search & Documentation MCP Tools for external AI agents.

Enforces strict privacy boundaries (published marketplace items only),
anti-scraping sample preview limits (strictly 3-5 cards max), and pagination bounds.
"""

from __future__ import annotations

import logging
import re
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
from models.deck_release_note_checkpoint import DeckReleaseNoteCheckpoint
from models.note import Note

logger = logging.getLogger(__name__)

# Constants & Anti-scraping guardrails
MAX_PAGE_LIMIT = 20
DEFAULT_PAGE_LIMIT = 10
MIN_PAGE_LIMIT = 1
MAX_PREVIEW_SAMPLES = 5  # Anti-scraping hard limit: strictly 3 to 5 sample cards
DEFAULT_PREVIEW_SAMPLES = 3

FLAMA_DOCUMENTATION_TOPICS: dict[str, dict[str, str]] = {
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

    # 2. Try release note checkpoints if available
    if deck_item.current_release_id:
        checkpoints = (
            DeckReleaseNoteCheckpoint.query.filter_by(release_id=deck_item.current_release_id)
            .order_by(DeckReleaseNoteCheckpoint.id.asc())
            .limit(clamped_limit * 2)
            .all()
        )
        for cp in checkpoints:
            fvals = cp.field_values if isinstance(cp.field_values, dict) else {}
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
        if samples:
            return samples[:MAX_PREVIEW_SAMPLES]

    # 3. Fallback to source deck live notes (author-owned notes within subtree)
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

    STRICT PRIVACY: Excludes all private user notes and unshared decks. Queries ONLY
    DeckMarketplaceItem where publish_status == 'published'.
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

        # Check preview samples cache first
        if isinstance(item.preview_samples_json, list):
            for sample in item.preview_samples_json:
                if not isinstance(sample, dict):
                    continue
                w = str(sample.get("word") or sample.get("term") or sample.get("Word") or "").strip()
                r = str(sample.get("reading") or sample.get("Reading") or sample.get("kana") or "").strip()
                m = str(sample.get("meaning") or sample.get("Meaning") or "").strip()
                if not w:
                    continue
                if clean_query in w.lower() or clean_query in r.lower() or clean_query in m.lower():
                    dedup_key = (str(item.id), w.lower())
                    if dedup_key not in seen_terms:
                        seen_terms.add(dedup_key)
                        matches.append({
                            "term": w,
                            "word": w,
                            "reading": r,
                            "meaning": m,
                            "deck_id": str(item.id),
                            "deck_title": str(item.title),
                            "canonical_url": canonical_url,
                            "jlpt_level": jlpt,
                        })

        # Check notes in source deck (STRICTLY constrained to this published deck and author)
        if item.source_deck_id is not None:
            try:
                subtree_ids = collect_subtree_ids(item.source_deck_id)
                if subtree_ids:
                    notes = Note.query.filter(
                        Note.deck_id.in_(subtree_ids),
                        Note.user_id == item.owner_user_id,
                    ).limit(500).all()

                    for n in notes:
                        fvals = n.field_values if isinstance(n.field_values, dict) else {}
                        w = _extract_field_text(fvals, ["Word", "word", "Term", "term", "Vocabulary", "vocabulary"])
                        if not w:
                            for val in fvals.values():
                                if val:
                                    w = str(val).strip()
                                    break
                        if not w:
                            continue
                        r = _extract_field_text(fvals, ["Reading", "reading", "Kana", "kana", "Yomigana", "yomigana"])
                        m = _extract_field_text(fvals, ["Meaning", "meaning", "Meaning_VI", "meaning_vi", "Translation_VI"])

                        if clean_query in w.lower() or clean_query in r.lower() or clean_query in m.lower():
                            dedup_key = (str(item.id), w.lower())
                            if dedup_key not in seen_terms:
                                seen_terms.add(dedup_key)
                                matches.append({
                                    "term": w,
                                    "word": w,
                                    "reading": r,
                                    "meaning": m,
                                    "deck_id": str(item.id),
                                    "deck_title": str(item.title),
                                    "canonical_url": canonical_url,
                                    "jlpt_level": jlpt,
                                })
            except Exception:
                logger.warning("Failed to search notes for published deck_item_id=%s", item.id, exc_info=True)

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
        "content": doc_info["markdown"],
        "canonical_url": f"https://flama.vn/docs/{resolved_key}",
        "available_topics": list(FLAMA_DOCUMENTATION_TOPICS.keys()),
    }


# ===========================================================================
# MCP Resources Helpers (flama://docs/...)
# ===========================================================================

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
        "text": doc_info["markdown"],
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
