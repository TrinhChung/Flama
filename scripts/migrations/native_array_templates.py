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
