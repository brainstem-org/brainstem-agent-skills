"""Example payloads are accepted by the mock API built from the snapshot (fields, required, schemas)."""

import json
import sys

import pytest

from static_paths import ROOT

sys.path.insert(0, str(ROOT / "tests" / "mock_api"))
from server import ApiError, Store  # noqa: E402

PAYLOADS = sorted((ROOT / "examples" / "payloads").glob("*.json"))


@pytest.mark.parametrize("path", PAYLOADS, ids=lambda p: p.name)
def test_payload_is_valid(path):
    example = json.loads(path.read_text(encoding="utf-8"))
    store = Store(ROOT / "tests" / "fixtures" / "demo_lab.json")
    fields = store.fields[example["resource"]]
    for name in example["body"]:
        assert name in fields or name in {f["name"] for f in store.resources[example["resource"]].get("form_only_fields", [])}, name
        if name in fields:
            assert fields[name]["write"] not in ("read_only", "not_in_form"), f"{name} is not writable"
    try:
        status, _ = store.write(example["resource"], example.get("id"), example["body"], partial=example["method"] == "PATCH")
    except ApiError as error:
        pytest.fail(f"{path.name} rejected: {error.body}")
    assert status in (200, 201)


def test_examples_readme_mentions_every_payload():
    text = (ROOT / "examples" / "README.md").read_text(encoding="utf-8")
    for path in PAYLOADS:
        assert f"payloads/{path.name}" in text
