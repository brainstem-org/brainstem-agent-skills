"""The change-plan illustration in references/write-protocol.md names only resources, fields and type
codes that exist in the server's agent reference, so it cannot drift silently."""

import re
import sys

import yaml

from static_paths import ROOT

sys.path.insert(0, str(ROOT / "tests" / "mock_api"))
from server import Store  # noqa: E402


def _change_plan():
    text = (ROOT / "references" / "write-protocol.md").read_text(encoding="utf-8")
    match = re.search(r"```yaml\n(.*?)```", text, re.S)
    assert match, "write-protocol.md has no yaml change plan"
    return yaml.safe_load(match.group(1))["change_plan"]


def _writable_fields(store, resource):
    names = set(store.fields[resource])
    names |= {f["name"] for f in store.resources[resource].get("form_only_fields", [])}
    return names


def test_example_operations_name_real_resources_and_fields():
    store = Store(ROOT / "tests" / "fixtures" / "demo_lab.json")
    plan = _change_plan()
    assert plan["operations"], "the illustration has no operations"
    for operation in plan["operations"]:
        resource = operation["resource"]
        assert resource in store.resources, f"unknown resource {resource}"
        allowed = _writable_fields(store, resource)
        for name in operation["payload"]:
            assert name in allowed, f"{resource} has no writable field {name}"
        if "request" in operation:
            method, path = operation["request"].split(" ", 1)
            assert method in {"POST", "PATCH", "DELETE"}
            model = store.resources[resource]["model"]
            app = model.split(".")[0]
            assert path == f"/api/private/{app}/{resource}/", path


def test_example_type_codes_exist():
    store = Store(ROOT / "tests" / "fixtures" / "demo_lab.json")
    plan = _change_plan()
    for operation in plan["operations"]:
        type_code = operation["payload"].get("type")
        if type_code is None:
            continue
        known = {type_name for _family, type_name in store.schemas}
        assert type_code in known, f"type {type_code} is in no schema family"
