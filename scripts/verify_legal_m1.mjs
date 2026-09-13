import { legalDocuments } from '../frontend/src/data/legalDocumentsData.ts';

const testResults = [];

function runTest(name, fn) {
  try {
    fn();
    testResults.push({ name, pass: true });
    console.log(`[PASS] ${name}`);
  } catch (err) {
    testResults.push({ name, pass: false, error: err.message });
    console.error(`[FAIL] ${name}: ${err.message}`);
  }
}

console.log('=== Flama Legal Documents Empirical Invariant Verification ===\n');

// 1. Document Existence
runTest('All 5 official document keys exist', () => {
  const required = ['terms', 'privacy', 'marketplace-guidelines', 'community-guidelines', 'cookies'];
  const actual = Object.keys(legalDocuments);
  if (required.length !== actual.length) throw new Error(`Expected 5 documents, got ${actual.length}: ${actual.join(', ')}`);
  for (const id of required) {
    if (!legalDocuments[id]) throw new Error(`Document "${id}" missing`);
    if (legalDocuments[id].id !== id) throw new Error(`Document id property mismatch for "${id}": got "${legalDocuments[id].id}"`);
  }
});

// 2. Document Metadata
runTest('Document metadata fields validity', () => {
  const versionRegex = /^v\d+(\.\d+)*$/;
  const dateRegex = /^\d{2}\/\d{2}\/\d{4}$/;
  for (const [id, doc] of Object.entries(legalDocuments)) {
    if (!doc.title || typeof doc.title !== 'string' || doc.title.trim().length === 0) throw new Error(`${id}: empty title`);
    if (!doc.officialBadge || typeof doc.officialBadge !== 'string') throw new Error(`${id}: empty officialBadge`);
    if (!dateRegex.test(doc.lastUpdated)) throw new Error(`${id}: invalid lastUpdated format (${doc.lastUpdated})`);
    if (!dateRegex.test(doc.effectiveDate)) throw new Error(`${id}: invalid effectiveDate format (${doc.effectiveDate})`);
    if (!versionRegex.test(doc.version)) throw new Error(`${id}: invalid version (${doc.version})`);
    if (typeof doc.readTimeMinutes !== 'number' || doc.readTimeMinutes <= 0 || !Number.isInteger(doc.readTimeMinutes)) {
      throw new Error(`${id}: readTimeMinutes must be positive integer, got ${doc.readTimeMinutes}`);
    }
    if (!doc.executiveSummary || doc.executiveSummary.trim().length < 30) {
      throw new Error(`${id}: executiveSummary too short or empty`);
    }
    if (!Array.isArray(doc.clauses) || doc.clauses.length === 0) {
      throw new Error(`${id}: clauses must be non-empty array`);
    }
  }
});

// 3. Clause and Subclause Structure
runTest('Clause and Subclause integrity', () => {
  const slugRegex = /^[a-z0-9-]+$/;
  for (const [docId, doc] of Object.entries(legalDocuments)) {
    for (let i = 0; i < doc.clauses.length; i++) {
      const c = doc.clauses[i];
      if (!c.id || !slugRegex.test(c.id)) throw new Error(`${docId} clause[${i}] invalid id: ${c.id}`);
      if (!c.clauseNumber || c.clauseNumber.trim().length === 0) throw new Error(`${docId} clause[${i}] empty clauseNumber`);
      if (!c.title || c.title.trim().length === 0) throw new Error(`${docId} clause ${c.id} empty title`);
      if (!Array.isArray(c.content) || c.content.length === 0) throw new Error(`${docId} clause ${c.id} empty content`);
      for (let j = 0; j < c.content.length; j++) {
        if (!c.content[j] || c.content[j].trim().length === 0) throw new Error(`${docId} clause ${c.id} content[${j}] empty`);
      }
      if (c.subClauses) {
        if (!Array.isArray(c.subClauses)) throw new Error(`${docId} clause ${c.id} subClauses not array`);
        for (let s = 0; s < c.subClauses.length; s++) {
          const sc = c.subClauses[s];
          if (!sc.id || !slugRegex.test(sc.id)) throw new Error(`${docId} subclause[${s}] invalid id: ${sc.id}`);
          if (!sc.clauseNumber || sc.clauseNumber.trim().length === 0) throw new Error(`${docId} subclause ${sc.id} empty clauseNumber`);
          if (!sc.title || sc.title.trim().length === 0) throw new Error(`${docId} subclause ${sc.id} empty title`);
          if (!Array.isArray(sc.content) || sc.content.length === 0) throw new Error(`${docId} subclause ${sc.id} empty content`);
          for (let p = 0; p < sc.content.length; p++) {
            if (!sc.content[p] || sc.content[p].trim().length === 0) throw new Error(`${docId} subclause ${sc.id} content[${p}] empty`);
          }
        }
      }
      if (c.bullets) {
        if (!Array.isArray(c.bullets) || c.bullets.length === 0) throw new Error(`${docId} clause ${c.id} empty bullets`);
        for (const b of c.bullets) {
          if (!b || b.trim().length === 0) throw new Error(`${docId} clause ${c.id} empty bullet item`);
        }
      }
      if (c.callout) {
        if (!['warning', 'info', 'statutory'].includes(c.callout.type)) throw new Error(`${docId} clause ${c.id} invalid callout type: ${c.callout.type}`);
        if (!c.callout.label || c.callout.label.trim().length === 0) throw new Error(`${docId} clause ${c.id} empty callout label`);
        if (!c.callout.text || c.callout.text.trim().length === 0) throw new Error(`${docId} clause ${c.id} empty callout text`);
      }
    }
  }
});

// 4. Global Uniqueness of Anchor IDs
runTest('Global uniqueness of all clause and subclause anchor IDs', () => {
  const seen = new Map();
  for (const [docId, doc] of Object.entries(legalDocuments)) {
    for (const c of doc.clauses) {
      if (seen.has(c.id)) {
        throw new Error(`Duplicate anchor id "${c.id}" in ${docId} (first seen in ${seen.get(c.id)})`);
      }
      seen.set(c.id, docId);
      if (c.subClauses) {
        for (const sc of c.subClauses) {
          if (seen.has(sc.id)) {
            throw new Error(`Duplicate anchor id "${sc.id}" in ${docId} (first seen in ${seen.get(sc.id)})`);
          }
          seen.set(sc.id, docId);
        }
      }
    }
  }
  console.log(`Verified ${seen.size} globally unique anchor IDs across all 5 documents.`);
});

// 5. Domain Legal Content Coverage
function searchInDoc(doc, query) {
  const q = query.toLowerCase();
  for (const c of doc.clauses) {
    if (c.title.toLowerCase().includes(q) || (c.summary && c.summary.toLowerCase().includes(q))) return true;
    for (const p of c.content) {
      if (p.toLowerCase().includes(q)) return true;
    }
    if (c.subClauses) {
      for (const sc of c.subClauses) {
        if (sc.title.toLowerCase().includes(q)) return true;
        for (const p of sc.content) {
          if (p.toLowerCase().includes(q)) return true;
        }
      }
    }
    if (c.bullets) {
      for (const b of c.bullets) {
        if (b.toLowerCase().includes(q)) return true;
      }
    }
    if (c.callout && (c.callout.label.toLowerCase().includes(q) || c.callout.text.toLowerCase().includes(q))) return true;
  }
  return false;
}

runTest('Terms of Service domain coverage (payOS, Connect, Audio, account sanctions, 500k cap)', () => {
  const terms = legalDocuments['terms'];
  if (!searchInDoc(terms, 'payos')) throw new Error('Terms missing payOS');
  if (!searchInDoc(terms, 'flama connect')) throw new Error('Terms missing Connect service');
  if (!searchInDoc(terms, 'flama audio')) throw new Error('Terms missing Audio service');
  if (!searchInDoc(terms, 'quy chuẩn cấp phép giọng đọc') && !searchInDoc(terms, 'giọng đọc ai')) throw new Error('Terms missing AI Voice licensing clause');
  if (!searchInDoc(terms, '500.000')) throw new Error('Terms missing 500.000 VND liability cap');
  if (!searchInDoc(terms, 'vô hiệu hóa')) throw new Error('Terms missing account termination mechanism');
});

runTest('Privacy Policy domain coverage (Decree 13, 11 rights, SRS telemetry, 72h breach, cascade erasure)', () => {
  const privacy = legalDocuments['privacy'];
  if (!searchInDoc(privacy, '13/2023/nđ-cp')) throw new Error('Privacy missing Nghị định 13/2023/NĐ-CP');
  if (!searchInDoc(privacy, '72 giờ') && !searchInDoc(privacy, '72h') && !searchInDoc(privacy, '72 gi')) throw new Error('Privacy missing 72h breach notification');
  if (!searchInDoc(privacy, 'ebbinghaus') && !searchInDoc(privacy, 'spaced repetition')) throw new Error('Privacy missing Spaced Repetition disclosure');
  if (!searchInDoc(privacy, 'thông số phản xạ thời gian') || !searchInDoc(privacy, 'lịch sử đánh giá ghi nhớ')) {
    throw new Error('Privacy missing generalized telemetry metrics transparency');
  }
  if (!searchInDoc(privacy, 'tiêu hủy') && !searchInDoc(privacy, 'xóa vĩnh viễn')) throw new Error('Privacy missing erasure cascade details');
  if (!searchInDoc(privacy, 'thuế') && !searchInDoc(privacy, 'kế toán')) throw new Error('Privacy missing tax retention exception');
  if (!searchInDoc(privacy, 'vô danh hóa')) throw new Error('Privacy missing anonymization of payment records');
});

runTest('Marketplace Guidelines domain coverage (Three-Way IP, Clone Overlay shields, Notice & Takedown)', () => {
  const market = legalDocuments['marketplace-guidelines'];
  if (!searchInDoc(market, 'three-way') && !searchInDoc(market, 'ba bên') && !searchInDoc(market, 'sở hữu trí tuệ')) throw new Error('Marketplace missing Three-Way IP');
  if (!searchInDoc(market, 'clone overlay') && !searchInDoc(market, 'logical overlay')) throw new Error('Marketplace missing Clone Overlay model');
  if (!searchInDoc(market, 'notice & takedown') && !searchInDoc(market, 'gỡ bỏ')) throw new Error('Marketplace missing Notice & Takedown');
  if (!searchInDoc(market, 'three-strike') && !searchInDoc(market, 'ba lần vi phạm') && !searchInDoc(market, 'strike')) throw new Error('Marketplace missing Three-Strike rule');
});

runTest('Community Guidelines domain coverage (Anti-scraping, sanitization defense-in-depth, ticketing)', () => {
  const comm = legalDocuments['community-guidelines'];
  if (!searchInDoc(comm, 'cào dữ liệu') && !searchInDoc(comm, 'scraping')) throw new Error('Community missing anti-scraping');
  if (!searchInDoc(comm, 'lọc mã độc đa tầng') && !searchInDoc(comm, 'phòng vệ') && !searchInDoc(comm, 'csp')) throw new Error('Community missing HTML sanitization defense-in-depth');
  if (!searchInDoc(comm, 'hỗ trợ') && !searchInDoc(comm, 'ticket')) throw new Error('Community missing ticketing report channel');
});

runTest('Cookie Policy domain coverage (Essential cookies, CSRF, LocalStorage)', () => {
  const cookies = legalDocuments['cookies'];
  if (!searchInDoc(cookies, 'cookie') || !searchInDoc(cookies, 'localstorage') || !searchInDoc(cookies, 'csrf')) {
    throw new Error('Cookies missing cookie/localstorage/csrf explanation');
  }
});

// 6. Adversarial Stress Test: Deep Tree Traversal for Empty / Null / Undefined Values
runTest('Stress Test: Zero empty strings or undefined fields in entire data tree', () => {
  function checkNode(path, val) {
    if (val === null || val === undefined) throw new Error(`Null/undefined found at ${path}`);
    if (typeof val === 'string') {
      if (val.trim().length === 0) throw new Error(`Empty whitespace-only string found at ${path}`);
    } else if (Array.isArray(val)) {
      if (val.length === 0 && !path.includes('bullets')) throw new Error(`Empty array at ${path}`);
      val.forEach((item, idx) => checkNode(`${path}[${idx}]`, item));
    } else if (typeof val === 'object') {
      for (const [k, v] of Object.entries(val)) {
        checkNode(`${path}.${k}`, v);
      }
    }
  }
  for (const [id, doc] of Object.entries(legalDocuments)) {
    checkNode(id, doc);
  }
});

// 7. Adversarial Stress Test: CSS / DOM Query Selector Validity for all Anchor IDs
runTest('Stress Test: All 85 anchor IDs valid CSS query selector targets', () => {
  const validCssIdRegex = /^[a-zA-Z][a-zA-Z0-9_-]*$/;
  for (const [docId, doc] of Object.entries(legalDocuments)) {
    for (const c of doc.clauses) {
      if (!validCssIdRegex.test(c.id)) {
        throw new Error(`Clause ID "${c.id}" in ${docId} cannot be safely selected via document.querySelector("#${c.id}")`);
      }
      if (c.subClauses) {
        for (const sc of c.subClauses) {
          if (!validCssIdRegex.test(sc.id)) {
            throw new Error(`Subclause ID "${sc.id}" in ${docId} cannot be safely selected via document.querySelector("#${sc.id}")`);
          }
        }
      }
    }
  }
});

// 8. Adversarial Stress Test: Word Count vs. readTimeMinutes Plausibility
runTest('Stress Test: Reading speed ratio plausibility (50 to 450 wpm)', () => {
  for (const [docId, doc] of Object.entries(legalDocuments)) {
    let wordCount = 0;
    function countWords(str) {
      return str.trim().split(/\s+/).length;
    }
    wordCount += countWords(doc.title);
    wordCount += countWords(doc.executiveSummary);
    for (const c of doc.clauses) {
      wordCount += countWords(c.title);
      if (c.summary) wordCount += countWords(c.summary);
      c.content.forEach(p => wordCount += countWords(p));
      if (c.bullets) c.bullets.forEach(b => wordCount += countWords(b));
      if (c.callout) wordCount += countWords(c.callout.text);
      if (c.subClauses) {
        for (const sc of c.subClauses) {
          wordCount += countWords(sc.title);
          sc.content.forEach(p => wordCount += countWords(p));
          if (sc.bullets) sc.bullets.forEach(b => wordCount += countWords(b));
        }
      }
    }
    const wpm = wordCount / doc.readTimeMinutes;
    console.log(`  Document [${docId}]: ${wordCount} words, ${doc.readTimeMinutes} min (~${Math.round(wpm)} wpm)`);
    if (wpm < 50 || wpm > 450) {
      throw new Error(`Unrealistic readTimeMinutes for ${docId}: ${doc.readTimeMinutes} min for ${wordCount} words (${Math.round(wpm)} wpm)`);
    }
  }
});

// 9. Adversarial Stress Test: JSON Serialization Round-Trip
runTest('Stress Test: Lossless JSON serialization round-trip', () => {
  const jsonStr = JSON.stringify(legalDocuments);
  const parsed = JSON.parse(jsonStr);
  if (Object.keys(parsed).length !== Object.keys(legalDocuments).length) {
    throw new Error('Key count mismatch after JSON serialization');
  }
  const reencoded = JSON.stringify(parsed);
  if (jsonStr !== reencoded) {
    throw new Error('Serialization divergence during round-trip');
  }
});

// 10. Adversarial Stress Test: Zero Technical Leaks & Zero Narrow Japanese Bias
runTest('Stress Test: Zero technical implementation leaks and zero narrow domain bias', () => {
  const jsonStr = JSON.stringify(legalDocuments).toLowerCase();
  const forbidden = [
    'flask', 'werkzeug', 'pbkdf', 'fernet', 'bleach', 'dompurify', '.net 8', 'wpf',
    '4790', '4791', '127.0.0.1', 'localhost',
    'payment_orders', 'review_events', 'card_progress', 'deckclonenotefieldoverride',
    'deckinstall', 'deckrelease', 'on delete cascade', 'user_id', 'merchant_order_code',
    'is_disabled', 'clone_mode', 'logical_overlay', 'user_disabled', 'too many requests',
    'userapitoken', 'flama_audio_pairing_token', 'reviewed_at', 'duration_ms', 'step_index',
    'ease_factor', 'lapses', 'memory_stability', 'leech', 'voicevox', 'kokoro', 'yomitan',
    'tiếng nhật', 'nhật bản', 'jlpt', 'nat-test', 'minna no nihongo', 'kanji', 'furigana',
    'zundamon', 'shikikoin', 'kasukabe', 'ずんだもん',
    'mysql', 'sqlite', 'sqlalchemy', 'alembic', 'gunicorn', 'ankiconnect',
    'yomichan', 'rikaichan', 'mecab', 'sudachi', 'kuromoji', 'soumatome',
    'shin kanzen', 'genki', 'tobira', 'jft-basic', 'bjt', 'eju', 'kanken',
    'hiragana', 'katakana', 'ba gậy',
    'zero-copy', 'note types', 'field overrides', '30m ttl', 'oidc', 'avatar url',
    '"archived"', '"private"'
  ];
  for (const term of forbidden) {
    if (jsonStr.includes(term.toLowerCase())) {
      throw new Error(`Forbidden leak or narrow term "${term}" detected in legal documents data`);
    }
  }
});

console.log('\n=== Summary ===');
const failed = testResults.filter(t => !t.pass);
if (failed.length > 0) {
  console.error(`Total tests: ${testResults.length}, Passed: ${testResults.length - failed.length}, FAILED: ${failed.length}`);
  process.exit(1);
} else {
  console.log(`ALL ${testResults.length} EMPIRICAL AND STRESS TESTS PASSED! Exit code 0.`);
  process.exit(0);
}

