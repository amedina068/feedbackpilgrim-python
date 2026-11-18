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
- `verify_signature()` and `construct_event()` for the `X-FeedbackPilgrim-Signature-V2` webhook header, with a 300-second tolerance parameter. `WebhookEvent.delivery_id` gives the delivery ID.
- An error class for each failure, under `FeedbackPilgrimError`.
- Retries for 429, 5xx and connection errors, with exponential backoff, jitter and `Retry-After`.
- Type hints and a `py.typed` file.
