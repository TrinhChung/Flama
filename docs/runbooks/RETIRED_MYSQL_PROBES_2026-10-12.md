# Historical MySQL probes retired on 2026-10-12

The following commands describe earlier migration rehearsals. Their exact sources remain in commit `e077d275`; recover them with `git show e077d275:scripts/<filename>` on that historical checkout. They cannot qualify the current runtime by constructing its metadata and pretending it is the old schema.

| Historical command | Required historical state | Current replacement |
| --- | --- | --- |
| `probe_p6_application_schema_mysql.py` | Physical Card/CP tables and the removed Phase 6 attribution writer | `probe_retirement_fresh_chain_mysql.py`; derived migration and archive contract tests |
| `bench_p6_migration_mysql.py` | Previous-release Card/contributor writers during migration 46 | Frozen migration fixtures and verified archive conservation; current NOTE concurrency probe |
| `bench_p9_profile_migration_mysql.py` | Pre-47 contributor tables and Card/CP foreign key parents | Full historical baseline-to-head MySQL chain; current NOTE codec, concurrency and retirement gates |
| `probe_p10_schema_mysql.py` | Pre-49 subjects without later queue/anchor indexes | Full historical baseline-to-head MySQL chain; consolidated schema and retirement tests |
| `probe_p10_drop_mysql.py` | Five historical NOTE tables plus their Card/CP parent schema | Private frozen historical schema and archive/restore contraction tests |

CI bootstraps only its explicitly named, empty GitHub Actions loopback `ci` schema before the real `flask --app wsgi.py db upgrade`. The separate fresh-chain probe creates an unpredictable, guarded schema, compares the migrated table inventory with current metadata, and keeps failed evidence for diagnosis. Successful proof permits cleanup of only that exact generated schema.

These fresh checks qualify an empty chain. Populated retirement additionally requires a checksum-matched external bundle, actual isolated MySQL restore and current NOTE audit checkpoint; empty-chain success alone does not authorize dropping populated data.

The active NOTE locking/concurrency, Connect fence, session retention, review analytics and deck snapshot gates remain in CI. Current scheduling continues to use both `due_day` and `due_at` with the existing timezone/day-boundary rules.
