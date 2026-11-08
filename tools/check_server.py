#!/usr/bin/env python3
"""Check that the skills match a live BrainSTEM server's agent reference.

    python tools/check_server.py https://www.brainstem.org

Reads data/manifest.json from the server's public agent reference (/reference/) and checks that its format
and data model are the ones references/connection.md declares as supported, and that every reference page
cited by a skill or behavior file is served. Exit 1 on any mismatch. Standard library only; needs no token.
"""

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE_PAGE = re.compile(r"`((?:[a-z]+/)*[A-Za-z0-9_.-]+\.md)`")


def cited_pages():
    files = sorted((ROOT / "references").glob("*.md")) + sorted((ROOT / "skills").glob("*/SKILL.md"))
    pages = {}
    for path in files:
        for page in REFERENCE_PAGE.findall(path.read_text(encoding="utf-8")):
            if not page.startswith("references/") and "<" not in page:
                pages.setdefault(page, path.relative_to(ROOT).as_posix())
    return pages


def supported():
    text = (ROOT / "references" / "connection.md").read_text(encoding="utf-8")
    major = re.search(r"`format_version` \*\*(\d+)\.x\*\*", text).group(1)
    data_model = re.search(r"`data_model`\s+\*\*`([^`]+)`\*\*", text).group(1)
    return major, data_model


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__)
        return 2
    url = argv[0].rstrip("/") + "/reference/data/manifest.json"
    request = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            manifest = json.loads(response.read())
    except urllib.error.HTTPError as error:
        print(f"{url}: HTTP {error.code}")
        return 1
    served = {page["path"] if isinstance(page, dict) else page for page in manifest.get("pages", [])}
    major, data_model = supported()
    problems = []
    if manifest["format_version"].split(".")[0] != major:
        problems.append(f"format_version {manifest['format_version']}, skills support {major}.x")
    if manifest["data_model"] != data_model:
        problems.append(f"data_model {manifest['data_model']}, skills support {data_model}")
    for page, cited_in in sorted(cited_pages().items()):
        if page not in served:
            problems.append(f"{cited_in} cites {page}, which the server does not serve")
    for problem in problems:
        print(problem)
    print(f"server {manifest.get('server_commit', '')[:12]}: {'OK' if not problems else f'{len(problems)} problem(s)'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
