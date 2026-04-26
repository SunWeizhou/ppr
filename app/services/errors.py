"""Domain exception classes for the arXiv paper recommender.

All application-level exceptions inherit from :class:`AppError` and carry an
HTTP status code so the Flask error handler can produce consistent JSON
responses without inspecting error messages.
"""


class AppError(Exception):
    """Base application error."""
    status_code = 500


class ConfigurationError(AppError):
    """Configuration is missing or invalid."""
    status_code = 500


class ArxivAPIError(AppError):
    """arXiv API call failed."""
    status_code = 502


class ValidationError(AppError):
    """Request validation failed."""
    status_code = 400


class NotFoundError(AppError):
    """Resource not found."""
    status_code = 404


class ConflictError(AppError):
    """Resource conflict (e.g., duplicate)."""
    status_code = 409
