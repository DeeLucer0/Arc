"""extract_json — robust recovery of JSON from fenced, bare, or prose-wrapped LLM output.

Regression coverage for the reflection/extraction silent-failure: a model that
prefaces its JSON with prose used to make json.loads() fail, returning None and
(in the policy engine) silently writing no bullets.
"""

from __future__ import annotations

import json

import pytest

from arcagent.utils.io import extract_json

_DELTA = {"additions": ["lesson a"], "updates": [], "rewrites": []}


def test_bare_json_object() -> None:
    assert json.loads(extract_json(json.dumps(_DELTA))) == _DELTA


def test_fenced_json() -> None:
    raw = f"```json\n{json.dumps(_DELTA)}\n```"
    assert json.loads(extract_json(raw)) == _DELTA


def test_prose_preamble_then_json() -> None:
    """The reported eval failure mode: prose before the JSON, no fence."""
    raw = f"Here is my evaluation of the agent.\n\n{json.dumps(_DELTA)}"
    assert json.loads(extract_json(raw)) == _DELTA


def test_prose_around_json() -> None:
    raw = f"Sure! {json.dumps(_DELTA)} Hope that helps."
    assert json.loads(extract_json(raw)) == _DELTA


def test_braces_inside_string_values_dont_unbalance() -> None:
    payload = {"additions": ["use {curly} braces carefully"], "updates": [], "rewrites": []}
    raw = f"Analysis complete: {json.dumps(payload)}"
    assert json.loads(extract_json(raw)) == payload


def test_json_array_in_prose() -> None:
    raw = 'The items are: ["a", "b"] — done.'
    assert json.loads(extract_json(raw)) == ["a", "b"]


def test_empty_and_none() -> None:
    assert extract_json(None) == ""
    assert extract_json("") == ""


def test_plain_prose_no_json_returned_as_is() -> None:
    # No JSON at all → return stripped text; caller's json.loads will raise,
    # which the caller already handles (now with a log line).
    assert extract_json("  no json here  ") == "no json here"
    with pytest.raises(json.JSONDecodeError):
        json.loads(extract_json("no json here"))
