import {
  fetchDeckDetail,
  installDeck,
  submitRating,
  fetchSourceNoteType,
  fetchTemplatePreview,
  requestJson,
} from "./api.js";

import {
  formatDate,
  renderTags,
  normalizeRatingValue,
  paintRatingStars,
} from "./ui.js";

const root = document.getElementById("shared-deck-detail-root");

if (root) {
  const deckItemId = root.getAttribute("data-deck-item-id") || "";
  const noteTypeDetailUrlTemplate = root.getAttribute("data-note-type-url-template") || "";
  const shareEditUrlTemplate = root.getAttribute("data-share-edit-url-template") || "";
  const changeRequestUrlTemplate = root.getAttribute("data-change-request-url-template") || "";
  const changeRequestInboxUrl = root.getAttribute("data-change-request-inbox-url") || "";
  const paymentResultUrl = root.getAttribute("data-payment-result-url") || "";
  const saveUrlTemplate = root.getAttribute("data-save-url-template") || "";
  const marketUrl = root.getAttribute("data-market-url") || "/";
  const ordersUrl = root.getAttribute("data-orders-url") || "/";

  const titleEls = [document.getElementById("deck-title"), document.getElementById("deck-title-secondary")];
  const metaEl = document.getElementById("deck-meta-line");
  const descriptionEl = document.getElementById("deck-description");
  const previewTextEl = document.getElementById("deck-preview-text");
  const tagsEl = document.getElementById("deck-tags");
  const statsEl = document.getElementById("deck-stats");
  const badgesEl = document.getElementById("deck-badges");
  const coverLabelEl = document.getElementById("deck-cover-label");
  const authorNameEl = document.getElementById("author-name");
  const authorSummaryEl = document.getElementById("author-summary");
  const authorStoreLinkEl = document.getElementById("author-store-link");
  const authorOtherItemsEl = document.getElementById("deck-author-other-items");
  const communityReviewsEl = document.getElementById("deck-community-reviews");
  const relatedItemsEl = document.getElementById("deck-related-items");
  const testSamplesEl = document.getElementById("deck-test-samples");
  const testNoteEl = document.getElementById("deck-test-note");
  const editBtn = document.getElementById("deck-edit-btn");
  const changeRequestBtn = document.getElementById("deck-change-request-btn");
  const changeRequestInboxBtn = document.getElementById("deck-change-request-inbox-btn");
  const saveBtn = document.getElementById("deck-save-btn");
  const installBtn = document.getElementById("deck-install-btn");
  const myReviewEl = document.getElementById("deck-my-review");
  const ratingValueEl = document.getElementById("deck-rating-value");
  const ratingStarsEl = document.getElementById("deck-rating-stars");
  const ratingValueLabelEl = document.getElementById("deck-rating-value-label");
  const ratingStarButtons = Array.from(ratingStarsEl?.querySelectorAll(".shared-rating-star") || []);
  const ratingCommentEl = document.getElementById("deck-rating-comment");
  const ratingHintEl = document.getElementById("deck-rating-hint");
  const ratingSubmitBtn = document.getElementById("deck-rating-submit-btn");
  const sourceNoteTypeLink = document.getElementById("source-note-type-link");
  const templateNameDisplayEl = document.getElementById("deck-template-name-display");
  const templateNoteEl = document.getElementById("deck-template-note");
  const samplePrevBtn = document.getElementById("deck-preview-sample-prev");
  const sampleNextBtn = document.getElementById("deck-preview-sample-next");
  const sampleLabelEl = document.getElementById("deck-preview-sample-label");
  const previewFrame = document.getElementById("deck-template-preview-frame");
  const frontBtn = document.getElementById("deck-preview-side-front");
  const backBtn = document.getElementById("deck-preview-side-back");
  const errorEl = document.getElementById("deck-detail-error");
  const paymentPanelEl = document.getElementById("deck-payment-panel");
  const paymentHeadlineEl = document.getElementById("deck-payment-headline");
  const paymentMessageEl = document.getElementById("deck-payment-message");
  const paymentBadgeEl = document.getElementById("deck-payment-badge");
  const paymentNextActionEl = document.getElementById("deck-payment-next-action");
  const paymentLinesEl = document.getElementById("deck-payment-lines");
  const paymentInstructionsEl = document.getElementById("deck-payment-instructions");
  const rendererHost = window.FlamaCardRendererHost;
  const previewController = previewFrame && rendererHost
    ? rendererHost.createRendererFrameController(previewFrame, { minHeight: 280 })
    : null;

  let deckDetail = null;
  let selectedTemplateId = "";
  let previewPayload = null;
  let previewSide = "front";
  let testSamples = [];
  let activeSampleIndex = -1;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function showError(message) {
    errorEl.textContent = message || "Không thể tải dữ liệu.";
    errorEl.classList.remove("d-none");
  }

  function clearError() {
    errorEl.textContent = "";
    errorEl.classList.add("d-none");
  }

  function formatCount(value) {
    return window.Utils?.formatNumber ? window.Utils.formatNumber(value) : String(value || 0);
  }

  function buildUrl(template, value) {
    return String(template || "").replaceAll("__ITEM_ID__", encodeURIComponent(value || ""));
  }

  function buildNoteTypeDetailUrl(noteTypeId) {
    return noteTypeDetailUrlTemplate.replace("__NOTE_TYPE_ID__", encodeURIComponent(noteTypeId || ""));
  }

  function buildEditUrl(sourceDeckId) {
    if (!sourceDeckId) return "#";
    return shareEditUrlTemplate.replace("/0/share", `/${encodeURIComponent(sourceDeckId)}/share`);
  }

  function buildChangeRequestUrl(itemId) {
    return changeRequestUrlTemplate.replace("__ITEM_ID__", encodeURIComponent(itemId || ""));
  }

  function buildChangeRequestInboxUrl(itemId) {
    if (!changeRequestInboxUrl) return "#";
    const url = new URL(changeRequestInboxUrl, window.location.origin);
    if (itemId) {
      url.searchParams.set("deck_item_id", itemId);
    }
    return `${url.pathname}${url.search}`;
  }

  function renderBadges(badges) {
    if (badgesEl) {
      badgesEl.innerHTML = (badges || []).map((badge) => `<span class="market-badge">${escapeHtml(badge)}</span>`).join("");
    }
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
          <a class="market-text-link" href="${escapeHtml(`${marketUrl.replace(/\/$/, "")}/${encodeURIComponent(item.id)}`)}">${escapeHtml(item.title || "Untitled")}</a>
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
    if (deckDetail?.author?.username) {
      authorStoreLinkEl.href = `${marketUrl}?author=${encodeURIComponent(deckDetail.author.username)}`;
    }
  }

  function setLoadingPreview(message) {
    previewController?.render(rendererHost.createNoticeHtml(message || "Dang tai phan xem truoc..."), {
      padding: "12px",
      background: "#fffaf6",
      color: "#1f1a17",
      config: {
        mode: "shared_deck_preview",
        side: previewSide,
        deckItemId,
      },
    });
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
          mode: "shared_deck_preview",
          side: previewSide,
          deckItemId,
          templateId: selectedTemplateId,
        },
        revealOnReady: {
          side: previewSide,
          reason: "preview_render",
        },
      }
    );
  }

  function getActiveSample() {
    return activeSampleIndex >= 0 && activeSampleIndex < testSamples.length ? testSamples[activeSampleIndex] : null;
  }

  function renderSampleNavState() {
    const hasSamples = testSamples.length > 0;
    samplePrevBtn.disabled = !hasSamples;
    sampleNextBtn.disabled = !hasSamples;
    sampleLabelEl.textContent = hasSamples
      ? `Mẫu ${activeSampleIndex + 1}/${testSamples.length}: ${(getActiveSample()?.word || "").trim() || "Từ mẫu"}`
      : "Chưa có từ mẫu.";
  }

  function renderTestSamples(samples) {
    testSamples = Array.isArray(samples) ? samples : [];
    if (!testSamples.length) {
      activeSampleIndex = -1;
      testSamplesEl.innerHTML = `<div class="market-empty-state">Deck này chưa có thẻ mẫu để chạy thử nhanh.</div>`;
      testNoteEl.textContent = "Không có dữ liệu để lấy từ mẫu.";
      renderSampleNavState();
      return;
    }
    if (activeSampleIndex < 0 || activeSampleIndex >= testSamples.length) {
      activeSampleIndex = 0;
    }
    testNoteEl.textContent = `Đang hiển thị ${formatCount(testSamples.length)} mẫu ngẫu nhiên để mô phỏng trải nghiệm học.`;
    testSamplesEl.innerHTML = testSamples.map((sample, index) => `
      <button class="btn ${index === activeSampleIndex ? "btn-primary" : "btn-outline-secondary"} text-start" type="button" data-sample-index="${index}">
        <strong>${escapeHtml(sample.word || `Từ #${index + 1}`)}</strong>
        <div class="small ${index === activeSampleIndex ? "text-white" : "text-muted"}">${escapeHtml(sample.reading || sample.meaning || "Không có mô tả")}</div>
      </button>
    `).join("");
    renderSampleNavState();
  }

  function renderInstallState() {
    if (!deckDetail) return;
    const editUrl = buildEditUrl(deckDetail.source_deck_id);
    const requestUrl = buildChangeRequestUrl(deckItemId);
    const inboxUrl = buildChangeRequestInboxUrl(deckItemId);
    editBtn.classList.toggle("d-none", !(deckDetail.is_owner && editUrl));
    changeRequestInboxBtn.classList.toggle("d-none", !deckDetail.is_owner);
    changeRequestBtn.classList.toggle("d-none", !!deckDetail.is_owner || !deckDetail.is_installed);
    saveBtn.classList.toggle("d-none", !!deckDetail.is_owner);
    if (deckDetail.is_owner) {
      changeRequestInboxBtn.href = inboxUrl;
    }
    if (!deckDetail.is_owner && deckDetail.is_installed) {
      changeRequestBtn.href = requestUrl;
    }
    if (deckDetail.is_owner) {
      if (editUrl) editBtn.href = editUrl;
      installBtn.textContent = "Bạn là tác giả";
      installBtn.disabled = true;
      return;
    }
    if (deckDetail.is_installed) {
      installBtn.textContent = "Đã cài";
      installBtn.disabled = true;
      return;
    }
    if (deckDetail.ownership_status === "owned_pending") {
      installBtn.textContent = "Xem đơn hàng";
      installBtn.disabled = false;
      return;
    }
    installBtn.textContent = deckDetail.pricing_mode === "paid" ? "Mua" : "Tải xuống";
    installBtn.disabled = false;
  }

  function renderRatingState() {
    const review = deckDetail?.my_review || null;
    if (review) {
      myReviewEl.textContent = `Đánh giá của bạn: ${review.rating}/5${review.comment ? ` · ${review.comment}` : ""} · ${formatDate(review.updated_at)}`;
      ratingCommentEl.value = review.comment || "";
      ratingValueEl.value = String(review.rating || 5);
      paintRatingStars(ratingStarButtons, normalizeRatingValue(review.rating || 5), ratingValueLabelEl);
    } else {
      myReviewEl.textContent = "Bạn chưa đánh giá deck này.";
      ratingCommentEl.value = "";
      ratingValueEl.value = "5";
      paintRatingStars(ratingStarButtons, 5, ratingValueLabelEl);
    }
    if (deckDetail?.can_rate) {
      ratingHintEl.textContent = `Bạn còn ${formatCount(deckDetail.review_submissions_remaining || 0)}/2 lượt đánh giá.`;
      ratingCommentEl.disabled = false;
      ratingSubmitBtn.disabled = false;
      ratingStarButtons.forEach((button) => { button.disabled = false; });
    } else {
      ratingHintEl.textContent = "Cần cài đặt và dùng thực tế trước khi gửi đánh giá.";
      ratingCommentEl.disabled = true;
      ratingSubmitBtn.disabled = true;
      ratingStarButtons.forEach((button) => { button.disabled = true; });
    }
  }

  async function loadTemplatePreview() {
    if (!deckDetail?.source_note_type_id || !selectedTemplateId) {
      setLoadingPreview("Deck này chưa có template preview.");
      return;
    }
    const selectedSample = getActiveSample();
    previewPayload = await fetchTemplatePreview(deckItemId, selectedTemplateId, selectedSample?.note_id);
    renderPreviewFrame();
  }

  async function loadSourceNoteType() {
    if (!deckDetail?.source_note_type_id) {
      sourceNoteTypeLink.classList.add("disabled");
      sourceNoteTypeLink.href = "#";
      templateNameDisplayEl.textContent = "Không có template";
      templateNoteEl.textContent = "Deck này chưa liên kết note type nguồn.";
      setLoadingPreview("Deck này chưa có template preview.");
      return;
    }
    sourceNoteTypeLink.classList.remove("disabled");
    sourceNoteTypeLink.href = buildNoteTypeDetailUrl(deckDetail.source_note_type_id);
    const sourceNoteType = deckDetail.source_note_type || await fetchSourceNoteType(deckDetail.source_note_type_id);
    const templates = Array.isArray(sourceNoteType.templates) ? sourceNoteType.templates.slice().sort((a, b) => (a.position || 0) - (b.position || 0)) : [];
    if (!templates.length) {
      templateNameDisplayEl.textContent = "Không có template";
      templateNoteEl.textContent = "Note type nguồn chưa có template để preview.";
      setLoadingPreview("Không có template preview khả dụng.");
      return;
    }
    selectedTemplateId = templates[0].id;
    templateNameDisplayEl.textContent = sourceNoteType.title || sourceNoteType.name || templates[0].name;
    templateNoteEl.textContent = `Preview lấy từ note type nguồn: ${sourceNoteType.title || sourceNoteType.name || "Không rõ"}`;
    await loadTemplatePreview();
  }

  async function loadDeckDetail() {
    clearError();
    deckDetail = await fetchDeckDetail(deckItemId);
    titleEls.forEach((el) => {
      if (el) el.textContent = deckDetail.title || "Deck";
    });
    if (coverLabelEl) coverLabelEl.textContent = (deckDetail.level_tokens || [deckDetail.primary_category || "Deck"]).join(" · ");
    metaEl.innerHTML = `<strong>${deckDetail.primary_category || "Chung"}</strong> · ${deckDetail.price_display || "Miễn phí"}`;
    descriptionEl.textContent = deckDetail.description || "Chưa có mô tả.";
    previewTextEl.textContent = deckDetail.preview_text || "Chưa có preview text.";
    statsEl.textContent = `${Number(deckDetail.rating_avg || 0).toFixed(1)} sao · ${formatCount(deckDetail.rating_count || 0)} đánh giá · ${formatCount(deckDetail.install_count || 0)} lượt sở hữu · cập nhật ${formatDate(deckDetail.updated_at)}`;
    renderBadges(deckDetail.badges || []);
    renderTags(tagsEl, deckDetail.display_tags || deckDetail.tags || []);
    renderAuthorProfile(deckDetail.author_profile || {});
    renderMiniCards(authorOtherItemsEl, deckDetail.author_other_items || [], "Tác giả này chưa có deck công khai khác.");
    renderMiniCards(relatedItemsEl, deckDetail.related_items || [], "Chưa có gợi ý liên quan.");
    renderReviews(deckDetail.recent_reviews || []);
    renderTestSamples(deckDetail.test_samples || []);
    renderInstallState();
    renderRatingState();
    saveBtn.textContent = deckDetail.is_saved ? "Đã lưu" : "Lưu";
    await loadSourceNoteType();
  }

  async function handleInstall() {
    if (deckDetail?.ownership_status === "owned_pending") {
      window.location.href = ordersUrl;
      return;
    }
    const response = await installDeck(deckItemId);
    if (response?.payment_required && response?.order) {
      const checkoutUrl = response?.order?.active_attempt?.checkout?.checkout_url
        || response?.order?.active_attempt?.checkout_url;
      if (checkoutUrl && response?.order?.status === "pending_payment") {
        window.location.href = checkoutUrl;
        return;
      }
      const url = new URL(paymentResultUrl, window.location.origin);
      url.searchParams.set("payment_order_id", response?.order?.id || "");
      url.searchParams.set("payment_product_type", "deck_marketplace_item");
      url.searchParams.set("payment_product_ref_id", deckItemId);
      window.location.href = url.toString();
      return;
    }
    paymentPanelEl.classList.add("d-none");
    await loadDeckDetail();
  }

  async function handleSave() {
    await requestJson(buildUrl(saveUrlTemplate, deckItemId), { method: deckDetail?.is_saved ? "DELETE" : "POST" });
    await loadDeckDetail();
  }

  async function handleSubmitRating() {
    await submitRating(deckItemId, Number(ratingValueEl.value || "5"), String(ratingCommentEl.value || "").trim());
    await loadDeckDetail();
  }

  installBtn?.addEventListener("click", () => {
    handleInstall().catch((error) => showError(error.message));
  });

  saveBtn?.addEventListener("click", () => {
    handleSave().catch((error) => showError(error.message));
  });

  ratingSubmitBtn?.addEventListener("click", () => {
    handleSubmitRating().catch((error) => showError(error.message));
  });

  testSamplesEl?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-sample-index]");
    if (!button) return;
    activeSampleIndex = Number(button.getAttribute("data-sample-index") || "0");
    renderTestSamples(testSamples);
    loadTemplatePreview().catch((error) => showError(error.message));
  });

  [frontBtn, backBtn].forEach((button) => {
    button?.addEventListener("click", () => {
      previewSide = button.getAttribute("data-side") || "front";
      frontBtn.classList.toggle("active", previewSide === "front");
      backBtn.classList.toggle("active", previewSide === "back");
      renderPreviewFrame();
    });
  });

  samplePrevBtn?.addEventListener("click", () => {
    if (!testSamples.length) return;
    activeSampleIndex = (activeSampleIndex - 1 + testSamples.length) % testSamples.length;
    renderTestSamples(testSamples);
    loadTemplatePreview().catch((error) => showError(error.message));
  });

  sampleNextBtn?.addEventListener("click", () => {
    if (!testSamples.length) return;
    activeSampleIndex = (activeSampleIndex + 1) % testSamples.length;
    renderTestSamples(testSamples);
    loadTemplatePreview().catch((error) => showError(error.message));
  });

  ratingStarButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const value = normalizeRatingValue(button.getAttribute("data-value") || "5");
      ratingValueEl.value = String(value);
      paintRatingStars(ratingStarButtons, value, ratingValueLabelEl);
    });
  });

  loadDeckDetail().catch((error) => showError(error.message));
}
