"""Webhook verification, with the V2 vectors that the app code made (gen-vectors.php)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from feedbackpilgrim import WebhookVerificationError, verify_signature, verify_webhook
from feedbackpilgrim.webhooks import DEFAULT_TOLERANCE, sign

FIXTURES = Path(__file__).parent / "fixtures"
VECTORS: dict[str, Any] = json.loads(
    (FIXTURES / "webhook-signature-vectors.json").read_text("utf-8")
)
LEGACY: dict[str, Any] = json.loads(
    (FIXTURES / "webhook-signature-vectors-legacy.json").read_text("utf-8")
)
SHARED: dict[str, Any] = json.loads((FIXTURES / "webhook-verify-vectors.json").read_text("utf-8"))
SECRET: str = VECTORS["secret"]
CASES: list[dict[str, Any]] = VECTORS["cases"]
VALID = [case for case in CASES if case["valid"]]
INVALID = [case for case in CASES if not case["valid"]]

DELIVERY_ID = "6f1c2d3e-0000-4000-8000-000000000000"


def headers_of(case: dict[str, Any]) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-FeedbackPilgrim-Event": case["event"],
        "X-FeedbackPilgrim-Delivery": DELIVERY_ID,
        "X-FeedbackPilgrim-Timestamp": case["timestamp"],
        "X-FeedbackPilgrim-Signature-V2": case["signature"],
    }


def now_of(case: dict[str, Any]) -> int:
    return int(case["timestamp"])


def test_the_vectors_have_valid_and_invalid_cases() -> None:
    assert len(VALID) == 3
    assert len(INVALID) == 4
    assert VECTORS["tolerance_seconds"] == DEFAULT_TOLERANCE
    assert VECTORS["signature_header"] == "X-FeedbackPilgrim-Signature-V2"


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_verify_signature_matches_the_vector(case: dict[str, Any]) -> None:
    body = case["body"].encode("utf-8")
    result = verify_signature(body, case["signature"], case["timestamp"], SECRET, now=now_of(case))
    assert result is case["valid"]


@pytest.mark.parametrize("case", VALID, ids=[case["name"] for case in VALID])
def test_sign_matches_the_app(case: dict[str, Any]) -> None:
    assert sign(case["timestamp"], case["body"], SECRET) == case["signature"]


@pytest.mark.parametrize("case", VALID, ids=[case["name"] for case in VALID])
def test_verify_webhook_returns_the_event_and_the_delivery_id(case: dict[str, Any]) -> None:
    event = verify_webhook(case["body"], headers_of(case), SECRET, now=now_of(case))
    data = json.loads(case["body"])["data"]
    assert event.type == case["event"]
    assert event.delivery_id == DELIVERY_ID
    assert event.timestamp == int(case["timestamp"])
    assert event.data.id == data["id"]
    assert event.data.title == data["title"]
    assert event.data.contact_id == data["contact_id"]
    assert event.payload == json.loads(case["body"])


@pytest.mark.parametrize("case", INVALID, ids=[case["name"] for case in INVALID])
def test_verify_webhook_rejects_the_invalid_vector(case: dict[str, Any]) -> None:
    with pytest.raises(WebhookVerificationError) as caught:
        verify_webhook(case["body"], headers_of(case), SECRET, now=now_of(case))
    assert caught.value.reason == "signature"


@pytest.mark.parametrize("case", SHARED["cases"], ids=[case["name"] for case in SHARED["cases"]])
def test_verify_webhook_matches_the_shared_vector(case: dict[str, Any]) -> None:
    expect = case["expect"]
    if not expect["valid"]:
        with pytest.raises(WebhookVerificationError) as caught:
            verify_webhook(case["body"], case["headers"], SHARED["secret"], now=case["now"])
        assert caught.value.reason == expect["reason"]
        return
    event = verify_webhook(case["body"], case["headers"], SHARED["secret"], now=case["now"])
    assert event.type == expect["type"]
    assert event.timestamp == expect["timestamp"]
    assert event.delivery_id == expect["delivery_id"]
    assert event.data.id == expect["data_id"]
    assert event.payload == json.loads(case["body"])


def test_the_stage_of_the_event() -> None:
    case = next(case for case in VALID if case["event"] == "post.completed")
    event = verify_webhook(case["body"], headers_of(case), SECRET, now=now_of(case))
    assert event.data.stage is not None
    assert (event.data.stage.id, event.data.stage.name, event.data.stage.type) == (
        6,
        "Shipped",
        "complete",
    )
    created = VALID[0]
    assert (
        verify_webhook(created["body"], headers_of(created), SECRET, now=now_of(created)).data.stage
        is None
    )


def test_a_body_encoded_again_does_not_match() -> None:
    case = next(case for case in VALID if "\\/" in case["body"])
    event = verify_webhook(case["body"], headers_of(case), SECRET, now=now_of(case))
    assert event.data.title == "Export to CSV/Excel"
    assert event.data.content == "Café menus need it."
    encoded_again = json.dumps(event.payload, ensure_ascii=False, separators=(",", ":"))
    assert not verify_signature(
        encoded_again, case["signature"], case["timestamp"], SECRET, now=now_of(case)
    )


def test_the_legacy_signature_is_not_accepted() -> None:
    # The deprecated header signs the body only. It does not pass as V2.
    legacy = LEGACY["cases"][0]
    timestamp = "1763456789"
    assert not verify_signature(
        legacy["body"], legacy["signature"], timestamp, SECRET, now=int(timestamp)
    )


def test_header_names_are_not_case_sensitive() -> None:
    case = VALID[0]
    headers = {name.lower(): value for name, value in headers_of(case).items()}
    event = verify_webhook(case["body"], headers, SECRET, now=now_of(case))
    assert event.delivery_id == DELIVERY_ID


def test_a_missing_delivery_header_gives_none() -> None:
    case = VALID[0]
    headers = {k: v for k, v in headers_of(case).items() if k != "X-FeedbackPilgrim-Delivery"}
    assert verify_webhook(case["body"], headers, SECRET, now=now_of(case)).delivery_id is None


def test_a_missing_signature() -> None:
    case = VALID[0]
    headers = {k: v for k, v in headers_of(case).items() if "Signature" not in k}
    with pytest.raises(WebhookVerificationError) as caught:
        verify_webhook(case["body"], headers, SECRET, now=now_of(case))
    assert caught.value.reason == "signature"
    assert not verify_signature(case["body"], None, case["timestamp"], SECRET, now=now_of(case))


def test_a_missing_timestamp() -> None:
    case = VALID[0]
    headers = {k: v for k, v in headers_of(case).items() if "Timestamp" not in k}
    with pytest.raises(WebhookVerificationError) as caught:
        verify_webhook(case["body"], headers, SECRET, now=now_of(case))
    assert caught.value.reason == "timestamp"
    assert not verify_signature(case["body"], case["signature"], None, SECRET, now=now_of(case))


def test_a_timestamp_that_is_not_a_number() -> None:
    body = '{"event":"post.created","data":{"id":1}}'
    headers = {
        "X-FeedbackPilgrim-Timestamp": "yesterday",
        "X-FeedbackPilgrim-Signature-V2": sign("yesterday", body, SECRET),
    }
    with pytest.raises(WebhookVerificationError) as caught:
        verify_webhook(body, headers, SECRET)
    assert caught.value.reason == "timestamp"


def test_an_uppercase_signature_is_valid() -> None:
    case = VALID[0]
    signature = f" {case['signature'].upper()} "
    assert verify_signature(case["body"], signature, case["timestamp"], SECRET, now=now_of(case))


def test_a_timestamp_with_unicode_digits_is_rejected() -> None:
    case = VALID[0]
    timestamp = "\u0661" + case["timestamp"][1:]
    signature = sign(timestamp, case["body"], SECRET)
    assert not verify_signature(case["body"], signature, timestamp, SECRET, now=now_of(case))


def test_a_signature_with_non_ascii_characters_is_rejected() -> None:
    case = VALID[0]
    assert not verify_signature(case["body"], "é", case["timestamp"], SECRET, now=now_of(case))


def test_the_tolerance_is_300_seconds_by_default_and_inclusive() -> None:
    case = VALID[0]
    signed_at = now_of(case)
    for now in (signed_at + 300, signed_at - 300):
        assert verify_signature(case["body"], case["signature"], case["timestamp"], SECRET, now=now)
    for now in (signed_at + 301, signed_at - 301):
        assert not verify_signature(
            case["body"], case["signature"], case["timestamp"], SECRET, now=now
        )


def test_an_old_timestamp_raises_with_the_timestamp_reason() -> None:
    case = VALID[0]
    with pytest.raises(WebhookVerificationError) as caught:
        verify_webhook(case["body"], headers_of(case), SECRET, now=now_of(case) + 301)
    assert caught.value.reason == "timestamp"


def test_the_tolerance_is_a_parameter() -> None:
    case = VALID[0]
    later = now_of(case) + 600
    args = (case["body"], case["signature"], case["timestamp"], SECRET)
    assert verify_signature(*args, tolerance=600, now=later)
    assert not verify_signature(*args, tolerance=599, now=later)


def test_default_now_is_the_current_time() -> None:
    body = '{"event":"post.created","data":{"id":1,"title":"x","stage":null}}'
    timestamp = str(int(time.time()))
    assert verify_signature(body, sign(timestamp, body, SECRET), timestamp, SECRET)


def test_an_empty_secret_raises() -> None:
    with pytest.raises(ValueError, match="secret"):
        verify_signature("{}", "x", "1", "")
