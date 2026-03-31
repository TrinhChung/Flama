const DATE_FORMATTER = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

const REQUEST_STATUS_META = {
  local_preview: {
    label: "Local edits",
    tone: "accent",
    icon: "bi-pencil-square",
    description: "Overlay changes đang sẵn sàng để dựng thành draft request.",
  },
  needs_sync: {
    label: "Needs sync",
    tone: "warning",
    icon: "bi-arrow-repeat",
    description: "Draft đã có nhưng cần sync lại với upstream trước khi gửi review.",
  },
  draft: {
    label: "Draft ready",
    tone: "info",
    icon: "bi-send-check",
    description: "Draft đã sạch conflict và có thể submit cho owner review.",
  },
  has_conflict: {
    label: "Has conflict",
    tone: "danger",
    icon: "bi-exclamation-diamond",
    description: "Upstream đã đổi. Hãy resolve conflict trước khi submit.",
  },
  pending_review: {
    label: "Pending review",
    tone: "warning",
    icon: "bi-hourglass-split",
    description: "Request đã được gửi và đang chờ owner quyết định.",
  },
  merged: {
    label: "Merged",
    tone: "success",
    icon: "bi-check2-circle",
    description: "Owner đã approve và merge thay đổi vào source deck.",
  },
  rejected: {
    label: "Rejected",
    tone: "muted",
    icon: "bi-slash-circle",
    description: "Owner đã reject. Overlay edits vẫn nằm ở local install.",
  },
  unknown: {
    label: "Unknown",
    tone: "neutral",
    icon: "bi-question-circle",
    description: "Không xác định được trạng thái request.",
  },
};

const CHANGE_TYPE_META = {
  note_field_set: {
    label: "Field update",
    tone: "info",
    icon: "bi-input-cursor-text",
    kicker: "Content",
  },
  note_field_remove: {
    label: "Field removal",
    tone: "danger",
    icon: "bi-eraser",
    kicker: "Content",
  },
  field_def_update: {
    label: "Field definition update",
    tone: "accent",
    icon: "bi-ui-checks-grid",
    kicker: "Schema",
  },
  field_def_disable: {
    label: "Field disabled",
    tone: "warning",
    icon: "bi-slash-square",
    kicker: "Schema",
  },
  field_def_add: {
    label: "Field added",
    tone: "success",
    icon: "bi-plus-square",
    kicker: "Schema",
  },
  field_order_update: {
    label: "Field order update",
    tone: "accent",
    icon: "bi-arrow-down-up",
    kicker: "Structure",
  },
};

const CONFLICT_META = {
  note_field: {
    label: "Note field conflict",
    tone: "danger",
    icon: "bi-journal-x",
  },
  field_order: {
    label: "Field order conflict",
    tone: "warning",
    icon: "bi-arrow-left-right",
  },
  field_def: {
    label: "Field definition conflict",
    tone: "danger",
    icon: "bi-braces-asterisk",
  },
};

const WORKFLOW_STEPS = [
  {
    key: "capture",
    number: "1",
    label: "Capture",
    help: "Chốt local overlay changes thành một proposal rõ ràng.",
  },
  {
    key: "sync",
    number: "2",
    label: "Sync",
    help: "So với upstream mới nhất để phát hiện drift và conflict.",
  },
  {
    key: "submit",
    number: "3",
    label: "Submit",
    help: "Gửi request khi draft đã sạch conflict và mô tả đủ rõ.",
  },
  {
    key: "review",
    number: "4",
    label: "Review",
    help: "Owner đọc diff và quyết định merge hoặc reject.",
  },
];

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function formatDate(value) {
  if (!value) return "Chưa có";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Chưa có";
  return DATE_FORMATTER.format(date);
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

function truncateMiddle(value, { left = 12, right = 10 } = {}) {
  const raw = String(value ?? "");
  if (!raw || raw.length <= left + right + 3) {
    return raw || "N/A";
  }
  return `${raw.slice(0, left)}...${raw.slice(-right)}`;
}

function formatManualValue(value) {
  if (typeof value === "undefined") {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  if (value === null) {
    return "null";
  }
  return JSON.stringify(value, null, 2);
}

function pluralize(count, singular, plural = `${singular}s`) {
  const number = Number(count || 0);
  return `${number} ${number === 1 ? singular : plural}`;
}

function humanizeChangeType(changeType) {
  const meta = CHANGE_TYPE_META[changeType];
  if (meta) {
    return meta.label;
  }
  return String(changeType || "Change")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function getChangeTypeMeta(changeType) {
  return CHANGE_TYPE_META[changeType] || {
    label: humanizeChangeType(changeType),
    tone: "neutral",
    icon: "bi-pencil",
    kicker: "Change",
  };
}

function getConflictMeta(conflictType) {
  return CONFLICT_META[conflictType] || {
    label: String(conflictType || "Conflict")
      .replaceAll("_", " ")
      .replace(/\b\w/g, (match) => match.toUpperCase()),
    tone: "danger",
    icon: "bi-exclamation-triangle",
  };
}

export function getRequestStatusMeta(status) {
  return REQUEST_STATUS_META[status] || REQUEST_STATUS_META.unknown;
}

function renderEmptyState(message, { icon = "bi-inbox" } = {}) {
  return `
    <div class="change-request-empty">
      <div class="change-request-status-list mb-2">
        <span class="change-request-status-badge" data-tone="neutral">
          <i class="bi ${escapeHtml(icon)}"></i> Trống
        </span>
      </div>
      <div>${escapeHtml(message)}</div>
    </div>
  `;
}

function renderChip(label, { tone = "neutral", icon = "" } = {}) {
  return `
    <span class="change-request-chip" data-tone="${escapeHtml(tone)}">
      ${icon ? `<i class="bi ${escapeHtml(icon)}"></i>` : ""}
      ${escapeHtml(label)}
    </span>
  `;
}

export function renderStatusBadge(status) {
  const meta = getRequestStatusMeta(status);
  return `
    <span class="change-request-status-badge" data-tone="${escapeHtml(meta.tone)}">
      <i class="bi ${escapeHtml(meta.icon)}"></i>
      ${escapeHtml(meta.label)}
    </span>
  `;
}

function renderMetricCard(label, value, help, { compact = false } = {}) {
  return `
    <article class="change-request-metric-card">
      <div class="change-request-metric-label">${escapeHtml(label)}</div>
      <div class="change-request-metric-value${compact ? " change-request-metric-value--compact" : ""}">${escapeHtml(value)}</div>
      ${help ? `<div class="change-request-metric-help">${escapeHtml(help)}</div>` : ""}
    </article>
  `;
}

function renderPersonCard(label, value, meta) {
  return `
    <article class="change-request-person-card">
      <div class="change-request-person-label">${escapeHtml(label)}</div>
      <div class="change-request-person-value">${escapeHtml(value)}</div>
      ${meta ? `<div class="change-request-person-meta">${escapeHtml(meta)}</div>` : ""}
    </article>
  `;
}

function renderNoteCard(title, body) {
  return `
    <article class="change-request-note-card">
      <div class="change-request-note-title">${escapeHtml(title)}</div>
      <p class="change-request-note-body">${escapeHtml(body)}</p>
    </article>
  `;
}

function renderValueCard(label, value, { tone = "before" } = {}) {
  return `
    <div class="change-request-value-card" data-tone="${escapeHtml(tone)}">
      <span class="change-request-value-label">${escapeHtml(label)}</span>
      <pre class="change-request-code">${escapeHtml(formatValue(value))}</pre>
    </div>
  `;
}

function buildStageStates(status) {
  switch (status) {
    case "needs_sync":
      return {
        capture: "complete",
        sync: "current",
        submit: "upcoming",
        review: "upcoming",
      };
    case "has_conflict":
      return {
        capture: "complete",
        sync: "blocked",
        submit: "upcoming",
        review: "upcoming",
      };
    case "draft":
      return {
        capture: "complete",
        sync: "complete",
        submit: "current",
        review: "upcoming",
      };
    case "pending_review":
      return {
        capture: "complete",
        sync: "complete",
        submit: "complete",
        review: "current",
      };
    case "merged":
    case "rejected":
      return {
        capture: "complete",
        sync: "complete",
        submit: "complete",
        review: "complete",
      };
    case "local_preview":
    default:
      return {
        capture: "current",
        sync: "upcoming",
        submit: "upcoming",
        review: "upcoming",
      };
  }
}

function renderWorkflowStages(status) {
  const states = buildStageStates(status);
  return WORKFLOW_STEPS.map((step) => `
    <article class="change-request-stage" data-state="${escapeHtml(states[step.key] || "upcoming")}">
      <span class="change-request-stage-dot">${escapeHtml(step.number)}</span>
      <div>
        <div class="change-request-stage-label">${escapeHtml(step.label)}</div>
        <div class="change-request-stage-help">${escapeHtml(step.help)}</div>
      </div>
    </article>
  `).join("");
}

function renderChangeCountChips(changeCounts) {
  const entries = Object.entries(changeCounts || {});
  if (!entries.length) {
    return "";
  }
  return entries
    .sort((left, right) => Number(right[1] || 0) - Number(left[1] || 0))
    .map(([key, value]) => renderChip(`${humanizeChangeType(key)} · ${value}`, {
      tone: "neutral",
      icon: getChangeTypeMeta(key).icon,
    }))
    .join("");
}

function getRequestNextAction(requestData) {
  if (!requestData) {
    return "Tạo draft từ local overlay changes hiện tại.";
  }

  switch (requestData.status) {
    case "needs_sync":
      return "Chạy sync để kiểm tra request có lệch upstream hay không.";
    case "has_conflict":
      return "Resolve toàn bộ conflict trước khi submit cho owner.";
    case "draft":
      return "Draft đã sạch conflict. Kiểm tra diff cuối cùng rồi submit.";
    case "pending_review":
      return requestData.can_review
        ? "Bạn có thể approve để merge hoặc reject kèm lý do."
        : "Request đang chờ owner review. Bạn có thể mở detail để theo dõi.";
    case "merged":
      return "Source deck đã được cập nhật. Overlay local nên quay về trạng thái sạch.";
    case "rejected":
      return "Request đã đóng. Nếu muốn gửi lại, hãy chỉnh overlay và tạo request mới.";
    default:
      return "Hoàn thiện mô tả, sau đó tạo draft từ local changes.";
  }
}

function buildSummaryBadges(requestData) {
  const badges = [renderStatusBadge(requestData.status)];

  if (Number(requestData.unresolved_conflict_count || 0) > 0) {
    badges.push(renderChip(`${requestData.unresolved_conflict_count} conflict`, {
      tone: "danger",
      icon: "bi-exclamation-diamond",
    }));
  } else {
    badges.push(renderChip("No open conflicts", {
      tone: "success",
      icon: "bi-check2-all",
    }));
  }

  if (requestData.can_review) {
    badges.push(renderChip("Bạn có thể review", {
      tone: "warning",
      icon: "bi-shield-check",
    }));
  } else if (requestData.can_submit) {
    badges.push(renderChip("Sẵn sàng gửi", {
      tone: "info",
      icon: "bi-send-check",
    }));
  } else if (requestData.can_resolve) {
    badges.push(renderChip("Cần resolve conflict", {
      tone: "danger",
      icon: "bi-tools",
    }));
  }

  return badges.join("");
}

export function renderRequestSummary(container, requestData, { emptyText = "Không có request." } = {}) {
  if (!container) return;

  if (!requestData) {
    container.innerHTML = renderEmptyState(emptyText);
    return;
  }

  const statusMeta = getRequestStatusMeta(requestData.status);
  const summaryNotes = [];
  if (requestData.description) {
    summaryNotes.push(renderNoteCard("Mô tả từ requester", requestData.description));
  }
  if (requestData.review_comment) {
    summaryNotes.push(renderNoteCard("Nhận xét review", requestData.review_comment));
  }

  const countChips = renderChangeCountChips(requestData.change_counts);
  const detailChips = [
    renderChip(`Requester ${requestData.requester?.username || "Unknown"}`, {
      tone: "neutral",
      icon: "bi-person",
    }),
    renderChip(`Owner ${requestData.owner?.username || "Unknown"}`, {
      tone: "neutral",
      icon: "bi-person-badge",
    }),
    renderChip(`Deck ${requestData.deck_item?.title || "Unknown deck"}`, {
      tone: "neutral",
      icon: "bi-collection",
    }),
    renderChip(`${requestData.item_count || 0} changes`, {
      tone: "info",
      icon: "bi-diagram-3",
    }),
    renderChip(`${requestData.unresolved_conflict_count || 0} conflicts`, {
      tone: Number(requestData.unresolved_conflict_count || 0) ? "danger" : "success",
      icon: Number(requestData.unresolved_conflict_count || 0) ? "bi-exclamation-diamond" : "bi-check2-all",
    }),
  ];

  const submittedLabel = requestData.submitted_at
    ? `Submitted ${formatDate(requestData.submitted_at)}`
    : `Updated ${formatDate(requestData.updated_at || requestData.created_at)}`;
  detailChips.push(renderChip(submittedLabel, {
    tone: "neutral",
    icon: "bi-clock-history",
  }));

  if (requestData.last_synced_at) {
    detailChips.push(renderChip(`Last sync ${formatDate(requestData.last_synced_at)}`, {
      tone: "neutral",
      icon: "bi-arrow-repeat",
    }));
  }

  if (requestData.reviewed_by?.username) {
    detailChips.push(renderChip(`Reviewed by ${requestData.reviewed_by.username}`, {
      tone: "neutral",
      icon: "bi-shield-check",
    }));
  }

  container.innerHTML = `
    <div class="change-request-summary">
      <div class="change-request-summary-head">
        <div>
          <h3 class="change-request-summary-title">${escapeHtml(requestData.title || "Change Request")}</h3>
          <p class="change-request-summary-subtitle change-request-copy">${escapeHtml(statusMeta.description)}</p>
        </div>
        <div class="change-request-status-list">
          ${buildSummaryBadges(requestData)}
        </div>
      </div>

      <div class="change-request-chip-list">
        ${detailChips.join("")}
      </div>

      ${countChips ? `<div class="change-request-chip-list">${countChips}</div>` : ""}

      ${renderNoteCard("Bước tiếp theo", getRequestNextAction(requestData))}

      ${summaryNotes.join("")}

      ${requestData.overlay_fingerprint ? `
        <div class="change-request-fingerprint change-request-card-meta">
          Overlay fingerprint: <code>${escapeHtml(truncateMiddle(requestData.overlay_fingerprint))}</code>
        </div>
      ` : ""}
    </div>
  `;
}

export function renderLocalPreviewSummary(container, preview, { deckTitle = "Deck" } = {}) {
  if (!container) return;

  if (!preview || !preview.item_count) {
    container.innerHTML = renderEmptyState("Clone này chưa có local changes để gửi lên source deck.", {
      icon: "bi-pencil",
    });
    return;
  }

  const changeCounts = renderChangeCountChips(preview.change_counts);
  container.innerHTML = `
    <div class="change-request-summary">
      <div class="change-request-summary-head">
        <div>
          <h3 class="change-request-summary-title">Local overlay changes đã sẵn sàng</h3>
          <p class="change-request-summary-subtitle change-request-copy">Kiểm tra diff, thêm mô tả và tạo draft để đóng gói proposal gửi cho owner.</p>
        </div>
        <div class="change-request-status-list">
          ${renderStatusBadge("local_preview")}
          ${renderChip(`${preview.item_count} thay đổi`, {
            tone: "info",
            icon: "bi-diagram-3",
          })}
        </div>
      </div>

      <div class="change-request-chip-list">
        ${renderChip(`Deck ${deckTitle || "Deck"}`, {
          tone: "neutral",
          icon: "bi-collection",
        })}
        ${renderChip(`${Object.keys(preview.change_counts || {}).length} nhóm thay đổi`, {
          tone: "neutral",
          icon: "bi-tags",
        })}
        ${renderChip(`Fingerprint ${truncateMiddle(preview.overlay_fingerprint)}`, {
          tone: "neutral",
          icon: "bi-fingerprint",
        })}
      </div>

      ${changeCounts ? `<div class="change-request-chip-list">${changeCounts}</div>` : ""}

      ${renderNoteCard("Bước tiếp theo", "Tạo draft để snapshot trạng thái overlay hiện tại, sau đó sync với upstream trước khi submit.")}
    </div>
  `;
}

export function renderChangeItems(container, items, { emptyText = "Không có thay đổi." } = {}) {
  if (!container) return;

  const rows = Array.isArray(items) ? items : [];
  if (!rows.length) {
    container.innerHTML = renderEmptyState(emptyText, { icon: "bi-file-earmark-minus" });
    return;
  }

  container.innerHTML = rows.map((item) => {
    const meta = getChangeTypeMeta(item.change_type);
    const metadata = item.metadata || {};
    const chips = [
      renderChip(meta.label, { tone: meta.tone, icon: meta.icon }),
    ];

    if (metadata.field_name) {
      chips.push(renderChip(`Field ${metadata.field_name}`, {
        tone: "neutral",
        icon: "bi-tag",
      }));
    }
    if (metadata.source_note_label) {
      chips.push(renderChip(`Note ${metadata.source_note_label}`, {
        tone: "neutral",
        icon: "bi-journal-text",
      }));
    }
    if (item.is_conflict) {
      chips.push(renderChip("Conflict", {
        tone: "danger",
        icon: "bi-exclamation-diamond",
      }));
    }

    return `
      <article class="change-request-entry">
        <div class="change-request-entry-head">
          <div>
            <p class="change-request-entry-kicker">${escapeHtml(meta.kicker)}</p>
            <h3 class="change-request-card-title">${escapeHtml(item.path_label || meta.label)}</h3>
            <p class="change-request-card-meta">${escapeHtml(meta.label)}${metadata.source_note_id ? ` · Source note ${metadata.source_note_id}` : ""}</p>
          </div>
          <div class="change-request-chip-list">
            ${chips.join("")}
          </div>
        </div>

        <div class="change-request-diff-grid">
          ${renderValueCard("Before", item.before_value, { tone: "before" })}
          ${renderValueCard("After", item.effective_after_value ?? item.after_value, { tone: "after" })}
        </div>
      </article>
    `;
  }).join("");
}

export function renderConflicts(container, conflicts, { interactive = false } = {}) {
  if (!container) return;

  const rows = Array.isArray(conflicts) ? conflicts : [];
  if (!rows.length) {
    container.innerHTML = renderEmptyState("Không có conflict.", { icon: "bi-check2-circle" });
    return;
  }

  container.innerHTML = rows.map((conflict) => {
    const meta = getConflictMeta(conflict.conflict_type);
    const resolved = Boolean(conflict.resolved_at);
    const chips = [
      renderChip(meta.label, { tone: meta.tone, icon: meta.icon }),
      resolved
        ? renderChip(`Resolved · ${conflict.resolution_mode || "manual"}`, {
          tone: "success",
          icon: "bi-check2-all",
        })
        : renderChip("Unresolved", {
          tone: "danger",
          icon: "bi-exclamation-octagon",
        }),
    ];

    return `
      <article class="change-request-entry">
        <div class="change-request-entry-head">
          <div>
            <p class="change-request-entry-kicker">Conflict</p>
            <h3 class="change-request-card-title">${escapeHtml(meta.label)}</h3>
            <p class="change-request-card-meta">
              ${resolved ? `Đã resolve lúc ${escapeHtml(formatDate(conflict.resolved_at))}` : "Cần quyết định trước khi request có thể tiếp tục."}
            </p>
          </div>
          <div class="change-request-chip-list">
            ${chips.join("")}
          </div>
        </div>

        <div class="change-request-diff-grid">
          ${renderValueCard("Base", conflict.base_value, { tone: "before" })}
          ${renderValueCard("Upstream", conflict.upstream_value, { tone: "before" })}
          ${renderValueCard("Mine", conflict.local_value, { tone: "after" })}
          ${renderValueCard("Resolved", conflict.resolved_value, { tone: "after" })}
        </div>

        ${interactive ? `
          <div class="change-request-conflict-actions">
            <button class="btn btn-dark btn-sm" type="button" data-resolve-conflict-id="${escapeHtml(conflict.id || "")}" data-resolution-mode="keep_mine">
              <i class="bi bi-person-check"></i> Keep mine
            </button>
            <button class="btn btn-outline-secondary btn-sm" type="button" data-resolve-conflict-id="${escapeHtml(conflict.id || "")}" data-resolution-mode="keep_upstream">
              <i class="bi bi-arrow-up-right-circle"></i> Keep upstream
            </button>
          </div>
          <div class="change-request-manual-card">
            <label class="form-label small" for="manual-${escapeHtml(conflict.id || "")}">Manual value (JSON hoặc text)</label>
            <textarea class="form-control" id="manual-${escapeHtml(conflict.id || "")}" rows="4" data-manual-conflict-id="${escapeHtml(conflict.id || "")}">${escapeHtml(formatManualValue(conflict.resolved_value))}</textarea>
            <button class="btn btn-outline-secondary btn-sm mt-2" type="button" data-manual-submit-conflict-id="${escapeHtml(conflict.id || "")}">
              <i class="bi bi-save2"></i> Save manual resolution
            </button>
          </div>
        ` : ""}
      </article>
    `;
  }).join("");
}
