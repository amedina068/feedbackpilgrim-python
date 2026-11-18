"""The retry logic: what the client retries, and how long it waits."""

from __future__ import annotations

import pytest

from feedbackpilgrim import (
    APIConnectionError,
    APITimeoutError,
    FeedbackPilgrim,
    RateLimitError,
    ServerError,
)
from feedbackpilgrim._client import backoff, parse_retry_after
from tests.conftest import FakeTransport, SleepRecorder
from tests.payloads import CONTACT, POST, TAG, page


def test_get_retries_a_5xx_then_succeeds(
    client: FeedbackPilgrim, transport: FakeTransport, sleeps: SleepRecorder
) -> None:
    transport.reply(503, {"message": "down"}).reply(200, page([TAG], path="/tags"))
    assert len(client.tags.list()) == 1
    assert len(transport.requests) == 2
    assert len(sleeps.delays) == 1


def test_get_stops_after_max_retries(
    client: FeedbackPilgrim, transport: FakeTransport, sleeps: SleepRecorder
) -> None:
    for _ in range(3):
        transport.reply(500, {"message": "boom"})
    with pytest.raises(ServerError):
        client.tags.list()
    assert len(transport.requests) == 3
    assert len(sleeps.delays) == 2


def test_post_does_not_retry_a_5xx(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(500, {"message": "boom"})
    with pytest.raises(ServerError):
        client.posts.create("t", "c")
    assert len(transport.requests) == 1


def test_post_retries_a_429(
    client: FeedbackPilgrim, transport: FakeTransport, sleeps: SleepRecorder
) -> None:
    # The rate limiter refuses the request before the app does the action.
    transport.reply(429, {"message": "Too Many Attempts."}, headers={"Retry-After": "3"})
    transport.reply(201, POST)
    client.posts.create("t", "c")
    assert len(transport.requests) == 2
    assert sleeps.delays == [3.0]


def test_patch_retries_a_5xx(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(502, {"message": "bad gateway"}).reply(200, POST)
    client.posts.update(1, title="x")
    assert len(transport.requests) == 2


def test_delete_retries_a_5xx(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(503, {"message": "down"}).reply(204)
    client.tags.delete(1)
    assert len(transport.requests) == 2


def test_contact_upsert_retries_a_5xx(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    # The upsert finds the contact by email, so a second copy is safe.
    transport.reply(500, {"message": "boom"}).reply(200, CONTACT)
    assert client.contacts.upsert("jane@example.com", "Jane").created is False
    assert len(transport.requests) == 2


def test_a_long_retry_after_raises_at_once(
    client: FeedbackPilgrim, transport: FakeTransport, sleeps: SleepRecorder
) -> None:
    transport.reply(429, {"message": "Too Many Attempts."}, headers={"Retry-After": "61"})
    with pytest.raises(RateLimitError) as caught:
        client.tags.list()
    assert caught.value.retry_after == 61.0
    assert sleeps.delays == []


def test_a_429_without_retry_after_uses_the_backoff(
    client: FeedbackPilgrim, transport: FakeTransport, sleeps: SleepRecorder
) -> None:
    transport.reply(429, {"message": "Too Many Attempts."}).reply(200, page([], path="/tags"))
    client.tags.list()
    assert 0.25 <= sleeps.delays[0] <= 0.5


def test_a_connection_error_before_the_request_is_retried_for_post(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.fail(APIConnectionError("refused", request_sent=False)).reply(201, POST)
    client.posts.create("t", "c")
    assert len(transport.requests) == 2


def test_a_timeout_after_the_request_is_not_retried_for_post(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.fail(APITimeoutError("read timed out", request_sent=True))
    with pytest.raises(APITimeoutError):
        client.posts.create("t", "c")
    assert len(transport.requests) == 1


def test_a_timeout_after_the_request_is_retried_for_get(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.fail(APITimeoutError("read timed out", request_sent=True)).reply(200, POST)
    assert client.posts.get(1).id == 1
    assert len(transport.requests) == 2


def test_max_retries_zero_stops_all_retries(transport: FakeTransport) -> None:
    client = FeedbackPilgrim(
        "https://feedback.example.com", "1|t", max_retries=0, transport=transport
    )
    transport.reply(429, {"message": "Too Many Attempts."}, headers={"Retry-After": "1"})
    with pytest.raises(RateLimitError):
        client.tags.list()
    assert len(transport.requests) == 1


def test_a_4xx_is_not_retried(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(404, {"message": "No query results"})
    with pytest.raises(Exception, match="404"):
        client.posts.get(1)
    assert len(transport.requests) == 1


def test_backoff_grows_and_has_a_ceiling() -> None:
    for attempt, ceiling in [(0, 0.5), (1, 1.0), (2, 2.0), (3, 4.0), (4, 8.0), (10, 8.0)]:
        delay = backoff(attempt)
        assert ceiling / 2 <= delay <= ceiling


def test_parse_retry_after() -> None:
    assert parse_retry_after(None) is None
    assert parse_retry_after(" 7 ") == 7.0
    assert parse_retry_after("-3") == 0.0
    assert parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0
    assert parse_retry_after("soon") is None
