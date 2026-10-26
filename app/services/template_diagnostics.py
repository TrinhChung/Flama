"""Bounded authoring diagnostics and original-source coordinates."""


def diagnostic(code, message, *, severity="warning", stage="template", source_part="front_html", hint="",
               line=None, column=None, suggestions=None):
    return dict(code=code, severity=severity, stage=stage, source_part=source_part,
                message=str(message)[:1000], hint=str(hint)[:1000], line=line, column=column,
                suggestions=list(suggestions or [])[:5])


def source_position(source, offset):
    """One-based original-source coordinates, in Unicode characters."""
    offset = max(0, min(len(source), offset))
    prefix = source[:offset].replace("\r\n", "\n").replace("\r", "\n")
    return {"line": prefix.count("\n") + 1, "column": len(prefix.rsplit("\n", 1)[-1]) + 1}
