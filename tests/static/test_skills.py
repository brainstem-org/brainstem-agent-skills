"""SKILL.md files follow the Agent Skills specification and stay within size limits."""

import re

import pytest
import yaml

from static_paths import ROOT, skill_dirs

SPEC_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_BODY_LINES = 500


def split_frontmatter(text):
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert match, "SKILL.md must start with YAML frontmatter between --- lines"
    return yaml.safe_load(match.group(1)), match.group(2)


@pytest.mark.parametrize("skill_dir", skill_dirs(), ids=lambda p: p.name)
def test_frontmatter_follows_spec(skill_dir):
    meta, body = split_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    assert set(meta) <= SPEC_KEYS, f"non-spec keys: {set(meta) - SPEC_KEYS}"
    assert meta["name"] == skill_dir.name
    assert len(meta["name"]) <= 64 and NAME_PATTERN.match(meta["name"])
    assert 1 <= len(meta["description"]) <= 1024
    if "compatibility" in meta:
        assert 1 <= len(meta["compatibility"]) <= 500
    if "metadata" in meta:
        assert all(isinstance(k, str) and isinstance(v, str) for k, v in meta["metadata"].items())
    assert len(body.splitlines()) < MAX_BODY_LINES


@pytest.mark.parametrize("skill_dir", skill_dirs(), ids=lambda p: p.name)
def test_skill_starts_with_connection_and_safety(skill_dir):
    _meta, body = split_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    assert "references/connection.md" in body
    assert "references/safety.md" in body


def test_every_skill_is_in_the_manifest():
    import json

    manifest = json.loads((ROOT / "tools" / "skill_manifest.json").read_text(encoding="utf-8"))["skills"]
    assert {p.name for p in skill_dirs()} == set(manifest)
