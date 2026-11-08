#!/usr/bin/env python3
"""Pack the output of `manage.py export_agent_reference --out <dir>` into one JSON fixture.

    python tests/fixtures/bundle_reference.py <export dir> tests/fixtures/agent_reference.json

The bundle holds every JSON document and every Markdown page, so the mock API can serve the reference
exactly as the server does and tests stay offline.
"""

import json
import sys
from pathlib import Path


def main(source, target):
    source = Path(source)
    bundle = {
        "documents": {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(source.glob("*.json"))},
        "pages": {
            p.relative_to(source / "pages").as_posix(): p.read_text(encoding="utf-8")
            for p in sorted((source / "pages").rglob("*")) if p.is_file()
        },
    }
    Path(target).write_text(json.dumps(bundle, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    manifest = bundle["documents"]["manifest"]
    print(f"bundled {len(bundle['pages'])} pages, format {manifest['format_version']}, "
          f"data model {manifest['data_model']}, server {manifest['server_commit'][:12]}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
