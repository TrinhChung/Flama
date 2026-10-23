"""Upgrade scalar array placeholders in reviewed templates, preserving their DOM/CSS.

Formatting belongs to these self-contained templates, never the renderers.
Legacy one-item-per-line strings still render BR nodes; native items retain
punctuation, empty positions, repetition and embedded newlines as one item.
"""
import html
import re

MARKER = 'flama-native-arrays.v1'
INITIALIZER = r'''<script>
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
  document.querySelectorAll('[data-native-array-value]').forEach(function (source) {
    var values = [];
    Array.from(source.children).forEach(function (item) {
      // Only legacy scalar strings acquire BR nodes from the renderer.
      var lines = [''];
      item.childNodes.forEach(function (node) {
        if (node.nodeName === 'BR') lines.push('');
        else lines[lines.length - 1] += node.textContent || '';
      });
      values.push.apply(values, lines);
    });
    source.parentNode.__flamaArrayItems = values;
    var content = document.createDocumentFragment();
    values.forEach(function (value, index) {
      if (index) content.appendChild(document.createElement('br'));
      content.appendChild(document.createTextNode(value));
    });
    source.replaceWith(content);
  });
})();
</script>
'''

TOKEN = re.compile(r'\{\{\{\s*([^{}]+?)\s*\}\}\}|\{\{\s*([#^/&!]?)\s*([^{}]+?)\s*\}\}')
SCRIPT = re.compile(r'<script\b[^>]*>[\s\S]*?</script\s*>', re.I)


def modernize(source: str, array_names: set[str]) -> str:
    """Only upgrade reviewed scalar templates; existing authored loops stay intact."""
    if MARKER in source or not array_names:
        return source
    protected = [(match.start(), match.end()) for match in SCRIPT.finditer(source)]
    # A genuine item loop needs no conversion. Rewriting it as a guard loses its
    # item scope, so fail closed for review instead of guessing the author's intent.
    for name in array_names:
        if re.search(r'\{\{\s*\^\s*' + re.escape(name) + r'\s*\}\}', source):
            raise ValueError(f'Inverted array section requires review: {name}')
        for match in re.finditer(r'\{\{\s*#\s*' + re.escape(name) + r'\s*\}\}([\s\S]*?)\{\{\s*/\s*' + re.escape(name) + r'\s*\}\}', source):
            if re.search(r'\{\{\{?\s*[&]?\s*\.\s*\}\}\}?', match.group(1)):
                raise ValueError(f'Already authored item loop requires review: {name}')
    changed = False
    def replace(match):
        nonlocal changed
        if any(start <= match.start() < end for start, end in protected):
            return match.group(0)
        triple, kind, name = match.groups()
        name = (triple or name).strip()
        if name not in array_names or kind in ('^', '!'):
            return match.group(0)
        # Inserting HTML into an attribute would alter template behavior.
        if source.rfind('<', 0, match.start()) > source.rfind('>', 0, match.start()):
            raise ValueError(f'Array attribute placeholder requires review: {name}')
        changed = True
        if kind == '#':
            return ('<span data-native-array-guard="' + html.escape(name, quote=True) + '" style="display:contents">'
                    '{{#' + name + '}}<span data-native-array-presence hidden></span>{{/' + name + '}}')
        if kind == '/':
            return '</span>'
        return ('<span data-native-array-value>{{#' + name + '}}'
                '<span data-native-array-item>{{.}}</span>{{/' + name + '}}</span>')
    result = TOKEN.sub(replace, source)
    if not changed:
        return source
    # Existing parser entry points use the exact stored item boundaries before
    # falling back to their legacy BR parser. No punctuation is re-split.
    result = re.sub(r'(function\s+(?:readArray|readAnswers|extractList)\s*\(\s*(\w+)\s*\)\s*\{)',
        lambda m: m[1] + '\n    if (' + m[2] + ' && Array.isArray(' + m[2] + '.__flamaArrayItems)) return ' + m[2] + '.__flamaArrayItems;', result)
    # Keep the old prose formatter, while native list punctuation remains literal.
    result = re.sub(r'(forEach\(function\s*\(\s*(el|element)\s*\)\s*\{)',
        lambda m: m[1] + '\n    if (Array.isArray(' + m[2] + '.__flamaArrayItems)) return;', result)
    first_script = re.search(r'<script\b', result, re.I)
    if first_script:
        # Keep document.currentScript.previousElementSibling pointing at the
        # card, as the original interaction/audio scripts expect.
        at = result.index('>', first_script.start()) + 1
        return result[:at] + '\n' + INITIALIZER[len('<script>'):INITIALIZER.rindex('</script>')] + result[at:]
    return result + INITIALIZER


# v2 (2026-10-21): fields converted from text-like types keep their item markup,
# templates already on v1 can take more fields, and a lone legacy string that
# still uses the template's own prose delimiter is left to that formatter, so
# installed clones pinned to an older release render exactly as before.
MARKER_V2 = 'flama-native-arrays.v2'
_V1_BODY = INITIALIZER[len('<script>'):INITIALIZER.rindex('</script>')]
INITIALIZER_V2 = r'''<script>
// flama-native-arrays.v2: template-owned formatting, before its interaction scripts.
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
  document.querySelectorAll('[data-native-array-value]').forEach(function (source) {
    // Items keep their markup. Only legacy scalar strings acquire BR nodes
    // from the renderer; those still separate lines.
    var items = Array.from(source.children);
    var lines = [];
    items.forEach(function (item) {
      lines.push([]);
      Array.from(item.childNodes).forEach(function (node) {
        if (node.nodeName === 'BR') lines.push([]);
        else lines[lines.length - 1].push(node);
      });
    });
    var values = lines.map(function (nodes) {
      return nodes.map(function (node) { return node.textContent || ''; }).join('');
    });
    var legacy = source.getAttribute('data-native-array-legacy');
    if (!(legacy && items.length === 1 && values.join('').indexOf(legacy) !== -1)) {
      source.parentNode.__flamaArrayItems = values;
      // An enclosing prose auto-split block must not re-split native items.
      var prose = source.parentNode.closest && source.parentNode.closest('[auto-split]');
      if (prose && !prose.__flamaArrayItems) prose.__flamaArrayItems = values;
    }
    var content = document.createDocumentFragment();
    lines.forEach(function (nodes, index) {
      if (index) content.appendChild(document.createElement('br'));
      nodes.forEach(function (node) { content.appendChild(node); });
    });
    source.replaceWith(content);
  });
})();
</script>
'''
_V2_BODY = INITIALIZER_V2[len('<script>'):INITIALIZER_V2.rindex('</script>')]
_READER_RE = re.compile(r'(function\s+(?:readArray|readAnswers|extractList)\s*\(\s*(\w+)\s*\)\s*\{)(\s*if \(\2 && Array\.isArray\(\2\.__flamaArrayItems\)\))?')
_PROSE_LOOP_RE = re.compile(r'(forEach\(function\s*\(\s*(el|element)\s*\)\s*\{)(\s*if \(Array\.isArray\(\2\.__flamaArrayItems\)\))?')


def modernize_v2(source: str, arrays: dict[str, str | None]) -> str:
    """Upgrade ``arrays`` (input name -> legacy prose delimiter or None) in place.

    ``{{{name}}}``/``{{&name}}`` items stay raw HTML (the renderer sanitizes the
    rendered card); ``{{name}}`` items stay escaped. Fails closed like v1.
    """
    if not arrays:
        return source
    names = set(arrays)
    protected = [(match.start(), match.end()) for match in SCRIPT.finditer(source)]
    for name in names:
        if re.search(r'\{\{\s*\^\s*' + re.escape(name) + r'\s*\}\}', source):
            raise ValueError(f'Inverted array section requires review: {name}')
        for match in re.finditer(r'\{\{\s*#\s*' + re.escape(name) + r'\s*\}\}([\s\S]*?)\{\{\s*/\s*' + re.escape(name) + r'\s*\}\}', source):
            if re.search(r'\{\{\{?\s*[&]?\s*\.\s*\}\}\}?', match.group(1)):
                raise ValueError(f'Already authored item loop requires review: {name}')
    changed = False

    def replace(match):
        nonlocal changed
        if any(start <= match.start() < end for start, end in protected):
            return match.group(0)
        triple, kind, name = match.groups()
        name = (triple or name).strip()
        if name not in names or kind in ('^', '!'):
            return match.group(0)
        if source.rfind('<', 0, match.start()) > source.rfind('>', 0, match.start()):
            raise ValueError(f'Array attribute placeholder requires review: {name}')
        changed = True
        if kind == '#':
            return ('<span data-native-array-guard="' + html.escape(name, quote=True) + '" style="display:contents">'
                    '{{#' + name + '}}<span data-native-array-presence hidden></span>{{/' + name + '}}')
        if kind == '/':
            return '</span>'
        item = '{{{.}}}' if triple is not None or kind == '&' else '{{.}}'
        legacy = arrays[name]
        holder = '<span data-native-array-value' + (
            ' data-native-array-legacy="' + html.escape(legacy, quote=True) + '"' if legacy else '') + '>'
        return holder + '{{#' + name + '}}<span data-native-array-item>' + item + '</span>{{/' + name + '}}</span>'

    result = TOKEN.sub(replace, source)
    if not changed:
        return source
    result = _READER_RE.sub(lambda m: m[0] if m[3] else m[1] + '\n    if (' + m[2] + ' && Array.isArray(' + m[2] + '.__flamaArrayItems)) return ' + m[2] + '.__flamaArrayItems;', result)
    result = _PROSE_LOOP_RE.sub(lambda m: m[0] if m[3] else m[1] + '\n    if (Array.isArray(' + m[2] + '.__flamaArrayItems)) return;', result)
    if MARKER_V2 in result:
        return result
    if MARKER in result:
        if result.count(_V1_BODY) != 1:
            raise ValueError('Customized v1 array initializer requires review')
        return result.replace(_V1_BODY, _V2_BODY)
    first_script = re.search(r'<script\b', result, re.I)
    if first_script:
        at = result.index('>', first_script.start()) + 1
        return result[:at] + '\n' + _V2_BODY + result[at:]
    return result + INITIALIZER_V2
