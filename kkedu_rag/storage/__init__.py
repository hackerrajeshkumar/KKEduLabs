"""Persistence layer: SQLite-backed chat threads and uploaded documents.

Conversation *messages* are stored by the SDK's SQLiteSession (keyed by thread
id); this package stores the thread metadata (titles, timestamps) and the raw
text of uploaded documents so both survive restarts. Import the concrete
modules: ``storage.conversations`` and ``storage.documents``.
"""
