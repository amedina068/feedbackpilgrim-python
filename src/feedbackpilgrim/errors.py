"""The errors that the Feedback Pilgrim client raises.

All errors come from :class:`FeedbackPilgrimError`::

    FeedbackPilgrimError
    +-- APIConnectionError         the client did not get a response
    |   +-- APITimeoutError        the request took more time than the timeout
    +-- APIError                   the instance sent an error status
    |   +-- AuthenticationError    401
    |   +-- AuthorizationError     403
    |   +-- NotFoundError          404
    |   +-- MethodNotAllowedError  405
    |   +-- ValidationError        422, with the field errors
    |   +-- RateLimitError         429, with the Retry-After value
    |   +-- ServerError            5xx
    +-- WebhookVerificationError   a webhook delivery is not valid
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

__all__ = [
    "APIConnectionError",
    "APIError",
    "APITimeoutError",
    "AuthenticationError",
    "AuthorizationError",
    "FeedbackPilgrimError",
    "MethodNotAllowedError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "ValidationError",
    "WebhookVerificationError",
]


class FeedbackPilgrimError(Exception):
    """The base class of every error that this package raises."""


class APIConnectionError(FeedbackPilgrimError):
    """The client did not get a response from the instance.

    The cause is a DNS error, a refused connection, a closed connection or a
    TLS error. The original exception is in ``__cause__``.

    Attributes:
        request_sent: ``False`` when the instance did not receive the request.
            Then a second attempt is safe for every method.
    """

    def __init__(self, message: str, *, request_sent: bool) -> None:
        super().__init__(message)
        self.message = message
        self.request_sent = request_sent


class APITimeoutError(APIConnectionError):
    """The request took more time than the timeout of the client."""


class APIError(FeedbackPilgrimError):
    """The instance sent a response with an error status.

    Attributes:
        status_code: The HTTP status code.
        message: The ``message`` or ``error`` field of the body, or ``HTTP <status>``.
        body: The decoded JSON body, or the text body.
        headers: The response headers, with lowercase names.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        body: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.body = body
        self.headers: Mapping[str, str] = headers or {}

    def __str__(self) -> str:
        return f"{self.status_code}: {self.message}"


class AuthenticationError(APIError):
    """The token is missing or wrong, or its user cannot use the client (401).

    The instance also sends 401 when the user is deactivated or is no longer a
    member of the client of the token.
    """


class AuthorizationError(APIError):
    """The token cannot do this action (403).

    The REST API does not send 403 today. The client maps it for a later version.
    """


class NotFoundError(APIError):
    """The client of the token has no record with this ID (404)."""


class MethodNotAllowedError(APIError):
    """The API does not support this operation (405).

    The API cannot delete a post, a release note or a testimonial.
    """


class ValidationError(APIError):
    """A field of the request failed a validation rule (422).

    Attributes:
        errors: The field errors, for example ``{"title": ["The title field is required."]}``.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        body: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, body=body, headers=headers)
        self.errors: dict[str, list[str]] = _field_errors(body)


class RateLimitError(APIError):
    """The user made more than 120 requests in one minute (429).

    All the tokens of one user share this limit.

    Attributes:
        retry_after: The seconds to wait, from the ``Retry-After`` header, or ``None``.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        body: Any = None,
        headers: Mapping[str, str] | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, body=body, headers=headers)
        self.retry_after = retry_after


class ServerError(APIError):
    """The instance had an internal error (5xx)."""


class WebhookVerificationError(FeedbackPilgrimError):
    """A webhook delivery did not pass the verification.

    Attributes:
        reason: ``"signature"`` when the signature is missing or wrong.
            ``"timestamp"`` when the timestamp is missing or outside the tolerance.
    """

    def __init__(self, message: str, *, reason: Literal["signature", "timestamp"]) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason


def _field_errors(body: Any) -> dict[str, list[str]]:
    raw = body.get("errors") if isinstance(body, dict) else None
    if not isinstance(raw, dict):
        return {}
    return {
        str(field): [str(item) for item in messages]
        if isinstance(messages, list)
        else [str(messages)]
        for field, messages in raw.items()
    }
