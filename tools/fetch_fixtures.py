#!/usr/bin/env python3
"""Download a BrainSTEM server's public agent reference and schema URLs for the tests.

    python3 tools/fetch_fixtures.py https://www.brainstem.org
    python3 tools/fetch_fixtures.py http://127.0.0.1:8000

Writes, in the format the mock API and the static tests read:

    tests/fixtures/agent_reference.json  every page and JSON document under /reference/
    tests/fixtures/schemas.json.gz       the /schemas/ index, each type's version list and every published version

These files are not committed: the agent reference and the schemas belong to BrainSTEM and may be read and
cached to work with a server, but not redistributed (see the server's `license.md`). Fetch them before
running the tests. Standard library only; needs no token.
"""

import gzip
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
WORKERS = 4
HEADERS = {"User-Agent": "brainstem-agent-skills-fixtures", "Accept-Encoding": "gzip"}


def fetch(url, attempts=8):
    for attempt in range(attempts):
        delay = min(2 ** attempt, 60)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as response:
                body = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return body
        except urllib.error.HTTPError as error:
            retryable = error.code == 429 or error.code >= 500
            if not retryable or attempt == attempts - 1:
                raise SystemExit(f"{url}: HTTP {error.code}")
            retry_after = error.headers.get("Retry-After", "")
            if retry_after.isdigit():
                delay = min(int(retry_after), 120)
        except urllib.error.URLError as error:
            if attempt == attempts - 1:
                raise SystemExit(f"{url}: {error.reason}")
        time.sleep(delay)


def fetch_json(url):
    return json.loads(fetch(url))


def fetch_reference(base, pool):
    manifest = fetch_json(f"{base}/reference/data/manifest.json")
    names = [name for name in manifest["documents"] if name != "manifest.json"]
    documents = dict(zip((Path(n).stem for n in names),
                         pool.map(lambda n: fetch_json(f"{base}/reference/data/{n}"), names)))
    documents["manifest"] = manifest
    paths = sorted({page["path"] if isinstance(page, dict) else page for page in manifest["pages"]} | {"index.md"})
    texts = pool.map(lambda p: fetch(f"{base}/reference/{p}").decode("utf-8"), paths)
    return {"documents": documents, "pages": dict(zip(paths, texts))}


def fetch_schemas(base, pool):
    index = fetch_json(f"{base}/schemas/")
    names = [f"{family}/{name}" for family, members in index["families"].items() for name in members]
    listings = dict(zip(names, pool.map(lambda n: fetch_json(f"{base}/schemas/{n}/"), names)))
    wanted = [(n, v) for n in names for v in listings[n]["versions"]]
    bodies = pool.map(lambda nv: fetch_json(f"{base}/schemas/{nv[0]}/{nv[1]}.json"), wanted)
    types = {n: {"listing": listings[n], "versions": {}} for n in names}
    for (name, version), body in zip(wanted, bodies):
        types[name]["versions"][version] = body
    return {"index": index, "types": types}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__)
        return 2
    base = argv[0].rstrip("/")
    with ThreadPoolExecutor(WORKERS) as pool:
        reference = fetch_reference(base, pool)
        schemas = fetch_schemas(base, pool)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / "agent_reference.json").write_text(
        json.dumps(reference, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    payload = json.dumps(schemas, ensure_ascii=False, sort_keys=True).encode("utf-8")
    (FIXTURES / "schemas.json.gz").write_bytes(gzip.compress(payload, mtime=0))
    manifest = reference["documents"]["manifest"]
    versions = sum(len(t["versions"]) for t in schemas["types"].values())
    print(f"reference: {len(reference['pages'])} pages, format {manifest['format_version']}, "
          f"data model {manifest['data_model']}, server {manifest.get('server_commit') or 'unknown'}")
    print(f"schemas: {len(schemas['types'])} types, {versions} versions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
