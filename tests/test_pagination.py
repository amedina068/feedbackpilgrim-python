"""The pagination helper: iter() reads all the pages of the Laravel paginator."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest

from feedbackpilgrim import FeedbackPilgrim
from tests.conftest import FakeTransport
from tests.payloads import CONTACT, POST, RELEASE_NOTE, TAG, TESTIMONIAL, page


def test_iter_reads_each_page_until_the_last_page(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.reply(200, page([POST, {**POST, "id": 2}], current_page=1, last_page=3, total=5))
    transport.reply(200, page([{**POST, "id": 3}, {**POST, "id": 4}], current_page=2, last_page=3))
    transport.reply(200, page([{**POST, "id": 5}], current_page=3, last_page=3))

    ids = [post.id for post in client.posts.iter(status="pending", per_page=2)]

    assert ids == [1, 2, 3, 4, 5]
    assert [transport.query(i)["page"] for i in range(3)] == ["1", "2", "3"]
    assert all(transport.query(i)["per_page"] == "2" for i in range(3))
    assert all(transport.query(i)["status"] == "pending" for i in range(3))


def test_iter_uses_100_records_per_page_by_default(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.reply(200, page([TAG], path="/tags"))
    assert len(list(client.tags.iter())) == 1
    assert transport.query() == {"per_page": "100", "page": "1"}


def test_iter_gets_a_page_only_when_the_caller_needs_it(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.reply(200, page([POST], current_page=1, last_page=2))
    posts = client.posts.iter()
    assert transport.requests == []
    assert next(posts).id == 1
    assert len(transport.requests) == 1


def test_iter_stops_on_an_empty_page(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    # The records can change while the caller reads. An empty page ends the loop.
    transport.reply(200, page([], current_page=1, last_page=4))
    assert list(client.posts.iter()) == []
    assert len(transport.requests) == 1


def test_page_fields(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(200, page([POST], current_page=2, last_page=3, per_page=1, total=3))
    result = client.posts.list(per_page=1, page=2)
    assert (result.current_page, result.last_page, result.per_page, result.total) == (2, 3, 1, 3)
    assert result.has_more
    assert result.next_page_url is not None
    assert result.next_page_url.endswith("page=3")
    assert len(result) == 1


def test_the_last_page_has_no_more(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(200, page([POST], current_page=3, last_page=3))
    assert client.posts.list(page=3).has_more is False


@pytest.mark.parametrize(
    ("iterate", "record", "path"),
    [
        (lambda c: c.release_notes.iter(published=True), RELEASE_NOTE, "/release-notes"),
        (lambda c: c.contacts.iter(tag="vip"), CONTACT, "/contacts"),
        (lambda c: c.testimonials.iter(approved=True), TESTIMONIAL, "/testimonials"),
    ],
)
def test_each_resource_has_iter(
    client: FeedbackPilgrim,
    transport: FakeTransport,
    iterate: Callable[[FeedbackPilgrim], Iterator[Any]],
    record: dict[str, Any],
    path: str,
) -> None:
    transport.reply(200, page([record], current_page=1, last_page=2, path=path))
    transport.reply(200, page([record], current_page=2, last_page=2, path=path))
    assert len(list(iterate(client))) == 2
    assert transport.path() == path
    assert transport.query()["page"] == "2"
