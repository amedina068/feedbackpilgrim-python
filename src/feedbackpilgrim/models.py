"""Typed response models.

Each model is a frozen dataclass. The ``raw`` field keeps the decoded JSON
object, so you can read a field that this version of the package does not know.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar

__all__ = [
    "Comment",
    "Contact",
    "Page",
    "Post",
    "ReleaseNote",
    "Stage",
    "Tag",
    "Testimonial",
    "Vote",
]

T = TypeVar("T")

# The fields of a contact that are not custom fields.
CONTACT_FIELDS = frozenset(
    {
        "id",
        "uuid",
        "user_id",
        "client_id",
        "name",
        "email",
        "notes",
        "avatar",
        "mrr",
        "ltv",
        "top_customer",
        "metadata",
        "created_at",
        "updated_at",
        "tags",
        "votes",
    }
)

# The app keeps its own data in custom fields with this prefix.
RESERVED_PREFIX = "pilgrim_"


def _raw() -> Any:
    return field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True)
class Page(Generic[T]):
    """One page of a list: the flat Laravel paginator.

    Iterate over a page to get its records. To read all the pages, use the
    ``iter()`` method of the resource.
    """

    data: tuple[T, ...]
    current_page: int
    last_page: int
    per_page: int
    total: int
    next_page_url: str | None = None

    @property
    def has_more(self) -> bool:
        """``True`` when a page comes after this page."""
        return self.next_page_url is not None and self.current_page < self.last_page

    def __iter__(self) -> Iterator[T]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    @classmethod
    def from_dict(cls, body: Mapping[str, Any], item: Callable[[Mapping[str, Any]], T]) -> Page[T]:
        return cls(
            data=tuple(item(record) for record in _dicts(body.get("data"))),
            current_page=_int(body.get("current_page"), 1),
            last_page=_int(body.get("last_page"), 1),
            per_page=_int(body.get("per_page")),
            total=_int(body.get("total")),
            next_page_url=_opt_str(body.get("next_page_url")),
        )


@dataclass(frozen=True)
class Tag:
    """A label for posts, release notes and contacts.

    ``posts_count`` and ``contacts_count`` are set only in ``tags.list()``.
    """

    id: int
    title: str
    client_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    posts_count: int | None = None
    contacts_count: int | None = None
    raw: Mapping[str, Any] = _raw()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Tag:
        return cls(
            id=_int(data.get("id")),
            title=_str(data.get("title")),
            client_id=_opt_int(data.get("client_id")),
            created_at=_datetime(data.get("created_at")),
            updated_at=_datetime(data.get("updated_at")),
            posts_count=_opt_int(data.get("posts_count")),
            contacts_count=_opt_int(data.get("contacts_count")),
            raw=data,
        )


@dataclass(frozen=True)
class Stage:
    """A column of the post pipeline.

    ``type`` is ``open``, ``planned``, ``active``, ``complete`` or ``closed``.
    A webhook delivery sends only ``id``, ``name`` and ``type``.
    """

    id: int
    name: str
    type: str
    slug: str | None = None
    color: str | None = None
    position: int | None = None
    show_on_roadmap: bool | None = None
    raw: Mapping[str, Any] = _raw()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Stage:
        show = data.get("show_on_roadmap")
        return cls(
            id=_int(data.get("id")),
            name=_str(data.get("name")),
            type=_str(data.get("type")),
            slug=_opt_str(data.get("slug")),
            color=_opt_str(data.get("color")),
            position=_opt_int(data.get("position")),
            show_on_roadmap=None if show is None else bool(show),
            raw=data,
        )


@dataclass(frozen=True)
class Vote:
    """A vote of a contact on a post, a release note or a testimonial."""

    id: int
    contact_id: int | None
    created_at: datetime | None = None
    raw: Mapping[str, Any] = _raw()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Vote:
        return cls(
            id=_int(data.get("id")),
            contact_id=_opt_int(data.get("contact_id")),
            created_at=_datetime(data.get("created_at")),
            raw=data,
        )


@dataclass(frozen=True)
class Comment:
    """A comment on a post, a release note or a testimonial."""

    id: int
    content: str
    contact_id: int | None = None
    hidden_at: datetime | None = None
    created_at: datetime | None = None
    raw: Mapping[str, Any] = _raw()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Comment:
        return cls(
            id=_int(data.get("id")),
            content=_str(data.get("content")),
            contact_id=_opt_int(data.get("contact_id")),
            hidden_at=_datetime(data.get("hidden_at")),
            created_at=_datetime(data.get("created_at")),
            raw=data,
        )


@dataclass(frozen=True)
class Contact:
    """A customer of the client.

    ``custom_fields`` holds the custom metadata of the contact. The Contacts
    operations send each custom field as a field of the contact. A contact
    inside a post or a testimonial sends them as a JSON string in ``metadata``.
    The model reads both shapes. It drops the ``pilgrim_`` fields of the app.

    ``created`` is set only by ``contacts.upsert()``: ``True`` for a new
    contact (201), ``False`` for an updated contact (200).
    """

    id: int
    email: str | None
    name: str | None
    uuid: str | None = None
    client_id: int | None = None
    user_id: int | None = None
    notes: str | None = None
    avatar: str | None = None
    mrr: float | None = None
    ltv: float | None = None
    top_customer: bool = False
    custom_fields: Mapping[str, Any] = field(default_factory=dict)
    tags: tuple[Tag, ...] = ()
    votes: tuple[Vote, ...] = ()
    created_at: datetime | None = None
    updated_at: datetime | None = None
    created: bool | None = None
    raw: Mapping[str, Any] = _raw()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, created: bool | None = None) -> Contact:
        return cls(
            id=_int(data.get("id")),
            email=_opt_str(data.get("email")),
            name=_opt_str(data.get("name")),
            uuid=_opt_str(data.get("uuid")),
            client_id=_opt_int(data.get("client_id")),
            user_id=_opt_int(data.get("user_id")),
            notes=_opt_str(data.get("notes")),
            # The app stores an empty string for a contact with no avatar.
            avatar=_opt_str(data.get("avatar")) or None,
            mrr=_opt_float(data.get("mrr")),
            ltv=_opt_float(data.get("ltv")),
            top_customer=bool(data.get("top_customer")),
            custom_fields=_custom_fields(data),
            tags=tuple(Tag.from_dict(item) for item in _dicts(data.get("tags"))),
            votes=tuple(Vote.from_dict(item) for item in _dicts(data.get("votes"))),
            created_at=_datetime(data.get("created_at")),
            updated_at=_datetime(data.get("updated_at")),
            created=created,
            raw=data,
        )


@dataclass(frozen=True)
class Post:
    """A feature request or other feedback.

    ``status`` is ``pending``, ``in_progress``, ``completed`` or ``None``. The
    stage of the post sets it. ``stage`` is set only in the response of
    ``posts.create()`` and of some calls to ``posts.update()``. ``comments`` is
    set only in the response of ``posts.get()``.
    """

    id: int
    title: str
    content: str | None
    status: str | None
    client_id: int | None = None
    board_id: int | None = None
    stage_id: int | None = None
    contact_id: int | None = None
    notes: str | None = None
    stage_position: int | None = None
    published_at: datetime | None = None
    archived_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    contact: Contact | None = None
    stage: Stage | None = None
    tags: tuple[Tag, ...] = ()
    votes: tuple[Vote, ...] = ()
    comments: tuple[Comment, ...] = ()
    raw: Mapping[str, Any] = _raw()

    @property
    def is_published(self) -> bool:
        return self.published_at is not None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Post:
        return cls(
            id=_int(data.get("id")),
            title=_str(data.get("title")),
            content=_opt_str(data.get("content")),
            status=_opt_str(data.get("status")),
            client_id=_opt_int(data.get("client_id")),
            board_id=_opt_int(data.get("board_id")),
            stage_id=_opt_int(data.get("stage_id")),
            contact_id=_opt_int(data.get("contact_id")),
            notes=_opt_str(data.get("notes")),
            stage_position=_opt_int(data.get("stage_position")),
            published_at=_datetime(data.get("published_at")),
            archived_at=_datetime(data.get("archived_at")),
            created_at=_datetime(data.get("created_at")),
            updated_at=_datetime(data.get("updated_at")),
            contact=_opt_model(Contact.from_dict, data.get("contact")),
            stage=_opt_model(Stage.from_dict, data.get("stage")),
            tags=tuple(Tag.from_dict(item) for item in _dicts(data.get("tags"))),
            votes=tuple(Vote.from_dict(item) for item in _dicts(data.get("votes"))),
            comments=tuple(Comment.from_dict(item) for item in _dicts(data.get("comments"))),
            raw=data,
        )


@dataclass(frozen=True)
class ReleaseNote:
    """A changelog entry. ``content`` is Markdown.

    A note with no ``published_at`` is a draft. ``votes`` and ``comments`` are
    set only in ``release_notes.list()`` and ``release_notes.get()``.
    """

    id: int
    title: str
    content: str
    slug: str | None = None
    client_id: int | None = None
    user_id: int | None = None
    published_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    tags: tuple[Tag, ...] = ()
    votes: tuple[Vote, ...] = ()
    comments: tuple[Comment, ...] = ()
    raw: Mapping[str, Any] = _raw()

    @property
    def is_published(self) -> bool:
        return self.published_at is not None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReleaseNote:
        return cls(
            id=_int(data.get("id")),
            title=_str(data.get("title")),
            content=_str(data.get("content")),
            slug=_opt_str(data.get("slug")),
            client_id=_opt_int(data.get("client_id")),
            user_id=_opt_int(data.get("user_id")),
            published_at=_datetime(data.get("published_at")),
            created_at=_datetime(data.get("created_at")),
            updated_at=_datetime(data.get("updated_at")),
            tags=tuple(Tag.from_dict(item) for item in _dicts(data.get("tags"))),
            votes=tuple(Vote.from_dict(item) for item in _dicts(data.get("votes"))),
            comments=tuple(Comment.from_dict(item) for item in _dicts(data.get("comments"))),
            raw=data,
        )


@dataclass(frozen=True)
class Testimonial:
    """A customer testimonial. A testimonial with no ``approved_at`` is pending.

    ``votes`` and ``comments`` are set only in ``testimonials.list()`` and
    ``testimonials.get()``.
    """

    id: int
    description: str
    username: str | None
    rating: int | None = None
    title: str | None = None
    subtitle: str | None = None
    avatar_image: str | None = None
    client_id: int | None = None
    contact_id: int | None = None
    approved_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    contact: Contact | None = None
    votes: tuple[Vote, ...] = ()
    comments: tuple[Comment, ...] = ()
    raw: Mapping[str, Any] = _raw()

    @property
    def is_approved(self) -> bool:
        return self.approved_at is not None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Testimonial:
        return cls(
            id=_int(data.get("id")),
            description=_str(data.get("description")),
            username=_opt_str(data.get("username")),
            rating=_opt_int(data.get("rating")),
            title=_opt_str(data.get("title")),
            subtitle=_opt_str(data.get("subtitle")),
            avatar_image=_opt_str(data.get("avatar_image")),
            client_id=_opt_int(data.get("client_id")),
            contact_id=_opt_int(data.get("contact_id")),
            approved_at=_datetime(data.get("approved_at")),
            created_at=_datetime(data.get("created_at")),
            updated_at=_datetime(data.get("updated_at")),
            contact=_opt_model(Contact.from_dict, data.get("contact")),
            votes=tuple(Vote.from_dict(item) for item in _dicts(data.get("votes"))),
            comments=tuple(Comment.from_dict(item) for item in _dicts(data.get("comments"))),
            raw=data,
        )


# --- Helpers -----------------------------------------------------------------


def _custom_fields(data: Mapping[str, Any]) -> dict[str, Any]:
    fields = {key: value for key, value in data.items() if key not in CONTACT_FIELDS}
    metadata = data.get("metadata")
    if isinstance(metadata, str) and metadata:
        try:
            decoded = json.loads(metadata)
        except ValueError:
            decoded = None
        if isinstance(decoded, dict):
            fields = {**decoded, **fields}
    return {key: value for key, value in fields.items() if not key.startswith(RESERVED_PREFIX)}


def _opt_model(build: Callable[[Mapping[str, Any]], T], value: Any) -> T | None:
    return build(value) if isinstance(value, dict) else None


def _dicts(value: Any) -> list[Mapping[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _opt_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _int(value: Any, default: int = 0) -> int:
    result = _opt_int(value)
    return default if result is None else result


def _opt_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _opt_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    # Python 3.10 does not read a "Z" suffix. Laravel sends one.
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None
