# Source before running the harness. Mirrors the post-R1 production flags
# (docs/runbooks/P5_NOTE_AUTHORITY_RUNBOOK.md section 1) against a DISPOSABLE database.
export SQLALCHEMY_DATABASE_URI="${LOAD_DB_URI:-mysql+pymysql://flama:flama@127.0.0.1:3306/flama_load?charset=utf8mb4}"
export SECRET_KEY=load-test-secret
export STUDY_WIRE_V4_ENABLED=1
export STUDY_NEW_LEARNER_NOTE_ENABLED=1
export STUDY_PROGRESS_SHADOW_WRITE_ENABLED=1
export STUDY_ASYNC_BATCH_ENABLED=0
export RATE_LIMIT_DAILY_ENABLED=0
export REDIS_URL=
export FLASHCARD_MEDIA_UPLOAD_ROOT="${LOAD_MEDIA_ROOT:-/tmp/flama-load-media}"
