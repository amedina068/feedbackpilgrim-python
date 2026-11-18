"""The HTTP layer: one request, one response and a transport that sends them.

The default transport uses ``urllib`` from the standard library. A test, or an
application with its own HTTP stack, can give another transport to the client.
"""

from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from feedbackpilgrim.errors import APIConnectionError, APITimeoutError

__all__ = ["Request", "Response", "Transport", "UrllibTransport"]


@dataclass(frozen=True)
class Request:
    """One HTTP request, with the full URL and the encoded body."""

    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes | None = None


@dataclass(frozen=True)
class Response:
    """One HTTP response. The header names are lowercase."""

    status_code: int
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""

    def header(self, name: str) -> str | None:
        return self.headers.get(name.lower())

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        """Return the decoded JSON body. Raise ``ValueError`` when the body is not JSON."""
        return json.loads(self.body)


class Transport(Protocol):
    """Sends one request and returns the response for every status code.

    A transport raises :class:`~feedbackpilgrim.APIConnectionError` when it gets
    no response. It sets ``request_sent=False`` only when the instance did not
    receive the request.
    """

    def __call__(self, request: Request, timeout: float | None) -> Response: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # A redirect can send the token to another host. The client returns the
    # 3xx response as an error instead.
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


class UrllibTransport:
    """The default transport. It uses ``urllib`` and does not follow redirects."""

    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(_NoRedirect)

    def __call__(self, request: Request, timeout: float | None) -> Response:
        raw = urllib.request.Request(
            request.url,
            data=request.body,
            headers=dict(request.headers),
            method=request.method,
        )
        try:
            with self._opener.open(raw, timeout=timeout) as response:
                return Response(response.status, _lower(response.headers), response.read())
        except urllib.error.HTTPError as error:
            with error:
                return Response(error.code, _lower(error.headers), error.read())
        except urllib.error.URLError as error:
            # urllib raises URLError while it connects and sends the request.
            # The instance did not receive a complete request.
            if isinstance(error.reason, TimeoutError):
                raise APITimeoutError(
                    f"The connection timed out: {error.reason}", request_sent=False
                ) from error
            raise APIConnectionError(
                f"The connection to the instance failed: {error.reason}", request_sent=False
            ) from error
        except TimeoutError as error:
            raise APITimeoutError(f"The response timed out: {error}", request_sent=True) from error
        except (OSError, http.client.HTTPException) as error:
            raise APIConnectionError(
                f"The connection closed before the response: {error}", request_sent=True
            ) from error


def _lower(headers: Any) -> dict[str, str]:
    return {str(name).lower(): str(value) for name, value in headers.items()}
