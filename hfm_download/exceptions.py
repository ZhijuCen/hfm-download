"""
Custom exceptions for hfm-download.
"""


class HfmDownloadError(Exception):
    """Base exception for hfm-download."""
    pass


class PathTraversalError(HfmDownloadError):
    """Raised when path escapes current working directory."""
    pass


class ConfigValidationError(HfmDownloadError):
    """Raised when YAML configuration is invalid."""
    pass


class DownloadError(HfmDownloadError):
    """Raised when download fails."""
    pass


class RetryableError(DownloadError):
    """Network errors that can be retried."""
    pass


class NonRetryableError(DownloadError):
    """Permanent errors that should not be retried."""
    pass
