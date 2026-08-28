"""Worksheet generator services package."""

from app.services.worksheets.template_catalog import (
    TEMPLATE_CATALOG,
    WorksheetTemplate,
    get_template,
    list_templates,
)
from app.services.worksheets.worksheet_service import (
    WorksheetServiceError,
    generate_worksheet_preview,
    get_deck_worksheet_meta,
    render_printable_html,
)

__all__ = [
    "TEMPLATE_CATALOG",
    "WorksheetServiceError",
    "WorksheetTemplate",
    "generate_worksheet_preview",
    "get_deck_worksheet_meta",
    "get_template",
    "list_templates",
    "render_printable_html",
]
