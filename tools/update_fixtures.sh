#!/usr/bin/env bash
# Refresh the test fixtures from a BrainSTEM server checkout (read-only on the server):
#   tests/fixtures/agent_reference.json  the server's agent reference (pages + JSON documents)
#   tests/fixtures/demo_lab.json         the demo project as the private API returns it
#   tests/fixtures/demo_export.json.gz   the demo project's export (format 2.x), scrubbed of user names
#   tests/fixtures/schemas.json.gz       the public /schemas/ URLs: index, version lists, every published version
#
#   tools/update_fixtures.sh <path-to-brainstem-server> [python-executable]
#
# The server must have the demo project loaded (manage.py generate_demo_project). Never run against a
# production database. Only demo_lab.json and demo_export.json.gz are committed; the reference and the schemas
# stay local (.gitignore). To test against a running server instead, use tools/fetch_fixtures.py.
set -euo pipefail

server="${1:?usage: tools/update_fixtures.sh <path-to-brainstem-server> [python]}"
python="${2:-python}"
repo="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

(cd "$server" && "$python" manage.py export_agent_reference --out "$tmp/reference" >/dev/null)
python3 "$repo/tests/fixtures/bundle_reference.py" "$tmp/reference" "$repo/tests/fixtures/agent_reference.json"
(cd "$server" && FIXTURE_OUT="$repo/tests/fixtures/demo_lab.json" "$python" manage.py shell \
  < "$repo/tests/fixtures/build_demo_fixture.py" | grep '^fixture:')
(cd "$server" && EXPORT_OUT="$tmp/demo_export.json" "$python" manage.py shell \
  < "$repo/tests/fixtures/build_demo_export.py" >/dev/null)
python3 "$repo/tests/fixtures/scrub_export.py" "$tmp/demo_export.json" "$repo/tests/fixtures/demo_export.json.gz"
(cd "$server" && SCHEMAS_OUT="$repo/tests/fixtures/schemas.json.gz" "$python" manage.py shell \
  < "$repo/tests/fixtures/build_schema_fixture.py" | grep '^schemas:')
python3 "$repo/tools/vendor_references.py"
