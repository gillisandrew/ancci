"""The failures a user can cause, kept in a module that imports nothing.

An entry script that only reads card files must be able to catch these without importing
an HTTP client it has no reason to depend on.
"""


class ConfigError(Exception):
    """Raised when a deck's configuration is missing or unusable."""


class AnkiError(RuntimeError):
    """Raised when AnkiConnect is unreachable or refuses a request."""
