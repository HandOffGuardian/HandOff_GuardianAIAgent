"""Errors raised while retrieving evidence from a provider."""


class EvidenceProviderError(Exception):
    """A provider could not complete an evidence lookup.

    Provider failures are distinct from a successful lookup that returns no
    records. When wrapping an underlying error, callers should preserve it with
    exception chaining (``raise EvidenceProviderError(...) from exc``).
    """

