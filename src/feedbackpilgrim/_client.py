"""The client: settings, request building, error mapping and retries."""

from __future__ import annotations

import email.utils
import json
import os
import random
import time
from collections.abc import Mapping
from typing import Any, Final
from urllib.parse import urlencode

from feedbackpilgrim._http import Request, Response, Transport, UrllibTransport
from feedbackpilgrim._resources import Contacts, Posts, ReleaseNotes, Tags, Testimonials, encode
from feedbackpilgrim._version import __version__
from feedbackpilgrim.errors import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    AuthorizationError,
    FeedbackPilgrimError,
    MethodNotAllowedError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)

__all__ = ["FeedbackPilgrim"]

DEFAULT_TIMEOUT: Final = 30.0
DEFAULT_MAX_RETRIES: Final = 2

BACKOFF_BASE: Final = 0.5
BACKOFF_MAX: Final = 8.0

# The client does not wait longer than this for one Retry-After value. If the
# instance asks for a longer wait, the client raises RateLimitError at once.
MAX_RETRY_AFTER: Final = 60.0

# A second copy of a request with one of these methods does no new action.
# Each update of this API sets absolute values, so PATCH is safe to repeat.
IDEMPOTENT_METHODS: Final = frozenset({"GET", "HEAD", "PUT", "PATCH", "DELETE"})

API_PREFIX: Final = "/api/public/v1"

USER_AGENT: Final = f"feedbackpilgrim-python/{__version__}"

_ERRORS_BY_STATUS: Final[dict[int, type[APIError]]] = {
    401: AuthenticationError,
    403: AuthorizationError,
    404: NotFoundError,
    405: MethodNotAllowedError,
    422: ValidationError,
}


# The tests replace this function, so that a retry does not wait.
def _sleep(seconds: float) -> None:
    time.sleep(seconds)


class FeedbackPilgrim:
    """A client for one Feedback Pilgrim instance.

    Example::

        client = FeedbackPilgrim("https://feedback.example.com", token="...")
        for post in client.posts.iter(status="pending"):
            print(post.title)

    Args:
        base_url: The URL of your instance. The default is ``$FEEDBACKPILGRIM_URL``.
        token: An API token from Settings, API Tokens. The default is
            ``$FEEDBACKPILGRIM_TOKEN``.
        timeout: The seconds to wait for the connection and for each read.
            The default is 30. ``None`` means no timeout.
        max_retries: The number of retries after a 429, a 5xx or a connection
            error. The default is 2. Use 0 to stop all retries.
        transport: Sends the HTTP requests. The default uses ``urllib``.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        *,
        timeout: float | None = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        transport: Transport | None = None,
    ) -> None:
        base_url = base_url or os.environ.get("FEEDBACKPILGRIM_URL")
        token = token or os.environ.get("FEEDBACKPILGRIM_TOKEN")
        if not base_url:
            raise ValueError(
                "Give the URL of your Feedback Pilgrim instance as base_url, "
                "or set the FEEDBACKPILGRIM_URL environment variable."
            )
        if not token:
            raise ValueError(
                "Give an API token as token, or set the FEEDBACKPILGRIM_TOKEN environment variable."
            )
        if max_retries < 0:
            raise ValueError("max_retries must be 0 or more")

        self.base_url = normalize_base_url(base_url)
        self.timeout = timeout
        self.max_retries = max_retries
        self._token = token
        self._transport: Transport = transport or UrllibTransport()

        self.posts = Posts(self)
        self.release_notes = ReleaseNotes(self)
        self.contacts = Contacts(self)
        self.testimonials = Testimonials(self)
        self.tags = Tags(self)

    def __repr__(self) -> str:
        # Never show the token.
        return f"FeedbackPilgrim(base_url={self.base_url!r})"

    def sign_in_url(
        self,
        email: str,
        *,
        name: str | None = None,
        mrr: float | None = None,
        ltv: float | None = None,
        avatar: str | None = None,
        custom_fields: Mapping[str, Any] | None = None,
    ) -> str:
        """Sign in a contact and return a sign-in link for the public site.

        The instance creates the contact, or updates the contact with this
        email. The link is valid for 24 hours. Send it only to that contact.
        ``custom_fields`` replace all the custom fields of an existing contact.
        """
        if not email.strip():
            raise ValueError("email must not be empty")
        known = encode(email=email, name=name, mrr=mrr, ltv=ltv, avatar=avatar)
        body = self._post("/init", {"contact": {**(custom_fields or {}), **known}})
        # Without a contact email, the instance sends [] and no link.
        auth_url = body.get("auth_url") if isinstance(body, dict) else None
        if not isinstance(auth_url, str):
            raise FeedbackPilgrimError("The instance sent no sign-in link for this contact.")
        return auth_url

    # --- Requests ------------------------------------------------------------

    def _get(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        return decode_body(self._request("GET", path, params=params))

    def _post(self, path: str, body: Mapping[str, Any]) -> Any:
        return decode_body(self._request("POST", path, body=body))

    def _post_response(self, path: str, body: Mapping[str, Any], *, idempotent: bool) -> Response:
        return self._request("POST", path, body=body, idempotent=idempotent)

    def _patch(self, path: str, body: Mapping[str, Any]) -> Any:
        return decode_body(self._request("PATCH", path, body=body))

    def _delete(self, path: str) -> None:
        self._request("DELETE", path)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        idempotent: bool = False,
    ) -> Response:
        request = self._build_request(method, path, params, body)
        idempotent = idempotent or method in IDEMPOTENT_METHODS
        attempt = 0
        while True:
            try:
                response = self._transport(request, self.timeout)
            except APIConnectionError as error:
                delay = self._connection_retry_delay(error, idempotent, attempt)
                if delay is None:
                    raise
            else:
                if 200 <= response.status_code < 300:
                    return _checked(response)
                delay = self._response_retry_delay(response, idempotent, attempt)
                if delay is None:
                    raise error_from_response(response)
            _sleep(delay)
            attempt += 1

    def _build_request(
        self,
        method: str,
        path: str,
        params: Mapping[str, Any] | None,
        body: Mapping[str, Any] | None,
    ) -> Request:
        url = f"{self.base_url}{API_PREFIX}{path}"
        query = urlencode(query_pairs(params or {}))
        if query:
            url = f"{url}?{query}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            # Without this header, Laravel sends an error as a redirect to
            # /login or as an HTML page.
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        return Request(method, url, headers, data)

    def _connection_retry_delay(
        self, error: APIConnectionError, idempotent: bool, attempt: int
    ) -> float | None:
        if attempt >= self.max_retries:
            return None
        if error.request_sent and not idempotent:
            return None
        return backoff(attempt)

    def _response_retry_delay(
        self, response: Response, idempotent: bool, attempt: int
    ) -> float | None:
        """Return the wait before the next attempt, or ``None`` for no retry.

        The client retries a 429 for every method, because the rate limiter
        refuses the request before the app does the action. The client retries
        a 5xx only for an idempotent request.
        """
        if attempt >= self.max_retries:
            return None
        status = response.status_code
        if status == 429:
            retry_after = parse_retry_after(response.header("retry-after"))
            if retry_after is None:
                return backoff(attempt)
            return retry_after if retry_after <= MAX_RETRY_AFTER else None
        if status >= 500 and idempotent:
            return backoff(attempt)
        return None


def normalize_base_url(base_url: str) -> str:
    """Return the instance URL with no trailing ``/``, ``/api`` or ``/api/public/v1``."""
    url = base_url.strip().rstrip("/")
    if not url.startswith(("https://", "http://")):
        raise ValueError(f"base_url must start with https:// or http://, not {base_url!r}")
    for suffix in (API_PREFIX, "/api"):
        if url.endswith(suffix):
            return url[: -len(suffix)]
    return url


def query_pairs(params: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Encode query parameters the way Laravel reads them.

    A boolean becomes ``1`` or ``0``. The app reads both with ``filter_var``.
    """
    pairs: list[tuple[str, str]] = []
    for name, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            pairs.append((name, "1" if value else "0"))
        else:
            pairs.append((name, str(value)))
    return pairs


def backoff(attempt: int) -> float:
    """Return the wait before retry number ``attempt + 1``: exponential, with jitter."""
    ceiling = min(BACKOFF_MAX, BACKOFF_BASE * (2.0**attempt))
    return ceiling * random.uniform(0.5, 1.0)


def parse_retry_after(value: str | None) -> float | None:
    """Read a ``Retry-After`` header: a number of seconds or an HTTP date."""
    if value is None:
        return None
    value = value.strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        moment = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, moment.timestamp() - time.time())


def _checked(response: Response) -> Response:
    content_type = response.header("content-type") or ""
    if response.body and "json" not in content_type:
        raise FeedbackPilgrimError(
            f"The instance sent {content_type or 'a response with no content type'}, "
            "not JSON. Make sure that base_url is the URL of a Feedback Pilgrim instance."
        )
    return response


def decode_body(response: Response) -> Any:
    """Return the JSON body, the text body when the body is not JSON, or ``None``."""
    if not response.body:
        return None
    try:
        return response.json()
    except ValueError:
        return response.text


def error_from_response(response: Response) -> APIError:
    """Convert an error response to the matching error class."""
    body = decode_body(response)
    status = response.status_code
    message = _message(body) or f"HTTP {status}"

    if status == 429:
        return RateLimitError(
            message,
            status_code=status,
            body=body,
            headers=response.headers,
            retry_after=parse_retry_after(response.header("retry-after")),
        )
    if status >= 500:
        return ServerError(message, status_code=status, body=body, headers=response.headers)
    error_class = _ERRORS_BY_STATUS.get(status, APIError)
    return error_class(message, status_code=status, body=body, headers=response.headers)


def _message(body: Any) -> str | None:
    # Most errors send "message". The token middleware sends "error".
    if not isinstance(body, dict):
        return None
    for key in ("message", "error"):
        value = body.get(key)
        if isinstance(value, str) and value:
            return value
    return None
