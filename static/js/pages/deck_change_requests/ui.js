export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function formatDate(value) {
  if (!value) return "N/A";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "N/A";
  return date.toLocaleString();
}

export function formatValue(value) {
  if (value && typeof value === "object" && value.__missing__ === true) {
    return "(missing)";
  }
  if (typeof value === "string") {
    return value;
  }
  if (value === null) {
    return "null";
  }
  if (typeof value === "undefined") {
    return "(undefined)";
  }
  return JSON.stringify(value, null, 2);
}

function renderValueBlock(label, value) {
  return `
    <div class="col-md-6">
      <div class="small text-muted mb-1">${escapeHtml(label)}</div>
      <pre class="bg-light border rounded p-2 small mb-0">${escapeHtml(formatValue(value))}</pre>
    </div>
  `;
}

export function renderRequestSummary(container, requestData, { emptyText = "Khong co request." } = {}) {
  if (!container) return;
  if (!requestData) {
    container.innerHTML = `<div class="market-empty-state">${escapeHtml(emptyText)}</div>`;
    return;
  }
  container.innerHTML = `
    <div class="row g-3">
      <div class="col-lg-8">
        <div class="fw-semibold">${escapeHtml(requestData.title || "Change Request")}</div>
        <div class="small text-muted mt-1">
          Status: ${escapeHtml(requestData.status || "unknown")}
          | Last sync: ${escapeHtml(formatDate(requestData.last_synced_at))}
          | Submitted: ${escapeHtml(formatDate(requestData.submitted_at))}
        </div>
        <div class="small text-muted mt-1">
          Item count: ${escapeHtml(String(requestData.item_count || 0))}
          | Unresolved conflicts: ${escapeHtml(String(requestData.unresolved_conflict_count || 0))}
        </div>
      </div>
      <div class="col-lg-4">
        <div class="small text-muted">Requester</div>
        <div>${escapeHtml(requestData.requester?.username || "Unknown")}</div>
        <div class="small text-muted mt-2">Deck</div>
        <div>${escapeHtml(requestData.deck_item?.title || "Unknown deck")}</div>
      </div>
    </div>
    ${requestData.description ? `<div class="mt-3"><div class="small text-muted mb-1">Description</div><div>${escapeHtml(requestData.description)}</div></div>` : ""}
    ${requestData.review_comment ? `<div class="mt-3"><div class="small text-muted mb-1">Review comment</div><div>${escapeHtml(requestData.review_comment)}</div></div>` : ""}
  `;
}

export function renderChangeItems(container, items, { emptyText = "Khong co thay doi." } = {}) {
  if (!container) return;
  if (!Array.isArray(items) || !items.length) {
    container.innerHTML = `<div class="market-empty-state">${escapeHtml(emptyText)}</div>`;
    return;
  }
  container.innerHTML = items.map((item) => `
    <article class="market-review-item mb-3">
      <div class="d-flex flex-wrap justify-content-between gap-2 align-items-start">
        <div>
          <div class="fw-semibold">${escapeHtml(item.path_label || item.change_type || "Change")}</div>
          <div class="small text-muted mt-1">
            Type: ${escapeHtml(item.change_type || "unknown")}
            ${item.is_conflict ? " | Conflict" : ""}
          </div>
        </div>
      </div>
      <div class="row g-3 mt-1">
        ${renderValueBlock("Before", item.before_value)}
        ${renderValueBlock("After", item.effective_after_value ?? item.after_value)}
      </div>
    </article>
  `).join("");
}

export function renderConflicts(container, conflicts, { interactive = false } = {}) {
  if (!container) return;
  if (!Array.isArray(conflicts) || !conflicts.length) {
    container.innerHTML = "<div class='market-empty-state'>Khong co conflict.</div>";
    return;
  }
  container.innerHTML = conflicts.map((conflict) => `
    <article class="market-review-item mb-3">
      <div class="fw-semibold">${escapeHtml(conflict.conflict_type || "conflict")} - ${escapeHtml(conflict.id || "")}</div>
      <div class="row g-3 mt-1">
        ${renderValueBlock("Base", conflict.base_value)}
        ${renderValueBlock("Upstream", conflict.upstream_value)}
        ${renderValueBlock("Mine", conflict.local_value)}
        ${renderValueBlock("Resolved", conflict.resolved_value)}
      </div>
      <div class="small text-muted mt-2">
        Resolution: ${escapeHtml(conflict.resolution_mode || "unresolved")}
        ${conflict.resolved_at ? ` | ${escapeHtml(formatDate(conflict.resolved_at))}` : ""}
      </div>
      ${interactive ? `
        <div class="d-flex flex-wrap gap-2 mt-3">
          <button class="btn btn-sm btn-dark" type="button" data-resolve-conflict-id="${escapeHtml(conflict.id || "")}" data-resolution-mode="keep_mine">Keep mine</button>
          <button class="btn btn-sm btn-outline-secondary" type="button" data-resolve-conflict-id="${escapeHtml(conflict.id || "")}" data-resolution-mode="keep_upstream">Keep upstream</button>
        </div>
        <div class="mt-3">
          <label class="form-label small" for="manual-${escapeHtml(conflict.id || "")}">Manual value (JSON or text)</label>
          <textarea class="form-control" id="manual-${escapeHtml(conflict.id || "")}" rows="3" data-manual-conflict-id="${escapeHtml(conflict.id || "")}"></textarea>
          <button class="btn btn-sm btn-outline-secondary mt-2" type="button" data-manual-submit-conflict-id="${escapeHtml(conflict.id || "")}">Save manual resolution</button>
        </div>
      ` : ""}
    </article>
  `).join("");
}
