"""Each error status maps to its error class."""

from __future__ import annotations

import pytest

from feedbackpilgrim import (
    APIError,
    AuthenticationError,
    AuthorizationError,
    FeedbackPilgrim,
    MethodNotAllowedError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from tests.conftest import FakeTransport


@pytest.fixture
def no_retry(transport: FakeTransport) -> FeedbackPilgrim:
    return FeedbackPilgrim(
        "https://feedback.example.com", "1|t", max_retries=0, transport=transport
    )


def test_401_with_message(no_retry: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(401, {"message": "Unauthenticated."})
    with pytest.raises(AuthenticationError) as caught:
        no_retry.posts.list()
    assert caught.value.status_code == 401
    assert caught.value.message == "Unauthenticated."
    assert str(caught.value) == "401: Unauthenticated."


def test_401_with_error_field(no_retry: FeedbackPilgrim, transport: FakeTransport) -> None:
    # The token middleware of the app sends "error", not "message".
    transport.reply(401, {"error": "Invalid API token"})
    with pytest.raises(AuthenticationError) as caught:
        no_retry.posts.list()
    assert caught.value.message == "Invalid API token"


def test_403(no_retry: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(403, {"message": "This action is unauthorized."})
    with pytest.raises(AuthorizationError):
        no_retry.posts.list()


def test_404(no_retry: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(404, {"message": "No query results for model [App\\Models\\Post] 999"})
    with pytest.raises(NotFoundError) as caught:
        no_retry.posts.get(999)
    assert "999" in caught.value.message


def test_405(no_retry: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(405, {"message": "Method not allowed"})
    with pytest.raises(MethodNotAllowedError):
        no_retry._request("DELETE", "/posts/1")


def test_422_has_the_field_errors(no_retry: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(
        422,
        {
            "message": "The title field is required. (and 1 more error)",
            "errors": {
                "title": ["The title field is required."],
                "tags.0": ["The selected tags.0 is invalid."],
            },
        },
    )
    with pytest.raises(ValidationError) as caught:
        no_retry.posts.create("", "x")
    assert caught.value.errors == {
        "title": ["The title field is required."],
        "tags.0": ["The selected tags.0 is invalid."],
    }


def test_422_from_metadata_guard(no_retry: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(
        422,
        {
            "message": "The metadata key [pilgrim_x] is reserved.",
            "errors": {"metadata": ["The metadata key [pilgrim_x] is reserved."]},
        },
    )
    with pytest.raises(ValidationError) as caught:
        no_retry.contacts.upsert("a@example.com", "A", custom_fields={"pilgrim_x": 1})
    assert list(caught.value.errors) == ["metadata"]


def test_429_has_retry_after(no_retry: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(
        429,
        {"message": "Too Many Attempts."},
        headers={"Retry-After": "42", "X-RateLimit-Limit": "120", "X-RateLimit-Remaining": "0"},
    )
    with pytest.raises(RateLimitError) as caught:
        no_retry.posts.list()
    assert caught.value.retry_after == 42.0
    assert caught.value.headers["x-ratelimit-limit"] == "120"


@pytest.mark.parametrize("status", [500, 502, 503])
def test_5xx(no_retry: FeedbackPilgrim, transport: FakeTransport, status: int) -> None:
    transport.reply(status, {"message": "Server Error"})
    with pytest.raises(ServerError) as caught:
        no_retry.posts.list()
    assert caught.value.status_code == status


def test_an_html_error_body(no_retry: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(500, body=b"<html>Whoops</html>", headers={"content-type": "text/html"})
    with pytest.raises(ServerError) as caught:
        no_retry.posts.list()
    assert caught.value.message == "HTTP 500"
    assert caught.value.body == "<html>Whoops</html>"


def test_an_unmapped_status_is_an_api_error(
    no_retry: FeedbackPilgrim, transport: FakeTransport
) -> None:
    # A redirect is not followed, because it can send the token to another host.
    transport.reply(302, body=b"", headers={"location": "/login"})
    with pytest.raises(APIError) as caught:
        no_retry.posts.list()
    assert type(caught.value) is APIError
    assert caught.value.status_code == 302
