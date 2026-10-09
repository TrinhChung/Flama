async (page) => {
  // All writes are synthetic sessions in the dedicated Chrome profile.
  await page.route('**/__cross_tab_probe', route => route.fulfill({ contentType: 'text/html', body: '<html><body>Isolated cross-tab storage check</body></html>' }));
  await page.goto('http://127.0.0.1:5179/__cross_tab_probe');
  const key = await page.evaluate(async () => {
    const { studySnapshotFixture } = await import('/src/features/study/session/studySessionTestFixture.ts');
    const engine = await import('/src/features/study/session/studySessionEngine.ts');
    const store = await import('/src/features/study/session/sessionStore.ts');
    const snapshot = studySnapshotFixture();
    snapshot.schema_version = 'study-session.v4'; snapshot.authority_mode = 'NOTE'; snapshot.enrollment_epoch = '1';
    snapshot.session_id = crypto.randomUUID(); snapshot.scope.id = `cross-tab-probe-${Date.now()}`;
    const pin = { schema_version: 'study-note-authority-pin.v1', authority_mode: 'NOTE', enrollment_epoch: '1', logical_note_key: 'probe-note', subject_generation: '1', base_authority_revision: '0', base_authority_state_hash: '11'.repeat(32) };
    snapshot.cards = [snapshot.cards[0], { ...snapshot.cards[0], card_id: 'sibling-card' }].map(card => ({ ...card, authority_pin: pin }));
    const session = engine.createPersistedSession(snapshot), id = snapshot.cards[0].card_id;
    const answered = engine.applyLocalAnswer(session, id, 'good', engine.decisionForCard(session, id, Date.parse(snapshot.server_now_utc) + 1000), 300);
    if (!await store.saveStudySession(answered)) throw new Error('Initial v4 save failed');
    window.__crossTabCheckpoint = answered;
    return answered.scope_key;
  });
  const other = await page.context().newPage();
  try {
    await other.route('**/__cross_tab_probe', route => route.fulfill({ contentType: 'text/html', body: '<html><body>Second isolated tab</body></html>' }));
    await other.goto('http://127.0.0.1:5179/__cross_tab_probe');
    await other.evaluate(async key => {
      const store = await import('/src/features/study/session/sessionStore.ts');
      const { applyCardContentPatch } = await import('/src/features/study/session/contentPatchAdapter.ts');
      const loaded = await store.loadStudySessionWithDurability(key);
      if (!loaded.durable || loaded.session.events[0].authority_mode !== 'NOTE' || loaded.session.snapshot.cards[1].state.reps !== 1) throw new Error('V4 pin/sibling answer restore failed');
      const patched = applyCardContentPatch(loaded.session, loaded.session.snapshot.cards[0].card_id, { Word: 'second-tab' }).nextSession;
      if (!await store.saveStudySession(patched)) throw new Error('Second tab patch save failed');
    }, key);
    // This is storage-level compatibility with the prior last-writer policy.
    // Lease ownership/concurrency rules live outside this persistence adapter.
    await page.evaluate(async () => {
      const store = await import('/src/features/study/session/sessionStore.ts');
      if (!await store.saveStudySession(window.__crossTabCheckpoint)) throw new Error('Missing cached artifact was not reinserted');
    });
    await other.reload();
    const result = await other.evaluate(async key => {
      const store = await import('/src/features/study/session/sessionStore.ts');
      const engine = await import('/src/features/study/session/studySessionEngine.ts');
      const { canonicalDigest } = await import('/src/features/study/session/canonicalDigest.ts');
      const loaded = await store.loadStudySessionWithDurability(key);
      if (!loaded.durable || loaded.session.events.length !== 1) throw new Error('Cross-tab checkpoint references a deleted bundle');
      const extracted = engine.extractPendingBatch(loaded.session);
      if (!await store.saveStudySession(extracted.session)) throw new Error('V4 batch save failed');
      const batched = (await store.loadStudySessionWithDurability(key)).session;
      const receipt = { schema_version: 'study-commit-receipt.v2', authority_mode: 'NOTE', enrollment_epoch: '1', batch_receipt_schema_version: 'study-note-batch-receipt.v1', success: true,
        session_id: loaded.session.snapshot.session_id, batch_id: extracted.batch.batch_id, commit_id: extracted.batch.batch_id, batch_sequence: 1, commit_reason: 'rollover', is_final: false,
        applied_event_count: 1, cumulative_event_count: 1, updated_cards: [], rating_counts: { again: 0, hard: 0, good: 1, easy: 0 }, committed_at: '2026-02-22T09:00:01Z', request_hash: canonicalDigest(extracted.batch), receipt_hash: `sha256-${'11'.repeat(32)}` };
      const acknowledged = engine.acknowledgeBatchReceipt(batched, extracted.batch.batch_id, receipt);
      if (!await store.saveStudySession(acknowledged)) throw new Error('V4 receipt checkpoint save failed');
      const final = await store.loadStudySessionWithDurability(key);
      if (!final.durable || final.session.in_flight_batches.length !== 0 || final.session.snapshot.cards[1].authority_pin.logical_note_key !== 'probe-note') throw new Error('V4 receipt/pin identity lost');
      await store.removeStudySession(key);
      return { cache_eviction_in_other_tab: true, cached_bundle_reinserted_atomically: true, v4_answer_sibling_and_pins: true, v4_batch_and_receipt_restore: true };
    }, key);
    return result;
  } finally {
    await other.close();
    await page.evaluate(async key => { const store = await import('/src/features/study/session/sessionStore.ts'); await store.removeStudySession(key); delete window.__crossTabCheckpoint; }, key);
  }
}
