"""Small validation helpers for immutable shared contracts."""


def require_nonempty_string(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def require_evidence_ids(value: object) -> None:
    if not isinstance(value, tuple):
        raise TypeError("evidence_ids must be a tuple of non-empty strings")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise TypeError("evidence_ids must be a tuple of non-empty strings")
    if len(set(value)) != len(value):
        raise ValueError("evidence_ids must not contain duplicates")
