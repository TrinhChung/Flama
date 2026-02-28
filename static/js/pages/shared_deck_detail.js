  (() => {
    const root = document.getElementById("shared-deck-detail-root");
    if (!root) return;

    const deckItemId = root.getAttribute("data-deck-item-id");
    const noteTypeDetailUrlTemplate = "{{ url_for('flashcards.shared_note_type_detail_page', note_type_id='__NOTE_TYPE_ID__') }}";

    const titleEl = document.getElementById("deck-title");
    const metaEl = document.getElementById("deck-meta-line");
    const descriptionEl = document.getElementById("deck-description");
    const previewTextEl = document.getElementById("deck-preview-text");
    const tagsEl = document.getElementById("deck-tags");
    const statsEl = document.getElementById("deck-stats");
    const testSamplesEl = document.getElementById("deck-test-samples");
    const testNoteEl = document.getElementById("deck-test-note");
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

    let deckDetail = null;
    let sourceNoteTypeDetail = null;
    let selectedTemplateId = "";
    let previewPayload = null;
    let previewSide = "front";
    let testSamples = [];
    let activeSampleIndex = -1;

    function showError(message) {
      errorEl.textContent = message || "Request failed.";
      errorEl.classList.remove("d-none");
    }

    function clearError() {
      errorEl.textContent = "";
      errorEl.classList.add("d-none");
    }

    function formatDate(isoString) {
      if (!isoString) return "";
      const date = new Date(isoString);
      if (Number.isNaN(date.getTime())) return "";
      return date.toLocaleString();
    }

    function buildNoteTypeDetailUrl(noteTypeId) {
      return noteTypeDetailUrlTemplate.replace("__NOTE_TYPE_ID__", encodeURIComponent(noteTypeId));
    }

    async function requestJson(url, options = {}) {
      const response = await fetch(url, options);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.message || "Request failed.");
      return data;
    }

    function renderTags(tags) {
      tagsEl.innerHTML = "";
      const normalized = Array.isArray(tags) ? tags : [];
      if (!normalized.length) {
        tagsEl.textContent = "Không có tags.";
        return;
      }
      normalized.forEach((tag) => {
        const span = document.createElement("span");
        span.className = "badge bg-light text-dark border me-1 mb-1";
        span.textContent = tag;
        tagsEl.appendChild(span);
      });
    }

    function getActiveSample() {
      if (!Array.isArray(testSamples)) return null;
      if (activeSampleIndex < 0 || activeSampleIndex >= testSamples.length) return null;
      return testSamples[activeSampleIndex];
    }

    function renderSampleNavState() {
      const hasSamples = Array.isArray(testSamples) && testSamples.length > 0;
      if (samplePrevBtn) samplePrevBtn.disabled = !hasSamples;
      if (sampleNextBtn) sampleNextBtn.disabled = !hasSamples;

      if (!sampleLabelEl) return;
      if (!hasSamples) {
        sampleLabelEl.textContent = "Khong co tu mau.";
        return;
      }
      const sample = getActiveSample();
      const word = ((sample?.word || "").trim() || ("Tu #" + String(activeSampleIndex + 1)));
      sampleLabelEl.textContent = "Mau " + String(activeSampleIndex + 1) + "/" + String(testSamples.length) + ": " + word;
    }

    function renderTestSamples(samples) {
      if (!testSamplesEl) return;
      testSamplesEl.innerHTML = "";

      const normalized = Array.isArray(samples) ? samples : [];
      testSamples = normalized;
      if (!normalized.length) {
        activeSampleIndex = -1;
        const emptyRow = document.createElement("div");
        emptyRow.className = "list-group-item px-0 text-muted";
        emptyRow.textContent = "Deck nay chua co tu mau de test.";
        testSamplesEl.appendChild(emptyRow);
        if (testNoteEl) {
          testNoteEl.textContent = "Khong co du lieu de lay 5 tu mau.";
        }
        renderSampleNavState();
        return;
      }

      if (activeSampleIndex < 0 || activeSampleIndex >= normalized.length) {
        activeSampleIndex = 0;
      }
      if (testNoteEl) {
        testNoteEl.textContent = "Dang hien thi " + normalized.length + " tu ngau nhien de mo phong preview card.";
      }

      normalized.forEach((sample, index) => {
        const row = document.createElement("button");
        row.type = "button";
        row.className = "list-group-item list-group-item-action px-0 text-start";
        if (index === activeSampleIndex) {
          row.classList.add("active");
        }

        const textWrap = document.createElement("div");
        textWrap.className = "d-flex flex-wrap justify-content-between align-items-start gap-2";
        const wordEl = document.createElement("div");
        wordEl.className = "fw-semibold";
        wordEl.textContent = (sample?.word || "").trim() || ("Tu #" + String(index + 1));
        const metaWrap = document.createElement("div");
        metaWrap.appendChild(wordEl);

        const reading = (sample?.reading || "").trim();
        if (reading) {
          const readingEl = document.createElement("div");
          readingEl.className = "small text-muted";
          readingEl.textContent = "Reading: " + reading;
          metaWrap.appendChild(readingEl);
        }

        const meaning = (sample?.meaning || "").trim();
        const meaningEl = document.createElement("div");
        meaningEl.className = "small";
        meaningEl.textContent = meaning ? ("Hint: " + meaning) : "Hint: (khong co)";

        textWrap.appendChild(metaWrap);
        textWrap.appendChild(meaningEl);
        row.appendChild(textWrap);

        row.addEventListener("click", () => {
          activeSampleIndex = index;
          renderTestSamples(testSamples);
          renderSampleNavState();
          loadTemplatePreview().catch((error) => showError(error.message));
        });

        testSamplesEl.appendChild(row);
      });
      renderSampleNavState();
    }

    function setLoadingPreview(message) {
      const safeMessage = message || "Loading preview...";
      previewFrame.srcdoc = "<!doctype html><html><body><div style='padding:12px;color:#6c757d;'>" + safeMessage + "</div></body></html>";
    }

    function renderPreviewFrame() {
      const html = previewSide === "back"
        ? (previewPayload?.back_html || "")
        : (previewPayload?.front_html || "");
      const fallback = "<div style='padding:12px;color:#6c757d;'>Empty preview.</div>";
      previewFrame.srcdoc = "<!doctype html><html><head><meta charset='utf-8'></head><body><div style='padding:8px;'>" + (html || fallback) + "</div></body></html>";
    }

    function applySideButtons() {
      frontBtn.classList.toggle("active", previewSide === "front");
      backBtn.classList.toggle("active", previewSide === "back");
    }

    function renderInstallState() {
      if (!deckDetail) return;
      if (deckDetail.is_owner) {
        installBtn.textContent = "Bạn là tác giả";
        installBtn.disabled = true;
        return;
      }
      if (deckDetail.is_installed) {
        installBtn.textContent = "Đã cài đặt";
        installBtn.disabled = true;
        return;
      }
      installBtn.textContent = deckDetail.pricing_mode === "paid" ? "Mua / Cài đặt" : "Cài đặt";
      installBtn.disabled = false;
    }

    function normalizeRatingValue(value) {
      const parsed = Number(value);
      if (!Number.isInteger(parsed)) return 5;
      return Math.max(1, Math.min(5, parsed));
    }

    function paintRatingStars(value) {
      const normalized = normalizeRatingValue(value);
      ratingStarButtons.forEach((button) => {
        const starValue = Number(button.getAttribute("data-value") || "0");
        const isActive = starValue <= normalized;
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-checked", starValue === normalized ? "true" : "false");
      });
      if (ratingValueLabelEl) {
        ratingValueLabelEl.textContent = normalized + "/5";
      }
    }

    function setSelectedRating(value) {
      const normalized = normalizeRatingValue(value);
      ratingValueEl.value = String(normalized);
      paintRatingStars(normalized);
    }

    function setRatingInputDisabled(disabled) {
      const isDisabled = Boolean(disabled);
      ratingValueEl.disabled = isDisabled;
      ratingCommentEl.disabled = isDisabled;
      ratingSubmitBtn.disabled = isDisabled;
      if (ratingStarsEl) {
        ratingStarsEl.classList.toggle("is-disabled", isDisabled);
        ratingStarsEl.setAttribute("aria-disabled", isDisabled ? "true" : "false");
      }
      ratingStarButtons.forEach((button) => {
        button.disabled = isDisabled;
      });
    }

    function renderRatingState() {
      if (!deckDetail) return;
      const review = deckDetail.my_review || null;
      if (review) {
        myReviewEl.textContent = "Đánh giá của bạn: " + review.rating + "/5"
          + (review.comment ? " - " + review.comment : "")
          + (review.updated_at ? " (" + formatDate(review.updated_at) + ")" : "");
        setSelectedRating(review.rating || 5);
        ratingCommentEl.value = review.comment || "";
      } else {
        myReviewEl.textContent = "Bạn chưa đánh giá deck này.";
        setSelectedRating(5);
        ratingCommentEl.value = "";
      }

      if (deckDetail.can_rate) {
        ratingHintEl.textContent = "Bạn có thể đánh giá ngay.";
        setRatingInputDisabled(false);
      } else {
        ratingHintEl.textContent = "Cần cài đặt và dùng thực tế trước khi đánh giá.";
        setRatingInputDisabled(true);
      }
    }

    function renderTemplateName(templates, defaultName) {
      const normalized = Array.isArray(templates) ? templates.slice().sort((a, b) => (a.position || 0) - (b.position || 0)) : [];
      if (!normalized.length) {
        if (templateNameDisplayEl) templateNameDisplayEl.textContent = "Không có template";
        selectedTemplateId = "";
        return;
      }
      const defaultTemplate = normalized.find(t => t.is_default) || normalized[0];
      selectedTemplateId = defaultTemplate.id;
      if (templateNameDisplayEl) {
        templateNameDisplayEl.textContent = "Template: " + (defaultName || defaultTemplate.name);
      }
    }

    async function loadTemplatePreview() {
      if (!deckDetail || !deckDetail.source_note_type_id || !selectedTemplateId) {
        setLoadingPreview("Deck này chưa có template preview.");
        return;
      }
      const selectedSample = getActiveSample();
      const previewRequestPayload = {};
      if (selectedSample?.note_id) {
        previewRequestPayload.note_id = selectedSample.note_id;
      }

      setLoadingPreview();
      previewPayload = await requestJson(`/api/shared/decks/${deckItemId}/templates/${selectedTemplateId}/preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(previewRequestPayload),
      });
      renderPreviewFrame();
    }

    async function loadSourceNoteType() {
      sourceNoteTypeDetail = null;
      selectedTemplateId = "";
      previewPayload = null;

      if (!deckDetail || !deckDetail.source_note_type_id) {
        sourceNoteTypeLink.classList.add("disabled");
        sourceNoteTypeLink.setAttribute("href", "#");
        templateNoteEl.textContent = "Deck này không liên kết note type nguồn.";
        if (templateNameDisplayEl) templateNameDisplayEl.textContent = "Không có template";
        setLoadingPreview("Deck này không có template preview.");
        return;
      }

      sourceNoteTypeLink.classList.remove("disabled");
      sourceNoteTypeLink.setAttribute("href", buildNoteTypeDetailUrl(deckDetail.source_note_type_id));

      const sourceFromDeckDetail = deckDetail.source_note_type || null;
      if (sourceFromDeckDetail && Array.isArray(sourceFromDeckDetail.templates) && sourceFromDeckDetail.templates.length) {
        sourceNoteTypeDetail = sourceFromDeckDetail;
        const displayName = sourceNoteTypeDetail.title || sourceNoteTypeDetail.name || "";
        renderTemplateName(sourceNoteTypeDetail.templates || [], displayName);
        templateNoteEl.textContent = "Preview lấy từ note type nguồn: " + displayName;
        await loadTemplatePreview();
        return;
      }

      try {
        sourceNoteTypeDetail = await requestJson(`/api/shared/note-types/${deckDetail.source_note_type_id}`);
        const displayName = sourceNoteTypeDetail.title || sourceNoteTypeDetail.name || "";
        renderTemplateName(sourceNoteTypeDetail.templates || [], displayName);
        templateNoteEl.textContent = "Preview lấy từ note type nguồn: " + displayName;
        await loadTemplatePreview();
      } catch (error) {
        templateNoteEl.textContent = "Không thể tải template preview nguồn.";
        if (templateNameDisplayEl) templateNameDisplayEl.textContent = "Không có template";
        setLoadingPreview("Không có template preview khả dụng.");
      }
    }

    async function loadDeckDetail() {
      clearError();
      deckDetail = await requestJson(`/api/shared/decks/${deckItemId}`);

      titleEl.textContent = deckDetail.title || "Shared deck";
      metaEl.textContent = "Tác giả: " + (deckDetail.author?.username || "Unknown")
        + " | Danh mục: " + (deckDetail.primary_category || "General")
        + " | Giá: " + (deckDetail.price_display || "Free");
      descriptionEl.textContent = deckDetail.description || "Không có mô tả.";
      previewTextEl.textContent = deckDetail.preview_text || "Không có preview text.";
      statsEl.textContent = "Sample cards: " + (deckDetail.sample_cards_count || 0)
        + " | Rating: " + Number(deckDetail.rating_avg || 0).toFixed(2) + " (" + (deckDetail.rating_count || 0) + ")"
        + " | Active usage: " + (deckDetail.active_usage_count || 0) + "/" + (deckDetail.install_count || 0)
        + " | Cập nhật: " + (formatDate(deckDetail.updated_at) || "N/A");

      renderTags(deckDetail.tags || []);
      renderTestSamples(deckDetail.test_samples || []);
      renderSampleNavState();
      renderInstallState();
      renderRatingState();
      await loadSourceNoteType();
    }

    async function onInstall() {
      if (!deckDetail || deckDetail.is_owner || deckDetail.is_installed) return;
      installBtn.disabled = true;
      try {
        await requestJson(`/api/shared/decks/${deckItemId}/install`, { method: "POST" });
        await loadDeckDetail();
      } finally {
        renderInstallState();
      }
    }

    async function onRateSubmit() {
      if (!deckDetail || !deckDetail.can_rate) return;
      const rating = Number(ratingValueEl.value || "5");
      if (!Number.isInteger(rating) || rating < 1 || rating > 5) {
        window.alert("Rating phải từ 1 đến 5.");
        return;
      }
      const comment = (ratingCommentEl.value || "").trim();
      await requestJson(`/api/shared/decks/${deckItemId}/rate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating, comment }),
      });
      await loadDeckDetail();
    }

    installBtn?.addEventListener("click", () => {
      onInstall().catch((error) => showError(error.message));
    });

    ratingSubmitBtn?.addEventListener("click", () => {
      onRateSubmit().catch((error) => showError(error.message));
    });

    ratingStarButtons.forEach((button) => {
      button.addEventListener("mouseenter", () => {
        if (button.disabled) return;
        paintRatingStars(button.getAttribute("data-value") || "5");
      });

      button.addEventListener("focus", () => {
        if (button.disabled) return;
        paintRatingStars(button.getAttribute("data-value") || "5");
      });

      button.addEventListener("click", () => {
        if (button.disabled) return;
        setSelectedRating(button.getAttribute("data-value") || "5");
      });
    });

    ratingStarsEl?.addEventListener("mouseleave", () => {
      paintRatingStars(ratingValueEl.value || "5");
    });

    ratingStarsEl?.addEventListener("focusout", (event) => {
      if (!ratingStarsEl.contains(event.relatedTarget)) {
        paintRatingStars(ratingValueEl.value || "5");
      }
    });



    [frontBtn, backBtn].forEach((button) => {
      button?.addEventListener("click", () => {
        previewSide = button.getAttribute("data-side") || "front";
        applySideButtons();
        renderPreviewFrame();
      });
    });

    samplePrevBtn?.addEventListener("click", () => {
      if (!Array.isArray(testSamples) || !testSamples.length) return;
      activeSampleIndex = (activeSampleIndex - 1 + testSamples.length) % testSamples.length;
      renderTestSamples(testSamples);
      renderSampleNavState();
      loadTemplatePreview().catch((error) => showError(error.message));
    });

    sampleNextBtn?.addEventListener("click", () => {
      if (!Array.isArray(testSamples) || !testSamples.length) return;
      activeSampleIndex = (activeSampleIndex + 1) % testSamples.length;
      renderTestSamples(testSamples);
      renderSampleNavState();
      loadTemplatePreview().catch((error) => showError(error.message));
    });

    setSelectedRating(ratingValueEl.value || "5");
    setRatingInputDisabled(true);
    applySideButtons();
    loadDeckDetail().catch((error) => showError(error.message));
  })();
