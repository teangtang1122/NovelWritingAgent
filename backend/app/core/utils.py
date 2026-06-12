"""Shared pure utility functions."""
from __future__ import annotations

import re


def count_words(text: str) -> int:
    """Count characters excluding spaces and newlines, matching mainstream novel platforms."""
    return len(re.sub(r"[\s]", "", text))
