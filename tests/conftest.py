from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import pytest

from feedbackpilgrim import FeedbackPilgrim, Request, Response, _client

BASE_URL = "https://feedback.example.com"
API = f"{BASE_URL}/api/public/v1"
TOKEN = "1|test-token"


class FakeTransport:
    """A transport that records each request and returns queued replies."""

    def __init__(self) -> None:
        self.requests: list[Request] = []
        self.timeouts: list[float | None] = []
        self._replies: list[Response | Exception] = []

    def reply(
        self,
        status: int = 200,
        json_body: Any = None,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> FakeTransport:
        all_headers = {"content-type": "application/json"} if json_body is not None else {}
        all_headers.update({name.lower(): value for name, value in (headers or {}).items()})
        content = json.dumps(json_body).encode() if json_body is not None else (body or b"")
        self._replies.append(Response(status, all_headers, content))
        return self

    def fail(self, error: Exception) -> FakeTransport:
        self._replies.append(error)
        return self

    def __call__(self, request: Request, timeout: float | None) -> Response:
        self.requests.append(request)
        self.timeouts.append(timeout)
        if not self._replies:
            raise AssertionError(f"No reply queued for {request.method} {request.url}")
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    @property
    def last(self) -> Request:
        return self.requests[-1]

    def path(self, index: int = -1) -> str:
        """Return the path of a request after /api/public/v1, without the query string."""
        url = self.requests[index].url
        assert url.startswith(API)
        return urlsplit(url).path[len(urlsplit(API).path) :]

    def query(self, index: int = -1) -> dict[str, str]:
        return dict(parse_qsl(urlsplit(self.requests[index].url).query))

    def json(self, index: int = -1) -> Any:
        body = self.requests[index].body
        return json.loads(body) if body is not None else None


class SleepRecorder:
    """Records each wait of the client instead of sleeping."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


@pytest.fixture(autouse=True)
def sleeps(monkeypatch: pytest.MonkeyPatch) -> SleepRecorder:
    recorder = SleepRecorder()
    monkeypatch.setattr(_client, "_sleep", recorder)
    return recorder


@pytest.fixture
def transport() -> FakeTransport:
    return FakeTransport()


@pytest.fixture
def client(transport: FakeTransport) -> FeedbackPilgrim:
    return FeedbackPilgrim(BASE_URL, TOKEN, transport=transport)
