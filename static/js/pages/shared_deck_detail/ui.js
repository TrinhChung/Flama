export function formatDate(isoString) {
    if (!isoString) return "";
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleString();
}

export function renderTags(tagsEl, tags) {
    tagsEl.innerHTML = "";
    const normalized = Array.isArray(tags) ? tags : [];
    if (!normalized.length) {
        tagsEl.textContent = "Chưa có thẻ gắn.";
        return;
    }
    normalized.forEach((tag) => {
        const span = document.createElement("span");
        span.className = "badge bg-light text-dark border me-1 mb-1";
        span.textContent = tag;
        tagsEl.appendChild(span);
    });
}

export function normalizeRatingValue(value) {
    const parsed = Number(value);
    if (!Number.isInteger(parsed)) return 5;
    return Math.max(1, Math.min(5, parsed));
}

export function paintRatingStars(stars, normalizedTarget, labelEl) {
    stars.forEach((button) => {
        const starValue = Number(button.getAttribute("data-value") || "0");
        const isActive = starValue <= normalizedTarget;
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-checked", starValue === normalizedTarget ? "true" : "false");
    });
    if (labelEl) {
        labelEl.textContent = normalizedTarget + "/5";
    }
}
