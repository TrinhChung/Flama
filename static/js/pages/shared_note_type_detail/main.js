const root = document.getElementById("shared-note-type-detail-root");

if (root) {
  const noteTypeId = root.dataset.noteTypeId || "";
  const marketUrl = root.dataset.marketUrl || "/";
  const ordersUrl = root.dataset.ordersUrl || "/";
  const saveUrlTemplate = root.dataset.saveUrlTemplate || "";
  const paymentResultUrl = root.dataset.paymentResultUrl || "";

  const refs = {
    error: document.getElementById("detail-error"),
    errorMessage: document.getElementById("detail-error-message"),
    retry: document.getElementById("detail-retry-btn"),
    status: document.getElementById("detail-status"),
    title: document.getElementById("nt-title-secondary"),
    previewText: document.getElementById("nt-preview-text"),
    meta: document.getElementById("nt-meta-line"),
    description: document.getElementById("nt-description"),
    badges: document.getElementById("nt-badges"),
    tags: document.getElementById("nt-tags"),
    price: document.getElementById("nt-price-display"),
    rating: document.getElementById("nt-hero-rating"),
    installs: document.getElementById("nt-hero-installs"),
    updated: document.getElementById("nt-hero-updated"),
    fieldCount: document.getElementById("nt-field-count"),
    templateCount: document.getElementById("nt-template-count"),
    version: document.getElementById("nt-version"),
    structureSummary: document.getElementById("nt-structure-summary"),
    fieldList: document.getElementById("nt-field-list"),
    changelogWrap: document.getElementById("nt-changelog-wrap"),
    changelog: document.getElementById("nt-changelog"),
    authorName: document.getElementById("author-name"),
    authorSummary: document.getElementById("author-summary"),
    authorStoreLink: document.getElementById("author-store-link"),
    relatedSection: document.getElementById("related-section"),
    relatedItems: document.getElementById("nt-related-items"),
    communityReviews: document.getElementById("nt-community-reviews"),
    install: document.getElementById("install-btn"),
    save: document.getElementById("save-btn"),
    edit: document.getElementById("edit-btn"),
    myReview: document.getElementById("my-review"),
    ratingFieldset: document.getElementById("rating-fieldset"),
    ratingValue: document.getElementById("rating-value"),
    ratingComment: document.getElementById("rating-comment"),
    ratingHint: document.getElementById("rating-hint"),
    ratingSubmit: document.getElementById("rating-submit-btn"),
    ratingStars: document.getElementById("rating-stars"),
    ratingValueLabel: document.getElementById("rating-value-label"),
    templateSelect: document.getElementById("template-select"),
    previewFrame: document.getElementById("template-preview-frame"),
    previewStage: document.getElementById("preview-stage"),
    previewLoading: document.getElementById("preview-loading"),
    front: document.getElementById("preview-side-front"),
    back: document.getElementById("preview-side-back"),
    paymentPanel: document.getElementById("payment-order-panel"),
  };
  const ratingStarButtons = Array.from(refs.ratingStars?.querySelectorAll(".shared-rating-star") || []);
  const rendererHost = window.FlamaCardRendererHost;
  const frameController = refs.previewFrame && rendererHost
    ? rendererHost.createRendererFrameController(refs.previewFrame, {
        minHeight: 480,
      })
    : null;

  const state = {
    detail: null,
    selectedTemplateId: "",
    previewSide: "front",
    previewPayload: null,
    detailController: null,
    previewController: null,
    pendingAction: "",
  };

  const fieldTypeLabels = {
    text: "Văn bản",
    richtext: "Văn bản định dạng",
    markdown: "Markdown",
    number: "Số",
    image: "Hình ảnh",
    audio: "Âm thanh",
    diagram: "Sơ đồ",
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function requestJson(url, options = {}) {
    return fetch(url, options).then(async (response) => {
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(
          data.message
          || (response.status >= 500
            ? "Máy chủ đang bận hoặc tạm thời không phản hồi."
            : "Không thể hoàn tất yêu cầu."),
        );
      }
      return data;
    });
  }

  function formatCount(value) {
    return window.Utils?.formatNumber ? window.Utils.formatNumber(value) : String(value || 0);
  }

  function formatDate(value) {
    const date = new Date(value || "");
    if (Number.isNaN(date.getTime())) return "Không rõ";
    return date.toLocaleDateString("vi-VN", { day: "numeric", month: "short", year: "numeric" });
  }

  function buildUrl(template, itemId) {
    return String(template || "").replaceAll("__ITEM_ID__", encodeURIComponent(itemId || ""));
  }

  function announce(message) {
    if (refs.status) refs.status.textContent = message || "";
  }

  function showError(message) {
    refs.errorMessage.textContent = message || "Không thể tải dữ liệu.";
    refs.error.classList.remove("d-none");
  }

  function clearError() {
    refs.errorMessage.textContent = "";
    refs.error.classList.add("d-none");
  }

  function setPageBusy(busy) {
    root.setAttribute("aria-busy", busy ? "true" : "false");
    root.classList.toggle("is-loading", busy);
  }

  function setPreviewBusy(busy) {
    refs.previewStage?.setAttribute("aria-busy", busy ? "true" : "false");
    refs.previewLoading.hidden = !busy;
    refs.templateSelect.disabled = busy || !state.selectedTemplateId;
    refs.front.disabled = busy || !state.selectedTemplateId;
    refs.back.disabled = busy || !state.selectedTemplateId;
  }

  function setButtonBusy(button, busy, label) {
    if (!button) return;
    if (busy) {
      button.dataset.originalHtml = button.innerHTML;
      button.innerHTML = `<span class="spinner-border spinner-border-sm" aria-hidden="true"></span>${escapeHtml(label || "Đang xử lý")}`;
    } else if (button.dataset.originalHtml) {
      button.innerHTML = button.dataset.originalHtml;
      delete button.dataset.originalHtml;
    }
    button.disabled = busy;
    button.setAttribute("aria-busy", busy ? "true" : "false");
  }

  function normalizeBadgeLabel(value) {
    const label = String(value || "").trim();
    const normalized = label.toLowerCase();
    if (normalized === "official") return "Chính thức";
    if (normalized === "cua ban") return "Của bạn";
    if (normalized === "mien phi") return "Miễn phí";
    if (normalized === "installed") return "Đã cài";
    if (normalized === "saved") return "Đã lưu";
    if (normalized === "free") return "Miễn phí";
    return label;
  }

  function renderBadges(badges = []) {
    const labels = Array.from(new Set(badges.map(normalizeBadgeLabel).filter(Boolean))).slice(0, 3);
    refs.badges.innerHTML = labels.map((label) => `<span class="market-badge">${escapeHtml(label)}</span>`).join("");
    refs.badges.hidden = !labels.length;
  }

  function renderTagList(tags = []) {
    const labels = Array.from(new Set(tags.map((tag) => String(tag || "").trim()).filter(Boolean))).slice(0, 8);
    refs.tags.innerHTML = labels.map((tag) => `<span class="market-support-chip">${escapeHtml(tag)}</span>`).join("");
    refs.tags.hidden = !labels.length;
  }

  function renderFields(fields = [], templates = []) {
    refs.fieldCount.textContent = formatCount(fields.length);
    refs.templateCount.textContent = formatCount(templates.length);
    refs.structureSummary.textContent = `${formatCount(fields.length)} trường · ${formatCount(templates.length)} kiểu thẻ`;

    if (!fields.length) {
      refs.fieldList.innerHTML = `
        <div class="market-empty-state market-structure-empty">
          <i class="bi bi-card-text" aria-hidden="true"></i>
          Chưa có thông tin cấu trúc trường dữ liệu.
        </div>`;
      return;
    }

    refs.fieldList.innerHTML = fields.map((field) => {
      const type = fieldTypeLabels[field.field_type] || field.field_type || "Văn bản";
      return `
        <article class="market-field-row">
          <span class="market-field-icon" aria-hidden="true"><i class="bi bi-braces"></i></span>
          <div>
            <strong>${escapeHtml(field.name || "Trường chưa đặt tên")}</strong>
            <span>${escapeHtml(type)}</span>
          </div>
          <span class="market-field-required${field.required ? " is-required" : ""}">${field.required ? "Bắt buộc" : "Tùy chọn"}</span>
        </article>`;
    }).join("");
  }

  function renderRelatedItems(items = []) {
    if (!items.length) {
      refs.relatedSection.hidden = true;
      refs.relatedItems.innerHTML = "";
      return;
    }
    refs.relatedSection.hidden = false;
    refs.relatedItems.innerHTML = items.slice(0, 4).map((item) => `
      <a class="market-related-item" href="${escapeHtml(`${marketUrl.replace(/\/$/, "")}/${encodeURIComponent(item.id)}`)}">
        <span class="market-related-copy">
          <strong>${escapeHtml(item.title || item.name || "Mẫu thẻ")}</strong>
          <small>${escapeHtml(item.price_display || "Miễn phí")} · ${Number(item.rating_avg || 0).toFixed(1)} sao</small>
        </span>
        <i class="bi bi-arrow-up-right" aria-hidden="true"></i>
      </a>
    `).join("");
  }

  function renderReviews(reviews = []) {
    if (!reviews.length) {
      refs.communityReviews.innerHTML = `
        <div class="market-empty-state market-review-empty">
          <i class="bi bi-chat-square-heart" aria-hidden="true"></i>
          <strong>Chưa có đánh giá cộng đồng</strong>
          <span>Đánh giá đầu tiên sẽ xuất hiện sau khi người học cài và sử dụng mẫu thẻ.</span>
        </div>`;
      return;
    }
    refs.communityReviews.innerHTML = reviews.map((review) => {
      const rating = Math.max(1, Math.min(5, Number(review.rating || 0)));
      return `
        <article class="market-review-item">
          <div class="market-review-item-head">
            <strong>${escapeHtml(review.username || "Người học")}</strong>
            <span>${escapeHtml(formatDate(review.updated_at))}</span>
          </div>
          <div class="market-review-stars" aria-label="${rating} trên 5 sao"><span aria-hidden="true">${"★".repeat(rating)}${"☆".repeat(5 - rating)}</span></div>
          <p>${escapeHtml(review.comment || "Người dùng chưa để lại nhận xét.")}</p>
        </article>`;
    }).join("");
  }

  function renderAuthorProfile(profile = {}) {
    const username = state.detail?.author?.username || profile.username || "Không rõ";
    refs.authorName.textContent = username;
    const publishedCount = Number(profile.published_count || 0);
    const averageRating = Number(profile.avg_rating || 0);
    const summaryParts = [];
    if (publishedCount > 0) summaryParts.push(`${formatCount(publishedCount)} mẫu công khai`);
    if (averageRating > 0) summaryParts.push(`${averageRating.toFixed(1)} sao`);
    refs.authorSummary.textContent = summaryParts.join(" · ") || "Tác giả trên Flama";
    refs.authorStoreLink.href = `${marketUrl}?author=${encodeURIComponent(username)}`;
  }

  function previewNotice(message) {
    return rendererHost?.createNoticeHtml(message) || `<div>${escapeHtml(message)}</div>`;
  }

  function previewFrameHeight() {
    const compactViewport = window.matchMedia("(max-width: 767px)").matches;
    if (state.previewSide === "back") return 720;
    return compactViewport ? 480 : 520;
  }

  function renderPreviewFrame() {
    const sidePayload = state.previewSide === "back"
      ? (state.previewPayload?.back_renderer_payload || state.previewPayload?.back_html || "")
      : (state.previewPayload?.front_renderer_payload || state.previewPayload?.front_html || "");
    frameController?.render(sidePayload || previewNotice("Chưa có nội dung xem trước."), {
      padding: "0",
      background: "#fff7f0",
      color: "#1f1a17",
      placeholderHeight: previewFrameHeight(),
      config: {
        mode: "shared_note_type_preview",
        heightMeasurement: "content-root",
        side: state.previewSide,
        noteTypeId,
        templateId: state.selectedTemplateId,
      },
      revealOnReady: { side: state.previewSide, reason: "preview_render" },
    });
  }

  function renderPreviewControls(templates = []) {
    const rows = templates.slice().sort((a, b) => Number(a.position || 0) - Number(b.position || 0));
    refs.templateSelect.innerHTML = "";
    if (!rows.length) {
      refs.templateSelect.innerHTML = `<option value="">Không có kiểu thẻ</option>`;
      state.selectedTemplateId = "";
      refs.templateSelect.disabled = true;
      return;
    }
    rows.forEach((template) => {
      const option = document.createElement("option");
      option.value = template.id;
      option.textContent = template.is_default ? `${template.name} · Mặc định` : template.name;
      refs.templateSelect.appendChild(option);
    });
    if (!rows.some((template) => template.id === state.selectedTemplateId)) {
      state.selectedTemplateId = rows[0].id;
    }
    refs.templateSelect.value = state.selectedTemplateId;
    refs.previewFrame.title = `Bản xem trước ${refs.templateSelect.selectedOptions[0]?.textContent || "mẫu thẻ"}`;
    refs.templateSelect.disabled = false;
  }

  function renderPreviewSide() {
    [refs.front, refs.back].forEach((button) => {
      const active = button.dataset.side === state.previewSide;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    renderPreviewFrame();
  }

  function normalizeRatingValue(value) {
    const parsed = Number(value);
    if (!Number.isInteger(parsed)) return 5;
    return Math.max(1, Math.min(5, parsed));
  }

  function paintRatingStars(value) {
    const selected = normalizeRatingValue(value);
    ratingStarButtons.forEach((button) => {
      const buttonValue = Number(button.dataset.value || 0);
      button.classList.toggle("is-active", buttonValue <= selected);
      button.setAttribute("aria-checked", buttonValue === selected ? "true" : "false");
      button.tabIndex = buttonValue === selected ? 0 : -1;
    });
    refs.ratingValue.value = String(selected);
    refs.ratingValueLabel.textContent = `${selected}/5`;
  }

  function selectRating(value, focus = false) {
    const selected = normalizeRatingValue(value);
    paintRatingStars(selected);
    if (focus) ratingStarButtons[selected - 1]?.focus();
  }

  function renderRatingState() {
    const review = state.detail?.my_review || null;
    const canRate = Boolean(state.detail?.can_rate);
    if (review) {
      refs.myReview.innerHTML = `<i class="bi bi-check-circle" aria-hidden="true"></i> Bạn đã đánh giá <strong>${review.rating}/5</strong>`;
      refs.ratingComment.value = review.comment || "";
      selectRating(review.rating || 5);
      refs.ratingSubmit.textContent = "Cập nhật đánh giá";
    } else {
      refs.myReview.textContent = "";
      refs.ratingComment.value = "";
      selectRating(5);
      refs.ratingSubmit.textContent = "Gửi đánh giá";
    }
    refs.ratingFieldset.disabled = !canRate;
    refs.ratingHint.textContent = canRate
      ? `Bạn còn ${formatCount(state.detail.review_submissions_remaining || 0)}/2 lượt gửi đánh giá.`
      : "Cài và sử dụng mẫu thẻ trước khi đánh giá.";
  }

  function renderInstallState() {
    const detail = state.detail;
    if (!detail) return;
    refs.edit.classList.toggle("d-none", !detail.is_owner);
    refs.save.classList.toggle("d-none", Boolean(detail.is_owner));

    if (detail.is_owner) {
      refs.install.innerHTML = `<i class="bi bi-person-check" aria-hidden="true"></i>Bạn là tác giả`;
      refs.install.disabled = true;
    } else if (detail.is_installed) {
      refs.install.innerHTML = `<i class="bi bi-check-circle" aria-hidden="true"></i>Đã cài vào thư viện`;
      refs.install.disabled = true;
    } else if (detail.ownership_status === "owned_pending") {
      refs.install.innerHTML = `<i class="bi bi-receipt" aria-hidden="true"></i>Xem đơn hàng`;
      refs.install.disabled = false;
    } else {
      const label = detail.pricing_mode === "paid"
        ? `Mua · ${detail.price_display || "Xem giá"}`
        : "Cài miễn phí";
      refs.install.innerHTML = `<i class="bi bi-plus-circle" aria-hidden="true"></i>${escapeHtml(label)}`;
      refs.install.disabled = false;
    }

    const saveLabel = detail.is_saved ? "Đã lưu mẫu thẻ" : "Lưu mẫu thẻ";
    refs.save.innerHTML = `<i class="bi ${detail.is_saved ? "bi-bookmark-fill" : "bi-bookmark"}" aria-hidden="true"></i><span>${saveLabel}</span>`;
    refs.save.classList.toggle("is-saved", Boolean(detail.is_saved));
    refs.save.setAttribute("aria-pressed", detail.is_saved ? "true" : "false");
    refs.save.disabled = false;
  }

  async function loadPreview() {
    state.previewController?.abort();
    const controller = new AbortController();
    state.previewController = controller;
    if (!state.selectedTemplateId) {
      state.previewPayload = null;
      frameController?.render(previewNotice("Mẫu thẻ này chưa có kiểu thẻ để xem trước."), {
        padding: "16px",
        background: "#f7f9fc",
        color: "#20242c",
      });
      setPreviewBusy(false);
      return;
    }

    setPreviewBusy(true);
    try {
      state.previewPayload = await requestJson(
        `/api/shared/note-types/${noteTypeId}/templates/${state.selectedTemplateId}/preview`,
        { method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.signal },
      );
      if (!controller.signal.aborted) renderPreviewFrame();
    } catch (error) {
      if (error.name !== "AbortError") {
        frameController?.render(previewNotice("Không thể tải bản xem trước. Hãy thử chọn lại kiểu thẻ."), {
          padding: "16px",
          background: "#f7f9fc",
          color: "#20242c",
        });
        announce("Không thể tải bản xem trước. Thông tin mẫu thẻ vẫn dùng được.");
      }
    } finally {
      if (state.previewController === controller) {
        state.previewController = null;
        setPreviewBusy(false);
      }
    }
  }

  async function renderDetail(detail) {
    state.detail = detail;
    const title = detail.title || detail.name || "Mẫu thẻ";
    const fields = Array.isArray(detail.field_defs) ? detail.field_defs : [];
    const templates = Array.isArray(detail.templates) ? detail.templates : [];
    const categories = [detail.primary_category, ...(detail.level_tokens || [])]
      .map((value) => String(value || "").trim())
      .filter(Boolean);

    document.title = `${title} · Flama`;
    refs.title.textContent = title;
    refs.previewText.textContent = detail.preview_text || detail.description || "Xem cấu trúc và bản thử trước khi cài vào thư viện.";
    refs.meta.textContent = Array.from(new Set(categories)).join(" · ") || "Mẫu thẻ học tập";
    refs.rating.textContent = `${Number(detail.rating_avg || 0).toFixed(1)} (${formatCount(detail.rating_count || 0)})`;
    refs.installs.textContent = formatCount(detail.install_count || 0);
    refs.updated.textContent = formatDate(detail.updated_at || detail.created_at);
    refs.price.textContent = detail.price_display || "Miễn phí";
    refs.version.textContent = detail.version || "1.0.0";

    const description = String(detail.description || "").trim();
    refs.description.textContent = description;
    refs.description.hidden = !description || description === String(detail.preview_text || "").trim();
    renderBadges(detail.badges || []);
    renderTagList(detail.display_tags || detail.tags || []);
    renderAuthorProfile(detail.author_profile || {});
    renderFields(fields, templates);
    renderPreviewControls(templates);
    renderReviews(detail.recent_reviews || []);
    renderRelatedItems(detail.related_items || []);
    renderInstallState();
    renderRatingState();

    const changelog = String(detail.changelog || "").trim();
    refs.changelog.textContent = changelog;
    refs.changelogWrap.classList.toggle("d-none", !changelog);

    if (state.selectedTemplateId) await loadPreview();
    announce(`Đã tải ${title}.`);
  }

  async function loadDetail() {
    state.detailController?.abort();
    const controller = new AbortController();
    state.detailController = controller;
    clearError();
    setPageBusy(true);
    announce("Đang tải chi tiết mẫu thẻ.");
    try {
      const detail = await requestJson(`/api/shared/note-types/${noteTypeId}`, { signal: controller.signal });
      if (!controller.signal.aborted) await renderDetail(detail);
    } catch (error) {
      if (error.name !== "AbortError") {
        showError(error.message);
        announce("Không thể tải chi tiết mẫu thẻ.");
      }
    } finally {
      if (state.detailController === controller) {
        state.detailController = null;
        setPageBusy(false);
      }
    }
  }

  async function handleInstall() {
    if (!state.detail || state.pendingAction) return;
    if (state.detail.ownership_status === "owned_pending") {
      window.location.href = ordersUrl;
      return;
    }
    state.pendingAction = "install";
    setButtonBusy(refs.install, true, "Đang xử lý");
    clearError();
    try {
      const response = await requestJson(`/api/shared/note-types/${noteTypeId}/install`, { method: "POST" });
      if (response?.payment_required && response?.order) {
        const checkoutUrl = response?.order?.active_attempt?.checkout?.checkout_url
          || response?.order?.active_attempt?.checkout_url;
        if (checkoutUrl && response?.order?.status === "pending_payment") {
          window.location.href = checkoutUrl;
          return;
        }
        const url = new URL(paymentResultUrl, window.location.origin);
        url.searchParams.set("payment_order_id", response?.order?.id || "");
        url.searchParams.set("payment_product_type", "note_type");
        url.searchParams.set("payment_product_ref_id", noteTypeId);
        window.location.href = url.toString();
        return;
      }
      refs.paymentPanel?.classList.add("d-none");
      await loadDetail();
      announce("Đã cài mẫu thẻ vào thư viện.");
    } finally {
      state.pendingAction = "";
      setButtonBusy(refs.install, false);
      renderInstallState();
    }
  }

  async function handleSave() {
    if (!state.detail || state.pendingAction) return;
    state.pendingAction = "save";
    setButtonBusy(refs.save, true, "Đang lưu");
    clearError();
    try {
      const wasSaved = Boolean(state.detail.is_saved);
      await requestJson(buildUrl(saveUrlTemplate, noteTypeId), { method: wasSaved ? "DELETE" : "POST" });
      await loadDetail();
      announce(wasSaved ? "Đã bỏ lưu mẫu thẻ." : "Đã lưu mẫu thẻ.");
    } finally {
      state.pendingAction = "";
      setButtonBusy(refs.save, false);
      renderInstallState();
    }
  }

  async function handleRatingSubmit() {
    if (!state.detail?.can_rate || state.pendingAction) return;
    state.pendingAction = "rating";
    setButtonBusy(refs.ratingSubmit, true, "Đang gửi");
    clearError();
    try {
      await requestJson(`/api/shared/note-types/${noteTypeId}/rate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rating: Number(refs.ratingValue.value || "5"),
          comment: String(refs.ratingComment.value || "").trim(),
        }),
      });
      await loadDetail();
      announce("Đã gửi đánh giá của bạn.");
    } finally {
      state.pendingAction = "";
      setButtonBusy(refs.ratingSubmit, false);
      renderRatingState();
    }
  }

  refs.install?.addEventListener("click", () => handleInstall().catch((error) => showError(error.message)));
  refs.save?.addEventListener("click", () => handleSave().catch((error) => showError(error.message)));
  refs.ratingSubmit?.addEventListener("click", () => handleRatingSubmit().catch((error) => showError(error.message)));
  refs.retry?.addEventListener("click", loadDetail);

  refs.templateSelect?.addEventListener("change", () => {
    state.selectedTemplateId = refs.templateSelect.value || "";
    loadPreview().catch((error) => showError(error.message));
  });

  [refs.front, refs.back].forEach((button) => {
    button?.addEventListener("click", () => {
      state.previewSide = button.dataset.side || "front";
      renderPreviewSide();
    });
  });

  ratingStarButtons.forEach((button) => {
    button.addEventListener("click", () => selectRating(button.dataset.value || 5));
    button.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const current = normalizeRatingValue(button.dataset.value || 5);
      const next = event.key === "Home"
        ? 1
        : event.key === "End"
          ? 5
          : Math.max(1, Math.min(5, current + (["ArrowRight", "ArrowUp"].includes(event.key) ? 1 : -1)));
      selectRating(next, true);
    });
  });

  loadDetail();
}
