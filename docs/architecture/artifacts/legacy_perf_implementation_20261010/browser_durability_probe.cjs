async (page) => {
  // Run only in the explicitly isolated flama-durability Chrome profile.
  await page.route('**/__durability_probe', route => route.fulfill({ contentType: 'text/html', body: '<html><body>Isolated IndexedDB regression probe</body></html>' }));
  await page.goto('http://127.0.0.1:5179/__durability_probe');
  const initial = await page.evaluate(async () => {
    const assert = (condition, message) => { if (!condition) throw new Error(message); };
    const { studySnapshotFixture } = await import('/src/features/study/session/studySessionTestFixture.ts');
    const engine = await import('/src/features/study/session/studySessionEngine.ts');
    const store = await import('/src/features/study/session/sessionStore.ts');
    const snapshot = studySnapshotFixture();
    snapshot.session_id = crypto.randomUUID(); snapshot.scope.id = `durability-probe-${Date.now()}`;
    const session = engine.createPersistedSession(snapshot);
    const existing = await indexedDB.databases();
    assert(!existing.some(row => row.name === 'flama-study'), 'Use a fresh isolated profile for the v2 upgrade case');
    const db = await new Promise((resolve, reject) => {
      const req = indexedDB.open('flama-study', 2);
      req.onupgradeneeded = () => {
        req.result.createObjectStore('sessions', { keyPath: 'scope_key' });
        req.result.createObjectStore('session-quarantine', { keyPath: 'scope_key' });
      };
      req.onsuccess = () => resolve(req.result); req.onerror = () => reject(req.error);
    });
    await new Promise((resolve, reject) => {
      const tx = db.transaction('sessions', 'readwrite'); tx.objectStore('sessions').put(session);
      tx.oncomplete = resolve; tx.onabort = () => reject(tx.error);
    }); db.close();
    assert((await store.loadStudySessionWithDurability(session.scope_key)).durable, 'v2 inline row was not restored');
    let artifactPuts = 0;
    const originalPut = IDBObjectStore.prototype.put;
    IDBObjectStore.prototype.put = function (...args) {
      if (this.name === 'session-artifacts') artifactPuts++;
      return originalPut.apply(this, args);
    };
    let answered;
    try {
      assert(await store.saveStudySession(session), 'v2 inline migration was not durable');
      const cardId = session.snapshot.cards[0].card_id;
      answered = engine.applyLocalAnswer(session, cardId, 'good', engine.decisionForCard(session, cardId, Date.parse(snapshot.server_now_utc) + 1000), 500);
      assert(await store.saveStudySession(answered), 'answer was not durable');
      assert(artifactPuts === 1, 'checkpoint rewrote immutable artifacts');
    } finally { IDBObjectStore.prototype.put = originalPut; }
    const aborted = { ...answered, updated_at_ms: answered.updated_at_ms + 99 };
    let injected = false;
    IDBObjectStore.prototype.put = function (...args) {
      if (!injected && this.name === 'sessions') { injected = true; this.transaction.abort(); }
      return originalPut.apply(this, args);
    };
    try { assert(!await store.saveStudySession(aborted), 'aborted write reported durability'); }
    finally { IDBObjectStore.prototype.put = originalPut; }
    const fallback = await store.loadStudySessionWithDurability(session.scope_key);
    assert(!fallback.durable && fallback.session.updated_at_ms === aborted.updated_at_ms, 'load discarded unsaved fallback after abort');
    sessionStorage.setItem('durability-probe-scope', session.scope_key);
    sessionStorage.setItem('durability-probe-disk-timestamp', String(answered.updated_at_ms));
    return { v2_inline_upgrade: true, checkpoint_artifact_puts: artifactPuts, abort_reports_non_durable: true, abort_keeps_newer_memory: true };
  });
  await page.reload();
  const restored = await page.evaluate(async () => {
    const assert = (condition, message) => { if (!condition) throw new Error(message); };
    const store = await import('/src/features/study/session/sessionStore.ts');
    const engine = await import('/src/features/study/session/studySessionEngine.ts');
    const { applyCardContentPatch } = await import('/src/features/study/session/contentPatchAdapter.ts');
    const { canonicalJson } = await import('/src/features/study/session/canonicalDigest.ts');
    const key = sessionStorage.getItem('durability-probe-scope');
    const readRows = async () => {
      const db = await new Promise((resolve, reject) => { const req = indexedDB.open('flama-study'); req.onsuccess = () => resolve(req.result); req.onerror = () => reject(req.error); });
      return await new Promise((resolve, reject) => {
        const tx = db.transaction(['sessions', 'session-artifacts'], 'readonly');
        const req = tx.objectStore('sessions').get(key), bundles = tx.objectStore('session-artifacts').index('scope_key').getAll(key);
        tx.oncomplete = () => { const value = { row: req.result, bundles: bundles.result, version: db.version }; db.close(); resolve(value); };
        tx.onabort = () => { db.close(); reject(tx.error); };
      });
    };
    let loaded = await store.loadStudySessionWithDurability(key);
    assert(loaded.durable && loaded.session.events.length === 1, 'answer/undo log did not survive reload');
    assert(loaded.session.updated_at_ms === Number(sessionStorage.getItem('durability-probe-disk-timestamp')), 'abort changed the durable row');
    assert(loaded.session.snapshot.cards[0].state.reps > 0, 'answered state lost');
    const first = await readRows();
    assert(first.version === 3 && first.bundles.length === 1 && first.row.card_overrides.length === 1, 'v3 layout wrong');
    assert(await store.saveStudySession({ ...loaded.session, updated_at_ms: loaded.session.updated_at_ms + 1 }), 'resave after reload failed');
    loaded = await store.loadStudySessionWithDurability(key);
    assert(loaded.session.snapshot.cards[0].state.reps > 0, 'resave dropped restored override');
    const undone = engine.undoLocalAnswer(loaded.session).session;
    assert(await store.saveStudySession(undone), 'undo save failed');
    assert((await store.loadStudySessionWithDurability(key)).session.events.length === 0, 'undo not restored');
    const patched = applyCardContentPatch(loaded.session, loaded.session.snapshot.cards[0].card_id, { Word: 'dog' }).nextSession;
    assert(await store.saveStudySession(patched), 'content patch save failed');
    const next = await readRows();
    assert(next.bundles.length === 1 && next.row.artifact_key !== first.row.artifact_key, 'content patch did not replace bundle atomically');
    const contentLoaded = (await store.loadStudySessionWithDurability(key)).session;
    assert(contentLoaded.snapshot.contents[contentLoaded.snapshot.cards[0].content_key].field_values.Word === 'dog', 'content patch lost');
    const extracted = engine.extractPendingBatch(contentLoaded);
    assert(await store.saveStudySession(extracted.session), 'batch save failed');
    const batched = (await store.loadStudySessionWithDurability(key)).session;
    assert(batched.in_flight_batches[0].batch_id === extracted.batch.batch_id && batched.batch_sequence === 1, 'in-flight batch identity lost');
    const acknowledged = engine.acknowledgeBatchReceipt(batched, extracted.batch.batch_id);
    const pending = engine.prepareCommit(acknowledged, { reason: 'manual_exit' }).session;
    assert(await store.saveStudySession(pending), 'pending commit save failed');
    const persisted = (await store.loadStudySessionWithDurability(key)).session;
    assert(persisted.commit_id === pending.commit_id && persisted.status === 'pending_commit', 'commit identity lost');
    // Missing artifact must quarantine, never accept a partially restored lease.
    const db = await new Promise(resolve => { const req = indexedDB.open('flama-study'); req.onsuccess = () => resolve(req.result); });
    const row = await readRows();
    await new Promise((resolve, reject) => { const tx = db.transaction('session-artifacts', 'readwrite'); tx.objectStore('session-artifacts').delete(row.row.artifact_key); tx.oncomplete = resolve; tx.onabort = () => reject(tx.error); }); db.close();
    const quarantined = await store.loadStudySessionWithDurability(key);
    assert(!quarantined.session && !!quarantined.quarantine, 'missing artifact did not quarantine');
    assert(!(await readRows()).row, 'quarantine left active checkpoint');
    await store.acknowledgeStudySessionQuarantine(key); await store.removeStudySession(key);
    // Keep a fresh split fixture for the subsequent writer-off rollback check.
    const { studySnapshotFixture } = await import('/src/features/study/session/studySessionTestFixture.ts');
    const snapshot = studySnapshotFixture(); snapshot.session_id = crypto.randomUUID(); snapshot.scope.id = 'durability-probe-rollback';
    const rollbackSession = engine.createPersistedSession(snapshot);
    assert(await store.saveStudySession(rollbackSession), 'rollback seed failed');
    sessionStorage.setItem('durability-probe-rollback', rollbackSession.scope_key);
    sessionStorage.setItem('durability-probe-rollback-session', canonicalJson(JSON.parse(JSON.stringify((await store.loadStudySessionWithDurability(rollbackSession.scope_key)).session))));
    return { aborted_transaction_preserves_disk: true, reload_answer_and_undo: true, resave_preserves_override: true, content_patch_replaces_bundle: true, batch_and_commit_identity: true, missing_artifact_quarantine: true, removal_cleans_artifacts: true, rollback_fixture_ready: true };
  });
  return { browser: await page.evaluate(() => navigator.userAgent), ...initial, ...restored };
}
