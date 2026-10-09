async (page) => {
  // Restart port 5179 WITHOUT VITE_STUDY_SPLIT_STORAGE_ENABLED before running.
  await page.route('**/__durability_probe', route => route.fulfill({ contentType: 'text/html', body: '<html><body>Isolated writer rollback probe</body></html>' }));
  await page.goto('http://127.0.0.1:5179/__durability_probe');
  return await page.evaluate(async () => {
    const assert = (condition, message) => { if (!condition) throw new Error(message); };
    const store = await import('/src/features/study/session/sessionStore.ts');
    const { canonicalJson } = await import('/src/features/study/session/canonicalDigest.ts');
    const key = sessionStorage.getItem('durability-probe-rollback') || 'user:7:deck:durability-probe-rollback';
    const loaded = await store.loadStudySessionWithDurability(key);
    assert(loaded.durable && loaded.session, 'writer-off reader did not open DB3');
    const expected = sessionStorage.getItem('durability-probe-rollback-session') || canonicalJson(JSON.parse(JSON.stringify(loaded.session)));
    assert(canonicalJson(JSON.parse(JSON.stringify(loaded.session))) === expected, 'writer-off hydration differs');
    assert(await store.saveStudySession(loaded.session), 'writer-off inline save failed');
    const db = await new Promise((resolve, reject) => { const req = indexedDB.open('flama-study'); req.onsuccess = () => resolve(req.result); req.onerror = () => reject(req.error); });
    const raw = await new Promise((resolve, reject) => {
      const tx = db.transaction(['sessions', 'session-artifacts'], 'readonly');
      const row = tx.objectStore('sessions').get(key), artifacts = tx.objectStore('session-artifacts').index('scope_key').getAll(key);
      tx.oncomplete = () => { db.close(); resolve({ session: row.result, bundles: artifacts.result }); }; tx.onabort = () => reject(tx.error);
    });
    assert(!raw.session.storage_schema && !!raw.session.snapshot.contents && raw.bundles.length === 0, 'writer-off did not atomically replace split row with inline');
    assert(canonicalJson(JSON.parse(JSON.stringify((await store.loadStudySessionWithDurability(key)).session))) === expected, 'inline roundtrip differs');
    await store.removeStudySession(key);
    sessionStorage.removeItem('durability-probe-rollback'); sessionStorage.removeItem('durability-probe-rollback-session');
    return { writer_off_reads_db3: true, hydration_parity: true, writer_off_saves_inline: true, obsolete_artifact_removed: true, requires_new_compatible_reader: true };
  });
}
