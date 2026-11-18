"""Verify the webhook deliveries of Feedback Pilgrim.

Feedback Pilgrim signs each delivery with the signing secret of the webhook.
The ``X-FeedbackPilgrim-Signature-V2`` header is the HMAC-SHA256 hex digest of
``<X-FeedbackPilgrim-Timestamp>.<raw body>``.

The app also sends the deprecated ``X-FeedbackPilgrim-Signature`` header, the
digest of the body only. This module does not read it.

Use this module only on a server. The signing secret is a secret.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from feedbackpilgrim.errors import WebhookVerificationError
from feedbackpilgrim.models import Stage

__all__ = [
    "DEFAULT_TOLERANCE",
    "DELIVERY_HEADER",
    "EVENT_HEADER",
    "SIGNATURE_HEADER",
    "TIMESTAMP_HEADER",
    "WebhookEvent",
    "WebhookPost",
    "construct_event",
    "sign",
    "verify_signature",
]

SIGNATURE_HEADER: Final = "X-FeedbackPilgrim-Signature-V2"
TIMESTAMP_HEADER: Final = "X-FeedbackPilgrim-Timestamp"
DELIVERY_HEADER: Final = "X-FeedbackPilgrim-Delivery"
EVENT_HEADER: Final = "X-FeedbackPilgrim-Event"

DEFAULT_TOLERANCE: Final = 300
"""The maximum difference in seconds between the timestamp and the current time."""


@dataclass(frozen=True)
class WebhookPost:
    """The post of a webhook delivery."""

    id: int
    title: str
    content: str | None
    status: str | None
    board_id: int | None
    contact_id: int | None
    stage: Stage | None
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WebhookPost:
        stage = data.get("stage")
        return cls(
            id=_int(data.get("id")) or 0,
            title=str(data.get("title") or ""),
            content=_opt_str(data.get("content")),
            status=_opt_str(data.get("status")),
            board_id=_int(data.get("board_id")),
            contact_id=_int(data.get("contact_id")),
            stage=Stage.from_dict(stage) if isinstance(stage, dict) else None,
            raw=data,
        )


@dataclass(frozen=True)
class WebhookEvent:
    """One verified webhook delivery.

    Attributes:
        type: ``post.created``, ``post.status_changed`` or ``post.completed``.
        delivery_id: The UUID of the delivery. Each retry of a delivery sends
            the same UUID. Store it to drop a repeated delivery.
        timestamp: The Unix time of this attempt, in seconds.
        post: The post of the event.
        raw: The decoded JSON body.
    """

    type: str
    delivery_id: str | None
    timestamp: int
    post: WebhookPost
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)


def verify_signature(
    payload: bytes | str,
    signature: str | None,
    timestamp: str | None,
    secret: str,
    *,
    tolerance: int = DEFAULT_TOLERANCE,
    now: float | None = None,
) -> bool:
    """Return ``True`` when the signature and the timestamp of a delivery are valid.

    Example::

        valid = verify_signature(
            request.body,
            request.headers.get("X-FeedbackPilgrim-Signature-V2"),
            request.headers.get("X-FeedbackPilgrim-Timestamp"),
            settings.FEEDBACKPILGRIM_WEBHOOK_SECRET,
        )

    Args:
        payload: The raw request body, byte for byte. Do not decode the JSON and
            encode it again: a new encoding gives other bytes.
        signature: The ``X-FeedbackPilgrim-Signature-V2`` header.
        timestamp: The ``X-FeedbackPilgrim-Timestamp`` header.
        secret: The signing secret of the webhook.
        tolerance: The maximum difference in seconds between the timestamp and
            the current time. The default is 300.
        now: The current Unix time. The default is ``time.time()``. Tests use it.
    """
    try:
        _verify(payload, signature, timestamp, secret, tolerance=tolerance, now=now)
    except WebhookVerificationError:
        return False
    return True


def construct_event(
    payload: bytes | str,
    headers: Mapping[str, str],
    secret: str,
    *,
    tolerance: int = DEFAULT_TOLERANCE,
    now: float | None = None,
) -> WebhookEvent:
    """Verify one delivery and return the event, with the delivery ID.

    Example::

        event = construct_event(request.body, request.headers, WEBHOOK_SECRET)
        if event.type == "post.completed":
            notify_voters(event.post.id)

    Args:
        payload: The raw request body, byte for byte.
        headers: The request headers. The names are not case-sensitive.
        secret: The signing secret of the webhook.
        tolerance: The maximum difference in seconds. The default is 300.
        now: The current Unix time. The default is ``time.time()``.

    Raises:
        WebhookVerificationError: The signature is missing or wrong
            (``reason="signature"``), or the timestamp is missing or outside the
            tolerance (``reason="timestamp"``).
    """
    body = _bytes(payload)
    signed_at = _verify(
        body,
        _header(headers, SIGNATURE_HEADER),
        _header(headers, TIMESTAMP_HEADER),
        secret,
        tolerance=tolerance,
        now=now,
    )
    decoded = json.loads(body)
    data = decoded.get("data") if isinstance(decoded, dict) else None
    return WebhookEvent(
        type=str(decoded.get("event") if isinstance(decoded, dict) else ""),
        delivery_id=_header(headers, DELIVERY_HEADER),
        timestamp=signed_at,
        post=WebhookPost.from_dict(data if isinstance(data, dict) else {}),
        raw=decoded if isinstance(decoded, dict) else {},
    )


def sign(timestamp: str, payload: bytes | str, secret: str) -> str:
    """Return the ``X-FeedbackPilgrim-Signature-V2`` value for a timestamp and a raw body.

    A test can use this function to make a signed delivery.
    """
    message = timestamp.encode("utf-8") + b"." + _bytes(payload)
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _verify(
    payload: bytes | str,
    signature: str | None,
    timestamp: str | None,
    secret: str,
    *,
    tolerance: int,
    now: float | None,
) -> int:
    """Return the timestamp as an int, or raise ``WebhookVerificationError``."""
    if not secret:
        raise ValueError("secret must not be empty")
    if not timestamp:
        raise WebhookVerificationError(
            f"The {TIMESTAMP_HEADER} header is missing.", reason="timestamp"
        )
    if not signature:
        raise WebhookVerificationError(
            f"The {SIGNATURE_HEADER} header is missing.", reason="signature"
        )

    expected = sign(timestamp, payload, secret)
    if not hmac.compare_digest(expected.encode("utf-8"), signature.strip().encode("utf-8")):
        raise WebhookVerificationError("The signature does not match.", reason="signature")

    try:
        signed_at = int(timestamp)
    except ValueError:
        raise WebhookVerificationError(
            f"The {TIMESTAMP_HEADER} header is not a Unix time.", reason="timestamp"
        ) from None
    current = time.time() if now is None else now
    if abs(current - signed_at) > tolerance:
        raise WebhookVerificationError(
            f"The timestamp is more than {tolerance} seconds from the current time.",
            reason="timestamp",
        )
    return signed_at


def _bytes(payload: bytes | str) -> bytes:
    return payload.encode("utf-8") if isinstance(payload, str) else payload


def _header(headers: Mapping[str, str], name: str) -> str | None:
    value = headers.get(name)
    if value is not None:
        return value
    wanted = name.lower()
    for key, item in headers.items():
        if key.lower() == wanted:
            return item
    return None


def _opt_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
