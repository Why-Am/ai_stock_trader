"""Errors raised by domain validation."""


class DomainValidationError(ValueError):
    """An input violates a domain rule and includes an actionable message."""


class StorageError(Exception):
    """An experiment file is missing, malformed, unsafe, or cannot be persisted."""
