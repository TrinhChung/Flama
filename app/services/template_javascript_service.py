"""Parse template scripts without evaluating them or starting a JS runtime."""

import re

from app.services.flashcard_renderer import _INLINE_SCRIPT_RE, _sanitize_inline_script
from app.services.template_diagnostics import diagnostic, source_position


def javascript_diagnostics(source, part):
    result = []
    for index, match in enumerate(_INLINE_SCRIPT_RE.finditer(source)):
        if index >= 100:
            result.append(diagnostic("JAVASCRIPT_LIMIT_EXCEEDED", "At most 100 script blocks can be checked per side.",
                severity="error", stage="javascript_syntax", source_part=part,
                hint="Reduce the number of inline script blocks.", **source_position(source, match.start())))
            break
        attrs, body = match.group(1), match.group(2)
        if not _sanitize_inline_script(attrs, body):
            result.append(diagnostic("SCRIPT_NOT_EXECUTED", "This script is removed by the Study renderer.",
                source_part=part, hint="Use inline JavaScript with a supported script type; external script sources are unavailable.",
                **source_position(source, match.start())))
            continue
        try:
            import esprima
            parser = esprima.parseModule if re.search(r'\btype\s*=\s*([\"\'])module\1', attrs, re.I) else esprima.parseScript
            # No eval, exec, subprocess, dynamic imports or AST execution.
            parser(body, {"tolerant": False, "jsx": False, "positionEncoding": "scalar"})
        except ImportError:
            result.append(diagnostic("JAVASCRIPT_VALIDATOR_UNAVAILABLE", "JavaScript syntax could not be checked.",
                severity="error", stage="javascript_syntax", source_part=part,
                hint="Retry after the syntax validator is available."))
            break
        except RecursionError:
            result.append(diagnostic("JAVASCRIPT_LIMIT_EXCEEDED", "JavaScript is too deeply nested to validate.",
                severity="error", stage="javascript_syntax", source_part=part,
                hint="Split deeply nested expressions into smaller functions.", **source_position(source, match.start(2))))
        except esprima.Error as exc:
            offset = match.start(2) + max(0, min(len(body), exc.index or 0))
            message = re.sub(r"^Line \d+:\s*", "", str(exc))
            result.append(diagnostic("JAVASCRIPT_SYNTAX_ERROR", message,
                severity="error", stage="javascript_syntax", source_part=part,
                hint="Fix this script's syntax and preview again. Syntax checking does not execute the script.",
                **source_position(source, offset)))
    return result
