const root = document.getElementById("marketplace-hub-root");

if (root) {
  const hubUrl = root.dataset.hubUrl || "";
  const detailTemplate = root.dataset.detailUrlTemplate || "";
  const editTemplate = root.dataset.editUrlTemplate || "";
  const installTemplate = root.dataset.installUrlTemplate || "";
  const saveTemplate = root.dataset.saveUrlTemplate || "";
  const ordersUrl = root.dataset.ordersUrl || "/";
  const orderDetailTemplate = root.dataset.orderDetailUrlTemplate || "";
  const paymentResultUrl = root.dataset.paymentResultUrl || "";
  const studyUrlTemplate = root.dataset.studyUrlTemplate || "";
  const libraryUrl = root.dataset.libraryUrl || "";
  const marketKind = root.dataset.marketKind || "";

  const filterForm = document.getElementById("marketplace-filter-form");
  const errorEl = document.getElementById("marketplace-hub-error");
  const heroSummaryEl = document.getElementById("marketplace-hero-summary");
  const heroNoteEl = document.getElementById("marketplace-hero-note");
  const resultsEl = document.getElementById("marketplace-results-grid");
  const resultsCountEl = document.getElementById("marketplace-results-count");
  const appliedFiltersEl = document.getElementById("marketplace-applied-filters");
  const quickFiltersEl = document.getElementById("marketplace-quick-filters");
  const featuredStageEl = document.getElementById("marketplace-featured-stage");
  const discoveryShelvesEl = document.getElementById("marketplace-discovery-shelves");
  const librarySpotlightEl = document.getElementById("marketplace-library-spotlight");
  const librarySummaryEl = document.getElementById("marketplace-library-summary");
  const librarySectionsEl = document.getElementById("marketplace-library-sections");
  const mobileFilterToggleEl = document.getElementById("market-mobile-filter-open");
  const mobileFilterBackdropEl = root.querySelector(".market-mobile-filter-backdrop");
  const filterSidebarEl = document.getElementById("marketplace-filter-sidebar");
  const switchButtons = Array.from(root.querySelectorAll(".market-hub-switch-btn"));
  const spacePanels = Array.from(root.querySelectorAll("[data-space-panel]"));

  const filterConfigs = [
    ["domain", "Lĩnh vực", "radio", "domains"],
    ["subject", "Môn học", "radio", "subjects"],
    ["difficulty_band", "Trình độ", "radio", "levels"],
    ["framework_level", "Cấp độ khung", "radio", "framework_levels"],
    ["framework_track", "Nhánh", "radio", "framework_tracks"],
    ["audience", "Đối tượng", "radio", "audiences"],
    ["learning_goals", "Mục tiêu học", "checkbox", "learning_goals"],
    ["primary_topics", "Nội dung chính", "checkbox", "primary_topics"],
    ["format_features", "Đặc điểm", "checkbox", "format_features"],
  ];
  const multiFilters = new Set(["learning_goals", "primary_topics", "format_features"]);
  const warmCoverPalettes = [
    ["#ff8a4c", "#b73700"],
    ["#ff9f43", "#c2410c"],
    ["#f59e0b", "#c2410c"],
    ["#fb923c", "#9a3412"],
  ];
  const state = {
    payload: null,
    timer: 0,
    labels: {},
    space: "discover",
    mobileFilterOpen: false,
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function formatCount(value) {
    return window.Utils?.formatNumber ? window.Utils.formatNumber(value) : String(value || 0);
  }

  function formatDate(value) {
    const date = new Date(value || "");
    return Number.isNaN(date.getTime()) ? "Không rõ" : date.toLocaleString();
  }

  function formatShortDate(value) {
    const date = new Date(value || "");
    if (Number.isNaN(date.getTime())) return "Không rõ";
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  }

  function buildUrl(template, value) {
    return String(template || "")
      .replaceAll("__ITEM_ID__", encodeURIComponent(value || ""))
      .replaceAll("__ORDER_ID__", encodeURIComponent(value || ""));
  }

  function buildStudyUrl(deckId) {
    if (!studyUrlTemplate || !deckId) return "";
    return studyUrlTemplate.replace("/0", `/${encodeURIComponent(deckId)}`);
  }

  function normalizeLabel(value) {
    return String(value || "")
      .toLowerCase()
      .replaceAll("đ", "d")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  function isGenericCardLabel(value) {
    const normalized = normalizeLabel(value);
    return [
      "",
      "general",
      "chung",
      "hoc tap",
      "seeded deck",
      "seeded note type",
      "seeded template",
    ].includes(normalized);
  }

  function dedupeLabels(values, options = {}) {
    const { exclude = [], limit = 3, allowGeneric = false } = options;
    const seen = new Set(exclude.map((value) => normalizeLabel(value)).filter(Boolean));
    const rows = [];

    (values || []).forEach((value) => {
      const text = String(value || "").trim();
      const normalized = normalizeLabel(text);
      if (!text || !normalized || seen.has(normalized)) return;
      if (!allowGeneric && isGenericCardLabel(text)) return;
      seen.add(normalized);
      rows.push(text);
    });

    return rows.slice(0, limit);
  }

  function formatBadgeLabel(badge) {
    const normalized = normalizeLabel(badge);
    if (normalized === "official") return "Chính thức";
    if (normalized === "cua ban") return "Của bạn";
    if (normalized === "da cai") return "Đã cài";
    if (normalized === "da mua") return "Đã mua";
    if (normalized === "da luu") return "Đã lưu";
    if (normalized === "mien phi") return "Miễn phí";
    return String(badge || "");
  }

  function requestJson(url, options = {}) {
    return fetch(url, options).then(async (response) => {
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.message || "Không thể hoàn tất yêu cầu.");
      }
      return data;
    });
  }

  function showError(message) {
    errorEl.textContent = message || "Không thể tải danh mục.";
    errorEl.classList.remove("d-none");
  }

  function clearError() {
    errorEl.textContent = "";
    errorEl.classList.add("d-none");
  }

  function isPhoneViewport() {
    return window.matchMedia("(max-width: 767.98px)").matches;
  }

  function setMobileFilterOpen(open) {
    const active = Boolean(open && isPhoneViewport() && state.space === "discover");
    state.mobileFilterOpen = active;
    root.classList.toggle("is-mobile-filter-open", active);
    document.body.classList.toggle("market-mobile-filter-lock", active);
    if (mobileFilterBackdropEl) {
      mobileFilterBackdropEl.hidden = !active;
    }
    if (filterSidebarEl) {
      filterSidebarEl.setAttribute("aria-hidden", active ? "false" : String(isPhoneViewport()));
    }
    if (mobileFilterToggleEl) {
      mobileFilterToggleEl.setAttribute("aria-expanded", active ? "true" : "false");
    }
  }

  function switchSpace(space) {
    state.space = space;
    setMobileFilterOpen(false);
    switchButtons.forEach((button) => {
      button.classList.toggle("is-active", button.dataset.space === space);
    });
    spacePanels.forEach((panel) => {
      const isActive = panel.dataset.spacePanel === space;
      panel.hidden = !isActive;
      panel.classList.toggle("is-active", isActive);
    });
  }

  function formatLabel(name, value) {
    return state.labels[name]?.[value] || value;
  }

  function buildEditUrl(item) {
    if (marketKind === "deck_marketplace_item" && item?.source_deck_id) {
      return editTemplate.replace("/0/share", `/${encodeURIComponent(item.source_deck_id)}/share`);
    }
    return buildUrl(editTemplate, item?.id);
  }

  function buildPaymentResultUrl(orderId, productRefId) {
    if (!paymentResultUrl || !orderId) return "";
    const url = new URL(paymentResultUrl, window.location.origin);
    url.searchParams.set("payment_order_id", orderId);
    url.searchParams.set("payment_product_type", marketKind);
    url.searchParams.set("payment_product_ref_id", productRefId || "");
    return url.toString();
  }

  function pickCoverPalette(item) {
    const title = String(item?.title || item?.name || "");
    const seed = Array.from(title).reduce((total, char) => total + char.charCodeAt(0), 0);
    const [start, end] = warmCoverPalettes[seed % warmCoverPalettes.length];
    return `--cover-start:${start};--cover-end:${end};`;
  }

  function buildCoverLabel(item) {
    return (
      (item?.level_tokens || []).slice(0, 2).join(" · ")
      || item?.framework_level_label
      || item?.difficulty_label
      || item?.subject_label
      || item?.primary_category
      || (marketKind === "deck_marketplace_item" ? "Deck" : "Note type")
    );
  }

  function buildSupportChips(item) {
    const metaChips = dedupeLabels(
      [item.subject_label, item.framework_level_label, item.difficulty_label],
      { limit: 3 },
    );
    const supportLabels = dedupeLabels(
      [
        ...(item.learning_goal_labels || []),
        ...(item.primary_topic_labels || []),
        ...(item.display_tags || []).slice(0, 2),
        item.subject_label ? "" : item.primary_category,
      ],
      { exclude: metaChips, limit: 3 },
    );
    return [...metaChips, ...supportLabels]
      .map((chip, index) => `<span class="market-support-chip ${index < metaChips.length ? "is-key" : ""}">${escapeHtml(chip)}</span>`)
      .join("");
  }

  function buildActivityLine(item, mode = "discover") {
    const parts = [];
    if (mode === "library") {
      if (item.last_activity_at) {
        parts.push(`Học gần đây ${formatShortDate(item.last_activity_at)}`);
      } else if (item.installed_at) {
        parts.push(`Đã thêm ${formatShortDate(item.installed_at)}`);
      }
      if (item.last_sync_status === "needs_sync") {
        parts.push("Có thay đổi local");
      } else if (item.last_sync_status === "has_conflict") {
        parts.push("Cần xử lý conflict");
      } else if (item.last_sync_status === "clean") {
        parts.push("Đã sync");
      }
    } else {
      if (item.subject_label) parts.push(item.subject_label);
      if (item.framework_level_label) parts.push(item.framework_level_label);
      if (!parts.length && item.primary_category) parts.push(item.primary_category);
      if (item.updated_at) parts.push(`Cập nhật ${formatShortDate(item.updated_at)}`);
    }
    return parts.join(" · ");
  }

  function renderBadges(badges = []) {
    return dedupeLabels(badges, { limit: 3, allowGeneric: true })
      .filter((badge) => normalizeLabel(badge) !== "mien phi")
      .map((badge) => `<span class="market-badge">${escapeHtml(formatBadgeLabel(badge))}</span>`)
      .join("");
  }

  function renderPrimaryButton(item, mode = "discover") {
    const detailUrl = buildUrl(detailTemplate, item.id);
    const editUrl = buildEditUrl(item);
    const action = item.primary_action || "";
    const studyUrl = item.installed_deck_id ? buildStudyUrl(item.installed_deck_id) : "";

    if (mode === "library") {
      if (marketKind === "deck_marketplace_item" && item.is_installed && studyUrl) {
        return `<a class="btn btn-primary" href="${escapeHtml(studyUrl)}">Học deck</a>`;
      }
      if (action === "order") {
        return `<a class="btn btn-primary" href="${escapeHtml(ordersUrl)}">Xem đơn hàng</a>`;
      }
      if (action === "edit") {
        return `<a class="btn btn-primary" href="${escapeHtml(editUrl)}">Chỉnh sửa</a>`;
      }
      if (!item.is_installed && action === "install") {
        return `<button class="btn btn-primary" type="button" data-action="install" data-id="${escapeHtml(item.id)}">${escapeHtml(item.primary_cta_label || "Cài đặt")}</button>`;
      }
      return `<a class="btn btn-primary" href="${escapeHtml(detailUrl)}">Mở chi tiết</a>`;
    }

    if (mode === "seller") {
      return action === "edit"
        ? `<a class="btn btn-primary" href="${escapeHtml(editUrl)}">Chỉnh sửa</a>`
        : `<a class="btn btn-primary" href="${escapeHtml(detailUrl)}">Xem chi tiết</a>`;
    }

    if (action === "edit") {
      return `<a class="btn btn-primary" href="${escapeHtml(editUrl)}">Chỉnh sửa</a>`;
    }
    if (action === "installed") {
      if (marketKind === "deck_marketplace_item" && studyUrl) {
        return `<a class="btn btn-primary" href="${escapeHtml(studyUrl)}">Học deck</a>`;
      }
      return `<a class="btn btn-outline-secondary" href="${escapeHtml(detailUrl)}">Đã cài</a>`;
    }
    if (action === "order") {
      return `<button class="btn btn-outline-secondary" type="button" data-action="orders">Xem đơn hàng</button>`;
    }
    return `<button class="btn btn-primary" type="button" data-action="install" data-id="${escapeHtml(item.id)}">${escapeHtml(item.primary_cta_label || "Thêm vào thư viện")}</button>`;
  }

  function renderSecondaryButtons(item, mode = "discover") {
    const detailUrl = buildUrl(detailTemplate, item.id);
    const actions = [];

    if (mode === "discover") {
      if (!item.is_owner) {
        actions.push(`<button class="btn btn-outline-secondary" type="button" data-action="save" data-id="${escapeHtml(item.id)}" data-saved="${item.is_saved ? "1" : "0"}">${escapeHtml(item.is_saved ? "Đã lưu" : "Lưu")}</button>`);
      }
      actions.push(`<a class="btn btn-outline-secondary" href="${escapeHtml(detailUrl)}">Chi tiết</a>`);
      return actions.join("");
    }

    if (mode === "seller") {
      actions.push(`<a class="btn btn-outline-secondary" href="${escapeHtml(detailUrl)}">Xem market</a>`);
      return actions.join("");
    }

    actions.push(`<a class="btn btn-outline-secondary" href="${escapeHtml(detailUrl)}">Chi tiết</a>`);
    if (!item.is_owner && !item.is_installed) {
      actions.push(`<button class="btn btn-outline-secondary" type="button" data-action="save" data-id="${escapeHtml(item.id)}" data-saved="${item.is_saved ? "1" : "0"}">${escapeHtml(item.is_saved ? "Đã lưu" : "Lưu")}</button>`);
    }
    return actions.join("");
  }

  function renderCard(item, mode = "discover") {
    const title = item.title || item.name || "Untitled";
    const badgeMarkup = renderBadges(item.badges || []);
    const supportChips = buildSupportChips(item);
    const activityLine = buildActivityLine(item, mode);
    const detailUrl = buildUrl(detailTemplate, item.id);
    const description = item.short_description || item.preview_text || "Chưa có mô tả ngắn.";

    return `
      <article class="market-card market-card--${escapeHtml(mode)}" data-item-id="${escapeHtml(item.id)}">
        <a class="market-card-cover" href="${escapeHtml(detailUrl)}" style="${pickCoverPalette(item)}">
          ${badgeMarkup ? `<div class="market-cover-badges">${badgeMarkup}</div>` : ""}
          <div class="market-cover-label">${escapeHtml(buildCoverLabel(item))}</div>
          <div class="market-card-cover-title">${escapeHtml(title)}</div>
        </a>
        <div class="market-card-body">
          <div class="market-card-head">
            <a class="market-card-title-link" href="${escapeHtml(detailUrl)}">
              <h3 class="market-card-title">${escapeHtml(title)}</h3>
            </a>
            <div class="market-card-meta">
              <button class="btn btn-link btn-sm p-0 align-baseline market-text-link" type="button" data-filter-author="${escapeHtml(item.author_filter_token || "")}">
                ${escapeHtml(item.author?.username || "Không rõ")}
              </button>
              <span class="market-card-meta-divider" aria-hidden="true">•</span>
              <span>${escapeHtml(item.primary_category || "General")}</span>
            </div>
          </div>
          <p class="market-card-description">${escapeHtml(description)}</p>
          ${supportChips ? `<div class="market-card-support">${supportChips}</div>` : ""}
          <div class="market-card-statbar">
            <div class="market-card-stat">
              <strong>${escapeHtml(item.price_display || "Miễn phí")}</strong>
              <span>${item.pricing_mode === "paid" ? "Giá hiện tại" : "Sẵn sàng dùng"}</span>
            </div>
            <div class="market-card-stat">
              <strong>${Number(item.rating_avg || 0).toFixed(1)}</strong>
              <span>${formatCount(item.rating_count || 0)} đánh giá</span>
            </div>
            <div class="market-card-stat">
              <strong>${formatCount(item.install_count || 0)}</strong>
              <span>${mode === "library" ? "lượt sở hữu" : "lượt cài"}</span>
            </div>
          </div>
          ${activityLine ? `<div class="market-card-summary">${escapeHtml(activityLine)}</div>` : ""}
          <div class="market-card-actions">
            ${renderPrimaryButton(item, mode)}
            ${renderSecondaryButtons(item, mode)}
          </div>
        </div>
      </article>
    `;
  }

  function renderShelf(title, kicker, items, mode, emptyText) {
    return `
      <section class="market-shelf">
        <div class="market-shelf-header">
          <div>
            <div class="market-shelf-kicker">${escapeHtml(kicker)}</div>
            <h3 class="market-hub-section-title h5 mb-0">${escapeHtml(title)}</h3>
          </div>
        </div>
        ${items?.length
          ? `<div class="market-card-grid market-card-grid--compact">${items.map((item) => renderCard(item, mode)).join("")}</div>`
          : `<div class="market-empty-state">${escapeHtml(emptyText || "Chưa có dữ liệu.")}</div>`}
      </section>
    `;
  }

  function renderSummaryCards(container, rows) {
    if (!container) return;
    container.innerHTML = rows.map((row) => `
      <article class="market-summary-card">
        <div class="market-summary-label">${escapeHtml(row[0])}</div>
        <div class="market-summary-value">${escapeHtml(row[1])}</div>
        <div class="market-summary-help">${escapeHtml(row[2])}</div>
      </article>
    `).join("");
  }

  function collectFilters() {
    const params = new URLSearchParams();
    const formData = new FormData(filterForm);
    const multiValues = {};

    for (const [key, rawValue] of formData.entries()) {
      const value = String(rawValue || "").trim();
      if (!value) continue;
      if (multiFilters.has(key)) {
        multiValues[key] = multiValues[key] || [];
        multiValues[key].push(value);
      } else {
        params.set(key, value);
      }
    }

    Object.entries(multiValues).forEach(([key, values]) => {
      params.set(key, Array.from(new Set(values)).join(","));
    });
    return params;
  }

  function setFormValue(name, value) {
    const control = filterForm?.elements?.namedItem(name);
    if (!control) return;
    if (control instanceof RadioNodeList) {
      control.value = value;
    } else if ("value" in control) {
      control.value = value;
    }
  }

  function hydrateStaticFilters(payload) {
    const filters = payload.filters || {};
    ["q", "author", "sort", "pricing_mode", "has_preview", "min_rating", "min_price", "max_price"].forEach((name) => {
      setFormValue(name, filters[name] || "");
    });
  }

  function buildLabelMaps(schema = {}) {
    const frameworkLevels = {};
    const frameworkTracks = {};

    Object.values(schema.subject_packs || {}).forEach((pack) => {
      (pack.frameworks || []).forEach((framework) => {
        (framework.levels || []).forEach((row) => {
          frameworkLevels[row.id] = row.label || row.id;
        });
        (framework.tracks || []).forEach((row) => {
          frameworkTracks[row.id] = row.label || row.id;
        });
      });
    });

    state.labels = {
      domain: Object.fromEntries((schema.domains || []).map((row) => [row.id, row.label])),
      subject: Object.fromEntries((schema.subjects || []).map((row) => [row.id, row.label])),
      difficulty_band: Object.fromEntries((schema.difficulty_bands || []).map((row) => [row.id, row.label])),
      audience: Object.fromEntries((schema.audiences || []).map((row) => [row.id, row.label])),
      learning_goals: Object.fromEntries((schema.learning_goals || []).map((row) => [row.id, row.label])),
      primary_topics: Object.fromEntries((schema.primary_topics || []).map((row) => [row.id, row.label])),
      format_features: Object.fromEntries((schema.format_features || []).map((row) => [row.id, row.label])),
      framework_level: frameworkLevels,
      framework_track: frameworkTracks,
      pricing_mode: { free: "Miễn phí", paid: "Trả phí" },
      has_preview: { yes: "Có bản xem thử", no: "Chưa có bản xem thử" },
    };
  }

  function renderFilterGroup(container, config, values, activeValues) {
    if (!container) return;
    const rows = (values || []).filter(Boolean);
    if (!rows.length) {
      container.classList.add("d-none");
      container.innerHTML = "";
      return;
    }

    container.classList.remove("d-none");
    const selected = new Set(Array.isArray(activeValues) ? activeValues.map(String) : [String(activeValues || "")].filter(Boolean));
    const allOption = config[2] === "radio"
      ? `<label class="market-filter-check"><input class="form-check-input" type="radio" name="${escapeHtml(config[0])}" value="" ${selected.size ? "" : "checked"}><span>Tất cả</span></label>`
      : "";

    container.innerHTML = `
      <div class="market-filter-group-title">${escapeHtml(config[1])}</div>
      <div class="market-filter-option-list">
        ${allOption}
        ${rows.map((value) => `
          <label class="market-filter-check">
            <input class="form-check-input" type="${config[2]}" name="${escapeHtml(config[0])}" value="${escapeHtml(value)}" ${selected.has(String(value)) ? "checked" : ""}>
            <span>${escapeHtml(formatLabel(config[0], value))}</span>
          </label>
        `).join("")}
      </div>
    `;
  }

  function renderSidebarFilters(payload) {
    const available = payload.available_filters || {};
    const filters = payload.filters || {};
    filterConfigs.forEach((config) => {
      renderFilterGroup(
        root.querySelector(`[data-filter-group="${config[0]}"]`),
        config,
        available[config[3]] || [],
        filters[config[0]],
      );
    });
  }

  function collectActiveChips(filters = {}) {
    const rows = [];
    if (filters.q) rows.push(["q", filters.q, `Tìm: ${filters.q}`]);
    if (filters.author) rows.push(["author", filters.author, `Tác giả: ${filters.author}`]);

    ["pricing_mode", "has_preview", "domain", "subject", "difficulty_band", "framework_level", "framework_track", "audience"].forEach((name) => {
      if (filters[name]) rows.push([name, filters[name], formatLabel(name, filters[name])]);
    });

    ["learning_goals", "primary_topics", "format_features"].forEach((name) => {
      (filters[name] || []).forEach((value) => {
        rows.push([name, value, formatLabel(name, value)]);
      });
    });
    if (filters.min_rating) rows.push(["min_rating", String(filters.min_rating), `Từ ${filters.min_rating} sao`]);
    if (filters.min_price != null) rows.push(["min_price", String(filters.min_price), `Giá từ ${formatCount(filters.min_price)}`]);
    if (filters.max_price != null) rows.push(["max_price", String(filters.max_price), `Giá đến ${formatCount(filters.max_price)}`]);
    return rows;
  }

  function hasActiveFilters(payload) {
    return collectActiveChips(payload?.filters || {}).length > 0;
  }

  function renderHeroSummary(payload) {
    const summary = payload.summary || {};
    const marketLabel = marketKind === "deck_marketplace_item" ? "Deck công khai" : "Note type công khai";
    const libraryLabel = marketKind === "deck_marketplace_item" ? "Deck trong thư viện" : "Template trong thư viện";
    renderSummaryCards(heroSummaryEl, [
      [marketLabel, formatCount(summary.market_count || 0), "Sẵn sàng để khám phá từ hub market hiện tại."],
      [libraryLabel, formatCount(summary.library_count || 0), "Nội dung bạn đã sở hữu hoặc đã cài gần đây."],
      ["Đã lưu", formatCount(summary.saved_count || 0), "Danh sách quay lại sau khi chưa muốn cài ngay."],
      ["Nội dung của bạn", formatCount(summary.seller_count || 0), "Các mục bạn đã chia sẻ hoặc đang quản lý."],
    ]);
  }

  function renderAppliedFilters(payload) {
    const chips = collectActiveChips(payload.filters || {});
    appliedFiltersEl.innerHTML = chips.length
      ? chips.map((chip) => `<button class="market-inline-chip" type="button" data-remove-filter="${escapeHtml(chip[0])}" data-remove-value="${escapeHtml(chip[1])}">${escapeHtml(chip[2])} <span aria-hidden="true">x</span></button>`).join("")
      : `<span class="market-applied-placeholder">Chưa áp dụng bộ lọc.</span>`;
  }

  function renderQuickFilters(payload) {
    const available = payload.available_filters || {};
    const filters = payload.filters || {};
    const rows = [];

    (available.subjects || []).slice(0, 4).forEach((value) => {
      rows.push(["subject", value, formatLabel("subject", value), filters.subject === value]);
    });
    (available.levels || []).slice(0, 3).forEach((value) => {
      rows.push(["difficulty_band", value, formatLabel("difficulty_band", value), filters.difficulty_band === value]);
    });
    (available.learning_goals || []).slice(0, 6).forEach((value) => {
      rows.push(["learning_goals", value, formatLabel("learning_goals", value), (filters.learning_goals || []).includes(value)]);
    });

    quickFiltersEl.innerHTML = rows.map((row) => `
      <button class="market-inline-chip ${row[3] ? "is-active" : ""}" type="button" data-quick-filter-name="${escapeHtml(row[0])}" data-quick-filter-value="${escapeHtml(row[1])}">
        ${escapeHtml(row[2])}
      </button>
    `).join("");
  }

  function renderFeaturedStage(payload) {
    if (!featuredStageEl) return;
    const heroItem = payload?.discovery?.hero || payload?.marketplace?.items?.[0];
    if (!heroItem || hasActiveFilters(payload)) {
      featuredStageEl.classList.add("d-none");
      featuredStageEl.innerHTML = "";
      return;
    }

    const badgeMarkup = renderBadges(heroItem.badges || []);
    const supportChips = buildSupportChips(heroItem);
    const detailUrl = buildUrl(detailTemplate, heroItem.id);
    const activityLine = buildActivityLine(heroItem, "discover");

    featuredStageEl.classList.remove("d-none");
    featuredStageEl.innerHTML = `
      <article class="market-featured-card market-featured-card--hero">
        <a class="market-featured-cover" href="${escapeHtml(detailUrl)}" style="${pickCoverPalette(heroItem)}">
          ${badgeMarkup ? `<div class="market-cover-badges">${badgeMarkup}</div>` : ""}
          <div class="market-cover-label">${escapeHtml(buildCoverLabel(heroItem))}</div>
          <div class="market-cover-title">${escapeHtml(heroItem.title || heroItem.name || "Untitled")}</div>
        </a>

        <div class="market-featured-body">
          <div>
            <div class="market-hub-section-kicker">Nổi bật</div>
            <h2 class="market-featured-title">${escapeHtml(heroItem.title || heroItem.name || "Untitled")}</h2>
            <p class="market-featured-meta mb-0">${escapeHtml(heroItem.preview_text || heroItem.short_description || "Đã chọn từ các mục nổi bật nhất trong marketplace hiện tại.")}</p>
          </div>

          <div class="market-featured-support">
            ${supportChips || `<span class="market-support-chip is-key">${escapeHtml(heroItem.primary_category || "General")}</span>`}
          </div>

          <div class="market-featured-statline">
            <div class="market-featured-stat">
              <strong>${escapeHtml(heroItem.price_display || "Miễn phí")}</strong>
              <span>${heroItem.pricing_mode === "paid" ? "Giá hiện tại" : "Có thể cài ngay"}</span>
            </div>
            <div class="market-featured-stat">
              <strong>${Number(heroItem.rating_avg || 0).toFixed(1)}</strong>
              <span>${formatCount(heroItem.rating_count || 0)} đánh giá</span>
            </div>
            <div class="market-featured-stat">
              <strong>${formatCount(heroItem.install_count || 0)}</strong>
              <span>lượt cài đặt</span>
            </div>
          </div>

          ${activityLine ? `<div class="market-card-summary">${escapeHtml(activityLine)}</div>` : ""}

          <div class="market-featured-actions">
            ${renderPrimaryButton(heroItem, "discover")}
            ${renderSecondaryButtons(heroItem, "discover")}
          </div>
        </div>
      </article>
    `;

    if (heroNoteEl) {
      heroNoteEl.textContent = heroItem.preview_text || "Mục nổi bật được chọn dựa trên hiệu suất, khả năng học nhanh và độ phù hợp với người dùng Flama.";
    }
  }

  function renderDiscoverShelves(payload) {
    if (!discoveryShelvesEl) return;
    if (hasActiveFilters(payload)) {
      discoveryShelvesEl.classList.add("d-none");
      discoveryShelvesEl.innerHTML = "";
      return;
    }

    const discovery = payload.discovery || {};
    const sections = [];
    if ((discovery.recommended || []).length) {
      sections.push(renderShelf("Gợi ý cho bạn", "Phù hợp", discovery.recommended.slice(0, 4), "discover", "Chưa có gợi ý phù hợp."));
    }
    if ((discovery.new_releases || []).length) {
      sections.push(renderShelf("Mới cập nhật", "Cập nhật", discovery.new_releases.slice(0, 4), "discover", "Chưa có nội dung mới."));
    }
    if ((discovery.best_sellers || []).length) {
      sections.push(renderShelf("Được cài nhiều", "Phổ biến", discovery.best_sellers.slice(0, 4), "discover", "Chưa có bestseller."));
    }

    if (!sections.length) {
      discoveryShelvesEl.classList.add("d-none");
      discoveryShelvesEl.innerHTML = "";
      return;
    }

    discoveryShelvesEl.classList.remove("d-none");
    discoveryShelvesEl.innerHTML = sections.join("");
  }

  function renderLibrarySpotlight(payload) {
    const items = [...((payload.library?.using_now || []).slice(0, 2)), ...((payload.library?.installed || []).slice(0, 2))].slice(0, 4);
    if (!items.length) {
      librarySpotlightEl.classList.add("d-none");
      librarySpotlightEl.innerHTML = "";
      return;
    }

    librarySpotlightEl.classList.remove("d-none");
    librarySpotlightEl.innerHTML = `
      <div class="market-shelf-header">
        <div>
          <div class="market-shelf-kicker">Từ thư viện của bạn</div>
          <h2 class="market-hub-section-title h5 mb-1">Tiếp tục nhanh từ nội dung đã cài</h2>
          <p class="market-section-help mb-0">Đưa các mục bạn đang học hoặc vừa cài lại gần hơn với vùng khám phá.</p>
        </div>
        ${libraryUrl ? `<a class="btn btn-outline-secondary btn-sm" href="${escapeHtml(libraryUrl)}">Mở thư viện chi tiết</a>` : ""}
      </div>
      <div class="market-card-grid market-card-grid--compact">${items.map((item) => renderCard(item, "library")).join("")}</div>
    `;
  }

  function renderPurchaseHistory(rows = []) {
    if (!rows.length) {
      return `<div class="market-empty-state">Chưa có đơn hàng phù hợp.</div>`;
    }

    return `
      <section class="market-purchase-list">
        <div class="market-shelf-header">
          <div>
            <div class="market-shelf-kicker">Lịch sử giao dịch</div>
            <h3 class="market-hub-section-title h5 mb-0">Lịch sử mua</h3>
          </div>
        </div>
        ${rows.map((row) => `
          <div class="market-purchase-row">
            <div>
              <div class="market-purchase-title">${escapeHtml(row.title || "Đơn hàng")}</div>
              <div class="market-purchase-meta">${escapeHtml(row.product_type_label || "")} | ${escapeHtml(row.status_label || "")} | ${escapeHtml(row.total_amount_display || "")}</div>
              <div class="market-purchase-meta">Tạo lúc ${escapeHtml(formatDate(row.created_at))}</div>
            </div>
            <div class="market-card-actions">
              <a class="btn btn-outline-secondary" href="${escapeHtml(buildUrl(orderDetailTemplate, row.order_id))}">Xem đơn</a>
              <a class="btn btn-primary" href="${escapeHtml(buildUrl(detailTemplate, row.product_ref_id))}">Mở nội dung</a>
            </div>
          </div>
        `).join("")}
      </section>
    `;
  }

  function renderSellerFeedback(rows = []) {
    if (!rows.length) {
      return `<div class="market-empty-state">Chưa có phản hồi mới.</div>`;
    }

    return `
      <section class="market-feedback-list">
        <div class="market-shelf-header">
          <div>
            <div class="market-shelf-kicker">Phản hồi mới</div>
            <h3 class="market-hub-section-title h5 mb-0">Phản hồi gần đây</h3>
          </div>
        </div>
        ${rows.map((row) => `
          <div class="market-feedback-row">
            <div>
              <div class="market-feedback-title">${escapeHtml(row.title || "Sản phẩm")}</div>
              <div class="market-feedback-meta">${escapeHtml(row.username || "Người dùng")} | ${escapeHtml(String(row.rating || 0))}/5 | ${escapeHtml(formatDate(row.updated_at))}</div>
              <div class="market-feedback-meta mt-1">${escapeHtml(row.comment || "Người dùng chưa để lại nhận xét.")}</div>
            </div>
            <a class="btn btn-outline-secondary" href="${escapeHtml(buildUrl(detailTemplate, row.item_id))}">Mở chi tiết</a>
          </div>
        `).join("")}
      </section>
    `;
  }

  function renderDiscover(payload) {
    const items = payload.marketplace?.items || [];
    resultsCountEl.textContent = `${formatCount(payload.marketplace?.result_count || items.length)} mục`;
    renderHeroSummary(payload);
    renderQuickFilters(payload);
    renderAppliedFilters(payload);
    renderFeaturedStage(payload);
    renderLibrarySpotlight(payload);
    renderDiscoverShelves(payload);
    resultsEl.innerHTML = items.length
      ? items.map((item) => renderCard(item, "discover")).join("")
      : `<div class="market-empty-state">Không tìm thấy nội dung phù hợp với bộ lọc hiện tại.</div>`;
  }

  function renderLibrary(payload) {
    const summary = payload.library?.summary || {};
    renderSummaryCards(librarySummaryEl, [
      ["Đang học", formatCount(summary.using_count || 0), "Các mục bạn vừa quay lại gần đây và nên tiếp tục."],
      ["Đã sở hữu", formatCount(summary.owned_count || 0), "Đã cài hoặc đã mua nhưng chưa cài vào workspace."],
      ["Đã lưu", formatCount(summary.saved_count || 0), "Các mục chờ quyết định hoặc quay lại sau."],
      ["Đơn hàng", formatCount(summary.purchase_count || 0), "Lịch sử giao dịch gắn với marketplace hiện tại."],
    ]);

    librarySectionsEl.innerHTML = [
      renderShelf("Đang học gần đây", "Tiếp tục", payload.library?.using_now || [], "library", "Bạn chưa có nội dung đang học."),
      renderShelf("Đã cài", "Đã cài", payload.library?.installed || [], "library", "Chưa có nội dung đã cài."),
      renderShelf("Đã mua chưa cài", "Đã mua", payload.library?.not_installed || [], "library", "Không có nội dung chờ cài đặt."),
      renderShelf("Đã lưu", "Đã lưu", payload.library?.saved || [], "library", "Danh sách lưu đang trống."),
      renderPurchaseHistory(payload.library?.purchase_history || []),
    ].join("");
  }

  function renderSeller(payload) {
    const sellerSummaryEl = document.getElementById("marketplace-seller-summary");
    const sellerSectionsEl = document.getElementById("marketplace-seller-sections");
    if (!sellerSummaryEl || !sellerSectionsEl) return;
    const summary = payload.seller?.summary || {};
    renderSummaryCards(sellerSummaryEl, [
      ["Tổng mục chia sẻ", formatCount(summary.total_listings || 0), "Tất cả mục chia sẻ thuộc tài khoản của bạn."],
      ["Đang công khai", formatCount(summary.published_count || 0), "Đang hiển thị trong danh mục công khai."],
      ["Người dùng hoạt động", formatCount(summary.active_usage_count || 0), "Số người đang dùng nội dung của bạn."],
      ["Điểm trung bình", Number(summary.avg_rating || 0).toFixed(1), `${formatCount(summary.rating_count || 0)} lượt đánh giá.`],
    ]);

    sellerSectionsEl.innerHTML = [
      renderShelf("Đang công khai", "Công khai", payload.seller?.published || [], "seller", "Bạn chưa có mục chia sẻ công khai."),
      renderShelf("Bản nháp", "Nháp", payload.seller?.drafts || [], "seller", "Không có bản nháp nào."),
      renderShelf("Lưu trữ", "Lưu trữ", payload.seller?.archived || [], "seller", "Không có mục lưu trữ."),
      renderSellerFeedback(payload.seller?.recent_feedback || []),
    ].join("");
  }

  function renderAll(payload) {
    state.payload = payload;
    buildLabelMaps(payload.taxonomy_schema || {});
    hydrateStaticFilters(payload);
    renderSidebarFilters(payload);
    renderDiscover(payload);
    renderLibrary(payload);
    renderSeller(payload);
  }

  async function loadHub() {
    clearError();
    const params = collectFilters();
    const query = params.toString();
    const payload = await requestJson(query ? `${hubUrl}?${query}` : hubUrl);
    renderAll(payload);
  }

  async function installItem(itemId) {
    const response = await requestJson(buildUrl(installTemplate, itemId), { method: "POST" });
    if (response?.payment_required && response?.order) {
      const checkoutUrl = response?.order?.active_attempt?.checkout?.checkout_url || response?.order?.active_attempt?.checkout_url;
      if (checkoutUrl && response?.order?.status === "pending_payment") {
        window.location.href = checkoutUrl;
        return;
      }
      window.location.href = buildPaymentResultUrl(response?.order?.id || "", itemId) || ordersUrl;
      return;
    }
    await loadHub();
  }

  async function saveItem(itemId, isSaved) {
    await requestJson(buildUrl(saveTemplate, itemId), { method: isSaved ? "DELETE" : "POST" });
    await loadHub();
  }

  function queueReload() {
    window.clearTimeout(state.timer);
    state.timer = window.setTimeout(() => {
      loadHub().catch((error) => showError(error.message));
    }, 180);
  }

  function clearNamedFilter(name, value) {
    const inputs = Array.from(filterForm.querySelectorAll(`[name="${name}"]`));
    inputs.forEach((input) => {
      if (input.type === "radio") {
        if (!value) {
          input.checked = input.value === "";
        } else if (input.value === value) {
          const allInput = inputs.find((row) => row.value === "");
          if (allInput) allInput.checked = true;
        }
      } else if (input.type === "checkbox") {
        if (!value || input.value === value) input.checked = false;
      } else if ("value" in input) {
        input.value = "";
      }
    });
  }

  function toggleQuickFilter(name, value) {
    const inputs = Array.from(filterForm.querySelectorAll(`[name="${name}"]`));
    const target = inputs.find((input) => input.value === value);
    if (!target) return;
    if (target.type === "checkbox") {
      target.checked = !target.checked;
    } else if (target.checked) {
      const allInput = inputs.find((input) => input.value === "");
      if (allInput) allInput.checked = true;
    } else {
      target.checked = true;
    }
  }

  switchButtons.forEach((button) => {
    button.addEventListener("click", () => switchSpace(button.dataset.space || "discover"));
  });

  mobileFilterToggleEl?.addEventListener("click", () => {
    setMobileFilterOpen(!state.mobileFilterOpen);
  });

  root.querySelectorAll("[data-mobile-filter-close]").forEach((button) => {
    button.addEventListener("click", () => setMobileFilterOpen(false));
  });

  window.addEventListener("resize", () => {
    if (!isPhoneViewport()) {
      setMobileFilterOpen(false);
      if (filterSidebarEl) {
        filterSidebarEl.setAttribute("aria-hidden", "false");
      }
      return;
    }
    if (filterSidebarEl && !state.mobileFilterOpen) {
      filterSidebarEl.setAttribute("aria-hidden", "true");
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.mobileFilterOpen) {
      setMobileFilterOpen(false);
    }
  });

  filterForm?.addEventListener("input", queueReload);
  filterForm?.addEventListener("change", queueReload);
  filterForm?.addEventListener("reset", () => {
    window.setTimeout(() => loadHub().catch((error) => showError(error.message)), 0);
  });

  root.addEventListener("click", (event) => {
    const installButton = event.target.closest('[data-action="install"]');
    if (installButton) {
      installItem(installButton.dataset.id).catch((error) => showError(error.message));
      return;
    }

    const saveButton = event.target.closest('[data-action="save"]');
    if (saveButton) {
      saveItem(saveButton.dataset.id, saveButton.dataset.saved === "1").catch((error) => showError(error.message));
      return;
    }

    const editButton = event.target.closest('[data-action="edit"]');
    if (editButton) {
      window.location.href = editButton.dataset.editUrl || ordersUrl;
      return;
    }

    const ordersButton = event.target.closest('[data-action="orders"]');
    if (ordersButton) {
      window.location.href = ordersUrl;
      return;
    }

    const authorButton = event.target.closest("[data-filter-author]");
    if (authorButton) {
      setFormValue("author", authorButton.dataset.filterAuthor || "");
      switchSpace("discover");
      loadHub().catch((error) => showError(error.message));
      return;
    }

    const removeButton = event.target.closest("[data-remove-filter]");
    if (removeButton) {
      clearNamedFilter(removeButton.dataset.removeFilter || "", removeButton.dataset.removeValue || "");
      loadHub().catch((error) => showError(error.message));
      return;
    }

    const quickButton = event.target.closest("[data-quick-filter-name]");
    if (quickButton) {
      toggleQuickFilter(quickButton.dataset.quickFilterName || "", quickButton.dataset.quickFilterValue || "");
      loadHub().catch((error) => showError(error.message));
      return;
    }

    const sellerButton = event.target.closest("[data-space-action='seller']");
    if (sellerButton) {
      switchSpace("seller");
    }
  });

  switchSpace("discover");
  loadHub().catch((error) => showError(error.message));
}
