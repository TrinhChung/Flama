async (page) => {
  await page.route('**/__legacy_perf_probe', route => route.fulfill({
    contentType: 'text/html', body: '<html><body>Isolated offline persistence probe</body></html>',
  }));
  await page.goto('http://127.0.0.1:5179/__legacy_perf_probe');
  return await page.evaluate(async () => {
    const { studySnapshotFixture } = await import('/src/features/study/session/studySessionTestFixture.ts');
    const { createPersistedSession } = await import('/src/features/study/session/studySessionEngine.ts');
    const { saveStudySession, loadStudySessionWithDurability, removeStudySession } = await import('/src/features/study/session/sessionStore.ts');
    const { canonicalJson } = await import('/src/features/study/session/canonicalDigest.ts');
    const results = [];
    const median = values => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
    for (const count of [100, 1000, 5000]) {
      const snapshot = studySnapshotFixture();
      snapshot.schema_version = 'study-session.v4';
      snapshot.authority_mode = 'NOTE';
      snapshot.enrollment_epoch = '1';
      snapshot.session_id = crypto.randomUUID();
      snapshot.scope.id = `perf-${count}-${Date.now()}`;
      const base = snapshot.cards[0], content = snapshot.contents.content;
      snapshot.contents = {};
      snapshot.cards = Array.from({ length: count }, (_, index) => {
        const noteId = crypto.randomUUID(), cardId = crypto.randomUUID(), key = `content-${index}`;
        snapshot.contents[key] = { ...content, id: noteId, note_id: noteId,
          field_values: { Word: 'cat', Body: 'x'.repeat(1024) }, render_context: { Word: 'cat' } };
        return { ...base, card_id: cardId, note_id: noteId, content_key: key,
          state: { ...base.state }, authority_pin: {
            schema_version: 'study-note-authority-pin.v1', authority_mode: 'NOTE', enrollment_epoch: '1',
            logical_note_key: noteId, subject_generation: '1', base_authority_revision: '0',
            base_authority_state_hash: '11'.repeat(32),
          } };
      });
      let session = createPersistedSession(snapshot);
      try {
        const initialStart = performance.now();
        if (!await saveStudySession(session)) throw new Error('Initial write is not durable');
        const initialMs = performance.now() - initialStart;
        const samples = [];
        for (let index = 0; index < 10; index++) {
          session = { ...session, updated_at_ms: session.updated_at_ms + 1 };
          const start = performance.now();
          if (!await saveStudySession(session)) throw new Error('Checkpoint write is not durable');
          if (index >= 3) samples.push(performance.now() - start);
        }
        const restored = await loadStudySessionWithDurability(session.scope_key);
        const canonicalStored = value => canonicalJson(JSON.parse(JSON.stringify(value)));
        if (!restored.durable || canonicalStored(restored.session) !== canonicalStored(session)) {
          // Normalization adds optional defaults. Compare normalized roundtrips.
          const { normalizePersistedStudySession } = await import('/src/features/study/session/sessionRestore.ts');
          const expected = normalizePersistedStudySession(session, session.scope_key);
          if (!restored.durable || canonicalStored(restored.session) !== canonicalStored(expected.session)) {
            throw new Error('Durable restore differs from the normalized checkpoint');
          }
        }
        results.push({ cards: count, first_save_ms: initialMs, checkpoint_median_browser_ms: median(samples),
          samples_ms: samples, session_json_bytes: new TextEncoder().encode(JSON.stringify(session)).length,
          durable_restore_parity: true });
      } finally { await removeStudySession(session.scope_key); }
    }
    return { browser: navigator.userAgent, measurement: 'Synthetic NOTE/v4, initial content 1KiB/note, no answer events. Real save + IndexedDB transaction completion; 3 warmups and 7 checkpoints, browser profile isolated. No production/network latency claim.', cases: results };
  });
}
