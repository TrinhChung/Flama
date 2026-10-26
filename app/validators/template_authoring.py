"""Authoring failures retain diagnostics for MCP while preserving service errors."""

from app.validators.flashcard_input import RequestValidationError


class TemplateAuthoringValidationError(RequestValidationError):
    def __init__(self, message, *, diagnostics, **kwargs):
        super().__init__(message, **kwargs)
        self.diagnostics = diagnostics[:100]
