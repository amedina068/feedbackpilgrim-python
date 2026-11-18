"""Response bodies in the shape that the app sends (spec examples and app source)."""

from __future__ import annotations

from typing import Any

from tests.conftest import API

NOW = "2026-06-01T09:00:00.000000Z"

TAG: dict[str, Any] = {
    "id": 1,
    "client_id": 1,
    "title": "feature",
    "created_at": NOW,
    "updated_at": NOW,
}

VOTE: dict[str, Any] = {
    "id": 3,
    "contact_id": 7,
    "votable_type": "App\\Models\\Post",
    "votable_id": 1,
    "created_at": NOW,
    "updated_at": NOW,
}

COMMENT: dict[str, Any] = {
    "id": 5,
    "contact_id": 7,
    "commentable_type": "App\\Models\\Post",
    "commentable_id": 1,
    "content": "Yes please.",
    "hidden_at": None,
    "created_at": NOW,
    "updated_at": NOW,
}

# A contact inside a post or a testimonial: custom fields in a JSON string.
NESTED_CONTACT: dict[str, Any] = {
    "id": 7,
    "uuid": "6e48ad77-fb51-449f-99d2-9c5cc2d9d0c5",
    "user_id": None,
    "client_id": 1,
    "name": "Jane Smith",
    "email": "jane@example.com",
    "metadata": '{"plan":"pro","pilgrim_last_login":"2026-06-01 09:00:00"}',
    "notes": None,
    "avatar": "https://feedback.example.com/storage/avatars/7/avatar.png",
    "mrr": 149.99,
    "ltv": 1800,
    "top_customer": 0,
    "created_at": NOW,
    "updated_at": NOW,
}

# A contact from the Contacts operations: each custom field is a field.
CONTACT: dict[str, Any] = {
    **{key: value for key, value in NESTED_CONTACT.items() if key != "metadata"},
    "plan": "pro",
    "tags": [TAG],
    "votes": [VOTE],
}

STAGE: dict[str, Any] = {
    "id": 4,
    "client_id": 1,
    "name": "In Progress",
    "slug": "in-progress",
    "color": "#3b82f6",
    "type": "active",
    "show_on_roadmap": True,
    "position": 3,
    "created_at": NOW,
    "updated_at": NOW,
}

POST: dict[str, Any] = {
    "id": 1,
    "client_id": 1,
    "stage_id": 4,
    "board_id": 1,
    "contact_id": 7,
    "title": "Add dark mode",
    "content": "Please add a dark theme.",
    "notes": None,
    "status": "in_progress",
    "stage_position": None,
    "published_at": None,
    "archived_at": None,
    "created_at": NOW,
    "updated_at": NOW,
    "contact": NESTED_CONTACT,
    "tags": [TAG],
    "votes": [VOTE],
}

RELEASE_NOTE: dict[str, Any] = {
    "id": 1,
    "client_id": 1,
    "user_id": 1,
    "title": "Version 2.1.0",
    "content": "## New\n- Dark mode",
    "slug": "version-210-20260601",
    "published_at": None,
    "created_at": NOW,
    "updated_at": NOW,
    "tags": [TAG],
    "votes": [],
    "comments": [],
}

TESTIMONIAL: dict[str, Any] = {
    "id": 1,
    "client_id": 1,
    "contact_id": 7,
    "title": None,
    "description": "The roadmap keeps our customers in the loop.",
    "rating": 5,
    "avatar_image": None,
    "username": "jane_doe",
    "subtitle": None,
    "approved_at": None,
    "created_at": NOW,
    "updated_at": NOW,
    "contact": NESTED_CONTACT,
    "votes": [],
    "comments": [],
}


def page(
    records: list[dict[str, Any]],
    *,
    current_page: int = 1,
    last_page: int = 1,
    per_page: int = 15,
    total: int | None = None,
    path: str = "/posts",
) -> dict[str, Any]:
    """Return a flat Laravel paginator, as the app sends it."""
    url = f"{API}{path}"
    return {
        "current_page": current_page,
        "data": records,
        "first_page_url": f"{url}?page=1",
        "from": 1 if records else None,
        "last_page": last_page,
        "last_page_url": f"{url}?page={last_page}",
        "links": [],
        "next_page_url": f"{url}?page={current_page + 1}" if current_page < last_page else None,
        "path": url,
        "per_page": per_page,
        "prev_page_url": f"{url}?page={current_page - 1}" if current_page > 1 else None,
        "to": len(records) or None,
        "total": len(records) if total is None else total,
    }
