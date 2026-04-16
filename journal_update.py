"""Compatibility shim for older imports.

The scheduled updater historically imported `journal_update`, while the
current implementation lives in `update_journals.py`.
"""

from update_journals import update_all_journals, update_journal

__all__ = ["update_all_journals", "update_journal"]
