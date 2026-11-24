"""Python client for the Feedback Pilgrim API.

Example::

    from feedbackpilgrim import FeedbackPilgrim

    client = FeedbackPilgrim("https://feedback.example.com", token="...")
    for post in client.posts.iter(status="pending"):
        print(post.id, post.title)
"""

from feedbackpilgrim._client import FeedbackPilgrim
from feedbackpilgrim._http import Request, Response, Transport, UrllibTransport
from feedbackpilgrim._version import __version__
from feedbackpilgrim.errors import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    AuthorizationError,
    FeedbackPilgrimError,
    MethodNotAllowedError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
    WebhookVerificationError,
)
from feedbackpilgrim.identity import identity_hash
from feedbackpilgrim.models import (
    Comment,
    Contact,
    Page,
    Post,
    ReleaseNote,
    Stage,
    Tag,
    Testimonial,
    Vote,
)
from feedbackpilgrim.webhooks import WebhookEvent, WebhookPost, verify_signature, verify_webhook

__all__ = [
    "APIConnectionError",
    "APIError",
    "APITimeoutError",
    "AuthenticationError",
    "AuthorizationError",
    "Comment",
    "Contact",
    "FeedbackPilgrim",
    "FeedbackPilgrimError",
    "MethodNotAllowedError",
    "NotFoundError",
    "Page",
    "Post",
    "RateLimitError",
    "ReleaseNote",
    "Request",
    "Response",
    "ServerError",
    "Stage",
    "Tag",
    "Testimonial",
    "Transport",
    "UrllibTransport",
    "ValidationError",
    "Vote",
    "WebhookEvent",
    "WebhookPost",
    "WebhookVerificationError",
    "__version__",
    "identity_hash",
    "verify_signature",
    "verify_webhook",
]
