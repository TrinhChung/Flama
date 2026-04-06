export async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.message || "Khong the hoan tat yeu cau.");
    error.status = response.status;
    error.code = data.error || "REQUEST_FAILED";
    error.payload = data;
    throw error;
  }
  return data;
}

export function fetchDeckDetail(deckItemId) {
  return requestJson(`/api/shared/decks/${deckItemId}`);
}

export function fetchLocalChanges(deckItemId) {
  return requestJson(`/api/shared/decks/${deckItemId}/change-requests/local-changes`);
}

export function fetchActiveRequest(deckItemId) {
  return requestJson(`/api/shared/decks/${deckItemId}/change-requests/active`);
}

export function createDraft(deckItemId, payload) {
  return requestJson(`/api/shared/decks/${deckItemId}/change-requests/draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
}

export function syncRequest(deckItemId, requestId) {
  return requestJson(`/api/shared/decks/${deckItemId}/change-requests/${requestId}/sync`, {
    method: "POST",
  });
}

export function resolveConflict(deckItemId, requestId, conflictId, payload) {
  return requestJson(
    `/api/shared/decks/${deckItemId}/change-requests/${requestId}/conflicts/${conflictId}/resolve`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    },
  );
}

export function submitRequest(deckItemId, requestId) {
  return requestJson(`/api/shared/decks/${deckItemId}/change-requests/${requestId}/submit`, {
    method: "POST",
  });
}

export function fetchIncomingRequests(deckItemId) {
  const suffix = deckItemId ? `?deck_item_id=${encodeURIComponent(deckItemId)}` : "";
  return requestJson(`/api/change-requests/incoming${suffix}`);
}

export function fetchRequestDetail(requestId) {
  return requestJson(`/api/change-requests/${requestId}`);
}

export function approveRequest(requestId, payload) {
  return requestJson(`/api/change-requests/${requestId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
}

export function rejectRequest(requestId, payload) {
  return requestJson(`/api/change-requests/${requestId}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
}
