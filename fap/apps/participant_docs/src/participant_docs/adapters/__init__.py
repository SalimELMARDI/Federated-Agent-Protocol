"""Adapter layer for participant_docs local data access."""

from participant_docs.adapters.local_docs import (
    DEFAULT_DOCS_DATA_DIR,
    DOCS_PATH_ENV_VAR,
    LocalDoc,
    get_docs_data_dir,
    load_docs,
    search_docs,
    validate_docs_data_dir,
)

__all__ = [
    "DEFAULT_DOCS_DATA_DIR",
    "DOCS_PATH_ENV_VAR",
    "LocalDoc",
    "get_docs_data_dir",
    "load_docs",
    "search_docs",
    "validate_docs_data_dir",
]
