"""The resources of the API: posts, release notes, contacts, testimonials and tags.

The API cannot delete a post, a release note or a testimonial. It always sends
405 for them, so the resources have no delete method for them.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Any, Final, Literal, TypeVar

from feedbackpilgrim.errors import FeedbackPilgrimError
from feedbackpilgrim.models import Contact, Page, Post, ReleaseNote, Tag, Testimonial

if TYPE_CHECKING:
    from feedbackpilgrim._client import FeedbackPilgrim

T = TypeVar("T")

MAX_PER_PAGE: Final = 100

PostStatus = Literal["pending", "in_progress", "completed"]
SortDirection = Literal["asc", "desc"]


class Resource:
    def __init__(self, client: FeedbackPilgrim) -> None:
        self._client = client

    def _page(
        self, path: str, item: Callable[[Mapping[str, Any]], T], params: Mapping[str, Any]
    ) -> Page[T]:
        return Page.from_dict(_object(self._client._get(path, params)), item)


def paginate(fetch: Callable[[int], Page[T]], page: int = 1) -> Iterator[T]:
    """Yield each record of each page. Get the next page only when the caller needs it."""
    while True:
        current = fetch(page)
        yield from current
        if not current.has_more or not current.data:
            return
        page = current.current_page + 1


def encode(**fields: Any) -> dict[str, Any]:
    """Return the fields that are not ``None``, ready for JSON."""
    return {name: _json_value(value) for name, value in fields.items() if value is not None}


def list_params(per_page: int | None, page: int, **filters: Any) -> dict[str, Any]:
    if per_page is not None and not 1 <= per_page <= MAX_PER_PAGE:
        raise ValueError(f"per_page must be from 1 to {MAX_PER_PAGE}, not {per_page}")
    if page < 1:
        raise ValueError(f"page must be 1 or more, not {page}")
    return {**filters, "per_page": per_page, "page": page}


def record_id(value: int, name: str) -> int:
    # The API reads each ID in the path as an integer.
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, not {type(value).__name__}")
    return value


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return list(value)
    return value


def _object(body: Any) -> Mapping[str, Any]:
    if not isinstance(body, dict):
        raise FeedbackPilgrimError(
            "The instance sent a response that is not a JSON object. "
            "Make sure that base_url is the URL of a Feedback Pilgrim instance."
        )
    return body


class Posts(Resource):
    """Feature requests and other feedback."""

    def list(
        self,
        *,
        search: str | None = None,
        status: PostStatus | None = None,
        board_id: int | None = None,
        tag: str | None = None,
        published: bool | None = None,
        sort_by: str | None = None,
        sort_direction: SortDirection | None = None,
        per_page: int | None = None,
        page: int = 1,
    ) -> Page[Post]:
        """Return one page of posts, newest first by default.

        ``tag`` is the exact title of a tag. ``published=False`` returns the drafts.
        """
        params = list_params(
            per_page,
            page,
            search=search,
            status=status,
            board_id=board_id,
            tag=tag,
            published=published,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )
        return self._page("/posts", Post.from_dict, params)

    def iter(
        self,
        *,
        search: str | None = None,
        status: PostStatus | None = None,
        board_id: int | None = None,
        tag: str | None = None,
        published: bool | None = None,
        sort_by: str | None = None,
        sort_direction: SortDirection | None = None,
        per_page: int = MAX_PER_PAGE,
    ) -> Iterator[Post]:
        """Iterate over all the posts that match the filters, page by page."""
        return paginate(
            lambda page: self.list(
                search=search,
                status=status,
                board_id=board_id,
                tag=tag,
                published=published,
                sort_by=sort_by,
                sort_direction=sort_direction,
                per_page=per_page,
                page=page,
            )
        )

    def get(self, post_id: int) -> Post:
        """Return one post with its contact, tags, votes and comments."""
        body = self._client._get(f"/posts/{record_id(post_id, 'post_id')}")
        return Post.from_dict(_object(body))

    def create(
        self,
        title: str,
        content: str,
        *,
        status: PostStatus | None = None,
        board_id: int | None = None,
        tags: Iterable[int] | None = None,
    ) -> Post:
        """Create a post. Without ``board_id``, the post goes on the first board."""
        body = encode(title=title, content=content, status=status, board_id=board_id, tags=tags)
        return Post.from_dict(_object(self._client._post("/posts", body)))

    def update(
        self,
        post_id: int,
        *,
        title: str | None = None,
        content: str | None = None,
        status: PostStatus | None = None,
        board_id: int | None = None,
        tags: Iterable[int] | None = None,
    ) -> Post:
        """Change the fields that you give. ``tags`` replaces all the tags of the post.

        A new ``status`` moves the post to the first stage of the matching type.
        The instance then sends the same emails, webhooks and Slack message as
        a stage change in the dashboard.
        """
        body = encode(title=title, content=content, status=status, board_id=board_id, tags=tags)
        path = f"/posts/{record_id(post_id, 'post_id')}"
        return Post.from_dict(_object(self._client._patch(path, body)))


class ReleaseNotes(Resource):
    """Changelog entries."""

    def list(
        self,
        *,
        search: str | None = None,
        published: bool | None = None,
        tag: str | None = None,
        sort_by: str | None = None,
        sort_direction: SortDirection | None = None,
        per_page: int | None = None,
        page: int = 1,
    ) -> Page[ReleaseNote]:
        """Return one page of release notes, newest first by default."""
        params = list_params(
            per_page,
            page,
            search=search,
            published=published,
            tag=tag,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )
        return self._page("/release-notes", ReleaseNote.from_dict, params)

    def iter(
        self,
        *,
        search: str | None = None,
        published: bool | None = None,
        tag: str | None = None,
        sort_by: str | None = None,
        sort_direction: SortDirection | None = None,
        per_page: int = MAX_PER_PAGE,
    ) -> Iterator[ReleaseNote]:
        """Iterate over all the release notes that match the filters, page by page."""
        return paginate(
            lambda page: self.list(
                search=search,
                published=published,
                tag=tag,
                sort_by=sort_by,
                sort_direction=sort_direction,
                per_page=per_page,
                page=page,
            )
        )

    def get(self, release_note_id: int) -> ReleaseNote:
        """Return one release note with its tags, votes and comments."""
        body = self._client._get(f"/release-notes/{record_id(release_note_id, 'release_note_id')}")
        return ReleaseNote.from_dict(_object(body))

    def create(
        self,
        title: str,
        content: str,
        *,
        published: bool | None = None,
        tags: Iterable[int] | None = None,
    ) -> ReleaseNote:
        """Create a release note. ``content`` is Markdown.

        Without ``published=True``, the note is a draft. The user of the API
        token becomes the author.
        """
        body = encode(title=title, content=content, published=published, tags=tags)
        return ReleaseNote.from_dict(_object(self._client._post("/release-notes", body)))

    def update(
        self,
        release_note_id: int,
        *,
        title: str | None = None,
        content: str | None = None,
        published: bool | None = None,
        tags: Iterable[int] | None = None,
    ) -> ReleaseNote:
        """Change the fields that you give. ``tags`` replaces all the tags of the note.

        ``published=True`` keeps a publication date that exists.
        ``published=False`` clears the date, and the note becomes a draft.
        """
        body = encode(title=title, content=content, published=published, tags=tags)
        path = f"/release-notes/{record_id(release_note_id, 'release_note_id')}"
        return ReleaseNote.from_dict(_object(self._client._patch(path, body)))


class Contacts(Resource):
    """The customers of the client."""

    def list(
        self,
        *,
        search: str | None = None,
        tag: str | None = None,
        sort_by: str | None = None,
        sort_direction: SortDirection | None = None,
        per_page: int | None = None,
        page: int = 1,
    ) -> Page[Contact]:
        """Return one page of contacts, newest first by default.

        ``search`` looks in the name and the email.
        """
        params = list_params(
            per_page, page, search=search, tag=tag, sort_by=sort_by, sort_direction=sort_direction
        )
        return self._page("/contacts", Contact.from_dict, params)

    def iter(
        self,
        *,
        search: str | None = None,
        tag: str | None = None,
        sort_by: str | None = None,
        sort_direction: SortDirection | None = None,
        per_page: int = MAX_PER_PAGE,
    ) -> Iterator[Contact]:
        """Iterate over all the contacts that match the filters, page by page."""
        return paginate(
            lambda page: self.list(
                search=search,
                tag=tag,
                sort_by=sort_by,
                sort_direction=sort_direction,
                per_page=per_page,
                page=page,
            )
        )

    def get(self, contact_id: int) -> Contact:
        """Return one contact with its tags, votes and custom fields."""
        body = self._client._get(f"/contacts/{record_id(contact_id, 'contact_id')}")
        return Contact.from_dict(_object(body))

    def upsert(
        self,
        email: str,
        name: str,
        *,
        mrr: float | None = None,
        ltv: float | None = None,
        avatar: str | None = None,
        tags: Iterable[int] | None = None,
        custom_fields: Mapping[str, Any] | None = None,
    ) -> Contact:
        """Create a contact, or update the contact of the client with this email.

        ``contact.created`` tells which one occurred. The instance merges
        ``custom_fields`` with the custom fields that the contact has. A key
        cannot start with ``pilgrim_``. ``tags`` replaces all the tags.
        """
        body = encode(
            email=email,
            name=name,
            mrr=mrr,
            ltv=ltv,
            avatar=avatar,
            tags=tags,
            metadata=custom_fields,
        )
        # The instance finds the contact by email, so a second copy is safe.
        response = self._client._post_response("/contacts", body, idempotent=True)
        return Contact.from_dict(_object(response.json()), created=response.status_code == 201)

    def update(
        self,
        contact_id: int,
        *,
        name: str | None = None,
        email: str | None = None,
        mrr: float | None = None,
        ltv: float | None = None,
        avatar: str | None = None,
        tags: Iterable[int] | None = None,
    ) -> Contact:
        """Change the fields that you give. ``tags`` replaces all the tags of the contact.

        This method cannot change the custom fields. Use :meth:`upsert` with the
        email of the contact.
        """
        body = encode(name=name, email=email, mrr=mrr, ltv=ltv, avatar=avatar, tags=tags)
        path = f"/contacts/{record_id(contact_id, 'contact_id')}"
        return Contact.from_dict(_object(self._client._patch(path, body)))


class Testimonials(Resource):
    """Customer testimonials."""

    def list(
        self,
        *,
        approved: bool = False,
        search: str | None = None,
        rating: int | None = None,
        sort_by: str | None = None,
        sort_direction: SortDirection | None = None,
        per_page: int | None = None,
        page: int = 1,
    ) -> Page[Testimonial]:
        """Return one page of testimonials, newest first by default.

        ``approved=False`` (the default) returns the pending testimonials.
        ``approved=True`` returns the approved testimonials.
        """
        params = list_params(
            per_page,
            page,
            approved=approved,
            search=search,
            rating=rating,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )
        return self._page("/testimonials", Testimonial.from_dict, params)

    def iter(
        self,
        *,
        approved: bool = False,
        search: str | None = None,
        rating: int | None = None,
        sort_by: str | None = None,
        sort_direction: SortDirection | None = None,
        per_page: int = MAX_PER_PAGE,
    ) -> Iterator[Testimonial]:
        """Iterate over all the testimonials that match the filters, page by page."""
        return paginate(
            lambda page: self.list(
                approved=approved,
                search=search,
                rating=rating,
                sort_by=sort_by,
                sort_direction=sort_direction,
                per_page=per_page,
                page=page,
            )
        )

    def get(self, testimonial_id: int) -> Testimonial:
        """Return one testimonial with its contact, votes and comments."""
        body = self._client._get(f"/testimonials/{record_id(testimonial_id, 'testimonial_id')}")
        return Testimonial.from_dict(_object(body))

    def create(
        self,
        description: str,
        username: str,
        *,
        rating: int | None = None,
        contact_id: int | None = None,
    ) -> Testimonial:
        """Create a pending testimonial. ``rating`` is 1 to 5."""
        body = encode(
            description=description, username=username, rating=rating, contact_id=contact_id
        )
        return Testimonial.from_dict(_object(self._client._post("/testimonials", body)))

    def update(
        self,
        testimonial_id: int,
        *,
        description: str | None = None,
        username: str | None = None,
        rating: int | None = None,
        approved_at: datetime | str | None = None,
    ) -> Testimonial:
        """Change the fields that you give. Set ``approved_at`` to approve the testimonial.

        The API cannot clear ``approved_at``.
        """
        body = encode(
            description=description, username=username, rating=rating, approved_at=approved_at
        )
        path = f"/testimonials/{record_id(testimonial_id, 'testimonial_id')}"
        return Testimonial.from_dict(_object(self._client._patch(path, body)))

    def approve(self, testimonial_id: int, *, at: datetime | None = None) -> Testimonial:
        """Approve a testimonial. ``at`` is the approval time. The default is now, in UTC."""
        return self.update(testimonial_id, approved_at=at or datetime.now(timezone.utc))


class Tags(Resource):
    """Labels for posts, release notes and contacts."""

    def list(
        self,
        *,
        search: str | None = None,
        sort_by: str | None = None,
        sort_direction: SortDirection | None = None,
        per_page: int | None = None,
        page: int = 1,
    ) -> Page[Tag]:
        """Return one page of tags with their usage counts, by title A to Z by default."""
        params = list_params(
            per_page, page, search=search, sort_by=sort_by, sort_direction=sort_direction
        )
        return self._page("/tags", Tag.from_dict, params)

    def iter(
        self,
        *,
        search: str | None = None,
        sort_by: str | None = None,
        sort_direction: SortDirection | None = None,
        per_page: int = MAX_PER_PAGE,
    ) -> Iterator[Tag]:
        """Iterate over all the tags, page by page."""
        return paginate(
            lambda page: self.list(
                search=search,
                sort_by=sort_by,
                sort_direction=sort_direction,
                per_page=per_page,
                page=page,
            )
        )

    def create(self, title: str) -> Tag:
        """Create a tag. The title must be unique in the client."""
        return Tag.from_dict(_object(self._client._post("/tags", {"title": title})))

    def update(self, tag_id: int, title: str) -> Tag:
        """Change the title of a tag. The title must be unique in the client."""
        path = f"/tags/{record_id(tag_id, 'tag_id')}"
        return Tag.from_dict(_object(self._client._patch(path, {"title": title})))

    def delete(self, tag_id: int) -> None:
        """Remove the tag from each post, release note and contact. Then delete the tag."""
        self._client._delete(f"/tags/{record_id(tag_id, 'tag_id')}")
