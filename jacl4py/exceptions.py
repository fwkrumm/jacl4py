"""Exceptions raised by logger lifecycle operations."""


class ResourceNotInitializedError(RuntimeError):
    """Raised when a deleted logger is used to log a message."""
