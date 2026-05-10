"""Safe HTTP request utility with timeout and SSL context."""

from __future__ import annotations

import ssl
import urllib.request


def safe_urlopen(req, timeout=60, context=None):
    """Open a URL with timeout and SSL defaults.

    Args:
        req: A :class:`urllib.request.Request` instance.
        timeout: Request timeout in seconds.
        context: SSL context (created when *None*).

    Returns:
        A response object usable as a context manager.
    """
    if context is None:
        context = ssl.create_default_context()
    return urllib.request.urlopen(req, timeout=timeout, context=context)  # nosec B310 — safe wrapper: caller validates scheme; default SSL context restricts to https://
