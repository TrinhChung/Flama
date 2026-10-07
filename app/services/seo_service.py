"""Technical SEO & GEO (Generative Engine Optimization) Service.

Provides generation logic for:
1. robots.txt with machine-readable crawler optimization for AI search bots
   (GPTBot, ChatGPT-User, PerplexityBot, ClaudeBot, Google-Extended).
2. dynamic sitemap.xml conforming to sitemaps.org schema with 38 authoritative public URLs.
3. llms.txt conforming to the llmstxt.org specification for AI Agent retrieval.
"""

from __future__ import annotations

import datetime
from typing import Any
import xml.etree.ElementTree as ET

# Canonical default domain
DEFAULT_BASE_URL = "https://flama.vn"

# Authoritative catalog of 38 public indexable pages for Flama
# (Priority and change frequency optimized according to search intent)
PUBLIC_SITEMAP_CATALOG: list[dict[str, Any]] = [
    # 1. Root & Primary Hubs
    {"path": "/", "changefreq": "weekly", "priority": "1.0"},
    {"path": "/guide", "changefreq": "weekly", "priority": "0.9"},
    # 2. Getting Started
    {"path": "/guide/getting-started/getting-started", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/getting-started/core-concepts", "changefreq": "monthly", "priority": "0.8"},
    # 3. Dashboard
    {"path": "/guide/dashboard/overview", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/dashboard/deck-grouping", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/dashboard/deck-management", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/dashboard/study-metrics", "changefreq": "monthly", "priority": "0.8"},
    # 4. Study & SRS Lifecycle
    {"path": "/guide/study/flashcard-flow", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/study/spaced-repetition", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/study/shortcuts", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/study/audio-and-furigana", "changefreq": "monthly", "priority": "0.8"},
    # 5. Browse & Card Search
    {"path": "/guide/browse/search-syntax", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/browse/batch-actions", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/browse/card-lifecycle", "changefreq": "monthly", "priority": "0.8"},
    # 6. Note Types & Templates
    {"path": "/guide/note-types/concept", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/note-types/fields", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/note-types/templates", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/note-types/cloze-deletion", "changefreq": "monthly", "priority": "0.8"},
    # 7. Marketplace & Community Decks
    {"path": "/guide/marketplace/discovery", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/marketplace/overlay-clone", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/marketplace/change-requests", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/marketplace/creator-publishing", "changefreq": "monthly", "priority": "0.8"},
    # 8. Audio & Local TTS
    {"path": "/guide/audio/cloud-tts-keys", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/audio/batch-generation", "changefreq": "monthly", "priority": "0.8"},
    # 9. Anki Import & Sync
    {"path": "/guide/import-sync/csv-wizard", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/import-sync/anki-connect-sync", "changefreq": "monthly", "priority": "0.8"},
    # 10. Integrations (Yomitan & MCP)
    {"path": "/guide/integrations/yomitan", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/integrations/yomitan-markers", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/integrations/mcp-ai", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/guide/integrations/mcp-tools", "changefreq": "monthly", "priority": "0.8"},
    # 11. Desktop Companion & Support Hub
    {"path": "/guide/flama-audio", "changefreq": "monthly", "priority": "0.8"},
    {"path": "/support", "changefreq": "monthly", "priority": "0.7"},
    # 12. Guidelines & Community Rules
    {"path": "/marketplace-guidelines", "changefreq": "monthly", "priority": "0.6"},
    {"path": "/community-guidelines", "changefreq": "monthly", "priority": "0.6"},
    # 13. Legal & Compliance
    {"path": "/terms", "changefreq": "yearly", "priority": "0.5"},
    {"path": "/privacy", "changefreq": "yearly", "priority": "0.5"},
    {"path": "/cookies", "changefreq": "yearly", "priority": "0.5"},
]


def generate_robots_txt(base_url: str = DEFAULT_BASE_URL) -> str:
    """Generate robots.txt content with AI crawler optimizations.

    Configures:
    - Standard crawler permissions (Allow public, Disallow private/auth/admin).
    - Explicit AI search engine crawler directives (GPTBot, ChatGPT-User,
      PerplexityBot, ClaudeBot, Google-Extended).
    - Dynamic Sitemap directive pointing to the canonical sitemap.xml.
    """
    clean_base = base_url.rstrip("/")
    return f"""# Robots.txt for Flama ({clean_base})
# Japanese SRS Flashcard & Language Learning Platform

User-agent: *
Allow: /
Allow: /guide/
Allow: /guide
Allow: /support
Allow: /terms
Allow: /privacy
Allow: /cookies
Allow: /marketplace-guidelines
Allow: /community-guidelines
Allow: /llms.txt
Disallow: /api/
Disallow: /dashboard
Disallow: /statistics
Disallow: /browse
Disallow: /study
Disallow: /installed-decks
Disallow: /sync
Disallow: /import
Disallow: /worksheets
Disallow: /audio/generate
Disallow: /settings/
Disallow: /admin/
Disallow: /wallet
Disallow: /orders
Disallow: /tickets
Disallow: /feedback
Disallow: /creator/

# AI Search Crawlers & GEO Optimization (ChatGPT Search, Perplexity, Claude, Google AI)
User-agent: GPTBot
Allow: /
Allow: /guide/
Allow: /guide
Allow: /support
Allow: /llms.txt
Disallow: /api/
Disallow: /dashboard
Disallow: /statistics
Disallow: /browse
Disallow: /study
Disallow: /admin/
Disallow: /settings/

User-agent: ChatGPT-User
Allow: /
Allow: /guide/
Allow: /guide
Allow: /support
Allow: /llms.txt
Disallow: /api/

User-agent: PerplexityBot
Allow: /
Allow: /guide/
Allow: /guide
Allow: /support
Allow: /llms.txt
Disallow: /api/
Disallow: /dashboard
Disallow: /statistics
Disallow: /browse
Disallow: /study
Disallow: /admin/
Disallow: /settings/

User-agent: ClaudeBot
Allow: /
Allow: /guide/
Allow: /guide
Allow: /support
Allow: /llms.txt
Disallow: /api/
Disallow: /dashboard
Disallow: /statistics
Disallow: /browse
Disallow: /study
Disallow: /admin/
Disallow: /settings/

User-agent: Google-Extended
Allow: /
Allow: /guide/
Allow: /guide
Allow: /support
Allow: /llms.txt
Disallow: /api/
Disallow: /dashboard
Disallow: /statistics
Disallow: /browse
Disallow: /study
Disallow: /admin/
Disallow: /settings/

# Sitemaps
Sitemap: {clean_base}/sitemap.xml
"""


def generate_sitemap_xml(base_url: str = DEFAULT_BASE_URL) -> str:
    """Generate dynamic XML sitemap conforming to sitemaps.org schema.

    Returns valid XML cataloging all 38 public indexable URLs with priority,
    change frequency, and lastmod timestamp.
    """
    clean_base = base_url.rstrip("/")
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

    for entry in PUBLIC_SITEMAP_CATALOG:
        url_elem = ET.SubElement(urlset, "url")

        path = entry["path"]
        loc_str = clean_base if path == "/" else f"{clean_base}{path}"

        loc = ET.SubElement(url_elem, "loc")
        loc.text = loc_str

        lastmod = ET.SubElement(url_elem, "lastmod")
        lastmod.text = today

        changefreq = ET.SubElement(url_elem, "changefreq")
        changefreq.text = str(entry.get("changefreq", "monthly"))

        priority = ET.SubElement(url_elem, "priority")
        priority.text = str(entry.get("priority", "0.8"))

    # Convert ElementTree to pretty XML string
    rough_string = ET.tostring(urlset, encoding="utf-8")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{rough_string.decode("utf-8")}\n'


def generate_llms_txt(base_url: str = DEFAULT_BASE_URL) -> str:
    """Generate llms.txt adhering to the llmstxt.org standard.

    Provides a clean, machine-readable Markdown document summarizing Flama's
    mission, 4 core feature clusters (SRS, Yomitan, Local TTS, Marketplace & JLPT),
    documentation links, and MCP AI Search endpoint.
    """
    clean_base = base_url.rstrip("/")

    return f"""# Flama

> Flama ({clean_base}) là nền tảng học tiếng Nhật và ghi nhớ đa lĩnh vực thông minh thế hệ mới, kết hợp thuật toán lặp lại ngắt quãng (SRS), khai thác từ vựng 1-click qua Yomitan bridge, phát âm chuẩn tự nhiên với Local TTS (VoiceVox & Kokoro), và cộng đồng chia sẻ bộ thẻ Flashcard.

Flama được thiết kế nhằm mang lại trải nghiệm học tập vượt trội thay thế và nâng cấp Anki truyền thống: giao diện hiện đại, đồng bộ đám mây tức thì, hỗ trợ mining từ vựng trực tiếp khi đọc báo/xem phim, phát âm chuẩn ngữ điệu Nhật Bản ngay trên máy không giới hạn chi phí API, và kho dữ liệu luyện thi JLPT từ N5 đến N1.

## Core Features & Concepts

- [Học Từ Vựng SRS (Spaced Repetition)]({clean_base}/guide/study/spaced-repetition): Thuật toán nhắc nhở thông minh tối ưu hóa điểm nhớ và đường cong quên lãng theo 4 mức đánh giá (Again, Hard, Good, Easy).
- [Khai Thác Từ Vựng Yomitan (1-Click Mining)]({clean_base}/guide/integrations/yomitan): Tiện ích Flama Connect tương thích giao thức AnkiConnect, cho phép lưu từ vựng, ngữ cảnh, furigana và âm thanh trực tiếp từ trình duyệt chỉ với 1 cú click.
- [Local TTS Tiếng Nhật (VoiceVox & Kokoro)]({clean_base}/guide/flama-audio): Bộ đồng hành Flama Audio desktop tích hợp VoiceVox và Kokoro TTS, phát âm ngữ điệu chuẩn tự nhiên 100% offline và miễn phí.
- [Kho Marketplace & Lộ Trình JLPT N5-N1]({clean_base}/guide/marketplace/discovery): Kho bộ thẻ cộng đồng được kiểm duyệt, phân cấp bài học theo chuẩn khung tham chiếu JLPT N5 đến N1.
- [Cơ Chế Clone Overlay]({clean_base}/guide/marketplace/overlay-clone): Mô hình cài đặt bộ thẻ độc quyền bảo toàn thay đổi cá nhân của người học khi bộ thẻ gốc được tác giả cập nhật.

## Guides & Documentation

- [3 Phút Bắt Đầu]({clean_base}/guide/getting-started/getting-started): Hướng dẫn nhanh cho người mới bắt đầu học tập trên Flama.
- [Các Khái Niệm Cốt Lõi]({clean_base}/guide/getting-started/core-concepts): Tìm hiểu về Deck (Bộ thẻ), Note (Ghi chú), Card (Thẻ hiển thị) và Mẫu thẻ (Note Types).
- [Quản Lý Note Types & Cloze Deletion]({clean_base}/guide/note-types/concept): Hướng dẫn tùy biến trường dữ liệu và thẻ điền từ vào chỗ trống (Cloze).
- [Hướng Dẫn Flama Audio Companion]({clean_base}/guide/flama-audio): Tải và cài đặt Flama Audio cho Windows để kích hoạt VoiceVox và Kokoro TTS.
- [Đồng Bộ Anki & Nhập File APKG/CSV]({clean_base}/guide/import-sync/anki-connect-sync): Chuyển đổi dữ liệu học tập từ Anki sang Flama dễ dàng mà không mất tiến độ.

## AI Agent & Model Context Protocol (MCP)

- [Flama Connect MCP Endpoint]({clean_base}/api/mcp): Endpoint giao thức Model Context Protocol (MCP JSON-RPC 2.0) hỗ trợ các AI Agent tra cứu từ khóa, danh mục bộ thẻ, và tham chiếu học liệu.
- [OAuth Protected Resource Metadata]({clean_base}/.well-known/oauth-protected-resource): Thông tin xác thực RFC 9728 cho MCP clients.

## Legal & Community

- [Điều Khoản Dịch Vụ]({clean_base}/terms): Quy định sử dụng nền tảng Flama.
- [Chính Sách Bảo Mật]({clean_base}/privacy): Cam kết bảo vệ dữ liệu cá nhân của người dùng.
- [Nguyên Tắc Cộng Đồng]({clean_base}/community-guidelines): Quy chuẩn đóng góp và chia sẻ nội dung học tập.
"""
