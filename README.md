# feedbackpilgrim

[![CI](https://github.com/amedina068/feedbackpilgrim-python/actions/workflows/ci.yml/badge.svg)](https://github.com/amedina068/feedbackpilgrim-python/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

The Python client for the Feedback Pilgrim API. Feedback Pilgrim collects feedback, release notes and testimonials for one client (a project).

Feedback Pilgrim is self-hosted. Each client of this package connects to one Feedback Pilgrim instance, so the URL of your instance is a required setting.

```python
from feedbackpilgrim import FeedbackPilgrim

client = FeedbackPilgrim("https://feedback.example.com", token="...")

for post in client.posts.iter(status="pending"):
    print(post.id, post.title)
```

## Contents

- [Install](#install)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Resources](#resources)
- [Pagination](#pagination)
- [Identity hash](#identity-hash)
- [Webhooks](#webhooks)
- [Errors](#errors)
- [Retries](#retries)
- [Django and FastAPI](#django-and-fastapi)
- [Supported Python versions](#supported-python-versions)
- [Related projects](#related-projects)
- [Community](#community)
- [License](#license)

## Install

The package is not on PyPI. Install it from the GitHub repository:

```bash
pip install "git+https://github.com/amedina068/feedbackpilgrim-python.git"
# or
uv add "git+https://github.com/amedina068/feedbackpilgrim-python.git"
```

The package has no dependencies. It uses only the Python standard library.

## Quick start

1. Open your Feedback Pilgrim instance. Go to **Settings → API Tokens** and create a token.
2. Keep the token on your server. The token gives full access to the data of one client.
3. Make a client and read the posts:

   ```python
   from feedbackpilgrim import FeedbackPilgrim

   client = FeedbackPilgrim("https://feedback.example.com", token="1|...")

   page = client.posts.list(status="pending", per_page=20)
   for post in page:
       print(post.id, post.title, len(post.votes))
   ```

4. Create a post:

   ```python
   post = client.posts.create("Add dark mode", "Please add a dark theme.", tags=[1])
   ```

## Configuration

```python
from feedbackpilgrim import FeedbackPilgrim

client = FeedbackPilgrim(
    "https://feedback.example.com",  # default: $FEEDBACKPILGRIM_URL
    token="1|...",  # default: $FEEDBACKPILGRIM_TOKEN
    timeout=30.0,  # seconds. None: no timeout
    max_retries=2,  # 0 stops all retries
)
```

| Setting | Default | Description |
|---|---|---|
| `base_url` | `$FEEDBACKPILGRIM_URL` | The URL of your instance (the `APP_URL`). The client removes a trailing `/`, `/api` and `/api/public/v1`. |
| `token` | `$FEEDBACKPILGRIM_TOKEN` | An API token. The client sends it as `Authorization: Bearer <token>`. |
| `timeout` | 30 seconds | The timeout of the connection and of each read. |
| `max_retries` | 2 | The number of retries. Read [Retries](#retries). |
| `transport` | `UrllibTransport()` | The object that sends the HTTP requests. |

The client sends `Accept: application/json` with each request. Without this header, Laravel sends an error as a redirect to `/login` or as an HTML page.

The client does not follow redirects, because a redirect can send the token to another host.

A token belongs to one client of the instance. Each request reads and changes only the data of that client. The API has no `client_id` argument.

### Custom transport

A transport is a callable that takes a `Request` and a timeout, and returns a `Response`. Give your own transport to use a proxy, custom TLS settings or another HTTP library:

```python
from feedbackpilgrim import APIConnectionError, APITimeoutError, FeedbackPilgrim, Request, Response
import httpx

http = httpx.Client(proxy="http://proxy.internal:3128")


def send(request: Request, timeout: float | None) -> Response:
    try:
        reply = http.request(
            request.method,
            request.url,
            headers=request.headers,
            content=request.body,
            timeout=timeout,
        )
    except httpx.ConnectTimeout as error:
        raise APITimeoutError(str(error), before_send=True) from error
    except httpx.TimeoutException as error:
        raise APITimeoutError(str(error)) from error
    except httpx.ConnectError as error:
        raise APIConnectionError(str(error), before_send=True) from error
    except httpx.TransportError as error:
        raise APIConnectionError(str(error)) from error
    return Response(
        reply.status_code, {k.lower(): v for k, v in reply.headers.items()}, reply.content
    )


client = FeedbackPilgrim("https://feedback.example.com", token="1|...", transport=send)
```

Raise `APIConnectionError` when the transport gets no response, and `APITimeoutError` after a timeout. Set `before_send=True` only for a DNS failure, a refused connection or a connect timeout. Then the client retries every request. For another connection error, the client retries only an idempotent request.

## Resources

Each ID is an `int`. Each method returns a frozen dataclass. The `raw` field of a model keeps the decoded JSON object, so you can read a field that this version does not know.

An update method sends only the arguments that you give. An argument that is `None` is not sent.

### Init: a sign-in link for a contact

```python
url = client.sign_in_url(
    "jane@example.com",
    name="Jane Doe",
    mrr=99.99,
    custom_fields={"plan": "premium"},
)
```

`sign_in_url()` sends `POST /api/public/v1/init`. The instance creates the contact, or updates the contact with this email. The link is valid for 24 hours. Send the link only to that contact.

For an existing contact, `custom_fields` replace all the custom fields. If the instance sends no link, `sign_in_url()` returns `None`. For example, an empty email gets `[]` and no link. The widget init call (`POST /api/v1/init`) runs in the browser. This package does not send it. To sign in a user in the widget, make an [identity hash](#identity-hash).

### Posts

```python
page = client.posts.list(search="dark", status="pending", board_id=1, tag="feature", published=True)
post = client.posts.get(42)
post = client.posts.create(
    "Add dark mode", "Please add a dark theme.", status="pending", board_id=1, tags=[1, 2]
)
post = client.posts.update(42, status="in_progress")
```

- `status` is `"pending"`, `"in_progress"` or `"completed"`.
- `published=False` returns the drafts.
- `sort_by` is `created_at` (the default), `updated_at`, `title`, `status` or `published_at`. `sort_direction` is `"desc"` (the default) or `"asc"`.
- Without `board_id`, `create()` puts the post on the first board of the client.
- A new `status` moves the post to the first stage of the matching type. The instance then sends the same emails, webhooks and Slack message as a stage change in the dashboard.
- `tags` replaces all the tags of the post. Give `tags=[]` to remove all the tags.
- `get()` also returns the comments. `post.contact.custom_fields` has the custom fields of the contact.

The API cannot delete a post. It always sends `405`, so the package has no `delete()` for posts.

### Release notes

```python
page = client.release_notes.list(published=True, tag="feature")
note = client.release_notes.get(7)
note = client.release_notes.create("Version 2.1.0", "## New\n- Dark mode", published=True, tags=[1])
note = client.release_notes.update(7, published=False)
```

- `content` is Markdown. The instance makes the `slug` from the title.
- Without `published=True`, a new note is a draft. The user of the API token becomes the author.
- `published=True` keeps a publication date that exists. `published=False` clears the date, and the note becomes a draft.
- `note.is_published` is `True` when the note has a publication date.

The API cannot delete a release note.

### Contacts

```python
page = client.contacts.list(search="jane", tag="vip", sort_by="mrr")
contact = client.contacts.get(7)
contact = client.contacts.upsert(
    "jane@example.com", "Jane Smith", mrr=149.99, tags=[1], custom_fields={"plan": "pro"}
)
contact = client.contacts.update(7, name="Jane S.", mrr=199)
```

- `upsert()` creates a contact, or updates the contact of the client with this email. `contact.created` is `True` for a new contact and `False` for an updated contact.
- `upsert()` merges `custom_fields` with the custom fields that the contact has. The custom fields can have 50 keys, 3 levels and 16 KB at most. A key cannot start with `pilgrim_`.
- `update()` cannot change the custom fields. To change them, call `upsert()` with the email of the contact.
- `contact.custom_fields` has the custom fields. The model reads them from a contact of the Contacts operations and from a contact inside a post or a testimonial.
- `sort_by` is `created_at`, `updated_at`, `name`, `email`, `mrr` or `ltv`.

The API cannot delete a contact.

### Testimonials

```python
page = client.testimonials.list(approved=True, rating=5)
testimonial = client.testimonials.get(3)
testimonial = client.testimonials.create(
    "The roadmap keeps our customers in the loop.", "jane_doe", rating=5, contact_id=7
)
testimonial = client.testimonials.update(3, rating=4)
testimonial = client.testimonials.approve(3)
```

- `list()` returns the pending testimonials by default. Give `approved=True` to get the approved testimonials.
- The list is newest first by default. `sort_by` is `created_at`, `updated_at`, `rating` or `approved_at`.
- `approve()` sets `approved_at` to the current time in UTC. Give `at=` for another time. `update(approved_at=...)` does the same.
- The API cannot clear `approved_at`, so the package cannot make an approved testimonial pending again.

The API cannot delete a testimonial.

### Tags

```python
page = client.tags.list(search="feat")
tag = client.tags.create("feature")
tag = client.tags.update(1, "enhancement")
client.tags.delete(1)
```

- A title must be unique in the client.
- `list()` sorts by title, A to Z, by default. Each tag of the list has `posts_count` and `contacts_count`.
- `delete()` removes the tag from each post, release note and contact. Then it deletes the tag.

## Pagination

A `list()` method returns one `Page`. A page has the records and the fields of the Laravel paginator:

```python
page = client.posts.list(per_page=50, page=2)

page.data  # a tuple of Post
page.current_page  # 2
page.last_page
page.per_page  # 50
page.total
page.next_page_url  # None on the last page
page.has_more  # True when a page comes after this page
```

`per_page` is 1 to 100. The default of the API is 15.

An `iter()` method reads all the pages and yields each record. It gets the next page only when your loop needs it. It uses 100 records on each page by default:

```python
for contact in client.contacts.iter(tag="vip"):
    print(contact.email)
```

`iter()` takes the same filters as `list()`, but not `page`. Each resource has it:

```python
drafts = list(client.posts.iter(published=False))
notes = list(client.release_notes.iter(tag="feature"))
approved = list(client.testimonials.iter(approved=True))
titles = [tag.title for tag in client.tags.iter()]
```

## Identity hash

The widget proves the email of the signed-in user with `user_hash`. Make the hash on your server:

```python
from feedbackpilgrim import identity_hash

user_hash = identity_hash(user.email, IDENTITY_SECRET)
```

Then give `user_hash` to the widget script in your page.

> **WARNING:** Make the hash on your server only. Never put the identity secret in browser code. A person with the secret can sign in as any of your users.

- The identity secret is a setting of the client in your instance. It is not the API token.
- The function normalizes the email exactly like the PHP code of the app: `strtolower(trim($email))`. It trims only the characters `" \t\n\r\0\x0B"`, and it changes only the letters `A` to `Z` to lowercase.
- Do not normalize the email with `str.strip()` or `str.lower()` first. They also change Unicode characters, and then the hash does not match.

## Webhooks

The instance sends a `POST` to your webhook URL for the events `post.created`, `post.status_changed` and `post.completed`. Each delivery has these headers:

| Header | Value |
|---|---|
| `X-FeedbackPilgrim-Event` | The event name. |
| `X-FeedbackPilgrim-Delivery` | A UUID. Each retry of the same delivery sends the same UUID. |
| `X-FeedbackPilgrim-Timestamp` | The Unix time of the attempt, in seconds. Each retry sends a new timestamp. |
| `X-FeedbackPilgrim-Signature-V2` | The HMAC-SHA256 hex digest of `<timestamp>.<raw body>`, with the signing secret of the webhook. |
| `X-FeedbackPilgrim-Signature` | Deprecated. The digest of the body only. The package does not read it. |

Verify the signature and get the event with `verify_webhook()`:

```python
from feedbackpilgrim import WebhookVerificationError, verify_webhook

try:
    event = verify_webhook(raw_body, headers, WEBHOOK_SECRET)
except WebhookVerificationError as error:
    ...  # send 400. error.reason is "timestamp", "signature" or "payload".

if event.delivery_id and already_processed(event.delivery_id):
    ...  # send 200 and do nothing
if event.type == "post.completed":
    notify_voters(event.data.id)
```

`event` is a `WebhookEvent`:

- `event.type`: `post.created`, `post.status_changed` or `post.completed`.
- `event.data`: `id`, `title`, `content`, `status`, `board_id`, `contact_id` and `stage` (`id`, `name`, `type`, or `None`).
- `event.payload`: the decoded body.
- `event.timestamp`: the Unix time of the attempt, as an `int`.
- `event.delivery_id`: the UUID of the delivery. Store it, and drop a delivery with an ID that you processed. The package does not store IDs. If the `X-FeedbackPilgrim-Delivery` header is missing, the verification passes and `delivery_id` is `None`. Older instances do not send this header.

`verify_webhook()` does the checks in this order. The first check that fails gives `error.reason`:

1. `"timestamp"`: the timestamp header is missing or has a character that is not an ASCII digit.
2. `"signature"`: the signature header is missing or does not match the timestamp and the raw body.
3. `"timestamp"`: the timestamp is outside the tolerance.
4. `"payload"`: the body is not a JSON object.

To get only a boolean, use `verify_signature()`:

```python
from feedbackpilgrim import verify_signature

valid = verify_signature(
    raw_body,
    headers.get("X-FeedbackPilgrim-Signature-V2"),
    headers.get("X-FeedbackPilgrim-Timestamp"),
    WEBHOOK_SECRET,
)
```

Rules:

- Give the raw bytes of the body. Do not decode the JSON and encode it again. The app escapes `/` as `\/` and each character that is not ASCII as `\uXXXX`, so a new encoding gives other bytes.
- The functions make the signature header lowercase, then compare the digests in constant time. An uppercase hex signature is valid.
- The functions refuse a timestamp that is more than 300 seconds from the current time. Give `tolerance=` to change the limit.
- The header names are not case-sensitive.

## Errors

All errors come from `FeedbackPilgrimError`:

```text
FeedbackPilgrimError
├── APIConnectionError        the client did not get a response
│   └── APITimeoutError       the request took more time than the timeout
├── APIError                  the instance sent an error status
│   ├── AuthenticationError   401: the token is missing or wrong, or the user is deactivated
│   ├── AuthorizationError    403
│   ├── NotFoundError         404: the client has no record with this ID
│   ├── MethodNotAllowedError 405
│   ├── ValidationError       422: .errors has the field errors
│   ├── RateLimitError        429: .retry_after
│   └── ServerError           5xx
└── WebhookVerificationError  a webhook delivery is not valid: .reason
```

Each `APIError` has `status_code`, `message`, `body` and `headers`. The `message` comes from the `message` field of the body, or from the `error` field.

```python
from feedbackpilgrim import NotFoundError, RateLimitError, ValidationError

try:
    post = client.posts.create(title, content, tags=[99])
except ValidationError as error:
    for field, messages in error.errors.items():
        print(field, messages)  # tags.0 ['The selected tags.0 is invalid.']
except RateLimitError as error:
    print("Wait", error.retry_after, "seconds")
except NotFoundError:
    print("No such record")
```

The REST API does not send 403 today. The package maps it for a later version of the API.

An argument that breaks a rule before the request raises `ValueError` or `TypeError`. For example, `per_page=200` raises `ValueError`, and `posts.get("42")` raises `TypeError`.

## Retries

The client retries a failed request two times by default. The wait before each retry grows exponentially (0.5, 1, 2 ... seconds, 8 seconds maximum) and has random jitter.

| Failure | GET, PATCH, DELETE, `contacts.upsert()` | Other POST |
|---|---|---|
| 429 | Retry | Retry |
| 5xx | Retry | No retry |
| DNS failure, refused connection or connect timeout | Retry | Retry |
| Read timeout, reset or other connection error | Retry | No retry |
| Other 4xx | No retry | No retry |

- If a retried response has a `Retry-After` header (whole seconds or an HTTP date), the client waits for that time.
- If `Retry-After` is more than 60 seconds, the client does not wait. It raises the error at once.
- The API allows 120 requests each minute for each user. All the tokens of one user share this limit.
- An update sets absolute values, so a second copy of a `PATCH` does no new action.
- `contacts.upsert()` finds the contact by email, so a second copy is safe.
- A second copy of `posts.create()` can make a second post. Thus the client does not retry it after a 5xx, a read timeout or a reset.
- `sign_in_url()` makes a new link for each call, so the client does not retry it after a 5xx, a read timeout or a reset.
- `APIConnectionError.before_send` is `True` for a DNS failure (`socket.gaierror`), a refused connection and a timeout while the request opens and sends. The instance did not get the request, so the client retries every request after these errors.
- Set `max_retries=0` to stop all retries.
- The JS, PHP and Ruby SDKs use the same retry rules.

## Django and FastAPI

The package has no framework code. The examples below show how to connect it.

### Django

Put the settings in `settings.py`:

```python
# settings.py
FEEDBACKPILGRIM_URL = env("FEEDBACKPILGRIM_URL")
FEEDBACKPILGRIM_TOKEN = env("FEEDBACKPILGRIM_TOKEN")
FEEDBACKPILGRIM_IDENTITY_SECRET = env("FEEDBACKPILGRIM_IDENTITY_SECRET")
FEEDBACKPILGRIM_WEBHOOK_SECRET = env("FEEDBACKPILGRIM_WEBHOOK_SECRET")
```

Make one client for the project, for example in `feedback/client.py`:

```python
from django.conf import settings
from feedbackpilgrim import FeedbackPilgrim

feedback = FeedbackPilgrim(settings.FEEDBACKPILGRIM_URL, settings.FEEDBACKPILGRIM_TOKEN)
```

Give the identity hash to the widget with a template tag, for example in `feedback/templatetags/feedbackpilgrim.py`:

```python
from django import template
from django.conf import settings
from feedbackpilgrim import identity_hash

register = template.Library()


@register.simple_tag(takes_context=True)
def pilgrim_user_hash(context) -> str:
    user = context["request"].user
    return identity_hash(user.email, settings.FEEDBACKPILGRIM_IDENTITY_SECRET)
```

```django
{% load feedbackpilgrim %}
<script>
  window.pilgrimUser = {
    email: "{{ request.user.email|escapejs }}",
    user_hash: "{% pilgrim_user_hash %}"
  };
</script>
```

Receive webhooks in a view. Feedback Pilgrim does not send a CSRF token, so the view must be `csrf_exempt`:

```python
from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from feedbackpilgrim import WebhookVerificationError, verify_webhook


@csrf_exempt
@require_POST
def feedbackpilgrim_webhook(request: HttpRequest) -> HttpResponse:
    try:
        event = verify_webhook(
            request.body, request.headers, settings.FEEDBACKPILGRIM_WEBHOOK_SECRET
        )
    except WebhookVerificationError:
        return HttpResponseBadRequest()

    first_time = True
    if event.delivery_id:  # older instances send no delivery ID
        _, first_time = ProcessedDelivery.objects.get_or_create(delivery_id=event.delivery_id)
    if first_time and event.type == "post.completed":
        notify_voters(event.data.id)
    return HttpResponse(status=204)
```

`request.body` is the raw body and `request.headers` is not case-sensitive. `ProcessedDelivery` is a model of your app with a unique `delivery_id` field.

### FastAPI

Make one client when the application starts. Then give it to each route with dependency injection:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from feedbackpilgrim import FeedbackPilgrim


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.feedback = FeedbackPilgrim()  # reads FEEDBACKPILGRIM_URL and FEEDBACKPILGRIM_TOKEN
    yield


app = FastAPI(lifespan=lifespan)


def get_feedback(request: Request) -> FeedbackPilgrim:
    return request.app.state.feedback


Feedback = Annotated[FeedbackPilgrim, Depends(get_feedback)]


@app.post("/feedback")
def send_feedback(title: str, content: str, feedback: Feedback) -> dict[str, int]:
    post = feedback.posts.create(title, content)
    return {"id": post.id}
```

The client is synchronous. Declare a route that calls it with `def`, not `async def`. FastAPI then runs the route in a thread pool, and the event loop does not stop. In an `async def` route, use `await run_in_threadpool(feedback.posts.create, title, content)` from `fastapi.concurrency`.

In a test, replace the dependency with `app.dependency_overrides[get_feedback]`.

Receive webhooks in a route. Read the raw body with `await request.body()`:

```python
import os

from fastapi import HTTPException, Request, Response
from feedbackpilgrim import WebhookVerificationError, verify_webhook

WEBHOOK_SECRET = os.environ["FEEDBACKPILGRIM_WEBHOOK_SECRET"]


@app.post("/hooks/feedbackpilgrim", status_code=204)
async def feedbackpilgrim_webhook(request: Request) -> Response:
    try:
        event = verify_webhook(await request.body(), request.headers, WEBHOOK_SECRET)
    except WebhookVerificationError as error:
        raise HTTPException(status_code=400, detail=error.reason) from error

    first_time = await mark_processed(event.delivery_id) if event.delivery_id else True
    if first_time and event.type == "post.completed":
        await notify_voters(event.data.id)
    return Response(status_code=204)
```

Do not declare the body as a Pydantic model in this route. FastAPI then parses the JSON, and the raw bytes are not available.

## Supported Python versions

The package supports Python 3.10, 3.11, 3.12, 3.13 and 3.14. CI runs the tests, the lint and the type check on each version.

The package has full type hints and a `py.typed` file. `mypy --strict` passes on the package.

## Related projects

- [Feedback Pilgrim](https://github.com/amedina068/feedbackpilgrim): the self-hosted app that this SDK calls. It uses the AGPL-3.0.
- [Documentation](https://feedbackpilgrim.com/docs): the guides for the app and the SDKs. The source is in [feedbackpilgrim-docs](https://github.com/amedina068/feedbackpilgrim-docs).
- [SDK overview](https://feedbackpilgrim.com/docs/sdks/overview): the install steps and the features of each SDK.
- SDKs for other languages: [TypeScript](https://github.com/amedina068/feedbackpilgrim-js), [PHP](https://github.com/amedina068/feedbackpilgrim-php), [Ruby](https://github.com/amedina068/feedbackpilgrim-ruby).

## Community

- [CONTRIBUTING.md](CONTRIBUTING.md): how to set up the code and open a pull request.
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md): the rules for issues, pull requests, and reviews.
- [SECURITY.md](SECURITY.md): how to report a security problem in private.
- [CHANGELOG.md](CHANGELOG.md): the changes in each version.

Report a problem with the SDK in the issues of this repository. Report a problem with the app in the [Feedback Pilgrim issues](https://github.com/amedina068/feedbackpilgrim/issues).

## License

This SDK is available under the [MIT License](LICENSE). You can use it in closed source code. The Feedback Pilgrim app uses the AGPL-3.0. That license does not cover this SDK.
