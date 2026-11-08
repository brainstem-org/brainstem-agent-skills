"""Skills cite only pages that exist in the server's agent reference, and their vendored files are current.

The reference itself lives on the server; tests/fixtures/agent_reference.json is a local copy of it,
downloaded with tools/fetch_fixtures.py (or built by tools/update_fixtures.sh) and not committed. Fetching it
and running these tests shows whether the skills still match that server.
"""

import json
import re
import subprocess
import sys

import pytest

from static_paths import ROOT, skill_dirs

LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
API_PATH = re.compile(r"/api/(?:private|public)/([a-z_]+)/([a-z_]+)/")
LOCAL_REFERENCE = re.compile(r"`(references/[^`*<>]+\.md)`")
# A backticked page path without the references/ prefix is a page of the agent reference.
REFERENCE_PAGE = re.compile(r"`((?:[a-z]+/)*[A-Za-z0-9_.-]+\.md)`")
PLACEHOLDER = re.compile(r"[<>]")

REFERENCE_FIXTURE = ROOT / "tests" / "fixtures" / "agent_reference.json"
if not REFERENCE_FIXTURE.exists():
    pytest.exit("missing tests/fixtures/agent_reference.json: run `python3 tools/fetch_fixtures.py <server url>` "
                "(for example https://www.brainstem.org) first", returncode=4)
BUNDLE = json.loads(REFERENCE_FIXTURE.read_text(encoding="utf-8"))
PAGES = set(BUNDLE["pages"])
MANIFEST = BUNDLE["documents"]["manifest"]


def markdown_files():
    files = sorted((ROOT / "references").glob("*.md"))
    files += [skill / "SKILL.md" for skill in skill_dirs()]
    return files


def test_vendored_copies_match_references():
    result = subprocess.run([sys.executable, str(ROOT / "tools" / "vendor_references.py"), "--check"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("path", markdown_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_resolve(path):
    for target in LINK.findall(path.read_text(encoding="utf-8")):
        if re.match(r"^[a-z]+:", target) or PLACEHOLDER.search(target):
            continue
        assert (path.parent / target).resolve().exists(), f"{path.relative_to(ROOT)} links to missing {target}"


@pytest.mark.parametrize("skill_dir", skill_dirs(), ids=lambda p: p.name)
def test_skill_mentions_only_vendored_files(skill_dir):
    for reference in LOCAL_REFERENCE.findall((skill_dir / "SKILL.md").read_text(encoding="utf-8")):
        assert (skill_dir / reference).exists(), f"{skill_dir.name} mentions {reference} but does not vendor it"


@pytest.mark.parametrize("path", markdown_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_cited_reference_pages_exist_on_the_server(path):
    for page in REFERENCE_PAGE.findall(path.read_text(encoding="utf-8")):
        if page.startswith("references/") or PLACEHOLDER.search(page):
            continue
        assert page in PAGES, f"{path.relative_to(ROOT)} cites `{page}`, which the server reference does not serve"


def test_supported_versions_match_the_server_reference():
    text = (ROOT / "references" / "connection.md").read_text(encoding="utf-8")
    major = MANIFEST["format_version"].split(".")[0]
    assert f"`format_version` **{major}.x**" in text
    assert f"`data_model`\n   **`{MANIFEST['data_model']}`**" in text or f"**`{MANIFEST['data_model']}`**" in text


def test_hand_written_api_paths_exist():
    known = {(r["app"], r["resource"]) for r in BUNDLE["documents"]["api_surface"]["resources"]}
    for path in markdown_files():
        for app, resource in API_PATH.findall(path.read_text(encoding="utf-8")):
            assert (app, resource) in known, f"{path.relative_to(ROOT)} names unknown endpoint {app}/{resource}"
