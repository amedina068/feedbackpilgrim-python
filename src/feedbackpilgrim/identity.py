"""The identity hash (``user_hash``) of the widget.

The widget proves the email of the signed-in user with ``user_hash``. Make the
hash on your server only. Never put the identity secret in browser code.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Final

__all__ = ["identity_hash", "normalize_email"]

# PHP trim() removes these characters, and no other characters.
_PHP_TRIM: Final = " \t\n\r\0\x0b"

# PHP strtolower() changes the ASCII letters A-Z only.
_ASCII_LOWER: Final = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def identity_hash(email: str, identity_secret: str) -> str:
    """Return the ``user_hash`` for an email: an HMAC-SHA256 hex digest.

    Example::

        user_hash = identity_hash(request.user.email, settings.FEEDBACKPILGRIM_IDENTITY_SECRET)

    Args:
        email: The email of the signed-in user. The function normalizes it.
        identity_secret: The identity secret of the client. It is not the API token.
    """
    if not identity_secret:
        raise ValueError("identity_secret must not be empty")
    message = normalize_email(email).encode("utf-8")
    return hmac.new(identity_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def normalize_email(email: str) -> str:
    """Normalize an email exactly like PHP ``strtolower(trim($email))``.

    Python ``strip()`` and ``lower()`` also change Unicode characters, so the
    app gives a different hash for some emails. This function does not.
    """
    return email.strip(_PHP_TRIM).translate(_ASCII_LOWER)
