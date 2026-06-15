"""Shared utilities for vagas modules."""

import unicodedata


def strip_accents(s: str) -> str:
    """Remove diacritical marks (accents) from a string."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
