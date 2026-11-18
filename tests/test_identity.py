"""The identity hash, with the vectors that the app code made (gen-vectors.php)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from feedbackpilgrim import identity_hash
from feedbackpilgrim.identity import normalize_email

VECTORS: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "identity-hash-vectors.json").read_text("utf-8")
)
SECRET: str = VECTORS["identity_secret"]
CASES: list[dict[str, Any]] = VECTORS["cases"]


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_identity_hash_matches_the_app(case: dict[str, Any]) -> None:
    assert identity_hash(case["email"], SECRET) == case["user_hash"]


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_normalize_email_matches_php(case: dict[str, Any]) -> None:
    assert normalize_email(case["email"]) == case["normalized_email"]


def test_only_php_trim_characters_are_removed() -> None:
    # PHP trim() removes NUL and vertical tab. It keeps a no-break space and a form feed.
    assert normalize_email("\0\x0bJane@Example.com\x0b\0") == "jane@example.com"
    assert normalize_email("\u00a0jane@example.com\f") == "\u00a0jane@example.com\f"


def test_only_ascii_letters_change_case() -> None:
    assert normalize_email("ÀÉÎ@EXAMPLE.COM") == "ÀÉÎ@example.com"
    assert normalize_email("İ@example.com") == "İ@example.com"


def test_the_secret_is_required() -> None:
    with pytest.raises(ValueError, match="identity_secret"):
        identity_hash("jane@example.com", "")
