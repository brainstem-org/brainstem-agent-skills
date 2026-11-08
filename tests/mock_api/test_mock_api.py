"""The mock API behaves like the real dynamic-rest API on the points the skills rely on."""

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from server import Store, serve

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "demo_lab.json"


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    log = tmp_path_factory.mktemp("mock") / "requests.jsonl"
    server, store = serve(FIXTURE, 0, str(log))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def call(method, path, token="contributor-token", body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(base + path, data=data, method=method)
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        if data:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request) as response:
                raw = response.read()
                return response.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as error:
            raw = error.read()
            return error.code, (json.loads(raw) if raw else None)

    def raw(path, token="contributor-token"):
        request = urllib.request.Request(base + path)
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, response.headers["Content-Type"], response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            return error.code, error.headers["Content-Type"], error.read().decode("utf-8")

    call.store = store
    call.log = log
    call.raw = raw
    call.base = base + "/"
    yield call
    server.shutdown()


def first(api, resource, key):
    status, body = api("GET", f"/api/private/{api.store.resources[resource]['app']}/{resource}/?per_page=1")
    assert status == 200
    return body[key][0]


def test_list_shape_and_paging(api):
    status, body = api("GET", "/api/private/stem/session/?per_page=10&page=2&limit=3")
    assert status == 200
    assert len(body["sessions"]) == 10
    assert body["meta"]["page"] == 2 and body["meta"]["total_results"] == 57


def test_non_nestable_traversal_is_rejected(api):
    usage = next(u for u in api.store.records["materialusage"].values() if u.get("consumable_stock"))
    stock = usage["consumable_stock"]
    status, body = api("GET", f"/api/private/modules/materialusage/?filter{{consumable_stock.id}}={stock}")
    assert status == 400 and body == ["Invalid nested filter field: consumable_stock"]
    status, body = api("GET", f"/api/private/modules/materialusage/?filter{{consumable_stock}}={stock}")
    assert status == 200 and body["materialusages"]
    assert all(u["consumable_stock"] == stock for u in body["materialusages"])


def test_module_relations_are_nestable(api):
    procedure = first(api, "procedure", "procedures")
    status, body = api("GET", f"/api/private/modules/procedure/?filter{{subject.id}}={procedure['subject']}")
    assert status == 200 and procedure["id"] in [p["id"] for p in body["procedures"]]


def test_nestable_traversal_and_in(api):
    session = first(api, "session", "sessions")
    subject = session["subjects"][0]
    status, body = api("GET", f"/api/private/stem/session/?filter{{subjects.in}}={subject}")
    assert status == 200 and session["id"] in [s["id"] for s in body["sessions"]]
    species = api.store.records["subject"][subject]["species"]
    status, body = api("GET", f"/api/private/stem/session/?filter{{subjects.species}}={species}")
    assert status == 200 and session["id"] in [s["id"] for s in body["sessions"]]


def test_invalid_uuid_and_unknown_field(api):
    status, body = api("GET", "/api/private/modules/procedure/?filter{subject}=abc")
    assert status == 400 and "is not a valid UUID" in body[0]
    status, body = api("GET", "/api/private/modules/procedure/?filter{nope}=1")
    assert status == 400 and body[0].startswith("Invalid filter field: nope. Choices are: ")


def test_include_sideloads_only_nestable(api):
    status, body = api("GET", "/api/private/stem/session/?per_page=2&include[]=subjects.*")
    assert status == 200 and body["subjects"]
    status, body = api("GET", "/api/private/modules/materialusage/?per_page=2&include[]=consumable.*")
    assert status == 200 and set(body) == {"materialusages", "meta"}


def test_paging_alias_cap_and_errors(api):
    status, body = api("GET", "/api/private/stem/session/?limit=10&offset=20")
    assert status == 200 and body["meta"]["page"] == 3 and body["meta"]["per_page"] == 10
    status, body = api("GET", "/api/private/stem/session/?limit=10&offset=5")
    assert status == 400 and "offset" in body
    status, body = api("GET", "/api/private/stem/session/?per_page=5000")
    assert status == 200 and body["meta"]["per_page"] == 500


def test_tags_filter_by_name(api):
    store = api.store
    session_id = sorted(store.records["session"])[0]
    store.records["session"][session_id]["tags"] = ["pilot"]
    status, body = api("GET", "/api/private/stem/session/?filter{tags.name}=pilot")
    assert status == 200 and [s["id"] for s in body["sessions"]] == [session_id]
    store.records["session"][session_id]["tags"] = []


def test_agent_reference_endpoint(api):
    status, content_type, text = api.raw("/reference/", token=None)
    assert status == 200 and content_type.startswith("text/markdown") and "data_model: `specimen-1`" in text
    status, _, _ = api.raw("/reference/index.md", token="stale-token")
    assert status == 200
    status, _, text = api.raw("/reference/resources/session.md", token=None)
    assert status == 200 and "session" in text
    status, content_type, text = api.raw("/reference/data/manifest.json", token=None)
    assert status == 200 and content_type == "application/json" and '"format_version"' in text
    status, _, text = api.raw("/reference/nope.md", token=None)
    assert status == 404 and "index.md" in text


def test_schema_urls(api):
    status, _, text = api.raw("/schemas/", token=None)
    assert status == 200 and "AdhesiveCement" in json.loads(text)["families"]["Consumable"]
    status, _, text = api.raw("/schemas/Consumable/AdhesiveCement/", token=None)
    listing = json.loads(text)
    assert status == 200 and listing["current"] in listing["versions"]
    status, content_type, text = api.raw("/schemas/Consumable/AdhesiveCement.json", token=None)
    assert status == 200 and content_type == "application/schema+json"
    assert json.loads(text)["schemaVersion"] == listing["current"]
    oldest = listing["versions"][0]
    status, _, text = api.raw(f"/schemas/Consumable/AdhesiveCement/{oldest}.json", token=None)
    assert status == 200 and json.loads(text)["schemaVersion"] == oldest
    status, _, _ = api.raw("/schemas/Consumable/Nope.json", token=None)
    assert status == 404


def test_public_portal_hides_private_project(api):
    status, body = api("GET", "/api/public/stem/session/", token=None)
    assert status == 200 and body["sessions"] == []
    status, _ = api("GET", "/api/private/stem/session/", token=None)
    assert status == 401


def test_create_requires_form_fields_and_validates_details(api):
    status, body = api("POST", "/api/private/stem/session/", body={"name": "x"})
    assert status == 400 and "projects" in body and "session_type" in body and "status" in body
    procedure = first(api, "procedure", "procedures")
    bad = {"type": "VirusInjection", "status": "performed", "subject": procedure["subject"],
           "coordinates_system": "Stereotaxic_BregmaBrainSurface",
           "details": {"volume": 300}}
    status, body = api("POST", "/api/private/modules/procedure/", body=bad)
    assert status == 400 and "JSON validation failed" in body["details"][0]
    good = dict(bad, details={"volume": {"value": 300, "unit": "nL"}})
    status, body = api("POST", "/api/private/modules/procedure/", body=good)
    assert status == 201 and body["procedure"]["details"]["volume"]["unit"] == "nL"


def test_patch_replaces_lists_and_member_cannot_write(api):
    session = first(api, "session", "sessions")
    status, _ = api("PATCH", f"/api/private/stem/session/{session['id']}/", token="member-token", body={"tags": ["a"]})
    assert status == 403
    status, body = api("PATCH", f"/api/private/stem/session/{session['id']}/", body={"tags": ["only"]})
    assert status == 200 and body["session"]["tags"] == ["only"]
    log = [json.loads(line) for line in api.log.read_text().splitlines()]
    assert any(e["method"] == "PATCH" and e["status"] == 200 for e in log)


def test_unique_names(api):
    session = first(api, "session", "sessions")
    status, body = api("PATCH", f"/api/private/stem/session/{session['id']}/",
                       body={"name": api.store.records["session"][sorted(api.store.records["session"])[-1]]["name"].upper()})
    assert status == 400 and body["name"] == ["Name must be unique."]


def test_reverse_lists_follow_creates(api):
    session = first(api, "session", "sessions")
    before = set(session["dataacquisition"])
    interface = first(api, "experimentalinterface",
                      api.store.resources["experimentalinterface"]["response_key_plural"])
    status, body = api("POST", "/api/private/modules/dataacquisition/",
                       body={"session": session["id"], "type": "VideoTracking", "interfaces": [interface["id"]],
                             "details": {}})
    assert status == 201
    new_id = body["data_acquisition"]["id"]
    status, body = api("GET", f"/api/private/stem/session/{session['id']}/")
    assert set(body["session"]["dataacquisition"]) == before | {new_id}


def test_reverse_lists_match_fixture():
    store = Store(FIXTURE)
    for (resource, name), _ in store.reverse_fields.items():
        for record in store.records[resource].values():
            assert set(store.present(resource, record)[name]) == set(record.get(name) or []), (resource, name)


def test_project_export(api):
    project = first(api, "project", "projects")
    status, body = api("GET", f"/api/private/stem/project/{project['id']}/export/")
    expected = api.store.reference_documents["manifest"]["export_format_version"]
    assert status == 200 and body["export_info"]["format_version"] == expected
    assert body["export_info"]["record_count"] == sum(body["export_info"]["counts"].values())
    assert "type_json" in body["records"]["modules.procedure"][0]["fields"]
    # Exports need read access only.
    status, _ = api("GET", f"/api/private/stem/project/{project['id']}/export/", token="member-token")
    assert status == 200


def test_background_export_job(api):
    import gzip
    import hashlib

    project = first(api, "project", "projects")
    status, body = api("POST", f"/api/private/stem/project/{project['id']}/export/")
    assert status == 202 and body["export_job"]["status"] == "completed"
    job = body["export_job"]
    status, body = api("GET", f"/api/private/stem/project/{project['id']}/export-jobs/{job['id']}/")
    assert status == 200 and body["export_job"]["id"] == job["id"]
    request = urllib.request.Request(api.base + job["download_url"].lstrip("/"))
    request.add_header("Authorization", "Bearer contributor-token")
    with urllib.request.urlopen(request) as response:
        content = response.read()
    assert hashlib.sha256(content).hexdigest() == job["file_sha256"]
    assert json.loads(gzip.decompress(content))["export_info"]["project_id"] == project["id"]


def test_session_export_is_not_offered(api):
    session = first(api, "session", "sessions")
    status, _, _ = api.raw(f"/api/private/stem/session/{session['id']}/export/")
    assert status == 404



def test_delete_follows_on_delete_rules():
    store = Store(FIXTURE)
    session_id = next(s["id"] for s in store.records["session"].values() if s["dataacquisition"])
    children = [d["id"] for d in store.records["dataacquisition"].values() if d["session"] == session_id]
    assert store.delete("session", session_id)[0] == 204
    assert not any(c in store.records["dataacquisition"] for c in children)
    setup_id = next(b["setup"] for b in store.records["behavior"].values())
    with pytest.raises(Exception) as error:
        store.delete("setup", setup_id)
    assert "still referenced" in str(error.value.body)
