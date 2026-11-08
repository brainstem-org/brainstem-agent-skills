#!/usr/bin/env python3
"""A small BrainSTEM REST API emulator for deterministic agent evaluations.

It serves a fixture (tests/fixtures/demo_lab.json) with the behavior of the real dynamic-rest API, as
described by the server's agent reference (tests/fixtures/agent_reference.json and schemas.json.gz, downloaded
from a server with tools/fetch_fixtures.py and not committed):

- filters may traverse only nestable relations; other relations only as the last segment
  (400 ["Invalid nested filter field: x"] otherwise)
- include[]=<nestable>.* sideloads records under the target's plural key; other relations are ignored
- page/per_page paging (at most 500), limit/offset as an alias, meta.total_results
- the agent reference at /reference/ and the schema URLs at /schemas/ (both public, like the server)
- create/update check form-required fields, relation ids, global name uniqueness and `details`
  against the type's JSON schema; PATCH replaces lists and JSON payloads
- tokens map to roles: contributors may write, members get 403 on writes, unknown tokens get 401
- every request is appended to a JSON-lines log for grading

Standard library only.

    python tests/mock_api/server.py --fixture tests/fixtures/demo_lab.json --port 8765 --log /tmp/requests.jsonl
"""

import argparse
import copy
import gzip
import hashlib
import json
import re
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "tests" / "fixtures" / "agent_reference.json"
OPERATORS = None  # filled from the reference
MAX_PAGE_SIZE = 500
REFERENCE_PATH = re.compile(r"^/reference/(.*)$")
SCHEMA_PATH = re.compile(r"^/schemas/(?:([A-Za-z0-9_]+)/([A-Za-z0-9_]+)(\.json|/|/([0-9][0-9.]*)\.json))?/?$")
SCHEMA_FIXTURE = ROOT / "tests" / "fixtures" / "schemas.json.gz"
DEFAULT_TOKENS = {"contributor-token": "contributor", "member-token": "member"}
PATH = re.compile(r"^/api/(private|public)/([a-z_]+)/([a-z_]+)/(?:([0-9a-fA-F-]{36})/)?$")
EXPORT_PATH = re.compile(r"^/api/private/stem/(project|session)/([0-9a-fA-F-]{36})/export/$")
EXPORT_JOB_PATH = re.compile(
    r"^/api/private/stem/(project|session)/([0-9a-fA-F-]{36})/export-jobs/([0-9a-fA-F-]{36})/(download/)?$")
EXPORT_FIXTURE = ROOT / "tests" / "fixtures" / "demo_export.json.gz"
FILTER_KEY = re.compile(r"^filter\{([^}]+)\}$")


class RawBody:
    """A non-JSON response body (gzipped exports, HTML error pages)."""

    def __init__(self, data, content_type):
        self.data = data
        self.content_type = content_type


class ApiError(Exception):
    def __init__(self, status, body):
        super().__init__(status)
        self.status = status
        self.body = body


def require_fetched(*paths):
    """The reference and schema fixtures are downloaded, not committed (tools/fetch_fixtures.py)."""
    missing = [str(Path(p).relative_to(ROOT)) if Path(p).is_relative_to(ROOT) else str(p)
               for p in paths if not Path(p).exists()]
    if missing:
        raise FileNotFoundError(f"missing {', '.join(missing)}: run `python3 tools/fetch_fixtures.py <server url>` "
                                "(for example https://www.brainstem.org) first")


class Store:
    def __init__(self, fixture_path, public_projects=(), reference_path=REFERENCE):
        require_fetched(reference_path, SCHEMA_FIXTURE)
        reference = json.loads(Path(reference_path).read_text(encoding="utf-8"))
        self.reference_pages = reference["pages"]
        self.reference_documents = reference["documents"]
        surface = reference["documents"]["api_surface"]
        global OPERATORS
        OPERATORS = {op for op in surface["query"]["filter_operators"] if op}
        self.resources = {r["resource"]: r for r in surface["resources"]}
        self.by_model = {r["model"]: r["resource"] for r in surface["resources"]}
        self.fields = {
            name: {f["name"]: f for f in r["fields"]} for name, r in self.resources.items()
        }
        schemas = reference["documents"]["schemas"]
        self.schemas = {
            (family["family"], t["type"]): t for family in schemas["families"] for t in family["types"]
        }
        fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
        self.records = {
            name: {str(rec["id"]): rec for rec in data["records"]} for name, data in fixture["resources"].items()
        }
        for name in self.resources:
            self.records.setdefault(name, {})
        self.public_projects = set(public_projects)
        self.lock = threading.Lock()
        self.reverse_fields = self._infer_reverse_fields()
        self.export_jobs = {}  # job id -> (model, record id)
        self.real_export = None
        self.schema_urls = json.loads(gzip.decompress(SCHEMA_FIXTURE.read_bytes()))
        if EXPORT_FIXTURE.exists():
            self.real_export = json.loads(gzip.decompress(EXPORT_FIXTURE.read_bytes()))
        self.edges = reference["documents"]["relationships"]["edges"]

    def _infer_reverse_fields(self):
        """Map each computed relation list (session.dataacquisition, ...) to the forward field that feeds it.

        The real server derives these lists from the related records. For every read-only or
        not-in-form many-relation, pick the writable field on the target resource that points back
        and agrees with the fixture, so the lists stay correct after the mock creates or deletes records.
        """
        mapping = {}
        for resource, fields in self.fields.items():
            model = self.resources[resource]["model"]
            for name, field in fields.items():
                if field["kind"] != "relation_many" or field["write"] not in ("read_only", "not_in_form"):
                    continue
                target = self.target(resource, name)
                if not target:
                    continue
                if any(isinstance(v, dict) for rec in self.records[resource].values() for v in rec.get(name) or []):
                    continue  # embedded objects, returned as stored
                candidates = [
                    other for other, f in self.fields[target].items()
                    if f.get("target") == model and f["write"] in ("form", "custom")
                ]
                best, best_score = None, -1
                for candidate in candidates:
                    score = 0
                    for rec in self.records[resource].values():
                        derived = {
                            t["id"] for t in self.records[target].values()
                            if rec["id"] in (t.get(candidate) if isinstance(t.get(candidate), list) else [t.get(candidate)])
                        }
                        score += derived == set(rec.get(name) or [])
                    if score > best_score:
                        best, best_score = candidate, score
                if best:
                    mapping[(resource, name)] = (target, best)
        return mapping

    def present(self, resource, record, portal="private"):
        """A copy of the record with computed relation lists derived from current state, without the fields
        the reference limits to other portals (the public portal shows no creators)."""
        out = copy.deepcopy(record)
        for name, field in self.fields[resource].items():
            if portal not in field.get("portals", [portal]):
                out.pop(name, None)
        for (res, name), (target, forward) in self.reverse_fields.items():
            if res != resource:
                continue
            out[name] = sorted(
                t["id"] for t in self.records[target].values()
                if record["id"] in (t.get(forward) if isinstance(t.get(forward), list) else [t.get(forward)])
            )
        return out

    # -- helpers ---------------------------------------------------------

    def target(self, resource, field_name):
        field = self.fields[resource].get(field_name)
        if not field or field["kind"] not in ("relation", "relation_many"):
            return None
        return self.by_model.get(field.get("target"))

    def visible(self, resource, record, portal):
        if portal == "private":
            return True
        projects = record.get("projects")
        if isinstance(projects, list):
            return bool(set(map(str, projects)) & self.public_projects)
        project = record.get("project")
        if project:
            return str(project) in self.public_projects
        return resource in ("species", "strain", "anatomicalregion", "anatomicalreference", "behavioralparadigm",
                            "behavioralcategory", "setuptype", "consumable", "hardwaredevice", "supplier",
                            "coordinatetransform", "regulatoryauthority", "journal")

    # -- filtering -------------------------------------------------------

    def filter_choices(self, resource, portal):
        """The field names the server lists after an invalid filter field (no write-only fields; fields the
        reference limits to other portals are left out)."""
        return sorted(name for name, field in self.fields[resource].items()
                      if field.get("write") != "write_only" and portal in field.get("portals", [portal]))

    def compile_filter(self, resource, key, portal="private"):
        parts = key.split(".")
        operator = "eq"
        if len(parts) > 1 and parts[-1] in OPERATORS:
            operator = parts.pop()
        steps = []
        current = resource
        for index, part in enumerate(parts):
            field = self.fields[current].get(part)
            if field is None:
                choices = ", ".join(self.filter_choices(current, portal))
                raise ApiError(400, [f"Invalid filter field: {part}. Choices are: {choices}."])
            if field.get("filter_by") and parts[index + 1:] == field["filter_by"].split(".")[1:]:
                # e.g. tags: stored as names, filtered as tags.name
                steps.append((current, part))
                break
            last = index == len(parts) - 1
            if last:
                steps.append((current, part))
                break
            if not field.get("nestable"):
                raise ApiError(400, [f"Invalid nested filter field: {part}"])
            steps.append((current, part))
            current = self.target(current, part)
        return steps, operator

    def values_at(self, record, steps):
        """All values reached by following the steps from one record."""
        frontier = [record]
        for index, (resource, field) in enumerate(steps):
            last = index == len(steps) - 1
            values = []
            for rec in frontier:
                value = rec.get(field)
                values.extend(value if isinstance(value, list) else [value])
            if last:
                return values
            target = self.target(resource, field)
            frontier = [self.present(target, self.records[target][str(v)])
                        for v in values if v is not None and str(v) in self.records[target]]
        return []

    @staticmethod
    def compare(value, operator, wanted):
        if operator == "isnull":
            want_null = str(wanted[0]).lower() in ("true", "1")
            return (value in (None, "", [])) == want_null
        if value is None:
            return False
        text = str(value)
        if operator in ("eq", "iexact"):
            return any((text.lower() == w.lower()) if operator == "iexact" else text == w for w in wanted[:1])
        if operator == "in":
            return text in wanted
        w = wanted[0]
        if operator == "icontains":
            return w.lower() in text.lower()
        if operator == "contains":
            return w in text
        if operator in ("startswith", "istartswith"):
            return text.lower().startswith(w.lower()) if operator[0] == "i" else text.startswith(w)
        if operator in ("endswith", "iendswith"):
            return text.lower().endswith(w.lower()) if operator[0] == "i" else text.endswith(w)
        if operator in ("gt", "gte", "lt", "lte"):
            try:
                a, b = float(value), float(w)
            except (TypeError, ValueError):
                a, b = text, w
            return {"gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b}[operator]
        raise ApiError(400, [f"Unsupported operator in mock: {operator}"])

    def check_uuid_values(self, resource, steps, wanted):
        last_resource, last_field = steps[-1]
        if self.target(last_resource, last_field) or last_field == "id":
            for w in wanted:
                try:
                    uuid.UUID(w)
                except ValueError:
                    raise ApiError(400, [f"“{w}” is not a valid UUID."])

    # -- endpoints -------------------------------------------------------

    def list(self, resource, portal, query):
        filters = []
        for key, values in query.items():
            match = FILTER_KEY.match(key)
            if match:
                steps, operator = self.compile_filter(resource, match.group(1), portal)
                if operator not in ("icontains", "contains", "startswith", "istartswith", "endswith", "iendswith"):
                    self.check_uuid_values(resource, steps, values)
                filters.append((steps, operator, values))
        rows = [self.present(resource, r, portal) for r in self.records[resource].values()
                if self.visible(resource, r, portal)]
        for steps, operator, wanted in filters:
            rows = [r for r in rows if any(self.compare(v, operator, wanted) for v in self.values_at(r, steps))]
        for key in reversed(query.get("sort[]", [])):
            field = key.lstrip("-")
            rows.sort(key=lambda r: (r.get(field) is None, str(r.get(field))), reverse=key.startswith("-"))
        if not query.get("sort[]"):
            rows.sort(key=lambda r: str(r["id"]))
        per_page, page = self.paging(query)
        total = len(rows)
        page_rows = rows[(page - 1) * per_page: page * per_page]
        info = self.resources[resource]
        body = {info["response_key_plural"]: copy.deepcopy(page_rows)}
        for include in query.get("include[]", []):
            name = include.split(".")[0]
            field = self.fields[resource].get(name)
            if field is None:
                raise ApiError(400, {"detail": f"\"{name}\" is not a valid field name for \"{info['response_key']}\"."})
            if not field.get("nestable"):
                continue
            target = self.target(resource, name)
            ids = []
            for row in page_rows:
                value = row.get(name)
                ids.extend(value if isinstance(value, list) else [value])
            plural = self.resources[target]["response_key_plural"]
            seen = {r["id"] for r in body.get(plural, [])}
            sideload = body.setdefault(plural, [])
            for i in ids:
                rec = self.records[target].get(str(i))
                if rec is not None and rec["id"] not in seen:
                    sideload.append(self.present(target, rec, portal))
                    seen.add(rec["id"])
        body["meta"] = {"page": page, "per_page": per_page, "total_results": total,
                        "total_pages": max(1, -(-total // per_page))}
        return 200, body

    @staticmethod
    def paging(query):
        """page/per_page, or limit/offset as an alias (offset must be a multiple of limit), capped at 500."""
        def number(name, minimum):
            try:
                value = int(query[name][0])
            except (KeyError, ValueError):
                value = None
            if value is None or value < minimum:
                raise ApiError(400, {name: [f"Must be an integer of at least {minimum}."]})
            return value

        if "per_page" in query:
            try:  # like dynamic-rest: an invalid per_page falls back to the default
                per_page = int(query["per_page"][0])
            except ValueError:
                per_page = 0
            per_page = per_page if per_page >= 1 else 100
        elif "limit" in query:
            per_page = number("limit", 1)
        else:
            per_page = 100
        per_page = min(per_page, MAX_PAGE_SIZE)
        if "page" in query:
            page = number("page", 1)
        elif "offset" in query:
            offset = number("offset", 0)
            if offset % per_page:
                raise ApiError(400, {"offset": [
                    f"Must be a multiple of the page size ({per_page}). Use page and per_page instead."]})
            page = offset // per_page + 1
        else:
            page = 1
        return per_page, page

    def reference(self, page):
        """A page or document of the agent reference, as (status, content type, body bytes)."""
        page = page or "index.md"
        if page.startswith("data/") and page.endswith(".json"):
            document = self.reference_documents.get(page[len("data/"):-len(".json")])
            if document is not None:
                return 200, "application/json", json.dumps(document).encode("utf-8")
        elif page in self.reference_pages:
            return 200, "text/markdown; charset=utf-8", self.reference_pages[page].encode("utf-8")
        body = f"# Not found\n\nNo agent reference page `{page}`. Start at [index.md](index.md).\n"
        return 404, "text/markdown; charset=utf-8", body.encode("utf-8")

    def schema(self, family, name, suffix, version):
        """The public schema URLs: index, current version, version list, one exact version."""
        if self.schema_urls is None:
            return 404, "application/json", b'{"detail": "Not found."}'
        if family is None:
            return 200, "application/json", json.dumps(self.schema_urls["index"]).encode("utf-8")
        entry = self.schema_urls["types"].get(f"{family}/{name}")
        if entry is None:
            return 404, "application/json", b'{"detail": "Not found."}'
        if suffix == "/":
            return 200, "application/json", json.dumps(entry["listing"]).encode("utf-8")
        wanted = version or entry["listing"]["current"]
        document = entry["versions"].get(wanted)
        if document is None:
            return 404, "application/json", b'{"detail": "Not found."}'
        return 200, "application/schema+json", json.dumps(document).encode("utf-8")

    def detail(self, resource, portal, record_id):
        rec = self.records[resource].get(record_id)
        if rec is None or not self.visible(resource, rec, portal):
            raise ApiError(404, {"detail": "Not found."})
        return 200, {self.resources[resource]["response_key"]: self.present(resource, rec, portal)}

    def validate_details(self, resource, record, errors):
        for payload in self.resources[resource].get("json_payloads", []):
            selector, field = payload["selector_field"], payload["payload_field"]
            type_code = record.get(selector)
            if not type_code:
                continue
            schema = self.schemas.get((payload["schema_group"], type_code))
            if schema is None:
                errors[selector] = ["Wrong type"]
                continue
            data = record.get(field)
            if data in (None, ""):
                if schema["required"]:
                    errors[field] = [f"Required fields missing: {schema['required']}"]
                continue
            if schema["shape"] == "array" or not isinstance(data, dict):
                continue
            problems = [f"'{name}' is a required property" for name in schema["required"] if name not in data]
            props = {p["path"]: p for p in schema["properties"]}
            for name, value in data.items():
                prop = props.get(name)
                if prop is None:
                    continue
                if prop.get("units"):
                    if not (isinstance(value, dict) and "value" in value and value.get("unit") in prop["units"]):
                        problems.append(f"'{name}' must be {{\"value\": number, \"unit\": one of {prop['units']}}}")
                elif prop.get("enum") and prop["shape"] == "enum":
                    if value not in [e["code"] for e in prop["enum"]]:
                        problems.append(f"'{name}': {value!r} is not one of the allowed codes")
            if problems:
                errors[field] = [f"JSON validation failed for type '{type_code}': " + "; ".join(problems)]

    def write(self, resource, record_id, data, partial):
        fields = self.fields[resource]
        current = self.records[resource].get(record_id) if record_id else None
        if record_id and current is None:
            raise ApiError(404, {"detail": "Not found."})
        record = copy.deepcopy(current) if current else {name: None for name in fields}
        if not current:
            record["id"] = str(uuid.uuid4())
            for name, field in fields.items():
                if field["kind"] == "relation_many" or field["kind"] == "list":
                    record[name] = []
        errors = {}
        for name, value in data.items():
            field = fields.get(name)
            if field is None or field["write"] in ("read_only", "not_in_form"):
                continue
            target = self.target(resource, name)
            if target:
                ids = value if isinstance(value, list) else [value]
                bad = [i for i in ids if i is not None and str(i) not in self.records[target]]
                if bad:
                    errors[name] = [f"Select a valid choice. {bad[0]} is not one of the available choices."]
                    continue
            if field["write"] != "write_only":
                record[name] = value
        if not partial:
            for name, field in fields.items():
                if field["required_on_create"] and data.get(name) in (None, "", []):
                    errors.setdefault(name, ["This field is required."])
            for extra in self.resources[resource].get("form_only_fields", []):
                value = data.get(extra["name"])
                if value in (None, ""):
                    errors.setdefault(extra["name"], ["This field is required."])
                elif extra.get("choices") and str(value) not in extra["choices"]:
                    errors.setdefault(extra["name"], [f"Select a valid choice. {value} is not one of the available choices."])
        if "name" in data and "name" in fields:
            for other in self.records[resource].values():
                if other["id"] != record["id"] and str(other.get("name", "")).lower() == str(data["name"]).lower():
                    if any(r["fields"] == ["name"] and r["scope"] == "global" for r in self.resources[resource]["uniqueness"]):
                        errors.setdefault("name", ["Name must be unique."])
        self.validate_details(resource, record, errors)
        if errors:
            raise ApiError(400, errors)
        self.records[resource][record["id"]] = record
        return (200 if current else 201), {self.resources[resource]["response_key"]: self.present(resource, record)}

    def export_project(self, project_id):
        """The project's export: the real server export from the fixture, or one built from the records."""
        if project_id not in self.records["project"]:
            raise ApiError(404, {"detail": "Not found."})
        if self.real_export and self.real_export["export_info"]["project_id"] == project_id:
            return 200, copy.deepcopy(self.real_export)
        records, counts = {}, {}
        for resource, rows in self.records.items():
            info = self.resources[resource]
            if info["app"] in ("users",) or resource.endswith("approval") or "invitation" in resource:
                continue
            label = info["model"]
            renamed = {f["name"]: f.get("internal_name", f["name"]) for f in info["fields"]}
            out = []
            for row in sorted(rows.values(), key=lambda r: str(r["id"])):
                fields = {renamed.get(k, k): v for k, v in self.present(resource, row).items() if k != "id"}
                out.append({"model": label, "pk": row["id"], "fields": fields})
            records[label] = out
            counts[label] = len(out)
        return 200, {"export_info": {"format_version": "2.0", "exported_at": "2026-10-15T00:00:00+00:00",
                                     "project_id": project_id, "lab_resources": "mock export",
                                     "record_count": sum(counts.values()), "counts": counts},
                     "records": records}

    def delete(self, resource, record_id):
        if record_id not in self.records[resource]:
            raise ApiError(404, {"detail": "Not found."})
        plan = {}
        self._plan_delete(resource, record_id, plan, set())
        for (res, rid), action in plan.items():
            if action == "delete":
                self.records[res].pop(rid, None)
        for (res, rid), action in plan.items():
            if isinstance(action, tuple) and rid in self.records[res]:
                field, removed = action
                value = self.records[res][rid].get(field)
                if isinstance(value, list):
                    self.records[res][rid][field] = [v for v in value if v != removed]
                else:
                    self.records[res][rid][field] = None
        return 204, None

    def _api_field(self, resource, model_field):
        for name, field in self.fields[resource].items():
            if name == model_field or field.get("internal_name") == model_field:
                return name
        return None

    def _plan_delete(self, resource, record_id, plan, seen):
        """Follow on_delete rules from snapshot/relationships.json: CASCADE, PROTECT, SET_NULL, m2m unlink."""
        if (resource, record_id) in seen:
            return
        seen.add((resource, record_id))
        plan[(resource, record_id)] = "delete"
        for edge in self.edges:
            if edge["target"] != resource:
                continue
            field = self._api_field(edge["source"], edge["field"])
            if field is None:
                continue
            for row in self.records.get(edge["source"], {}).values():
                value = row.get(field)
                if record_id not in (value if isinstance(value, list) else [value]):
                    continue
                rule = edge.get("on_delete")
                if rule == "PROTECT":
                    raise ApiError(400, [f"Cannot delete: this record is still referenced by {edge['source']}. "
                                         "Remove those entries first."])
                if rule == "CASCADE":
                    self._plan_delete(edge["source"], row["id"], plan, seen)
                elif (edge["source"], row["id"]) not in plan:
                    plan[(edge["source"], row["id"])] = (field, record_id)


def make_handler(store, tokens, log_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, status, body, content_type="application/json"):
            if isinstance(body, bytes):
                payload = body
            else:
                payload = b"" if body is None else json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _log(self, method, path, query, body, status):
            if not log_path:
                return
            entry = {"method": method, "path": path, "query": query, "body": body, "status": status}
            with store.lock, open(log_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry) + "\n")

        def _handle(self, method):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query, keep_blank_values=True)
            body = None
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                try:
                    body = json.loads(self.rfile.read(length) or b"null")
                except json.JSONDecodeError:
                    self._log(method, parsed.path, query, None, 400)
                    return self._send(400, {"detail": "JSON parse error"})
            reference = REFERENCE_PATH.match(parsed.path)
            schema = SCHEMA_PATH.match(parsed.path)
            if (reference or schema) and method == "GET":
                # Public, like the server: no token needed and a stale token does not matter.
                if reference:
                    status, content_type, payload = store.reference(reference.group(1))
                else:
                    status, content_type, payload = store.schema(*schema.groups())
                self._log(method, parsed.path, query, None, status)
                return self._send(status, payload, content_type)
            status, response = self._dispatch(method, parsed.path, query, body)
            self._log(method, parsed.path, query, body, status)
            if isinstance(response, RawBody):
                return self._send(status, response.data, response.content_type)
            self._send(status, response)

        def _dispatch(self, method, path, query, body):
            export = EXPORT_PATH.match(path) or EXPORT_JOB_PATH.match(path)
            if export:
                auth = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
                if tokens.get(auth) is None:
                    return 401, {"detail": "Authentication credentials were not provided."}
                return self._export(method, export.groups())
            match = PATH.match(path)
            if not match:
                return 404, {"detail": "Not found."}
            portal, app, resource, record_id = match.groups()
            info = store.resources.get(resource)
            if info is None or info["app"] != app or portal not in info["portals"]:
                return 404, {"detail": "Not found."}
            auth = self.headers.get("Authorization", "")
            role = None
            if auth:
                role = tokens.get(auth.removeprefix("Bearer ").strip())
                if role is None:
                    return 401, {"detail": "Given token not valid for any token type"}
            try:
                with store.lock:
                    if portal == "private" and role is None:
                        raise ApiError(401, {"detail": "Authentication credentials were not provided."})
                    if method == "GET":
                        if record_id:
                            return store.detail(resource, portal, record_id)
                        return store.list(resource, portal, query)
                    if portal == "public":
                        raise ApiError(403, {"detail": "You do not have permission to perform this action."})
                    if role != "contributor":
                        raise ApiError(403, {"detail": "You do not have permission to perform this action."})
                    data = body.get(info["response_key"], body) if isinstance(body, dict) else {}
                    if method == "POST" and not record_id:
                        return store.write(resource, None, data, partial=False)
                    if method in ("PATCH", "PUT") and record_id:
                        return store.write(resource, record_id, data, partial=True)
                    if method == "DELETE" and record_id:
                        return store.delete(resource, record_id)
                    raise ApiError(405, {"detail": f"Method \"{method}\" not allowed."})
            except ApiError as error:
                return error.status, error.body

        def _export(self, method, groups):
            """Direct (GET) and background (POST, then job status and download) exports, like the server."""
            model, record_id = groups[0], groups[1]
            if model == "session":
                return 404, RawBody(b"<h1>Not Found</h1>", "text/html")  # as a server without session exports
            if len(groups) == 2:
                try:
                    with store.lock:
                        status, body = store.export_project(record_id)
                except ApiError as error:
                    return error.status, error.body
                if method == "GET":
                    return status, body
                if method == "POST":
                    job_id = str(uuid.uuid4())
                    store.export_jobs[job_id] = (model, record_id)
                    return 202, {"export_job": self._job(model, record_id, job_id)}
                return 405, {"detail": f"Method \"{method}\" not allowed."}
            job_id, download = groups[2], groups[3]
            if store.export_jobs.get(job_id) != (model, record_id):
                return 404, {"detail": "Not found."}
            if not download:
                return 200, {"export_job": self._job(model, record_id, job_id)}
            return 200, RawBody(self._export_bytes(record_id), "application/gzip")

        def _export_bytes(self, record_id):
            _status, body = store.export_project(record_id)
            return gzip.compress(json.dumps(body).encode("utf-8"), mtime=0)

        def _job(self, model, record_id, job_id):
            return {"id": job_id, "status": "completed", "progress_percent": 100,
                    "download_url": f"/api/private/stem/{model}/{record_id}/export-jobs/{job_id}/download/",
                    "file_sha256": hashlib.sha256(self._export_bytes(record_id)).hexdigest()}

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def do_PATCH(self):
            self._handle("PATCH")

        def do_PUT(self):
            self._handle("PUT")

        def do_DELETE(self):
            self._handle("DELETE")

    return Handler


def serve(fixture, port, log_path=None, tokens=None, public_projects=()):
    store = Store(fixture, public_projects)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(store, tokens or DEFAULT_TOKENS, log_path))
    return server, store


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixture", default=str(ROOT / "tests" / "fixtures" / "demo_lab.json"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--log")
    parser.add_argument("--public-project", action="append", default=[])
    args = parser.parse_args(argv)
    server, _store = serve(args.fixture, args.port, args.log, public_projects=args.public_project)
    print(f"mock BrainSTEM API on http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
