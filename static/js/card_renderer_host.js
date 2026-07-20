(function attachFlamaCardRendererHost(global) {
  "use strict";

  const CHANNEL = "flama-card-renderer";
  const HOST_DIRECTION = "host_to_renderer";
  const RENDERER_DIRECTION = "renderer_to_host";
  const DEFAULT_MIN_HEIGHT = 180;
  const MAX_FRAME_HEIGHT = 4096;
  const PROXY_MEDIA_RE = /^\/media\/proxy\/([A-Za-z0-9][A-Za-z0-9_-]{0,127})$/;

  let sharedAudioEl = null;

  function generateInstanceId() {
    if (global.crypto && typeof global.crypto.randomUUID === "function") {
      return global.crypto.randomUUID();
    }
    return "fc-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function escapeJsonForScript(value) {
    return String(value || "")
      .replaceAll("<", "\\u003c")
      .replaceAll(">", "\\u003e")
      .replaceAll("&", "\\u0026");
  }

  function clampFrameHeight(rawHeight, minHeight) {
    const parsed = Number(rawHeight);
    const floor = Math.max(0, Math.trunc(Number(minHeight) || DEFAULT_MIN_HEIGHT));
    if (!Number.isFinite(parsed)) {
      return floor;
    }
    return Math.max(floor, Math.min(MAX_FRAME_HEIGHT, Math.ceil(parsed)));
  }

  function normalizeProxyRef(rawValue) {
    if (typeof rawValue !== "string") {
      return null;
    }
    const trimmed = rawValue.trim();
    if (!trimmed) {
      return null;
    }
    const directMatch = trimmed.match(PROXY_MEDIA_RE);
    if (directMatch) {
      return "/media/proxy/" + directMatch[1];
    }
    try {
      const parsed = new URL(trimmed, global.location.href);
      if (parsed.origin === global.location.origin) {
        const normalizedPath = String(parsed.pathname || "").trim();
        const absoluteMatch = normalizedPath.match(PROXY_MEDIA_RE);
        if (absoluteMatch) {
          return "/media/proxy/" + absoluteMatch[1];
        }
      }
    } catch (_error) {
      // Ignore URL parsing failures and keep checking other formats.
    }
    const assetOnlyMatch = trimmed.match(/^([A-Za-z0-9][A-Za-z0-9_-]{0,127})$/);
    if (assetOnlyMatch) {
      return "/media/proxy/" + assetOnlyMatch[1];
    }
    return null;
  }

  function assetIdFromProxyRef(proxyRef) {
    const match = String(proxyRef || "").match(PROXY_MEDIA_RE);
    return match ? match[1] : "";
  }

  function normalizeStringList(values) {
    const output = [];
    const seen = new Set();
    if (!Array.isArray(values)) {
      return output;
    }
    values.forEach((value) => {
      if (typeof value !== "string") {
        return;
      }
      const normalized = value.trim();
      if (!normalized || seen.has(normalized)) {
        return;
      }
      seen.add(normalized);
      output.push(normalized);
    });
    return output;
  }

  function collectAllowedMediaFromHtml(html) {
    const normalizedHtml = typeof html === "string" ? html : "";
    const documentHtml = "<!doctype html><html><body>" + normalizedHtml + "</body></html>";
    const parsed = new global.DOMParser().parseFromString(documentHtml, "text/html");
    const allowedMediaUrls = new Set();
    const allowedAudioUrls = new Set();
    parsed.querySelectorAll("img[src], audio[src], video[src], source[src], a[href]").forEach((node) => {
      const attrName = node.hasAttribute("src") ? "src" : "href";
      const rawValue = String(node.getAttribute(attrName) || "").trim();
      const normalizedRef = normalizeProxyRef(rawValue);
      if (!normalizedRef) {
        return;
      }
      allowedMediaUrls.add(normalizedRef);
      const tagName = String(node.tagName || "").toLowerCase();
      if (tagName === "audio") {
        allowedAudioUrls.add(normalizedRef);
        return;
      }
      if (tagName === "source") {
        const sourceType = String(node.getAttribute("type") || "").trim().toLowerCase();
        if (sourceType.startsWith("audio/")) {
          allowedAudioUrls.add(normalizedRef);
        }
      }
    });
    return {
      html: normalizedHtml,
      allowed_media_urls: Array.from(allowedMediaUrls),
      allowed_audio_urls: Array.from(allowedAudioUrls),
      allowed_audio_asset_ids: Array.from(allowedAudioUrls).map(assetIdFromProxyRef).filter(Boolean),
    };
  }

  function normalizeRendererSidePayload(sidePayload) {
    const basePayload =
      sidePayload && typeof sidePayload === "object" && !Array.isArray(sidePayload)
        ? sidePayload
        : { html: typeof sidePayload === "string" ? sidePayload : "" };
    const html = typeof basePayload.html === "string" ? basePayload.html : "";
    const derived = collectAllowedMediaFromHtml(html);
    const allowedMediaUrls = new Set(derived.allowed_media_urls);
    const allowedAudioUrls = new Set(derived.allowed_audio_urls);

    normalizeStringList(basePayload.allowed_media_urls).forEach((value) => {
      const normalized = normalizeProxyRef(value);
      if (normalized) {
        allowedMediaUrls.add(normalized);
      }
    });
    normalizeStringList(basePayload.allowed_audio_urls).forEach((value) => {
      const normalized = normalizeProxyRef(value);
      if (normalized) {
        allowedAudioUrls.add(normalized);
      }
    });
    normalizeStringList(basePayload.allowed_audio_asset_ids).forEach((value) => {
      const normalized = normalizeProxyRef(value);
      if (normalized) {
        allowedAudioUrls.add(normalized);
      }
    });
    const templateKey = typeof basePayload.template_key === "string" ? basePayload.template_key.trim() : "";
    const shellKey = typeof basePayload.shell_key === "string"
      ? basePayload.shell_key.trim()
      : templateKey;
    const hasInlineScript = basePayload.has_inline_script === true || html.toLowerCase().includes("<script");
    const supportsLivePatch = (
      basePayload.supports_live_patch === true &&
      templateKey.length > 0 &&
      shellKey.length > 0 &&
      !hasInlineScript
    );

    return {
      html,
      allowed_media_urls: Array.from(allowedMediaUrls),
      allowed_audio_urls: Array.from(allowedAudioUrls),
      allowed_audio_asset_ids: Array.from(allowedAudioUrls).map(assetIdFromProxyRef).filter(Boolean),
      template_key: templateKey,
      shell_key: shellKey,
      has_inline_script: hasInlineScript,
      supports_live_patch: supportsLivePatch,
    };
  }

  function getSharedAudioElement() {
    if (sharedAudioEl instanceof global.HTMLAudioElement) {
      return sharedAudioEl;
    }
    const audioEl = global.document.createElement("audio");
    audioEl.preload = "none";
    audioEl.className = "d-none";
    audioEl.setAttribute("aria-hidden", "true");
    global.document.body.appendChild(audioEl);
    sharedAudioEl = audioEl;
    return audioEl;
  }

  function buildCspSourceList(values) {
    const sources = [];
    const seen = new Set();
    normalizeStringList(values).forEach((value) => {
      const normalized = normalizeProxyRef(value);
      if (!normalized) {
        return;
      }
      try {
        const absoluteUrl = new URL(normalized, global.location.href);
        const source = absoluteUrl.origin + absoluteUrl.pathname;
        if (!source || seen.has(source)) {
          return;
        }
        seen.add(source);
        sources.push(source);
      } catch (_error) {
        return;
      }
    });
    return sources;
  }

  function buildRendererCsp(options) {
    const allowedMediaSources = buildCspSourceList(options.allowedMediaUrls);
    const imgSrc = allowedMediaSources.length ? allowedMediaSources.join(" ") : "'none'";
    const mediaSrc = allowedMediaSources.length ? allowedMediaSources.join(" ") : "'none'";
    return [
      "default-src 'none'",
      "base-uri 'none'",
      "form-action 'none'",
      "frame-ancestors 'none'",
      "connect-src 'none'",
      "font-src 'none'",
      "frame-src 'none'",
      "img-src " + imgSrc,
      "manifest-src 'none'",
      "media-src " + mediaSrc,
      "navigate-to 'none'",
      "object-src 'none'",
      "script-src 'unsafe-inline'",
      "style-src 'unsafe-inline'",
      "worker-src 'none'",
    ].join("; ");
  }

  function createNoticeHtml(message) {
    return "<div style=\"padding:12px;color:#6c757d;\">" + escapeHtml(message || "") + "</div>";
  }

  function buildRendererDocument(options) {
    const bootstrap = {
      instanceId: String(options.instanceId || ""),
      config: options.config && typeof options.config === "object" ? options.config : {},
      context: options.context && typeof options.context === "object" ? options.context : {},
    };
    const bootstrapJson = escapeJsonForScript(JSON.stringify(bootstrap));
    const contentHtml = typeof options.html === "string" ? options.html : "";
    const background = escapeHtml(options.background || "#ffffff");
    const textColor = escapeHtml(options.color || "#1f1a17");
    const padding = escapeHtml(options.padding || "8px");
    const bodyClass = escapeHtml(options.bodyClass || "");
    const rendererCsp = escapeHtml(
      buildRendererCsp({
        allowedMediaUrls: Array.isArray(options.allowedMediaUrls) ? options.allowedMediaUrls : [],
      })
    );
    const shellScript = [
      "(function initFlamaCardSandbox(){",
      "  'use strict';",
      "  var bootstrap = {};",
      "  try {",
      "    var bootstrapEl = document.getElementById('flama-card-bootstrap');",
      "    bootstrap = JSON.parse((bootstrapEl && bootstrapEl.textContent) || '{}');",
      "  } catch (_error) {",
      "    bootstrap = {};",
      "  }",
      "  var channel = '" + CHANNEL + "';",
      "  var instanceId = String(bootstrap.instanceId || '');",
      "  var revealCallbacks = [];",
      "  var rendererConfig = bootstrap.config && typeof bootstrap.config === 'object' ? bootstrap.config : {};",
      "  var rendererContext = bootstrap.context && typeof bootstrap.context === 'object' ? bootstrap.context : {};",
      "  var lastHeight = 0;",
      "  function post(action, payload) {",
      "    parent.postMessage({",
      "      channel: channel,",
      "      direction: '" + RENDERER_DIRECTION + "',",
      "      instanceId: instanceId,",
      "      action: action,",
      "      payload: payload && typeof payload === 'object' ? payload : {}",
      "    }, '*');",
      "  }",
      "  function cloneJson(value) {",
      "    try {",
      "      return JSON.parse(JSON.stringify(value || {}));",
      "    } catch (_error) {",
      "      return {};",
      "    }",
      "  }",
      "  function applyAutoSplit() {",
      "    document.querySelectorAll('[auto-split]').forEach(function (el) {",
      "      var rawHtml = String(el.innerHTML || '');",
      "      if (rawHtml.indexOf('$') === -1) {",
      "        return;",
      "      }",
      "      el.innerHTML = rawHtml.replace(/\\$/g, '<br>');",
      "    });",
      "  }",
      "  function measureHeight() {",
      "    var docEl = document.documentElement;",
      "    var body = document.body;",
      "    var root = document.getElementById('flama-card-root');",
      "    if (rendererConfig.heightMeasurement === 'content-root' && root) {",
      "      return Math.max(root.scrollHeight || 0, root.offsetHeight || 0);",
      "    }",
      "    return Math.max(",
      "      docEl ? docEl.scrollHeight : 0,",
      "      docEl ? docEl.offsetHeight : 0,",
      "      body ? body.scrollHeight : 0,",
      "      body ? body.offsetHeight : 0",
      "    );",
      "  }",
      "  function notifyHeight() {",
      "    var height = measureHeight();",
      "    if (!Number.isFinite(height) || Math.abs(height - lastHeight) < 1) {",
      "      return;",
      "    }",
      "    lastHeight = height;",
      "    post('resize_request', { height: height });",
      "  }",
      "  function replaceRootContent(nextHtml) {",
      "    var root = document.getElementById('flama-card-root');",
      "    if (!root) {",
      "      return;",
      "    }",
      "    if (typeof DOMParser !== 'function') {",
      "      return;",
      "    }",
      "    var parsed = new DOMParser().parseFromString('<!doctype html><html><body>' + String(nextHtml || '') + '</body></html>', 'text/html');",
      "    var fragment = document.createDocumentFragment();",
      "    var parsedBody = parsed && parsed.body ? parsed.body : null;",
      "    if (!parsedBody) {",
      "      root.replaceChildren();",
      "      return;",
      "    }",
      "    while (parsedBody.firstChild) {",
      "      fragment.appendChild(document.importNode(parsedBody.firstChild, true));",
      "      parsedBody.removeChild(parsedBody.firstChild);",
      "    }",
      "    root.replaceChildren(fragment);",
      "  }",
      "  function applyPatchedContent(payload) {",
      "    if (payload && payload.config && typeof payload.config === 'object') {",
      "      rendererConfig = payload.config;",
      "    } else {",
      "      rendererConfig = {};",
      "    }",
      "    if (payload && payload.context && typeof payload.context === 'object') {",
      "      rendererContext = payload.context;",
      "    } else {",
      "      rendererContext = {};",
      "    }",
      "    replaceRootContent(payload && typeof payload.html === 'string' ? payload.html : '');",
      "    applyAutoSplit();",
      "    notifyHeight();",
      "    if (typeof window.requestAnimationFrame === 'function') {",
      "      window.requestAnimationFrame(notifyHeight);",
      "    }",
      "    if (payload && payload.reveal && typeof payload.reveal === 'object') {",
      "      dispatchReveal(payload.reveal);",
      "    }",
      "  }",
      "  function resolveAudioRef(ref) {",
      "    if (typeof ref !== 'string') {",
      "      return '';",
      "    }",
      "    var raw = ref.trim();",
      "    if (!raw) {",
      "      return '';",
      "    }",
      "    if (/^\\/media\\/proxy\\/[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(raw)) {",
      "      return raw;",
      "    }",
      "    try {",
      "      var absoluteUrl = new URL(raw, document.baseURI || window.location.href);",
      "      if (/^\\/media\\/proxy\\/[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(String(absoluteUrl.pathname || ''))) {",
      "        return String(absoluteUrl.pathname || '');",
      "      }",
      "    } catch (_error) {",
      "      // Ignore invalid URLs and fall through to the remaining resolvers.",
      "    }",
      "    if (/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(raw)) {",
      "      return '/media/proxy/' + raw;",
      "    }",
      "    var escaped = window.CSS && typeof window.CSS.escape === 'function' ? window.CSS.escape(raw) : raw.replace(/([\"\\\\])/g, '\\\\$1');",
      "    var selector = 'audio[data-flama-media-field=\"' + escaped + '\"]';",
      "    var audioEl = document.querySelector(selector);",
      "    if (audioEl instanceof HTMLAudioElement) {",
      "      var assetId = String(audioEl.getAttribute('data-flama-media-asset-id') || '').trim();",
      "      if (/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(assetId)) {",
      "        return '/media/proxy/' + assetId;",
      "      }",
      "      var src = String(audioEl.getAttribute('src') || '').trim();",
      "      if (/^\\/media\\/proxy\\/[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(src)) {",
      "        return src;",
      "      }",
      "    }",
      "    return '';",
      "  }",
      "  function resolveAudioElementRef(element) {",
      "    if (!element || typeof element !== 'object') {",
      "      return '';",
      "    }",
      "    var assetId = '';",
      "    try {",
      "      assetId = String(element.getAttribute && element.getAttribute('data-flama-media-asset-id') || '').trim();",
      "    } catch (_error) {",
      "      assetId = '';",
      "    }",
      "    if (/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(assetId)) {",
      "      return '/media/proxy/' + assetId;",
      "    }",
      "    var srcCandidates = [];",
      "    try {",
      "      srcCandidates.push(String(element.currentSrc || ''));",
      "    } catch (_error) {",
      "      srcCandidates.push('');",
      "    }",
      "    try {",
      "      srcCandidates.push(String(element.src || ''));",
      "    } catch (_error) {",
      "      srcCandidates.push('');",
      "    }",
      "    try {",
      "      srcCandidates.push(String((element.getAttribute && element.getAttribute('src')) || ''));",
      "    } catch (_error) {",
      "      srcCandidates.push('');",
      "    }",
      "    for (var idx = 0; idx < srcCandidates.length; idx += 1) {",
      "      var resolvedCandidate = resolveAudioRef(srcCandidates[idx]);",
      "      if (resolvedCandidate) {",
      "        return resolvedCandidate;",
      "      }",
      "    }",
      "    if (typeof element.querySelectorAll === 'function') {",
      "      var sources = element.querySelectorAll('source[src]');",
      "      for (var sourceIndex = 0; sourceIndex < sources.length; sourceIndex += 1) {",
      "        var sourceRef = resolveAudioRef(String(sources[sourceIndex].getAttribute('src') || ''));",
      "        if (sourceRef) {",
      "          return sourceRef;",
      "        }",
      "      }",
      "    }",
      "    return '';",
      "  }",
      "  function installMediaPlaybackBridge() {",
      "    if (typeof HTMLMediaElement !== 'function' || !HTMLMediaElement.prototype) {",
      "      return;",
      "    }",
      "    var mediaProto = HTMLMediaElement.prototype;",
      "    var originalPlay = mediaProto.play;",
      "    if (typeof originalPlay !== 'function' || originalPlay.__flamaBridgeWrapped) {",
      "      return;",
      "    }",
      "    var originalPause = typeof mediaProto.pause === 'function' ? mediaProto.pause : null;",
      "    var wrappedPlay = function () {",
      "      var element = this;",
      "      var tagName = String((element && element.tagName) || '').toLowerCase();",
      "      if (tagName === 'audio' && !element.controls) {",
      "        var approvedRef = resolveAudioElementRef(element);",
      "        if (approvedRef) {",
      "          post('play_audio', { ref: approvedRef });",
      "          return Promise.resolve();",
      "        }",
      "      }",
      "      return originalPlay.apply(element, arguments);",
      "    };",
      "    wrappedPlay.__flamaBridgeWrapped = true;",
      "    wrappedPlay.__flamaOriginal = originalPlay;",
      "    mediaProto.play = wrappedPlay;",
      "    if (originalPause && !originalPause.__flamaBridgeWrapped) {",
      "      var wrappedPause = function () {",
      "        var element = this;",
      "        var tagName = String((element && element.tagName) || '').toLowerCase();",
      "        if (tagName === 'audio' && !element.controls) {",
      "          var approvedRef = resolveAudioElementRef(element);",
      "          if (approvedRef) {",
      "            post('pause_audio', { ref: approvedRef });",
      "            return;",
      "          }",
      "        }",
      "        return originalPause.apply(element, arguments);",
      "      };",
      "      wrappedPause.__flamaBridgeWrapped = true;",
      "      wrappedPause.__flamaOriginal = originalPause;",
      "      mediaProto.pause = wrappedPause;",
      "    }",
      "  }",
      "  function dispatchReveal(payload) {",
      "    applyAutoSplit();",
      "    revealCallbacks.slice().forEach(function (callback) {",
      "      try {",
      "        callback(payload || {});",
      "      } catch (error) {",
      "        var message = error && error.message ? error.message : String(error || 'Renderer reveal callback failed.');",
      "        post('log_error', { message: message });",
      "      }",
      "    });",
      "    notifyHeight();",
      "  }",
      "  window.FlamaCard = Object.freeze({",
      "    playAudio: function (ref) {",
      "      var resolved = resolveAudioRef(ref);",
      "      if (!resolved) {",
      "        return false;",
      "      }",
      "      post('play_audio', { ref: resolved });",
      "      return true;",
      "    },",
      "    notifyHeight: notifyHeight,",
      "    onReveal: function (callback) {",
      "      if (typeof callback === 'function') {",
      "        revealCallbacks.push(callback);",
      "      }",
      "    },",
      "    getConfig: function () {",
      "      return cloneJson(rendererConfig);",
      "    },",
      "    getContext: function () {",
      "      return cloneJson(rendererContext);",
      "    }",
      "  });",
      "  installMediaPlaybackBridge();",
      "  window.addEventListener('message', function (event) {",
      "    var data = event && event.data;",
      "    if (!data || data.channel !== channel || data.direction !== '" + HOST_DIRECTION + "' || data.instanceId !== instanceId) {",
      "      return;",
      "    }",
      "    if (data.action === 'reveal') {",
      "      dispatchReveal(data.payload || {});",
      "      return;",
      "    }",
      "    if (data.action === 'patch_content') {",
      "      applyPatchedContent(data.payload || {});",
      "    }",
      "  });",
      "  window.addEventListener('error', function (event) {",
      "    post('log_error', { message: String((event && event.message) || 'Sandbox renderer error.') });",
      "  }, true);",
      "  window.addEventListener('unhandledrejection', function (event) {",
      "    var reason = event && event.reason;",
      "    var message = reason && reason.message ? reason.message : String(reason || 'Sandbox renderer promise rejection.');",
      "    post('log_error', { message: message });",
      "  });",
      "  if (typeof ResizeObserver === 'function') {",
      "    var resizeObserver = new ResizeObserver(function () {",
      "      window.requestAnimationFrame(notifyHeight);",
      "    });",
      "    if (document.documentElement) {",
      "      resizeObserver.observe(document.documentElement);",
      "    }",
      "    if (document.body) {",
      "      resizeObserver.observe(document.body);",
      "    }",
      "  }",
      "  function announceReady() {",
      "    if (announceReady.__done) {",
      "      return;",
      "    }",
      "    announceReady.__done = true;",
      "    applyAutoSplit();",
      "    notifyHeight();",
      "    post('renderer_ready', { height: measureHeight() });",
      "  }",
      "  window.addEventListener('load', function () {",
      "    if (typeof window.requestAnimationFrame === 'function') {",
      "      window.requestAnimationFrame(announceReady);",
      "    }",
      "    window.setTimeout(announceReady, 0);",
      "  });",
      "})();",
    ].join("\n");
    return [
      "<!doctype html>",
      "<html>",
      "<head>",
      "<meta charset=\"utf-8\">",
      "<meta http-equiv=\"Content-Security-Policy\" content=\"" + rendererCsp + "\">",
      "<style>",
      "html, body { margin: 0; padding: 0; background: " + background + "; color: " + textColor + "; overflow-x: hidden; }",
      "body { padding: " + padding + "; }",
      "#flama-card-root { min-height: 0; overflow-wrap: anywhere; word-break: break-word; }",
      "#flama-card-root img, #flama-card-root video, #flama-card-root canvas, #flama-card-root svg, #flama-card-root audio { max-width: 100%; }",
      "#flama-card-root audio { width: min(100%, 20rem); }",
      "#flama-card-root table { display: block; max-width: 100%; overflow-x: auto; }",
      "#flama-card-root pre { max-width: 100%; overflow: auto; }",
      "</style>",
      "<script id=\"flama-card-bootstrap\" type=\"application/json\">" + bootstrapJson + "</script>",
      "<script>" + shellScript + "</script>",
      "</head>",
      "<body class=\"" + bodyClass + "\">",
      "<div id=\"flama-card-root\">" + contentHtml + "</div>",
      "</body>",
      "</html>",
    ].join("");
  }

  function createRendererFrameController(frameEl, options) {
    if (!(frameEl instanceof global.HTMLIFrameElement)) {
      throw new Error("Renderer frame must be an iframe element.");
    }
    const initialOptions = options && typeof options === "object" ? options : {};
    let instanceId = "";
    let activePayload = normalizeRendererSidePayload(initialOptions.initialPayload || "");
    let activeConfig = initialOptions.initialConfig && typeof initialOptions.initialConfig === "object"
      ? initialOptions.initialConfig
      : {};
    let activeContext = initialOptions.initialContext && typeof initialOptions.initialContext === "object"
      ? initialOptions.initialContext
      : {};
    let ready = false;
    let pendingRevealPayload = null;
    const minHeight = clampFrameHeight(initialOptions.minHeight || DEFAULT_MIN_HEIGHT, DEFAULT_MIN_HEIGHT);
    const autoHeight = initialOptions.autoHeight !== false;
    const enableLivePatch = initialOptions.enableLivePatch === true;
    const fixedHeight = clampFrameHeight(
      initialOptions.fixedHeight || initialOptions.minHeight || DEFAULT_MIN_HEIGHT,
      DEFAULT_MIN_HEIGHT
    );
    const allowedAudioUrls = new Set();

    function syncAllowedAudioUrls(payload) {
      allowedAudioUrls.clear();
      normalizeStringList(payload.allowed_audio_urls).forEach((value) => {
        const normalized = normalizeProxyRef(value);
        if (normalized) {
          allowedAudioUrls.add(normalized);
        }
      });
      normalizeStringList(payload.allowed_audio_asset_ids).forEach((value) => {
        const normalized = normalizeProxyRef(value);
        if (normalized) {
          allowedAudioUrls.add(normalized);
        }
      });
    }

    function normalizedListSignature(values) {
      return normalizeStringList(values).slice().sort().join("|");
    }

    function canLivePatchPayload(nextPayload) {
      if (!enableLivePatch || !ready || !instanceId || !frameEl.contentWindow || typeof global.DOMParser !== "function") {
        return false;
      }
      if (!nextPayload || typeof nextPayload !== "object") {
        return false;
      }
      if (!activePayload.supports_live_patch || !nextPayload.supports_live_patch) {
        return false;
      }
      if (!activePayload.template_key || activePayload.template_key !== nextPayload.template_key) {
        return false;
      }
      if (!activePayload.shell_key || activePayload.shell_key !== nextPayload.shell_key) {
        return false;
      }
      // Keep the iframe CSP exact to the current document; if allowed media changes, reload.
      if (normalizedListSignature(activePayload.allowed_media_urls) !== normalizedListSignature(nextPayload.allowed_media_urls)) {
        return false;
      }
      if (normalizedListSignature(activePayload.allowed_audio_urls) !== normalizedListSignature(nextPayload.allowed_audio_urls)) {
        return false;
      }
      if (normalizedListSignature(activePayload.allowed_audio_asset_ids) !== normalizedListSignature(nextPayload.allowed_audio_asset_ids)) {
        return false;
      }
      return true;
    }

    function setFrameHeight(nextHeight) {
      frameEl.style.height = clampFrameHeight(nextHeight, minHeight) + "px";
    }

    function resetFrameViewport() {
      try {
        frameEl.scrollTop = 0;
        frameEl.scrollLeft = 0;
      } catch (_error) {
        // Best-effort only for browsers that do not expose scroll state on iframe elements.
      }
    }

    function postHostMessage(action, payload) {
      if (!ready || !frameEl.contentWindow || !instanceId) {
        return;
      }
      frameEl.contentWindow.postMessage(
        {
          channel: CHANNEL,
          direction: HOST_DIRECTION,
          instanceId,
          action,
          payload: payload && typeof payload === "object" ? payload : {},
        },
        "*"
      );
    }

    function resolveApprovedAudioRef(rawValue) {
      const normalized = normalizeProxyRef(rawValue);
      if (!normalized) {
        return null;
      }
      return allowedAudioUrls.has(normalized) ? normalized : null;
    }

    function playApprovedAudio(rawValue) {
      const approvedRef = resolveApprovedAudioRef(rawValue);
      if (!approvedRef) {
        return false;
      }
      const audioEl = getSharedAudioElement();
      try {
        audioEl.pause();
      } catch (_error) {
        // Ignore pause failures and continue attempting playback.
      }
      if (audioEl.getAttribute("src") !== approvedRef) {
        audioEl.setAttribute("src", approvedRef);
      }
      try {
        audioEl.currentTime = 0;
      } catch (_error) {
        // Some browsers disallow seeking before metadata; best-effort only.
      }
      const playPromise = audioEl.play();
      if (playPromise && typeof playPromise.catch === "function") {
        playPromise.catch(function () {
          return undefined;
        });
      }
      return true;
    }

    function pauseApprovedAudio(rawValue) {
      const approvedRef = rawValue ? resolveApprovedAudioRef(rawValue) : null;
      const audioEl = getSharedAudioElement();
      const currentRef = normalizeProxyRef(audioEl.getAttribute("src") || "");
      if (approvedRef && currentRef && approvedRef !== currentRef) {
        return false;
      }
      try {
        audioEl.pause();
      } catch (_error) {
        return false;
      }
      return true;
    }

    function handleRendererMessage(event) {
      const data = event && event.data;
      if (!data || data.channel !== CHANNEL || data.direction !== RENDERER_DIRECTION) {
        return;
      }
      if (!instanceId || data.instanceId !== instanceId) {
        return;
      }
      if (event.source !== frameEl.contentWindow) {
        return;
      }
      const action = String(data.action || "");
      const payload = data.payload && typeof data.payload === "object" ? data.payload : {};
      if (action === "renderer_ready") {
        ready = true;
        if (autoHeight) {
          setFrameHeight(payload.height);
        }
        if (pendingRevealPayload) {
          postHostMessage("reveal", pendingRevealPayload);
          pendingRevealPayload = null;
        }
        return;
      }
      if (action === "resize_request") {
        if (autoHeight) {
          setFrameHeight(payload.height);
        }
        return;
      }
      if (action === "play_audio") {
        playApprovedAudio(payload.ref);
        return;
      }
      if (action === "pause_audio") {
        pauseApprovedAudio(payload.ref);
        return;
      }
      if (action === "log_error") {
        const message = typeof payload.message === "string" ? payload.message.trim() : "";
        if (message) {
          global.console.warn("Flama card renderer:", message);
        }
      }
    }

    global.addEventListener("message", handleRendererMessage);

    function patch(nextPayload, renderOptions) {
      const normalizedPayload = normalizeRendererSidePayload(nextPayload);
      if (!canLivePatchPayload(normalizedPayload)) {
        return false;
      }
      const optionsObject = renderOptions && typeof renderOptions === "object" ? renderOptions : {};
      activePayload = normalizedPayload;
      activeConfig = optionsObject.config && typeof optionsObject.config === "object"
        ? optionsObject.config
        : {};
      activeContext = optionsObject.context && typeof optionsObject.context === "object"
        ? optionsObject.context
        : {};
      syncAllowedAudioUrls(activePayload);
      pendingRevealPayload = null;
      if (optionsObject.resetViewport !== false) {
        resetFrameViewport();
      }
      postHostMessage("patch_content", {
        html: activePayload.html,
        config: activeConfig,
        context: activeContext,
        reveal: optionsObject.revealOnReady && typeof optionsObject.revealOnReady === "object"
          ? optionsObject.revealOnReady
          : null,
      });
      return true;
    }

    function render(nextPayload, renderOptions) {
      const optionsObject = renderOptions && typeof renderOptions === "object" ? renderOptions : {};
      const normalizedPayload = normalizeRendererSidePayload(nextPayload);
      if (patch(normalizedPayload, optionsObject)) {
        return;
      }
      activePayload = normalizedPayload;
      activeConfig = optionsObject.config && typeof optionsObject.config === "object"
        ? optionsObject.config
        : {};
      activeContext = optionsObject.context && typeof optionsObject.context === "object"
        ? optionsObject.context
        : {};
      syncAllowedAudioUrls(activePayload);
      instanceId = generateInstanceId();
      ready = false;
      pendingRevealPayload = optionsObject.revealOnReady && typeof optionsObject.revealOnReady === "object"
        ? optionsObject.revealOnReady
        : null;
      const renderBaseHeight = autoHeight
        ? (optionsObject.placeholderHeight || minHeight)
        : (optionsObject.fixedHeight || fixedHeight);
      setFrameHeight(renderBaseHeight);
      resetFrameViewport();
      frameEl.setAttribute("sandbox", "allow-scripts");
      frameEl.setAttribute("referrerpolicy", "no-referrer");
      frameEl.classList.add("flama-card-renderer-frame");
      const documentHtml = buildRendererDocument({
        instanceId,
        html: activePayload.html,
        config: activeConfig,
        context: activeContext,
        background: optionsObject.background || "#ffffff",
        color: optionsObject.color || "#1f1a17",
        padding: optionsObject.padding || "8px",
        bodyClass: optionsObject.bodyClass || "",
        allowedMediaUrls: activePayload.allowed_media_urls,
      });
      frameEl.srcdoc = documentHtml;
    }

    function reveal(payload) {
      const nextPayload = payload && typeof payload === "object" ? payload : {};
      if (!ready) {
        pendingRevealPayload = nextPayload;
        return;
      }
      postHostMessage("reveal", nextPayload);
    }

    function destroy() {
      global.removeEventListener("message", handleRendererMessage);
      ready = false;
      pendingRevealPayload = null;
      frameEl.removeAttribute("srcdoc");
      frameEl.style.height = "";
    }

    setFrameHeight(autoHeight ? minHeight : fixedHeight);

    return {
      render,
      patch,
      reveal,
      destroy,
      createNoticeHtml,
    };
  }

  global.FlamaCardRendererHost = {
    createRendererFrameController,
    createNoticeHtml,
    normalizeRendererSidePayload,
  };
})(window);
