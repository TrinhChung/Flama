export async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.message || "Request failed.");
    return data;
}

export async function fetchDeckDetail(deckItemId) {
    return requestJson(`/api/shared/decks/${deckItemId}`);
}

export async function installDeck(deckItemId) {
    return requestJson(`/api/shared/decks/${deckItemId}/install`, { method: "POST" });
}

export async function submitRating(deckItemId, rating, comment) {
    return requestJson(`/api/shared/decks/${deckItemId}/rate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating, comment }),
    });
}

export async function fetchSourceNoteType(noteTypeId) {
    return requestJson(`/api/shared/note-types/${noteTypeId}`);
}

export async function fetchTemplatePreview(deckItemId, templateId, noteId) {
    const payload = {};
    if (noteId) {
        payload.note_id = noteId;
    }
    return requestJson(`/api/shared/decks/${deckItemId}/templates/${templateId}/preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
}
