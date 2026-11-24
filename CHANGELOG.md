# Changelog

All notable changes to this package are in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The package uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - Unreleased

### Added

- The client `FeedbackPilgrim`, with the settings `base_url`, `token`, `timeout`, `max_retries` and `transport`. `FEEDBACKPILGRIM_URL` and `FEEDBACKPILGRIM_TOKEN` are the defaults.
- A transport on `urllib` from the standard library. The package has no dependencies.
- Init: `sign_in_url()` returns a sign-in link for a contact.
- Posts: `list()`, `iter()`, `get()`, `create()` and `update()`.
- Release notes: `list()`, `iter()`, `get()`, `create()` and `update()`.
- Contacts: `list()`, `iter()`, `get()`, `upsert()` and `update()`.
- Testimonials: `list()`, `iter()`, `get()`, `create()`, `update()` and `approve()`.
- Tags: `list()`, `iter()`, `create()`, `update()` and `delete()`.
- `Page`, with the fields of the Laravel paginator and `has_more`.
- Frozen dataclass models with a `raw` field. `Contact.custom_fields` reads the custom fields of a contact in both shapes that the API sends.
- `identity_hash()`, which makes the `user_hash` of the widget exactly like the PHP code of the app.
- `verify_signature()` and `verify_webhook()` for the `X-FeedbackPilgrim-Signature-V2` webhook header, with a 300-second tolerance parameter. `WebhookEvent.delivery_id` gives the delivery ID.
- An error class for each failure, under `FeedbackPilgrimError`.
- Retries for 429, 5xx and connection errors, with exponential backoff, jitter and `Retry-After`.
- Type hints and a `py.typed` file.
- The MIT license: `LICENSE` and `license = "MIT"` in `pyproject.toml`.

### Changed

The package now behaves the same as the JS, PHP and Ruby SDKs. These changes break code that uses the package from git:

- `construct_event()` is now `verify_webhook()`, the same name as in the other SDKs.
- `WebhookEvent.post` is now `WebhookEvent.data`, and `WebhookEvent.raw` is now `WebhookEvent.payload`.
- `verify_webhook()` raises `WebhookVerificationError` with the reason `"payload"` when the body is not a JSON object after a valid signature. Before, it raised the JSON error of Python.
- The signature check makes the header lowercase. An uppercase hex signature is now valid.
- The timestamp header must be ASCII digits only. Before, `int()` accepted a sign, an underscore and digits of other scripts.
- An empty `X-FeedbackPilgrim-Delivery` header gives `delivery_id=None`.
- `sign_in_url()` returns `None` when the instance sends no link. Before, it raised `FeedbackPilgrimError`, and it raised `ValueError` for an empty email before the request.
- `APIConnectionError(request_sent=...)` is now `APIConnectionError(before_send=...)`, with the opposite value and `False` as the default. The default transport sets it only for a DNS failure, a refused connection and a timeout before the read. Before, it also set it for each other `URLError`, for example an unreachable host or a TLS error. The client retries a request that is not idempotent only after a 429 or one of these errors.
- The client waits for `Retry-After` on a retried 5xx, as on a 429.
- `Retry-After` must be whole seconds or an HTTP date. A decimal value is ignored.
