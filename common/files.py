import logging

from django.db import transaction

logger = logging.getLogger(__name__)


def delete_stored_file_after_commit(storage, name):
    """Delete `name` from `storage` once the surrounding transaction commits."""
    if not name:
        return

    def _delete():
        try:
            storage.delete(name)
        except Exception:  # never let cleanup break a request
            logger.exception("Could not delete stored file %s", name)

    transaction.on_commit(_delete)


def delete_file_after_commit(field_file):
    """Same, for a FieldFile (e.g. `instance.cover_image`)."""
    if field_file and field_file.name:
        delete_stored_file_after_commit(field_file.storage, field_file.name)
