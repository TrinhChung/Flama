"""Explicit bounded operational drain for the durable template delivery queue."""

import json

import click


def register_template_sync_commands(app):
    @app.cli.command("template-sync-status")
    def template_sync_status():
        """Read durable job counts and safe failure codes without mutating rows."""
        from app.services.template_subscription_sync_service import inspect_template_sync_queue
        click.echo(json.dumps(inspect_template_sync_queue(), sort_keys=True))

    @app.cli.command("template-sync-drain")
    @click.option("--max-jobs", type=click.IntRange(1, 1000), default=100, show_default=True)
    @click.option("--batch-size", type=click.IntRange(1, 500), default=100, show_default=True)
    def template_sync_drain(max_jobs, batch_size):
        """Dispatch/apply a bounded page; failed recipients keep durable retries."""
        from app.services.template_subscription_sync_service import drain_template_sync_jobs
        result = drain_template_sync_jobs(max_jobs=max_jobs, dispatcher_batch_size=batch_size)
        click.echo(json.dumps(result, sort_keys=True))
        if result["failed_count"]:
            raise click.exceptions.Exit(1)
