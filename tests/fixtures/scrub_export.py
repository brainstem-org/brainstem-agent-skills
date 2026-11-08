#!/usr/bin/env python3
"""Make a server project export safe to keep as a test fixture.

    python tests/fixtures/scrub_export.py <export.json> tests/fixtures/demo_export.json.gz

- user records get placeholder names (the export holds names only, no email addresses);
- records the demo dataset does not own and that are not catalog entries (publications, journals) are
  removed, together with references to them;
- counts in export_info are recomputed.
"""

import gzip
import json
import sys
from pathlib import Path

REMOVE_LABELS = ("dissemination.publication", "dissemination.journal")


def main(source, target):
    data = json.loads(Path(source).read_text(encoding="utf-8"))
    records = data["records"]
    for index, user in enumerate(records.get("users.user", []), start=1):
        user["fields"] = {"first_name": "Demo", "last_name": f"User {index}"}
    removed = set()
    for label in REMOVE_LABELS:
        removed |= {str(r["pk"]) for r in records.get(label, [])}
        records[label] = []
    for rows in records.values():
        for row in rows:
            for key, value in list(row["fields"].items()):
                if isinstance(value, list) and any(str(v) in removed for v in value):
                    row["fields"][key] = [v for v in value if str(v) not in removed]
                elif isinstance(value, str) and value in removed:
                    row["fields"][key] = None
    info = data["export_info"]
    info["counts"] = {label: len(rows) for label, rows in records.items()}
    info["record_count"] = sum(info["counts"].values())
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
    Path(target).write_bytes(gzip.compress(payload, mtime=0))
    print(f"scrubbed export: {info['record_count']} records, format {info['format_version']}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
