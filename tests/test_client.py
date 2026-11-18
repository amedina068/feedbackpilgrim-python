"""The settings of the client and the request that it builds."""

from __future__ import annotations

import pytest

from feedbackpilgrim import FeedbackPilgrim, FeedbackPilgrimError, __version__
from tests.conftest import BASE_URL, TOKEN, FakeTransport
from tests.payloads import TAG, page


def test_each_request_sends_the_token_and_accepts_json(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.reply(200, page([TAG], path="/tags"))
    client.tags.list()
    headers = transport.last.headers
    assert headers["Authorization"] == f"Bearer {TOKEN}"
    assert headers["Accept"] == "application/json"
    assert headers["User-Agent"] == f"feedbackpilgrim-python/{__version__}"
    assert "Content-Type" not in headers
    assert transport.last.body is None


def test_a_request_with_a_body_sends_json(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.reply(201, TAG)
    client.tags.create("Café")
    assert transport.last.headers["Content-Type"] == "application/json"
    assert transport.json() == {"title": "Café"}


@pytest.mark.parametrize(
    "base_url",
    [
        "https://feedback.example.com",
        "https://feedback.example.com/",
        "https://feedback.example.com/api",
        "https://feedback.example.com/api/public/v1/",
        "  https://feedback.example.com  ",
    ],
)
def test_base_url_is_normalized(base_url: str) -> None:
    assert FeedbackPilgrim(base_url, TOKEN).base_url == BASE_URL


def test_base_url_needs_a_scheme() -> None:
    with pytest.raises(ValueError, match="https://"):
        FeedbackPilgrim("feedback.example.com", TOKEN)


def test_settings_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEEDBACKPILGRIM_URL", BASE_URL)
    monkeypatch.setenv("FEEDBACKPILGRIM_TOKEN", TOKEN)
    client = FeedbackPilgrim()
    assert client.base_url == BASE_URL


def test_base_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEEDBACKPILGRIM_URL", raising=False)
    with pytest.raises(ValueError, match="FEEDBACKPILGRIM_URL"):
        FeedbackPilgrim(token=TOKEN)


def test_token_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEEDBACKPILGRIM_TOKEN", raising=False)
    with pytest.raises(ValueError, match="FEEDBACKPILGRIM_TOKEN"):
        FeedbackPilgrim(BASE_URL)


def test_max_retries_cannot_be_negative() -> None:
    with pytest.raises(ValueError, match="max_retries"):
        FeedbackPilgrim(BASE_URL, TOKEN, max_retries=-1)


def test_repr_does_not_show_the_token() -> None:
    client = FeedbackPilgrim(BASE_URL, TOKEN)
    assert TOKEN not in repr(client)
    assert repr(client) == f"FeedbackPilgrim(base_url={BASE_URL!r})"


def test_the_timeout_goes_to_the_transport(transport: FakeTransport) -> None:
    client = FeedbackPilgrim(BASE_URL, TOKEN, timeout=5.0, transport=transport)
    transport.reply(200, page([], path="/tags"))
    client.tags.list()
    assert transport.timeouts == [5.0]


def test_the_default_timeout_is_30_seconds(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.reply(200, page([], path="/tags"))
    client.tags.list()
    assert transport.timeouts == [30.0]


def test_a_success_that_is_not_json_raises(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    # A wrong base_url can return the HTML page of another site.
    transport.reply(200, body=b"<html></html>", headers={"content-type": "text/html"})
    with pytest.raises(FeedbackPilgrimError, match="not JSON"):
        client.tags.list()
