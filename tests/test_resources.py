"""Each resource method sends the right request and reads the response."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from feedbackpilgrim import Contact, FeedbackPilgrim, FeedbackPilgrimError, Page, Post
from tests.conftest import FakeTransport
from tests.payloads import (
    COMMENT,
    CONTACT,
    POST,
    RELEASE_NOTE,
    STAGE,
    TAG,
    TESTIMONIAL,
    page,
)

# --- Posts -------------------------------------------------------------------


def test_posts_list_sends_the_filters(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(200, page([POST]))

    result = client.posts.list(
        search="dark",
        status="in_progress",
        board_id=1,
        tag="feature",
        published=False,
        sort_by="title",
        sort_direction="asc",
        per_page=10,
        page=2,
    )

    assert transport.last.method == "GET"
    assert transport.path() == "/posts"
    assert transport.query() == {
        "search": "dark",
        "status": "in_progress",
        "board_id": "1",
        "tag": "feature",
        "published": "0",
        "sort_by": "title",
        "sort_direction": "asc",
        "per_page": "10",
        "page": "2",
    }
    assert isinstance(result, Page)
    assert [post.title for post in result] == ["Add dark mode"]


def test_posts_list_sends_only_the_page_by_default(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.reply(200, page([]))
    client.posts.list()
    assert transport.query() == {"page": "1"}


def test_post_model_reads_the_nested_records(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.reply(200, {**POST, "comments": [COMMENT]})

    post = client.posts.get(1)

    assert transport.path() == "/posts/1"
    assert post.id == 1
    assert post.status == "in_progress"
    assert post.created_at == datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    assert post.is_published is False
    assert post.tags[0].title == "feature"
    assert post.votes[0].contact_id == 7
    assert post.comments[0].content == "Yes please."
    assert post.contact is not None
    assert post.contact.email == "jane@example.com"
    assert post.raw["title"] == "Add dark mode"


def test_a_nested_contact_reads_custom_fields_from_metadata(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.reply(200, POST)
    contact = client.posts.get(1).contact
    assert contact is not None
    # The app keeps pilgrim_ fields in the metadata. The model drops them.
    assert contact.custom_fields == {"plan": "pro"}
    assert contact.mrr == 149.99
    assert contact.ltv == 1800.0
    assert contact.top_customer is False


def test_posts_create(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    created = {**POST, "status": "pending", "contact": None, "stage": STAGE}
    transport.reply(201, created)

    post = client.posts.create("Add dark mode", "Please add a dark theme.", tags=(1, 2))

    assert transport.last.method == "POST"
    assert transport.path() == "/posts"
    assert transport.json() == {
        "title": "Add dark mode",
        "content": "Please add a dark theme.",
        "tags": [1, 2],
    }
    assert post.contact is None
    assert post.stage is not None
    assert post.stage.type == "active"


def test_posts_update_sends_only_the_given_fields_with_patch(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.reply(200, POST)

    client.posts.update(1, status="completed", tags=[])

    assert transport.last.method == "PATCH"
    assert transport.path() == "/posts/1"
    assert transport.json() == {"status": "completed", "tags": []}


def test_posts_have_no_delete(client: FeedbackPilgrim) -> None:
    # The API always sends 405 for the delete of a post.
    assert not hasattr(client.posts, "delete")
    assert not hasattr(client.release_notes, "delete")
    assert not hasattr(client.testimonials, "delete")


# --- Release notes ------------------------------------------------------------


def test_release_notes_list(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(200, page([RELEASE_NOTE], path="/release-notes"))

    notes = client.release_notes.list(published=True, tag="feature", per_page=5)

    assert transport.path() == "/release-notes"
    assert transport.query() == {"published": "1", "tag": "feature", "per_page": "5", "page": "1"}
    assert notes.data[0].slug == "version-210-20260601"


def test_release_notes_get(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(200, {**RELEASE_NOTE, "published_at": "2026-06-02T10:00:00.000000Z"})
    note = client.release_notes.get(1)
    assert transport.path() == "/release-notes/1"
    assert note.is_published
    assert note.content == "## New\n- Dark mode"


def test_release_notes_create(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(201, RELEASE_NOTE)
    client.release_notes.create("Version 2.1.0", "## New", published=True, tags=[1])
    assert transport.last.method == "POST"
    assert transport.json() == {
        "title": "Version 2.1.0",
        "content": "## New",
        "published": True,
        "tags": [1],
    }


def test_release_notes_update(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(200, RELEASE_NOTE)
    client.release_notes.update(1, published=False)
    assert transport.last.method == "PATCH"
    assert transport.path() == "/release-notes/1"
    assert transport.json() == {"published": False}


# --- Contacts -----------------------------------------------------------------


def test_contacts_list(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(200, page([CONTACT], path="/contacts"))

    contacts = client.contacts.list(search="jane", sort_by="mrr", sort_direction="desc")

    assert transport.path() == "/contacts"
    assert transport.query() == {
        "search": "jane",
        "sort_by": "mrr",
        "sort_direction": "desc",
        "page": "1",
    }
    assert contacts.data[0].custom_fields == {"plan": "pro"}


def test_contacts_get_reads_custom_fields_as_fields(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.reply(200, {**CONTACT, "company": {"name": "Acme", "size": 12}})

    contact = client.contacts.get(7)

    assert transport.path() == "/contacts/7"
    assert contact.custom_fields == {"plan": "pro", "company": {"name": "Acme", "size": 12}}
    assert contact.tags[0].id == 1
    assert contact.created is None


@pytest.mark.parametrize(("status", "created"), [(201, True), (200, False)])
def test_contacts_upsert(
    client: FeedbackPilgrim, transport: FakeTransport, status: int, created: bool
) -> None:
    transport.reply(status, CONTACT)

    contact = client.contacts.upsert(
        "jane@example.com",
        "Jane Smith",
        mrr=149.99,
        tags=[1],
        custom_fields={"plan": "pro"},
    )

    assert transport.last.method == "POST"
    assert transport.path() == "/contacts"
    assert transport.json() == {
        "email": "jane@example.com",
        "name": "Jane Smith",
        "mrr": 149.99,
        "tags": [1],
        "metadata": {"plan": "pro"},
    }
    assert isinstance(contact, Contact)
    assert contact.created is created


def test_contacts_update_cannot_send_custom_fields(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.reply(200, CONTACT)
    client.contacts.update(7, name="Jane S.", mrr=199)
    assert transport.last.method == "PATCH"
    assert transport.path() == "/contacts/7"
    assert transport.json() == {"name": "Jane S.", "mrr": 199}


def test_an_empty_avatar_is_none(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(200, {**CONTACT, "avatar": ""})
    assert client.contacts.get(7).avatar is None


# --- Testimonials -------------------------------------------------------------


def test_testimonials_list_reads_pending_by_default(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.reply(200, page([TESTIMONIAL], path="/testimonials"))
    result = client.testimonials.list()
    assert transport.path() == "/testimonials"
    assert transport.query() == {"approved": "0", "page": "1"}
    assert result.data[0].is_approved is False


def test_testimonials_list_approved(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(200, page([], path="/testimonials"))
    client.testimonials.list(approved=True, rating=5)
    assert transport.query() == {"approved": "1", "rating": "5", "page": "1"}


def test_testimonials_get(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(200, TESTIMONIAL)
    testimonial = client.testimonials.get(1)
    assert transport.path() == "/testimonials/1"
    assert testimonial.rating == 5
    assert testimonial.contact is not None
    assert testimonial.contact.custom_fields == {"plan": "pro"}


def test_testimonials_create(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(201, TESTIMONIAL)
    client.testimonials.create("Great roadmap.", "jane_doe", rating=5, contact_id=7)
    assert transport.last.method == "POST"
    assert transport.json() == {
        "description": "Great roadmap.",
        "username": "jane_doe",
        "rating": 5,
        "contact_id": 7,
    }


def test_testimonials_update_with_approved_at(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.reply(200, {**TESTIMONIAL, "approved_at": "2026-06-15T10:00:00.000000Z"})

    testimonial = client.testimonials.update(
        1, approved_at=datetime(2026, 6, 15, 10, tzinfo=timezone.utc)
    )

    assert transport.last.method == "PATCH"
    assert transport.json() == {"approved_at": "2026-06-15T10:00:00+00:00"}
    assert testimonial.is_approved


def test_testimonials_approve_sends_the_current_time(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.reply(200, TESTIMONIAL)
    before = datetime.now(timezone.utc)

    client.testimonials.approve(1)

    sent = datetime.fromisoformat(transport.json()["approved_at"])
    assert before <= sent <= datetime.now(timezone.utc)


# --- Tags ---------------------------------------------------------------------


def test_tags_list_reads_the_counts(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(200, page([{**TAG, "posts_count": 4, "contacts_count": 2}], path="/tags"))
    tag = client.tags.list(search="feat").data[0]
    assert transport.path() == "/tags"
    assert transport.query() == {"search": "feat", "page": "1"}
    assert (tag.posts_count, tag.contacts_count) == (4, 2)


def test_tags_create(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(201, TAG)
    tag = client.tags.create("feature")
    assert transport.last.method == "POST"
    assert transport.json() == {"title": "feature"}
    assert tag.posts_count is None


def test_tags_update(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(200, {**TAG, "title": "enhancement"})
    tag = client.tags.update(1, "enhancement")
    assert transport.last.method == "PATCH"
    assert transport.path() == "/tags/1"
    assert tag.title == "enhancement"


def test_tags_delete_reads_an_empty_204(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(204)
    client.tags.delete(1)
    assert transport.last.method == "DELETE"
    assert transport.path() == "/tags/1"


# --- Init ---------------------------------------------------------------------


def test_sign_in_url(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(200, {"auth_url": "https://acme.example.com/authenticate/abc?signature=x"})

    url = client.sign_in_url(
        "jane@example.com", name="Jane Doe", mrr=99.99, custom_fields={"plan": "premium"}
    )

    assert transport.last.method == "POST"
    assert transport.path() == "/init"
    assert transport.json() == {
        "contact": {
            "plan": "premium",
            "email": "jane@example.com",
            "name": "Jane Doe",
            "mrr": 99.99,
        }
    }
    assert url == "https://acme.example.com/authenticate/abc?signature=x"


def test_sign_in_url_known_fields_win_over_custom_fields(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.reply(200, {"auth_url": "https://acme.example.com/a"})
    client.sign_in_url("jane@example.com", custom_fields={"email": "other@example.com"})
    assert transport.json() == {"contact": {"email": "jane@example.com"}}


def test_sign_in_url_returns_none_when_the_instance_sends_an_empty_array(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    # The app sends [] when the request has no contact email.
    transport.reply(200, [])
    assert client.sign_in_url("") is None
    assert transport.json() == {"contact": {"email": ""}}


# --- Arguments ----------------------------------------------------------------


@pytest.mark.parametrize("bad_id", ["1", 1.0, True, None])
def test_an_id_must_be_an_int(client: FeedbackPilgrim, bad_id: object) -> None:
    with pytest.raises(TypeError, match="post_id must be an int"):
        client.posts.get(bad_id)  # type: ignore[arg-type]


@pytest.mark.parametrize("per_page", [0, 101])
def test_per_page_must_be_from_1_to_100(client: FeedbackPilgrim, per_page: int) -> None:
    with pytest.raises(ValueError, match="per_page must be from 1 to 100"):
        client.tags.list(per_page=per_page)


def test_page_must_be_1_or_more(client: FeedbackPilgrim) -> None:
    with pytest.raises(ValueError, match="page must be 1 or more"):
        client.contacts.list(page=0)


def test_a_body_that_is_not_an_object_raises(
    client: FeedbackPilgrim, transport: FakeTransport
) -> None:
    transport.reply(200, ["not", "an", "object"])
    with pytest.raises(FeedbackPilgrimError, match="not a JSON object"):
        client.posts.get(1)


def test_unknown_fields_stay_in_raw(client: FeedbackPilgrim, transport: FakeTransport) -> None:
    transport.reply(200, {**POST, "priority": "high"})
    post: Post = client.posts.get(1)
    assert post.raw["priority"] == "high"
