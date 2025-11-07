from typing import Any, Optional
from unidecode import unidecode


def normalize_str(value: Optional[str]):
    """Normalize string for matching (lowercase, remove accents, collapse whitespace)."""
    if value is None:
        return ""

    normalized = unidecode(value)
    normalized = normalized.lower()
    normalized = " ".join(normalized.split())

    return normalized


def normalize_field(value: Any):
    """Normalize field value with basic cleaning while keeping original casing."""
    if value is None:
        return None

    if not isinstance(value, str):
        value = str(value)

    normalized = " ".join(value.split())

    return normalized or None
