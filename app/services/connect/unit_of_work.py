"""Filesystem compensation tied to the owning database transaction."""

from app.services import flama_connect_media_service as media
from models import db


class ConnectUnitOfWork:
    def __init__(self):
        self.materialized = []
        self.created_paths = []

    def commit(self):
        db.session.commit()
        committed = list(self.materialized)
        self.materialized.clear()
        self.created_paths.clear()
        for item in committed:
            media.finalize_materialized(item)

    def rollback(self):
        db.session.rollback()
        for item in self.materialized:
            media.compensate_materialized(item)
        for path in self.created_paths:
            media._unlink_quietly(path)
        self.materialized.clear()
        self.created_paths.clear()
