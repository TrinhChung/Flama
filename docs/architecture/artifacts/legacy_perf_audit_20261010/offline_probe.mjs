// Node CPU/clone probe only: does not open a browser or an IndexedDB database.
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { performance } from 'node:perf_hooks';
import { randomUUID } from 'node:crypto';

const folder = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(folder, '../../../..');
const frontend = path.join(repo, 'frontend');
const { createServer } = await import(pathToFileURL(path.join(frontend, 'node_modules/vite/dist/node/index.js')));
const server = await createServer({ root: frontend, server: { watch: null }, logLevel: 'error' });
try {
  const { studySnapshotFixture } = await server.ssrLoadModule('/src/features/study/session/studySessionTestFixture.ts');
  const { createPersistedSession, buildSessionView } = await server.ssrLoadModule('/src/features/study/session/studySessionEngine.ts');
  const { normalizePersistedStudySession } = await server.ssrLoadModule('/src/features/study/session/sessionRestore.ts');
  const result = [];
  const median = values => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
  const elapsed = fn => { const start = performance.now(); fn(); return performance.now() - start; };
  for (const count of [100, 1000, 5000]) {
    const snapshot = studySnapshotFixture();
    snapshot.schema_version = 'study-session.v4';
    snapshot.authority_mode = 'NOTE';
    snapshot.enrollment_epoch = '1';
    const base = snapshot.cards[0], content = snapshot.contents.content;
    snapshot.contents = {};
    snapshot.cards = Array.from({ length: count }, (_, index) => {
      const noteId = randomUUID(), cardId = randomUUID(), key = `content-${index}`;
      snapshot.contents[key] = { ...content, id: noteId, note_id: noteId,
        field_values: { Word: 'cat', Body: 'x'.repeat(1024) }, render_context: { Word: 'cat' } };
      return { ...base, card_id: cardId, note_id: noteId, content_key: key,
        state: { ...base.state }, authority_pin: {
          schema_version: 'study-note-authority-pin.v1', authority_mode: 'NOTE', enrollment_epoch: '1',
          logical_note_key: noteId, subject_generation: '1', base_authority_revision: '0',
          base_authority_state_hash: '11'.repeat(32),
        } };
    });
    const session = createPersistedSession(snapshot);
    const first = normalizePersistedStudySession(session, session.scope_key);
    if (first.status === 'quarantine') throw new Error(`Synthetic v4 session rejected: ${JSON.stringify(first.quarantine)}`);
    for (let i = 0; i < 3; i++) normalizePersistedStudySession(session, session.scope_key);
    const normalize = [], clone = [], view = [];
    for (let i = 0; i < 7; i++) {
      normalize.push(elapsed(() => normalizePersistedStudySession(session, session.scope_key)));
      clone.push(elapsed(() => structuredClone(session)));
      view.push(elapsed(() => buildSessionView(session, Date.parse(snapshot.server_now_utc))));
    }
    result.push({ cards: count, wire: snapshot.schema_version, validation_status: first.status,
      json_equivalent_bytes: Buffer.byteLength(JSON.stringify(session)),
      normalize_median_node_ms: median(normalize), structured_clone_median_node_ms: median(clone),
      build_session_view_median_node_ms: median(view), measured_iterations: 7 });
  }
  fs.writeFileSync(path.join(folder, 'offline_results.json'), JSON.stringify({
    node: process.version,
    limitation: 'Synthetic NOTE/v4 initial sessions, no events and 1 KiB Body/Note. Node CPU and structuredClone only; no browser or IndexedDB timing. Frozen composition contract is absent in this minimal accepted fixture.',
    cases: result,
  }, null, 2) + '\n');
  process.stdout.write(JSON.stringify(result) + '\n');
} finally {
  await server.close();
}
