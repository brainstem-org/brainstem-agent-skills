"""The mock API accepts and rejects the same queries as a real BrainSTEM server.

Compares status codes and error messages on the public portal, so no token is needed:

    BRAINSTEM_CONTRACT_URL=http://127.0.0.1:8000 python -m pytest tests/contract -q

Skipped when BRAINSTEM_CONTRACT_URL is not set.
"""

import json
import os
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "mock_api"))
from server import serve  # noqa: E402

REAL = os.environ.get("BRAINSTEM_CONTRACT_URL")
U = "11111111-1111-1111-1111-111111111111"

QUERIES = [
    f"/api/public/modules/procedure/?filter{{subject}}={U}",
    f"/api/public/modules/procedure/?filter{{subject.id}}={U}",
    f"/api/public/modules/procedure/?filter{{target_regions.in}}={U}",
    "/api/public/modules/procedure/?filter{target_regions.acronym}=CA1",
    f"/api/public/modules/dataacquisition/?filter{{interfaces.in}}={U}&filter{{type.in}}=ExtracellularEphys",
    "/api/public/modules/dataacquisition/?filter{details.sr}=20000",
    f"/api/public/stem/session/?filter{{subjects.in}}={U}",
    f"/api/public/stem/session/?filter{{subjects.species}}={U}",
    f"/api/public/stem/session/?filter{{specimen_sets.target_regions}}={U}",
    f"/api/public/stem/specimen/?filter{{specimen_set.subject}}={U}",
    f"/api/public/modules/materialusage/?filter{{experimental_interface.in}}={U}",
    "/api/public/modules/procedure/?filter{subject}=not-a-uuid",
    "/api/public/stem/session/?filter{nonexistent}=1",
    "/api/public/modules/experimentalinterface/?filter{type}=SiliconProbe",
    f"/api/public/modules/procedure/?filter{{target_regions.acronym}}=CA1",
    f"/api/public/modules/dataacquisition/?filter{{interfaces.target_regions}}={U}",
    f"/api/public/modules/materialusage/?filter{{consumable_stock.id}}={U}",
    "/api/public/stem/session/?filter{tags.name}=pilot",
    "/api/public/stem/session/?limit=10&offset=20",
    "/api/public/stem/session/?limit=10&offset=5",
    "/api/public/stem/session/?per_page=0",
]


def fetch(base, path):
    try:
        with urllib.request.urlopen(base + path + "&format=json", timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null")


@pytest.fixture(scope="module")
def mock_base():
    server, _store = serve(ROOT / "tests" / "fixtures" / "demo_lab.json", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.mark.skipif(not REAL, reason="set BRAINSTEM_CONTRACT_URL to compare with a real server")
@pytest.mark.parametrize("path", QUERIES)
def test_mock_matches_real_server(mock_base, path):
    real_status, real_body = fetch(REAL.rstrip("/"), path)
    mock_status, mock_body = fetch(mock_base, path)
    assert mock_status == real_status, (real_body, mock_body)
    if real_status == 400:
        assert mock_body == real_body
    if real_status == 200 and isinstance(real_body, dict) and "meta" in real_body:
        assert mock_body["meta"]["per_page"] == real_body["meta"]["per_page"]
        assert mock_body["meta"]["page"] == real_body["meta"]["page"]


PUBLIC_URLS = [
    "/reference/index.md",
    "/reference/rules.md",
    "/reference/data/manifest.json",
    "/schemas/",
    "/schemas/Consumable/AdhesiveCement/",
    "/schemas/Consumable/AdhesiveCement.json",
    "/schemas/Procedure/VirusInjection.json",
]


def fetch_raw(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


@pytest.mark.skipif(not REAL, reason="set BRAINSTEM_CONTRACT_URL to compare with a real server")
@pytest.mark.parametrize("path", PUBLIC_URLS)
def test_public_urls_match_real_server(mock_base, path):
    """The fixtures are exports of the server: reference pages and schemas must be identical."""
    real_status, real_body = fetch_raw(REAL.rstrip("/"), path)
    mock_status, mock_body = fetch_raw(mock_base, path)
    assert mock_status == real_status == 200
    if path.endswith(".json") or path.endswith("/"):
        assert json.loads(mock_body) == json.loads(real_body)
    else:
        assert mock_body == real_body
