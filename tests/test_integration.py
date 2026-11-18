"""Integration tests against a live instance.

The tests run only when FEEDBACKPILGRIM_TEST_URL and FEEDBACKPILGRIM_TEST_TOKEN
are set. They are read-only: they list posts and tags.
"""

from __future__ import annotations

import os
import time

import pytest

from feedbackpilgrim import FeedbackPilgrim, _client

URL = os.environ.get("FEEDBACKPILGRIM_TEST_URL")
TOKEN = os.environ.get("FEEDBACKPILGRIM_TEST_TOKEN")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (URL and TOKEN), reason="Set FEEDBACKPILGRIM_TEST_URL and FEEDBACKPILGRIM_TEST_TOKEN."
    ),
]


@pytest.fixture
def live(monkeypatch: pytest.MonkeyPatch) -> FeedbackPilgrim:
    # The autouse fixture replaces the sleep function. A live retry needs the real one.
    monkeypatch.setattr(_client, "_sleep", time.sleep)
    return FeedbackPilgrim(URL, TOKEN)


def test_list_posts(live: FeedbackPilgrim) -> None:
    page = live.posts.list(per_page=5)
    assert page.current_page == 1
    assert page.per_page == 5
    assert len(page) <= 5
    for post in page:
        assert post.id > 0


def test_list_tags(live: FeedbackPilgrim) -> None:
    page = live.tags.list(per_page=5)
    assert page.current_page == 1
    for tag in page:
        assert tag.title
        assert tag.posts_count is not None
