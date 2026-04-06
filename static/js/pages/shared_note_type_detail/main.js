const root = document.getElementById("shared-note-type-detail-root");

if (root) {
  const noteTypeId = root.getAttribute("data-note-type-id") || "";
  const marketUrl = root.getAttribute("data-market-url") || "/";
  const ordersUrl = root.getAttribute("data-orders-url") || "/";
  const editUrl = root.getAttribute("data-edit-url") || "#";
  const saveUrlTemplate = root.getAttribute("data-save-url-template") || "";
  const paymentResultUrl = root.getAttribute("data-payment-result-url") || "";

  const titleEls = [document.getElementById("nt-title"), document.getElementById("nt-title-secondary")];
  const metaEl = document.getElementById("nt-meta-line");
  const descriptionEl = document.getElementById("nt-description");
  const statsEl = document.getElementById("nt-stats");
  const previewTextEl = document.getElementById("nt-preview-text");
  const tagsEl = document.getElementById("nt-tags");
  const badgesEl = document.getElementById("nt-badges");
  const coverLabelEl = document.getElementById("nt-cover-label");
  const authorNameEl = document.getElementById("author-name");
  const authorSummaryEl = document.getElementById("author-summary");
  const authorStoreLinkEl = document.getElementById("author-store-link");
  const authorOtherItemsEl = document.getElementById("author-other-items");
  const relatedItemsEl = document.getElementById("nt-related-items");
  const communityReviewsEl = document.getElementById("nt-community-reviews");
  const installBtn = document.getElementById("install-btn");
  const saveBtn = document.getElementById("save-btn");
  const editBtn = document.getElementById("edit-btn");
  const errorEl = document.getElementById("detail-error");
  const myReviewEl = document.getElementById("my-review");
  const ratingValueEl = document.getElementById("rating-value");
  const ratingCommentEl = document.getElementById("rating-comment");
  const ratingHintEl = document.getElementById("rating-hint");
  const ratingSubmitBtn = document.getElementById("rating-submit-btn");
  const ratingStarsEl = document.getElementById("rating-stars");
  const ratingValueLabelEl = document.getElementById("rating-value-label");
  const ratingStarButtons = Array.from(ratingStarsEl?.querySelectorAll(".shared-rating-star") || []);
  const templateSelectEl = document.getElementById("template-select");
  const previewFrame = document.getElementById("template-preview-frame");
  const frontBtn = document.getElementById("preview-side-front");
  const backBtn = document.getElementById("preview-side-back");
  const paymentPanelEl = document.getElementById("payment-order-panel");
  const paymentHeadlineEl = document.getElementById("payment-order-headline");
  const paymentBadgeEl = document.getElementById("payment-order-badge");
  const paymentMessageEl = document.getElementById("payment-order-message");
  const paymentNextActionEl = document.getElementById("payment-order-next-action");
  const paymentLinesEl = document.getElementById("payment-order-lines");
  const paymentInstructionsEl = document.getElementById("payment-order-instructions");
  const rendererHost = window.FlamaCardRendererHost;
  const previewController = previewFrame && rendererHost
    ? rendererHost.createRendererFrameController(previewFrame, { minHeight: 280 })
    : null;

  let detail = null;
  let selectedTemplateId = "";
  let previewSide = "front";
  let previewPayload = null;

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
          || (response.status >= 500 ? "Máy chủ đang bận hoặc tạm thời không phản hồi." : "Không thể hoàn tất yêu cầu.")
        );
      }
      return data;
    });
  }

  function showError(message) {
    errorEl.textContent = message || "Không thể tải dữ liệu.";
    errorEl.classList.remove("d-none");
  }

  function clearError() {
    errorEl.textContent = "";
    errorEl.classList.add("d-none");
  }

  function formatDate(value) {
    if (!value) return "Không rõ";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "Không rõ" : date.toLocaleString();
  }

  function formatCount(value) {
    return window.Utils?.formatNumber ? window.Utils.formatNumber(value) : String(value || 0);
  }

  function buildUrl(template, itemId) {
    return String(template || "").replaceAll("__ITEM_ID__", encodeURIComponent(itemId || ""));
  }

  function renderBadges(badges) {
    if (badgesEl) {
      badgesEl.innerHTML = (badges || []).map((badge) => `<span class="market-badge">${escapeHtml(badge)}</span>`).join("");
    }
  }

  function renderTagList(tags) {
    tagsEl.innerHTML = (tags || []).length
      ? (tags || []).map((tag) => `<span class="market-badge me-2 mb-2">${escapeHtml(tag)}</span>`).join("")
      : `<span class="text-muted">Chưa có tag.</span>`;
  }

  function normalizeRatingValue(value) {
    const parsed = Number(value);
    if (!Number.isInteger(parsed)) return 5;
    return Math.max(1, Math.min(5, parsed));
  }

  function paintRatingStars(value) {
    const normalized = normalizeRatingValue(value);
    ratingStarButtons.forEach((button) => {
      const active = Number(button.getAttribute("data-value") || "0") <= normalized;
      button.classList.toggle("is-active", active);
    });
    ratingValueLabelEl.textContent = `${normalized}/5`;
  }

  function setRatingDisabled(disabled) {
    ratingCommentEl.disabled = disabled;
    ratingSubmitBtn.disabled = disabled;
    ratingValueEl.disabled = disabled;
    ratingStarButtons.forEach((button) => {
      button.disabled = disabled;
    });
  }

  function renderMiniCards(container, items, emptyText) {
    if (!container) return;
    if (!items || !items.length) {
      container.innerHTML = `<div class="market-empty-state">${escapeHtml(emptyText)}</div>`;
      return;
    }
    container.innerHTML = items.map((item) => `
      <article class="market-review-item">
        <div class="market-purchase-title">
          <a class="market-text-link" href="${escapeHtml(`${marketUrl}?author=${encodeURIComponent(item.author_filter_token || item.author?.username || "")}`)}">${escapeHtml(item.author?.username || "Không rõ")}</a>
          ·
          <a class="market-text-link" href="${escapeHtml(`${marketUrl.replace(/\/$/, "")}/${encodeURIComponent(item.id)}`)}">${escapeHtml(item.title || item.name || "Untitled")}</a>
        </div>
        <div class="market-feedback-meta mt-2">${escapeHtml(item.price_display || "Miễn phí")} · ${Number(item.rating_avg || 0).toFixed(1)} sao</div>
      </article>
    `).join("");
  }

  function renderReviews(reviews) {
    if (!reviews || !reviews.length) {
      communityReviewsEl.innerHTML = `<div class="market-empty-state">Chưa có đánh giá cộng đồng.</div>`;
      return;
    }
    communityReviewsEl.innerHTML = reviews.map((review) => `
      <article class="market-review-item">
        <div class="market-review-stars">${"★".repeat(Math.max(1, Number(review.rating || 0)))} ${Number(review.rating || 0)}/5</div>
        <div class="market-feedback-meta mt-2">${escapeHtml(review.username || "Người dùng")} · ${escapeHtml(formatDate(review.updated_at))}</div>
        <div class="market-detail-richtext mt-2">${escapeHtml(review.comment || "Người dùng chưa để lại nhận xét.")}</div>
      </article>
    `).join("");
  }

  function renderAuthorProfile(profile) {
    authorNameEl.textContent = profile?.username || "Không rõ";
    authorSummaryEl.textContent = `${formatCount(profile?.published_count || 0)} ấn phẩm · ${formatCount(profile?.total_installs || 0)} lượt sở hữu · ${Number(profile?.avg_rating || 0).toFixed(1)} sao`;
    if (detail?.author?.username) {
      authorStoreLinkEl.href = `${marketUrl}?author=${encodeURIComponent(detail.author.username)}`;
    }
  }

  function renderPreviewFrame() {
    const sidePayload = previewSide === "back"
      ? (previewPayload?.back_renderer_payload || previewPayload?.back_html || "")
      : (previewPayload?.front_renderer_payload || previewPayload?.front_html || "");
    previewController?.render(
      sidePayload || rendererHost.createNoticeHtml("Chua co noi dung xem truoc."),
      {
        padding: "12px",
        background: "#fffaf6",
        color: "#1f1a17",
        config: {
          mode: "shared_note_type_preview",
          side: previewSide,
          noteTypeId,
          templateId: selectedTemplateId,
        },
        revealOnReady: {
          side: previewSide,
          reason: "preview_render",
        },
      }
    );
  }

  function renderPreviewControls(templates) {
    templateSelectEl.innerHTML = "";
    const rows = Array.isArray(templates) ? templates.slice().sort((a, b) => (a.position || 0) - (b.position || 0)) : [];
    if (!rows.length) {
      templateSelectEl.innerHTML = `<option value="">Không có template</option>`;
      templateSelectEl.disabled = true;
      selectedTemplateId = "";
      return;
    }
    rows.forEach((template) => {
      const option = document.createElement("option");
      option.value = template.id;
      option.textContent = template.is_default ? `${template.name} (default)` : template.name;
      templateSelectEl.appendChild(option);
    });
    if (!selectedTemplateId || !rows.some((template) => template.id === selectedTemplateId)) {
      selectedTemplateId = rows[0].id;
    }
    templateSelectEl.value = selectedTemplateId;
    templateSelectEl.disabled = false;
  }

  function renderInstallState() {
    if (!detail) return;
    editBtn.classList.toggle("d-none", !detail.is_owner);
    saveBtn.classList.toggle("d-none", !!detail.is_owner);

    if (detail.is_owner) {
      installBtn.textContent = "Bạn là tác giả";
      installBtn.disabled = true;
      return;
    }
    if (detail.is_installed) {
      installBtn.textContent = "Đã cài";
      installBtn.disabled = true;
      return;
    }
    if (detail.ownership_status === "owned_pending") {
      installBtn.textContent = "Xem đơn hàng";
      installBtn.disabled = false;
      return;
    }
    installBtn.textContent = detail.pricing_mode === "paid" ? "Mua" : "Tải xuống";
    installBtn.disabled = false;
  }

  function renderRatingState() {
    const review = detail?.my_review || null;
    if (review) {
      myReviewEl.textContent = `Đánh giá của bạn: ${review.rating}/5${review.comment ? ` · ${review.comment}` : ""} · ${formatDate(review.updated_at)}`;
      ratingCommentEl.value = review.comment || "";
      ratingValueEl.value = String(review.rating || 5);
      paintRatingStars(review.rating || 5);
    } else {
      myReviewEl.textContent = "Bạn chưa đánh giá template này.";
      ratingCommentEl.value = "";
      ratingValueEl.value = "5";
      paintRatingStars(5);
    }

    if (detail?.can_rate) {
      ratingHintEl.textContent = `Bạn còn ${formatCount(detail.review_submissions_remaining || 0)}/2 lượt đánh giá.`;
      setRatingDisabled(false);
    } else {
      ratingHintEl.textContent = "Cần cài đặt và dùng thực tế trước khi gửi đánh giá.";
      setRatingDisabled(true);
    }
  }

  async function loadPreview() {
    if (!selectedTemplateId) {
      previewController?.render(rendererHost.createNoticeHtml("Khong co template de xem truoc."), {
        padding: "12px",
        background: "#fffaf6",
        color: "#1f1a17",
        config: {
          mode: "shared_note_type_preview",
          side: previewSide,
        },
      });
      return;
    }
    previewPayload = await requestJson(`/api/shared/note-types/${noteTypeId}/templates/${selectedTemplateId}/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    renderPreviewFrame();
  }

  async function loadDetail() {
    clearError();
    detail = await requestJson(`/api/shared/note-types/${noteTypeId}`);

    titleEls.forEach((el) => {
      if (el) el.textContent = detail.title || detail.name || "Template";
    });
    if (coverLabelEl) coverLabelEl.textContent = (detail.level_tokens || [detail.primary_category || "Template"]).join(" · ");
    metaEl.innerHTML = `<strong>${detail.primary_category || "Chung"}</strong> · ${detail.price_display || "Miễn phí"}`;
    descriptionEl.textContent = detail.description || "Chưa có mô tả.";
    previewTextEl.textContent = detail.preview_text || "Chưa có preview text.";
    statsEl.textContent = `${Number(detail.rating_avg || 0).toFixed(1)} sao · ${formatCount(detail.rating_count || 0)} đánh giá · ${formatCount(detail.install_count || 0)} lượt sở hữu · cập nhật ${formatDate(detail.updated_at)}`;
    renderBadges(detail.badges || []);
    renderTagList(detail.display_tags || detail.tags || []);
    renderPreviewControls(detail.templates || []);
    renderAuthorProfile(detail.author_profile || {});
    renderMiniCards(authorOtherItemsEl, detail.author_other_items || [], "Tác giả này chưa có thêm template công khai.");
    renderMiniCards(relatedItemsEl, detail.related_items || [], "Chưa có gợi ý liên quan.");
    renderReviews(detail.recent_reviews || []);
    renderInstallState();
    renderRatingState();
    saveBtn.textContent = detail.is_saved ? "Đã lưu" : "Lưu";
    if (selectedTemplateId) {
      await loadPreview();
    }
  }

  async function handleInstall() {
    if (!detail) return;
    if (detail.ownership_status === "owned_pending") {
      window.location.href = ordersUrl;
      return;
    }
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
    paymentPanelEl.classList.add("d-none");
    await loadDetail();
  }

  async function handleSave() {
    await requestJson(buildUrl(saveUrlTemplate, noteTypeId), { method: detail?.is_saved ? "DELETE" : "POST" });
    await loadDetail();
  }

  async function handleRatingSubmit() {
    await requestJson(`/api/shared/note-types/${noteTypeId}/rate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rating: Number(ratingValueEl.value || "5"),
        comment: String(ratingCommentEl.value || "").trim(),
      }),
    });
    await loadDetail();
  }

  installBtn?.addEventListener("click", () => {
    handleInstall().catch((error) => showError(error.message));
  });

  saveBtn?.addEventListener("click", () => {
    handleSave().catch((error) => showError(error.message));
  });

  ratingSubmitBtn?.addEventListener("click", () => {
    handleRatingSubmit().catch((error) => showError(error.message));
  });

  templateSelectEl?.addEventListener("change", () => {
    selectedTemplateId = templateSelectEl.value || "";
    loadPreview().catch((error) => showError(error.message));
  });

  [frontBtn, backBtn].forEach((button) => {
    button?.addEventListener("click", () => {
      previewSide = button.getAttribute("data-side") || "front";
      frontBtn.classList.toggle("active", previewSide === "front");
      backBtn.classList.toggle("active", previewSide === "back");
      renderPreviewFrame();
    });
  });

  ratingStarButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const value = normalizeRatingValue(button.getAttribute("data-value") || "5");
      ratingValueEl.value = String(value);
      paintRatingStars(value);
    });
  });

  loadDetail().catch((error) => showError(error.message));
}
