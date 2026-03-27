(function () {
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function cssEscape(value) {
    const raw = String(value == null ? "" : value);
    if (window.CSS && typeof window.CSS.escape === "function") {
      return window.CSS.escape(raw);
    }
    return raw.replace(/["\\]/g, "\\$&");
  }

  function normalizeLinebreaks(value) {
    return String(value == null ? "" : value).replace(/\r\n?/g, "\n");
  }

  function isImageFile(file) {
    return Boolean(file && String(file.type || "").toLowerCase().startsWith("image/"));
  }

  function normalizeAltText(raw) {
    const normalized = String(raw || "image")
      .replace(/[\[\]\(\)]/g, "")
      .trim()
      .slice(0, 80);
    return normalized || "image";
  }

  function sanitizeHref(rawHref) {
    const value = String(rawHref || "").trim();
    if (!value) {
      return "";
    }
    if (value.startsWith("/media/proxy/") || value.startsWith("https://") || value.startsWith("http://")) {
      return value;
    }
    return `https://${value.replace(/^\/+/, "")}`;
  }

  function hasComplexMarkdown(markdown) {
    const source = normalizeLinebreaks(markdown);
    if (!source.trim()) {
      return false;
    }
    return [
      /^\s{2,}[-*+]\s+/m,
      /^\s*\|.+\|\s*$/m,
      /^\s*[-*]\s+\[[ xX]\]\s+/m,
      /^\s{4,}\S/m,
      /<[/a-z][^>]*>/i,
      /^\[\^.+\]:/m,
    ].some(function (pattern) {
      return pattern.test(source);
    });
  }

  function buildInlineHtml(text) {
    const placeholders = [];
    let html = escapeHtml(text);

    html = html.replace(/`([^`\n]+)`/g, function (_match, code) {
      const token = `%%FCMDCODE${placeholders.length}%%`;
      placeholders.push(`<code>${escapeHtml(code)}</code>`);
      return token;
    });

    html = html.replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, function (_match, alt, href) {
      const safeHref = sanitizeHref(href);
      if (!safeHref) {
        return escapeHtml(_match);
      }
      return `<img src="${escapeHtml(safeHref)}" alt="${escapeHtml(String(alt || "").trim().slice(0, 160) || "image")}">`;
    });

    html = html.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, function (_match, label, href) {
      const safeHref = sanitizeHref(href);
      if (!safeHref) {
        return escapeHtml(_match);
      }
      return `<a href="${escapeHtml(safeHref)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
    });

    html = html.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/__([^_\n]+)__/g, "<strong>$1</strong>");
    html = html.replace(/~~([^~\n]+)~~/g, "<s>$1</s>");
    html = html.replace(/(^|[^\*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
    html = html.replace(/(^|[^_])_([^_\n]+)_(?!_)/g, "$1<em>$2</em>");

    placeholders.forEach(function (value, index) {
      html = html.replaceAll(`%%FCMDCODE${index}%%`, value);
    });

    return html;
  }

  function parseBlocks(markdown) {
    const lines = normalizeLinebreaks(markdown).split("\n");
    const blocks = [];
    let index = 0;

    function nextNonEmpty(start) {
      for (let cursor = start; cursor < lines.length; cursor += 1) {
        if (String(lines[cursor] || "").trim()) {
          return cursor;
        }
      }
      return lines.length;
    }

    while (index < lines.length) {
      const line = lines[index];
      if (!String(line || "").trim()) {
        index += 1;
        continue;
      }

      if (/^```/.test(line)) {
        const codeLines = [];
        index += 1;
        while (index < lines.length && !/^```/.test(lines[index])) {
          codeLines.push(lines[index]);
          index += 1;
        }
        if (index < lines.length) {
          index += 1;
        }
        blocks.push({ type: "code", text: codeLines.join("\n") });
        continue;
      }

      const heading = line.match(/^(#{1,3})\s+(.*)$/);
      if (heading) {
        blocks.push({ type: `h${heading[1].length}`, text: heading[2] });
        index += 1;
        continue;
      }

      if (/^>\s?/.test(line)) {
        const quoteLines = [];
        while (index < lines.length && /^>\s?/.test(lines[index])) {
          quoteLines.push(lines[index].replace(/^>\s?/, ""));
          index += 1;
        }
        blocks.push({ type: "blockquote", text: quoteLines.join("\n") });
        continue;
      }

      if (/^[-*+]\s+/.test(line)) {
        const items = [];
        while (index < lines.length) {
          const current = lines[index].match(/^[-*+]\s+(.*)$/);
          if (!current) {
            break;
          }
          items.push(current[1]);
          index += 1;
        }
        blocks.push({ type: "ul", items: items });
        continue;
      }

      if (/^\d+\.\s+/.test(line)) {
        const items = [];
        while (index < lines.length) {
          const current = lines[index].match(/^\d+\.\s+(.*)$/);
          if (!current) {
            break;
          }
          items.push(current[1]);
          index += 1;
        }
        blocks.push({ type: "ol", items: items });
        continue;
      }

      const paragraphLines = [line];
      index += 1;
      while (index < lines.length) {
        const current = lines[index];
        if (!String(current || "").trim()) {
          index = nextNonEmpty(index);
          break;
        }
        if (/^(#{1,3})\s+/.test(current) || /^>\s?/.test(current) || /^[-*+]\s+/.test(current) || /^\d+\.\s+/.test(current) || /^```/.test(current)) {
          break;
        }
        paragraphLines.push(current);
        index += 1;
      }
      blocks.push({ type: "p", text: paragraphLines.join("\n") });
    }

    return blocks;
  }

  function markdownToHtml(markdown) {
    const blocks = parseBlocks(markdown);
    if (!blocks.length) {
      return "";
    }
    return blocks
      .map(function (block) {
        if (block.type === "code") {
          return `<pre><code>${escapeHtml(block.text || "")}</code></pre>`;
        }
        if (block.type === "blockquote") {
          return `<blockquote><p>${buildInlineHtml(String(block.text || "").replace(/\n/g, "<br>"))}</p></blockquote>`;
        }
        if (block.type === "ul" || block.type === "ol") {
          const items = (block.items || []).map(function (item) {
            return `<li>${buildInlineHtml(item)}</li>`;
          });
          return `<${block.type}>${items.join("")}</${block.type}>`;
        }
        if (block.type === "h1" || block.type === "h2" || block.type === "h3") {
          return `<${block.type}>${buildInlineHtml(block.text || "")}</${block.type}>`;
        }
        return `<p>${buildInlineHtml(String(block.text || "").replace(/\n/g, "<br>"))}</p>`;
      })
      .join("");
  }

  function unwrapNode(node) {
    if (!(node instanceof HTMLElement) || !node.parentNode) {
      return;
    }
    while (node.firstChild) {
      node.parentNode.insertBefore(node.firstChild, node);
    }
    node.parentNode.removeChild(node);
  }

  function sanitizeVisualRoot(root) {
    if (!(root instanceof HTMLElement)) {
      return;
    }

    root.querySelectorAll("script, style, iframe, object, embed").forEach(function (node) {
      node.remove();
    });

    root.querySelectorAll("*").forEach(function (node) {
      if (!(node instanceof HTMLElement)) {
        return;
      }

      const tag = node.tagName.toLowerCase();
      if (tag === "b") {
        const strong = document.createElement("strong");
        strong.innerHTML = node.innerHTML;
        node.replaceWith(strong);
        return;
      }
      if (tag === "i") {
        const em = document.createElement("em");
        em.innerHTML = node.innerHTML;
        node.replaceWith(em);
        return;
      }
      if (tag === "strike" || tag === "del") {
        const s = document.createElement("s");
        s.innerHTML = node.innerHTML;
        node.replaceWith(s);
        return;
      }
      if (tag === "font") {
        unwrapNode(node);
        return;
      }

      Array.from(node.attributes).forEach(function (attr) {
        const name = String(attr.name || "").toLowerCase();
        if (name === "href") {
          node.setAttribute("href", sanitizeHref(attr.value));
          return;
        }
        if (name === "src") {
          if (!String(attr.value || "").startsWith("/media/proxy/")) {
            node.removeAttribute(name);
          }
          return;
        }
        if (name === "alt") {
          return;
        }
        node.removeAttribute(attr.name);
      });

      if (!["p", "br", "strong", "em", "s", "ul", "ol", "li", "blockquote", "pre", "code", "a", "img", "h1", "h2", "h3"].includes(tag)) {
        if (tag === "div") {
          const p = document.createElement("p");
          p.innerHTML = node.innerHTML;
          node.replaceWith(p);
        } else {
          unwrapNode(node);
        }
      }
    });

    Array.from(root.childNodes).forEach(function (node) {
      if (node.nodeType === Node.TEXT_NODE && String(node.textContent || "").trim()) {
        const p = document.createElement("p");
        p.textContent = node.textContent || "";
        root.replaceChild(p, node);
      }
    });
  }

  function textToMarkdown(text) {
    return normalizeLinebreaks(text)
      .replace(/\u00a0/g, " ")
      .replace(/[ \t]+\n/g, "\n");
  }

  function childrenToMarkdown(node, context) {
    return Array.from(node.childNodes || [])
      .map(function (child) {
        return nodeToMarkdown(child, context);
      })
      .join("");
  }

  function blockToMarkdown(node, context) {
    const inner = childrenToMarkdown(node, context).trim();
    if (!inner) {
      return "";
    }
    return `${inner}\n\n`;
  }

  function listToMarkdown(node, ordered) {
    const items = Array.from(node.children || [])
      .filter(function (child) {
        return child.tagName && child.tagName.toLowerCase() === "li";
      })
      .map(function (item, index) {
        const marker = ordered ? `${index + 1}. ` : "- ";
        const content = childrenToMarkdown(item, { inline: true }).trim().replace(/\n+/g, "\n");
        return `${marker}${content}`;
      })
      .join("\n");
    return items ? `${items}\n\n` : "";
  }

  function nodeToMarkdown(node, context) {
    if (!node) {
      return "";
    }
    if (node.nodeType === Node.TEXT_NODE) {
      return textToMarkdown(node.textContent || "");
    }
    if (!(node instanceof HTMLElement)) {
      return "";
    }

    const tag = node.tagName.toLowerCase();
    if (tag === "br") {
      return "\n";
    }
    if (tag === "strong" || tag === "b") {
      return `**${childrenToMarkdown(node, { inline: true })}**`;
    }
    if (tag === "em" || tag === "i") {
      return `*${childrenToMarkdown(node, { inline: true })}*`;
    }
    if (tag === "s" || tag === "strike" || tag === "del") {
      return `~~${childrenToMarkdown(node, { inline: true })}~~`;
    }
    if (tag === "code" && (!node.parentElement || node.parentElement.tagName.toLowerCase() !== "pre")) {
      return `\`${childrenToMarkdown(node, { inline: true }).replace(/\n+/g, " ").trim()}\``;
    }
    if (tag === "a") {
      const href = sanitizeHref(node.getAttribute("href") || "");
      const label = childrenToMarkdown(node, { inline: true }).trim() || href;
      return href ? `[${label}](${href})` : label;
    }
    if (tag === "img") {
      const src = String(node.getAttribute("src") || "").trim();
      if (!src) {
        return "";
      }
      return `![${normalizeAltText(node.getAttribute("alt") || "image")}](${src})`;
    }
    if (tag === "h1") {
      return `# ${childrenToMarkdown(node, { inline: true }).trim()}\n\n`;
    }
    if (tag === "h2") {
      return `## ${childrenToMarkdown(node, { inline: true }).trim()}\n\n`;
    }
    if (tag === "h3") {
      return `### ${childrenToMarkdown(node, { inline: true }).trim()}\n\n`;
    }
    if (tag === "p" || tag === "div") {
      return blockToMarkdown(node, context);
    }
    if (tag === "ul") {
      return listToMarkdown(node, false);
    }
    if (tag === "ol") {
      return listToMarkdown(node, true);
    }
    if (tag === "blockquote") {
      const raw = childrenToMarkdown(node, { inline: false }).trim();
      if (!raw) {
        return "";
      }
      return raw
        .split("\n")
        .map(function (line) {
          return line ? `> ${line}` : ">";
        })
        .join("\n")
        .concat("\n\n");
    }
    if (tag === "pre") {
      const code = node.textContent || "";
      return `\`\`\`\n${normalizeLinebreaks(code).replace(/\n+$/, "")}\n\`\`\`\n\n`;
    }
    return childrenToMarkdown(node, context);
  }

  function htmlToMarkdown(root) {
    sanitizeVisualRoot(root);
    return Array.from(root.childNodes || [])
      .map(function (node) {
        return nodeToMarkdown(node, { inline: false });
      })
      .join("")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function insertPlainTextAtCursor(text) {
    const selection = window.getSelection();
    if (!selection || !selection.rangeCount) {
      return;
    }
    selection.deleteFromDocument();
    const lines = normalizeLinebreaks(text).split("\n");
    const fragment = document.createDocumentFragment();
    lines.forEach(function (line, index) {
      if (index > 0) {
        fragment.appendChild(document.createElement("br"));
      }
      fragment.appendChild(document.createTextNode(line));
    });
    const range = selection.getRangeAt(0);
    range.insertNode(fragment);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
  }

  function insertNodeAtSelection(root, node) {
    if (!(root instanceof HTMLElement) || !(node instanceof Node)) {
      return false;
    }

    const selection = window.getSelection();
    if (!selection || !selection.rangeCount) {
      root.appendChild(node);
      return true;
    }

    let range = selection.getRangeAt(0);
    const anchorNode = range.commonAncestorContainer;
    const isInsideRoot = anchorNode === root || (anchorNode instanceof Node && root.contains(anchorNode));
    if (!isInsideRoot) {
      root.appendChild(node);
      return true;
    }

    range.deleteContents();
    range.insertNode(node);
    range = document.createRange();
    range.setStartAfter(node);
    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);
    return true;
  }

  function wrapSelectionWithTextareaSyntax(textarea, prefix, suffix, fallbackText) {
    const start = Number(textarea.selectionStart ?? 0);
    const end = Number(textarea.selectionEnd ?? start);
    const current = String(textarea.value || "");
    const selected = current.slice(start, end) || fallbackText || "";
    const nextValue = `${current.slice(0, start)}${prefix}${selected}${suffix}${current.slice(end)}`;
    textarea.value = nextValue;
    const nextStart = start + prefix.length;
    const nextEnd = nextStart + selected.length;
    textarea.focus();
    textarea.setSelectionRange(nextStart, nextEnd);
  }

  function toggleLinePrefix(textarea, prefix, ordered) {
    const current = String(textarea.value || "");
    const start = Number(textarea.selectionStart ?? 0);
    const end = Number(textarea.selectionEnd ?? start);
    const before = current.slice(0, start);
    const selected = current.slice(start, end);
    const after = current.slice(end);
    const lines = (selected || current.slice(start, end || current.length)).split("\n");
    const prefixed = lines.map(function (line, index) {
      const marker = ordered ? `${index + 1}. ` : prefix;
      if (ordered && /^\d+\.\s+/.test(line)) {
        return line.replace(/^\d+\.\s+/, "");
      }
      if (!ordered && line.startsWith(prefix)) {
        return line.slice(prefix.length);
      }
      return `${marker}${line}`;
    });
    const replacement = prefixed.join("\n");
    textarea.value = `${before}${replacement}${after}`;
    textarea.focus();
    textarea.setSelectionRange(start, start + replacement.length);
  }

  function applyHeadingToTextarea(textarea, level) {
    const current = String(textarea.value || "");
    const start = Number(textarea.selectionStart ?? 0);
    const end = Number(textarea.selectionEnd ?? start);
    const before = current.slice(0, start);
    const selected = current.slice(start, end) || "Tiêu đề";
    const clean = selected.replace(/^#{1,3}\s+/, "");
    const prefix = level === "paragraph" ? "" : `${"#".repeat(Number(level) || 1)} `;
    const replacement = clean
      .split("\n")
      .map(function (line) {
        return prefix ? `${prefix}${line.replace(/^#{1,3}\s+/, "")}` : line.replace(/^#{1,3}\s+/, "");
      })
      .join("\n");
    textarea.value = `${before}${replacement}${current.slice(end)}`;
    textarea.focus();
    textarea.setSelectionRange(start, start + replacement.length);
  }

  function promptLinkValue(existing) {
    const candidate = window.prompt("Nhập link", existing || "https://");
    return candidate == null ? null : sanitizeHref(candidate);
  }

  function createToolbarHost(toolbarHost) {
    const toolbar = document.createElement("div");
    toolbar.className = "flama-md-toolbar is-disabled";
    toolbar.innerHTML = `
      <div class="flama-md-toolbar__meta">
        <span class="flama-md-toolbar__title">Trình soạn markdown</span>
        <span class="flama-md-toolbar__target">Chọn field</span>
        <span class="flama-md-toolbar__mode">Trực quan</span>
      </div>
      <div class="flama-md-toolbar__group">
        <select class="flama-md-toolbar__select" data-md-action="heading" aria-label="Kiểu tiêu đề">
          <option value="paragraph">Văn bản</option>
          <option value="1">Tiêu đề 1</option>
          <option value="2">Tiêu đề 2</option>
          <option value="3">Tiêu đề 3</option>
        </select>
      </div>
      <div class="flama-md-toolbar__group">
        <button type="button" class="flama-md-toolbar__btn" data-md-action="bold" title="In đậm"><i class="bi bi-type-bold"></i></button>
        <button type="button" class="flama-md-toolbar__btn" data-md-action="italic" title="In nghiêng"><i class="bi bi-type-italic"></i></button>
        <button type="button" class="flama-md-toolbar__btn" data-md-action="strike" title="Gạch ngang"><i class="bi bi-type-strikethrough"></i></button>
      </div>
      <div class="flama-md-toolbar__group">
        <button type="button" class="flama-md-toolbar__btn" data-md-action="bullet" title="Danh sách chấm đầu dòng"><i class="bi bi-list-ul"></i></button>
        <button type="button" class="flama-md-toolbar__btn" data-md-action="ordered" title="Danh sách đánh số"><i class="bi bi-list-ol"></i></button>
        <button type="button" class="flama-md-toolbar__btn" data-md-action="quote" title="Trích dẫn"><i class="bi bi-blockquote-left"></i></button>
      </div>
      <div class="flama-md-toolbar__group">
        <button type="button" class="flama-md-toolbar__btn" data-md-action="code" title="Mã inline"><i class="bi bi-code"></i></button>
        <button type="button" class="flama-md-toolbar__btn" data-md-action="codeblock" title="Khối mã"><i class="bi bi-braces-asterisk"></i></button>
        <button type="button" class="flama-md-toolbar__btn" data-md-action="link" title="Liên kết"><i class="bi bi-link-45deg"></i></button>
      </div>
      <div class="flama-md-toolbar__group">
        <button type="button" class="flama-md-toolbar__btn" data-md-action="undo" title="Hoàn tác"><i class="bi bi-arrow-counterclockwise"></i></button>
        <button type="button" class="flama-md-toolbar__btn" data-md-action="redo" title="Làm lại"><i class="bi bi-arrow-clockwise"></i></button>
      </div>
      <div class="flama-md-toolbar__group">
        <button type="button" class="flama-md-toolbar__mode-toggle" data-md-action="toggle-mode">Chế độ markdown</button>
      </div>
    `;
    toolbarHost.replaceChildren(toolbar);
    return toolbar;
  }

  function MarkdownEditorManager(options) {
    this.toolbarHost = options.toolbarHost;
    this.toolbar = createToolbarHost(options.toolbarHost);
    this.activeEditor = null;
    this.editors = new Map();
    this.boundHandleToolbarClick = this.handleToolbarClick.bind(this);
    this.boundHandleToolbarChange = this.handleToolbarChange.bind(this);
    this.toolbar.addEventListener("click", this.boundHandleToolbarClick);
    this.toolbar.addEventListener("change", this.boundHandleToolbarChange);
    this.syncToolbarState();
  }

  function createToolbarHost(toolbarHost) {
    const toolbar = document.createElement("div");
    toolbar.className = "flama-md-toolbar is-disabled";
    toolbar.innerHTML = `
      <div class="flama-md-toolbar__top">
        <div class="flama-md-toolbar__meta">
          <span class="flama-md-toolbar__title">Markdown</span>
          <span class="flama-md-toolbar__target">Chọn field</span>
          <span class="flama-md-toolbar__mode">Trực quan</span>
        </div>
        <button type="button" class="flama-md-toolbar__mode-toggle" data-md-action="toggle-mode">Chế độ markdown</button>
      </div>
      <div class="flama-md-toolbar__controls">
        <div class="flama-md-toolbar__group">
          <select class="flama-md-toolbar__select" data-md-action="heading" aria-label="Kiểu tiêu đề">
            <option value="paragraph">Văn bản</option>
            <option value="1">Tiêu đề 1</option>
            <option value="2">Tiêu đề 2</option>
            <option value="3">Tiêu đề 3</option>
          </select>
        </div>
        <div class="flama-md-toolbar__group">
          <button type="button" class="flama-md-toolbar__btn" data-md-action="bold" title="In đậm"><i class="bi bi-type-bold"></i></button>
          <button type="button" class="flama-md-toolbar__btn" data-md-action="italic" title="In nghiêng"><i class="bi bi-type-italic"></i></button>
          <button type="button" class="flama-md-toolbar__btn" data-md-action="strike" title="Gạch ngang"><i class="bi bi-type-strikethrough"></i></button>
        </div>
        <div class="flama-md-toolbar__group">
          <button type="button" class="flama-md-toolbar__btn" data-md-action="bullet" title="Danh sách chấm đầu dòng"><i class="bi bi-list-ul"></i></button>
          <button type="button" class="flama-md-toolbar__btn" data-md-action="ordered" title="Danh sách đánh số"><i class="bi bi-list-ol"></i></button>
          <button type="button" class="flama-md-toolbar__btn" data-md-action="quote" title="Trích dẫn"><i class="bi bi-blockquote-left"></i></button>
        </div>
        <div class="flama-md-toolbar__group">
          <button type="button" class="flama-md-toolbar__btn" data-md-action="code" title="Mã inline"><i class="bi bi-code"></i></button>
          <button type="button" class="flama-md-toolbar__btn" data-md-action="codeblock" title="Khối mã"><i class="bi bi-braces-asterisk"></i></button>
          <button type="button" class="flama-md-toolbar__btn" data-md-action="link" title="Liên kết"><i class="bi bi-link-45deg"></i></button>
        </div>
        <div class="flama-md-toolbar__group">
          <button type="button" class="flama-md-toolbar__btn" data-md-action="undo" title="Hoàn tác"><i class="bi bi-arrow-counterclockwise"></i></button>
          <button type="button" class="flama-md-toolbar__btn" data-md-action="redo" title="Làm lại"><i class="bi bi-arrow-clockwise"></i></button>
        </div>
      </div>
    `;
    toolbarHost.replaceChildren(toolbar);
    return toolbar;
  }

  MarkdownEditorManager.prototype.syncToolbarState = function () {
    const disabled = !this.activeEditor;
    this.toolbar.classList.toggle("is-disabled", disabled);
    this.toolbar.querySelectorAll("[data-md-action]").forEach(function (control) {
      if (!(control instanceof HTMLButtonElement) && !(control instanceof HTMLSelectElement)) {
        return;
      }
      control.disabled = disabled;
    });

    const targetEl = this.toolbar.querySelector(".flama-md-toolbar__target");
    const modeEl = this.toolbar.querySelector(".flama-md-toolbar__mode");
    const toggleEl = this.toolbar.querySelector('[data-md-action="toggle-mode"]');
    const headingEl = this.toolbar.querySelector('[data-md-action="heading"]');
    if (targetEl) {
      targetEl.textContent = disabled ? "Chọn field" : this.activeEditor.label;
    }
    if (modeEl) {
      modeEl.textContent = disabled ? "Trực quan" : this.activeEditor.modeLabel();
    }
    if (toggleEl) {
      toggleEl.textContent = disabled
        ? "Chế độ markdown"
        : (this.activeEditor.mode === "visual" ? "Chế độ markdown" : "Chế độ trực quan");
    }
    if (headingEl && !disabled) {
      headingEl.value = this.activeEditor.detectHeadingLevel();
    }
  };

  MarkdownEditorManager.prototype.setActiveEditor = function (editor) {
    if (this.activeEditor === editor) {
      this.syncToolbarState();
      return;
    }
    this.editors.forEach(function (candidate) {
      candidate.root.classList.toggle("is-active", candidate === editor);
    });
    this.activeEditor = editor || null;
    this.syncToolbarState();
  };

  MarkdownEditorManager.prototype.syncToolbarState = function () {
    const disabled = !this.activeEditor;
    this.toolbar.classList.toggle("is-disabled", disabled);
    this.toolbar.querySelectorAll("[data-md-action]").forEach(function (control) {
      if (!(control instanceof HTMLButtonElement) && !(control instanceof HTMLSelectElement)) {
        return;
      }
      control.disabled = disabled;
    });

    const targetEl = this.toolbar.querySelector(".flama-md-toolbar__target");
    const modeEl = this.toolbar.querySelector(".flama-md-toolbar__mode");
    const toggleEl = this.toolbar.querySelector('[data-md-action="toggle-mode"]');
    const headingEl = this.toolbar.querySelector('[data-md-action="heading"]');
    if (targetEl) {
      targetEl.textContent = disabled ? "Chọn field" : this.activeEditor.label;
    }
    if (modeEl) {
      modeEl.textContent = disabled ? "Trực quan" : this.activeEditor.modeLabel();
    }
    if (toggleEl) {
      toggleEl.textContent = disabled
        ? "Chế độ markdown"
        : (this.activeEditor.mode === "visual" ? "Chế độ markdown" : "Chế độ trực quan");
    }
    if (headingEl && !disabled) {
      headingEl.value = this.activeEditor.detectHeadingLevel();
    }
  };

  MarkdownEditorManager.prototype.register = function (options) {
    const editor = new MarkdownFieldEditor(this, options);
    this.editors.set(editor.fieldName, editor);
    return editor;
  };

  MarkdownEditorManager.prototype.destroyAll = function () {
    this.editors.forEach(function (editor) {
      editor.destroy();
    });
    this.editors.clear();
    this.activeEditor = null;
    this.syncToolbarState();
  };

  MarkdownEditorManager.prototype.handleToolbarChange = function (event) {
    const action = event.target && event.target.getAttribute("data-md-action");
    if (action !== "heading" || !this.activeEditor) {
      return;
    }
    this.activeEditor.applyHeading(String(event.target.value || "paragraph"));
    this.syncToolbarState();
  };

  MarkdownEditorManager.prototype.handleToolbarClick = function (event) {
    const button = event.target && event.target.closest("[data-md-action]");
    if (!(button instanceof HTMLElement) || !this.activeEditor) {
      return;
    }
    const action = button.getAttribute("data-md-action");
    if (!action || action === "heading") {
      return;
    }
    event.preventDefault();
    if (action === "toggle-mode") {
      this.activeEditor.toggleMode();
    } else {
      this.activeEditor.applyAction(action);
    }
    this.syncToolbarState();
  };

  function MarkdownFieldEditor(manager, options) {
    this.manager = manager;
    this.mount = options.mount;
    this.fieldName = String(options.fieldName || "").trim();
    this.label = options.label || this.fieldName;
    this.placeholder = options.placeholder || "Nhập nội dung...";
    this.hint = options.hint || "";
    this.uploadImage = typeof options.uploadImage === "function" ? options.uploadImage : null;
    this.onChange = typeof options.onChange === "function" ? options.onChange : null;
    this.preferRawWhenComplex = options.preferRawWhenComplex !== false;
    this.mode = "visual";
    this.value = normalizeLinebreaks(options.value || "");

    this.root = document.createElement("div");
    this.root.className = "flama-md";
    this.root.style.setProperty("--flama-md-height", options.minHeight || "2.75rem");
    this.root.innerHTML = `
      <div class="flama-md__frame">
        <div class="flama-md__surface flama-md__surface--visual" contenteditable="true" spellcheck="true" data-placeholder="${escapeHtml(this.placeholder)}"></div>
        <textarea class="flama-md__surface flama-md__surface--raw" spellcheck="false"></textarea>
      </div>
      <div class="flama-md__footer">
        <div class="flama-md__hint">${escapeHtml(this.hint)}</div>
      </div>
    `;
    this.frame = this.root.querySelector(".flama-md__frame");
    this.visual = this.root.querySelector(".flama-md__surface--visual");
    this.raw = this.root.querySelector(".flama-md__surface--raw");
    this.hintEl = this.root.querySelector(".flama-md__hint");
    this.raw.name = options.inputName || "";
    this.raw.dataset.markdownStorage = "1";
    this.raw.dataset.markdownField = this.fieldName;
    this.root.dataset.markdownField = this.fieldName;
    this.root.classList.toggle("has-hint", Boolean(this.hint));

    this.boundHandleVisualInput = this.handleVisualInput.bind(this);
    this.boundHandleRawInput = this.handleRawInput.bind(this);
    this.boundActivate = this.activate.bind(this);
    this.boundHandlePaste = this.handlePaste.bind(this);
    this.boundHandleDragOver = this.handleDragOver.bind(this);
    this.boundHandleDragLeave = this.handleDragLeave.bind(this);
    this.boundHandleDrop = this.handleDrop.bind(this);

    this.visual.addEventListener("input", this.boundHandleVisualInput);
    this.raw.addEventListener("input", this.boundHandleRawInput);
    this.visual.addEventListener("focus", this.boundActivate);
    this.raw.addEventListener("focus", this.boundActivate);
    this.visual.addEventListener("click", this.boundActivate);
    this.raw.addEventListener("click", this.boundActivate);
    this.visual.addEventListener("paste", this.boundHandlePaste);
    this.raw.addEventListener("paste", this.boundHandlePaste);
    this.visual.addEventListener("dragover", this.boundHandleDragOver);
    this.raw.addEventListener("dragover", this.boundHandleDragOver);
    this.visual.addEventListener("dragleave", this.boundHandleDragLeave);
    this.raw.addEventListener("dragleave", this.boundHandleDragLeave);
    this.visual.addEventListener("drop", this.boundHandleDrop);
    this.raw.addEventListener("drop", this.boundHandleDrop);

    this.mount.replaceChildren(this.root);
    this.setValue(this.value, { silent: true });
    if (this.preferRawWhenComplex && hasComplexMarkdown(this.value)) {
      this.setMode("raw", { silent: true });
    } else {
      this.setMode("visual", { silent: true });
    }
  }

  MarkdownFieldEditor.prototype.modeLabel = function () {
    return this.mode === "visual" ? "Trực quan" : "Markdown";
  };

  MarkdownFieldEditor.prototype.activate = function () {
    this.manager.setActiveEditor(this);
  };

  MarkdownFieldEditor.prototype.detectHeadingLevel = function () {
    if (this.mode !== "visual") {
      const current = String(this.raw.value || "").trim();
      if (/^###\s+/m.test(current)) {
        return "3";
      }
      if (/^##\s+/m.test(current)) {
        return "2";
      }
      if (/^#\s+/m.test(current)) {
        return "1";
      }
      return "paragraph";
    }
    const selection = window.getSelection();
    let node = selection && selection.anchorNode;
    while (node && node !== this.visual) {
      if (node.nodeType === Node.ELEMENT_NODE) {
        const tag = node.nodeName.toLowerCase();
        if (tag === "h1") return "1";
        if (tag === "h2") return "2";
        if (tag === "h3") return "3";
      }
      node = node.parentNode;
    }
    return "paragraph";
  };

  MarkdownFieldEditor.prototype.setMode = function (mode, options) {
    this.mode = mode === "raw" ? "raw" : "visual";
    this.root.classList.toggle("is-raw", this.mode === "raw");
    if (this.mode === "visual") {
      this.visual.innerHTML = markdownToHtml(this.raw.value || "");
    }
    if (!options || !options.silent) {
      this.activate();
    }
  };

  MarkdownFieldEditor.prototype.toggleMode = function () {
    if (this.mode === "visual") {
      this.syncFromVisual();
      this.setMode("raw");
      this.raw.focus();
      this.raw.setSelectionRange(this.raw.value.length, this.raw.value.length);
    } else {
      this.setMode("visual");
      this.placeCaretAtEnd();
    }
  };

  MarkdownFieldEditor.prototype.placeCaretAtEnd = function () {
    this.visual.focus();
    const selection = window.getSelection();
    if (!selection) {
      return;
    }
    const range = document.createRange();
    range.selectNodeContents(this.visual);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
  };

  MarkdownFieldEditor.prototype.syncFromVisual = function () {
    sanitizeVisualRoot(this.visual);
    this.value = htmlToMarkdown(this.visual);
    this.raw.value = this.value;
    if (this.onChange) {
      this.onChange(this.value, this);
    }
  };

  MarkdownFieldEditor.prototype.syncFromRaw = function () {
    this.value = normalizeLinebreaks(this.raw.value || "");
    if (this.onChange) {
      this.onChange(this.value, this);
    }
  };

  MarkdownFieldEditor.prototype.handleVisualInput = function () {
    this.syncFromVisual();
  };

  MarkdownFieldEditor.prototype.handleRawInput = function () {
    this.syncFromRaw();
  };

  MarkdownFieldEditor.prototype.setHint = function (text) {
    this.hintEl.textContent = text || "";
    this.root.classList.toggle("has-hint", Boolean(text));
  };

  MarkdownFieldEditor.prototype.setValue = function (markdown, options) {
    this.value = normalizeLinebreaks(markdown || "");
    this.raw.value = this.value;
    this.visual.innerHTML = markdownToHtml(this.value);
    this.setHint(this.hint);
    if ((!options || !options.silent) && this.onChange) {
      this.onChange(this.value, this);
    }
  };

  MarkdownFieldEditor.prototype.getValue = function () {
    if (this.mode === "visual") {
      this.syncFromVisual();
    } else {
      this.syncFromRaw();
    }
    return this.value;
  };

  MarkdownFieldEditor.prototype.insertMarkdownImage = function (url, filename) {
    const snippet = `![${normalizeAltText(filename || "image")}](${url})`;
    if (this.mode === "raw") {
      wrapSelectionWithTextareaSyntax(this.raw, "", "", snippet);
      this.syncFromRaw();
      return;
    }
    const currentMarkdown = String(this.getValue() || "").trim();
    const nextValue = currentMarkdown
      ? `${currentMarkdown}\n\n${snippet}`
      : snippet;
    this.setValue(nextValue);
    this.placeCaretAtEnd();
  };

  MarkdownFieldEditor.prototype.uploadInlineImage = async function (file) {
    if (!this.uploadImage || !isImageFile(file)) {
      return false;
    }
    this.root.classList.add("is-dragover");
    this.setHint("Đang tải ảnh...");
    try {
      const payload = await this.uploadImage(file, this);
      if (payload && payload.url) {
        this.insertMarkdownImage(payload.url, payload.filename || file.name);
        this.setHint(this.hint || "Đã chèn ảnh vào markdown.");
      }
      return true;
    } catch (error) {
      this.setHint(error && error.message ? error.message : "Upload ảnh thất bại.");
      return false;
    } finally {
      this.root.classList.remove("is-dragover");
    }
  };

  MarkdownFieldEditor.prototype.handlePaste = function (event) {
    const file = Array.from(event.clipboardData && event.clipboardData.items ? event.clipboardData.items : [])
      .map(function (item) {
        return item.kind === "file" ? item.getAsFile() : null;
      })
      .find(isImageFile);

    if (file) {
      event.preventDefault();
      this.uploadInlineImage(file).catch(function () {
        return undefined;
      });
      return;
    }

    if (this.mode === "visual") {
      const text = event.clipboardData ? event.clipboardData.getData("text/plain") : "";
      if (text) {
        event.preventDefault();
        insertPlainTextAtCursor(text);
        this.syncFromVisual();
      }
    }
  };

  MarkdownFieldEditor.prototype.handleDragOver = function (event) {
    const file = Array.from(event.dataTransfer && event.dataTransfer.files ? event.dataTransfer.files : []).find(isImageFile);
    if (!file) {
      return;
    }
    event.preventDefault();
    this.root.classList.add("is-dragover");
  };

  MarkdownFieldEditor.prototype.handleDragLeave = function () {
    this.root.classList.remove("is-dragover");
  };

  MarkdownFieldEditor.prototype.handleDrop = function (event) {
    const file = Array.from(event.dataTransfer && event.dataTransfer.files ? event.dataTransfer.files : []).find(isImageFile);
    this.root.classList.remove("is-dragover");
    if (!file) {
      return;
    }
    event.preventDefault();
    this.uploadInlineImage(file).catch(function () {
      return undefined;
    });
  };

  MarkdownFieldEditor.prototype.applyHeading = function (level) {
    this.activate();
    if (this.mode === "raw") {
      applyHeadingToTextarea(this.raw, level);
      this.syncFromRaw();
      return;
    }

    this.visual.focus();
    if (level === "paragraph") {
      document.execCommand("formatBlock", false, "p");
    } else {
      document.execCommand("formatBlock", false, `h${level}`);
    }
    this.syncFromVisual();
  };

  MarkdownFieldEditor.prototype.applyAction = function (action) {
    this.activate();
    if (this.mode === "raw") {
      if (action === "bold") {
        wrapSelectionWithTextareaSyntax(this.raw, "**", "**", "in đậm");
      } else if (action === "italic") {
        wrapSelectionWithTextareaSyntax(this.raw, "*", "*", "in nghiêng");
      } else if (action === "strike") {
        wrapSelectionWithTextareaSyntax(this.raw, "~~", "~~", "văn bản");
      } else if (action === "bullet") {
        toggleLinePrefix(this.raw, "- ", false);
      } else if (action === "ordered") {
        toggleLinePrefix(this.raw, "", true);
      } else if (action === "quote") {
        toggleLinePrefix(this.raw, "> ", false);
      } else if (action === "code") {
        wrapSelectionWithTextareaSyntax(this.raw, "`", "`", "mã");
      } else if (action === "codeblock") {
        wrapSelectionWithTextareaSyntax(this.raw, "```\n", "\n```", "mã");
      } else if (action === "link") {
        const existing = this.raw.value.slice(this.raw.selectionStart || 0, this.raw.selectionEnd || 0);
        const href = promptLinkValue(existing);
        if (href) {
          wrapSelectionWithTextareaSyntax(this.raw, "[", `](${href})`, "liên kết");
        }
      } else if (action === "undo") {
        document.execCommand("undo");
      } else if (action === "redo") {
        document.execCommand("redo");
      }
      this.syncFromRaw();
      return;
    }

    this.visual.focus();
    if (action === "bold") {
      document.execCommand("bold");
    } else if (action === "italic") {
      document.execCommand("italic");
    } else if (action === "strike") {
      document.execCommand("strikeThrough");
    } else if (action === "bullet") {
      document.execCommand("insertUnorderedList");
    } else if (action === "ordered") {
      document.execCommand("insertOrderedList");
    } else if (action === "quote") {
      document.execCommand("formatBlock", false, "blockquote");
    } else if (action === "code") {
      const selection = window.getSelection();
      const text = selection ? selection.toString() : "";
      document.execCommand("insertHTML", false, `<code>${escapeHtml(text || "mã")}</code>`);
    } else if (action === "codeblock") {
      const selection = window.getSelection();
      const text = selection ? selection.toString() : "";
      document.execCommand("insertHTML", false, `<pre><code>${escapeHtml(text || "mã")}</code></pre>`);
    } else if (action === "link") {
      const selection = window.getSelection();
      const href = promptLinkValue(selection ? selection.toString() : "");
      if (href) {
        document.execCommand("createLink", false, href);
      }
    } else if (action === "undo") {
      document.execCommand("undo");
    } else if (action === "redo") {
      document.execCommand("redo");
    }
    this.syncFromVisual();
  };

  MarkdownFieldEditor.prototype.destroy = function () {
    this.visual.removeEventListener("input", this.boundHandleVisualInput);
    this.raw.removeEventListener("input", this.boundHandleRawInput);
    this.visual.removeEventListener("focus", this.boundActivate);
    this.raw.removeEventListener("focus", this.boundActivate);
    this.visual.removeEventListener("click", this.boundActivate);
    this.raw.removeEventListener("click", this.boundActivate);
    this.visual.removeEventListener("paste", this.boundHandlePaste);
    this.raw.removeEventListener("paste", this.boundHandlePaste);
    this.visual.removeEventListener("dragover", this.boundHandleDragOver);
    this.raw.removeEventListener("dragover", this.boundHandleDragOver);
    this.visual.removeEventListener("dragleave", this.boundHandleDragLeave);
    this.raw.removeEventListener("dragleave", this.boundHandleDragLeave);
    this.visual.removeEventListener("drop", this.boundHandleDrop);
    this.raw.removeEventListener("drop", this.boundHandleDrop);
  };

  window.FlamaMarkdownEditor = {
    createManager: function (options) {
      return new MarkdownEditorManager(options);
    },
    markdownToHtml: markdownToHtml,
    htmlToMarkdown: htmlToMarkdown,
    hasComplexMarkdown: hasComplexMarkdown,
    cssEscape: cssEscape,
    escapeHtml: escapeHtml,
  };
})();
