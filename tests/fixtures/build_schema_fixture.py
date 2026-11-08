"""Capture the server's public schema URLs for tests/fixtures/schemas.json.gz.

Run inside the server's Django shell (no running server needed; uses Django's test client):

    cd <brainstem server> && SCHEMAS_OUT=<path>.json.gz python manage.py shell < build_schema_fixture.py

Holds the /schemas/ index, each type's version list (/schemas/<Family>/<Type>/) and every published version
of each schema (/schemas/<Family>/<Type>/<version>.json), so the mock API can serve them offline.
"""

import gzip
import json
import os

from django.conf import settings
from django.test import Client

# The per-IP limit on /schemas/ also counts the test client; this runs in a local shell, never on a live server.
settings.RATELIMIT_ENABLE = False
client = Client(HTTP_HOST="localhost")


def get(path):
    response = client.get(path)
    if response.status_code != 200:
        raise SystemExit(f"{path}: HTTP {response.status_code}")
    return json.loads(response.content)


index = get("/schemas/")
types = {}
for family, names in index["families"].items():
    for name in names:
        listing = get(f"/schemas/{family}/{name}/")
        types[f"{family}/{name}"] = {
            "listing": listing,
            "versions": {version: get(f"/schemas/{family}/{name}/{version}.json") for version in listing["versions"]},
        }
payload = json.dumps({"index": index, "types": types}, ensure_ascii=False, sort_keys=True).encode("utf-8")
with open(os.environ["SCHEMAS_OUT"], "wb") as handle:
    handle.write(gzip.compress(payload, mtime=0))
print(f"schemas: {len(types)} types, {sum(len(t['versions']) for t in types.values())} versions")
