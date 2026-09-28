"""Standalone continuous Study consumer (no web server or schema maintenance)."""

import argparse
import json
import logging
import signal
import threading


def create_worker_app(config=None):
    from app import create_app

    worker_config = dict(config or {})
    # Explicit overrides win over .env and caller config. Migrations are an
    # independent deploy step, never a restart side effect of this consumer.
    worker_config.update(STARTUP_RUN_MAINTENANCE=False, STARTUP_CHECK_DB_CONNECTIVITY=False)
    return create_app(worker_config)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-ready", action="store_true", help="Check shared readiness; exit 0 if a compatible worker is live, 1 otherwise.")
    mode.add_argument("--check-code-rollback", action="store_true", help="Read-only code rollback gate; does not change learner authority.")
    parser.add_argument("--writers-quiesced", action="store_true", help="Assert HTTP/Connect writers have stopped before rollback inspection.")
    args = parser.parse_args(argv)
    if args.writers_quiesced and not args.check_code_rollback:
        parser.error("--writers-quiesced requires --check-code-rollback")
    logging.basicConfig(level=logging.INFO)
    app = create_worker_app()
    if args.check_code_rollback:
        from app.services.study_deploy_safety_service import inspect_study_code_rollback

        with app.app_context():
            result = inspect_study_code_rollback(writers_quiesced=args.writers_quiesced)
            print(json.dumps(result, sort_keys=True))
            return 0 if result["status"] == "PASS" else 1
    if args.check_ready:
        from app.services.study_worker_readiness_service import has_ready_study_worker

        with app.app_context():
            return 0 if has_ready_study_worker("study-session.v4") else 1
    from app.services.study_consumer_service import run_study_consumer

    stop_event = threading.Event()
    previous = {}
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, lambda _signum, _frame: stop_event.set())
        run_study_consumer(app, stop_event=stop_event)
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
