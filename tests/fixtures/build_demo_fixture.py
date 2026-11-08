"""Build tests/fixtures/demo_lab.json from a BrainSTEM server that has the demo project loaded.

Run inside the server's Django shell (never against a production database):

    cd <brainstem server> && FIXTURE_OUT=<path>/demo_lab.json python manage.py shell < build_demo_fixture.py

Prerequisite: `python manage.py generate_demo_project --user-email <user>` (dataset brainstem_rich_demo_v1).
Records are serialized with the private-portal API serializers, so the fixture holds exactly what the
REST API returns. Taxonomy and catalog records referenced by the project are added by following
relations; anatomical regions sharing an acronym across atlases are added to keep that ambiguity.
Email addresses are replaced by placeholders.
"""

import json
import os
import re
from collections import defaultdict

from django.test import RequestFactory
from guardian.shortcuts import get_users_with_perms
from rest_framework.request import Request
from rest_framework.utils.encoders import JSONEncoder

from brainstem.models import DemoDatasetRecord
from brainstem.urls import API_ROUTE_REGISTRY
from stem.models.Project import Project
from stem.services.project_export import export_querysets
from taxonomies.models.AnatomicalRegion import AnatomicalRegion

DATASET = "brainstem_rich_demo_v1"
SKIP_APPS = {"users"}
#: Shared public catalogs: any referenced entry may be included. Everything else must be owned by the
#: demo dataset, so no record of a real project, lab resource or user can enter the fixture.
CATALOG_APPS = {"taxonomies", "resources"}
MAX_REGIONS_PER_ACRONYM = 15
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

project_id = DemoDatasetRecord.objects.get(dataset_id=DATASET, model_label__iexact="stem.project").object_id
project = Project.objects.get(pk=project_id)
owners = get_users_with_perms(project, only_with_perms_in=["own_project"])
user = owners.first()
if user is None:
    raise SystemExit("The demo project has no owner; run generate_demo_project with --user-email first.")

http_request = RequestFactory().get("/")
http_request.user = user
request = Request(http_request)
request.user = user

routes = {}  # model label -> (app, resource, viewset class)
for app_label, resource, portals in API_ROUTE_REGISTRY:
    viewset = portals.get("private")
    if viewset is None or app_label in SKIP_APPS:
        continue
    label = viewset.serializer_class.Meta.model._meta.label_lower
    routes.setdefault(label, (app_label, resource, viewset))


def serialize(viewset_class, obj):
    view = viewset_class()
    view.request = request
    view.format_kwarg = None
    view.action = "retrieve"
    data = viewset_class.serializer_class(obj, context={"request": request, "view": view}).data
    # Render exactly as the API does (querysets -> lists, UUIDs -> strings).
    return json.loads(json.dumps(data, cls=JSONEncoder))


demo_ids = defaultdict(set)  # model label -> ids owned by the demo dataset
for label, object_id in DemoDatasetRecord.objects.filter(dataset_id=DATASET).values_list("model_label", "object_id"):
    demo_ids[label.lower()].add(str(object_id))


def allowed(label, pk):
    return label.split(".")[0] in CATALOG_APPS or str(pk) in demo_ids.get(label, set())


records = defaultdict(dict)  # resource -> {id: record}
relation_targets = defaultdict(dict)  # resource -> {field: target resource}
pending = defaultdict(set)  # model label -> ids to add

for queryset in export_querysets(user, project=project):
    label = queryset.model._meta.label_lower
    if label in routes:
        pending[label].update(str(pk) for pk in queryset.values_list("pk", flat=True))

for _round in range(4):
    if not pending:
        break
    current, pending = pending, defaultdict(set)
    for label, ids in current.items():
        app_label, resource, viewset_class = routes[label]
        model = viewset_class.serializer_class.Meta.model
        missing = [i for i in ids if i not in records[resource] and allowed(label, i)]
        for obj in model.objects.filter(pk__in=missing):
            data = serialize(viewset_class, obj)
            records[resource][str(obj.pk)] = data
            serializer = viewset_class.serializer_class()
            for name, field in serializer.fields.items():
                value = data.get(name)
                if not value:
                    continue
                try:
                    target = model._meta.get_field(getattr(field, "source", name) or name).related_model
                except Exception:
                    target = None
                if not hasattr(target, "_meta"):
                    continue
                target_label = target._meta.label_lower
                if target_label not in routes:
                    continue
                relation_targets[resource][name] = routes[target_label][1]
                values = value if isinstance(value, list) else [value]
                pending[target_label].update(str(v) for v in values if isinstance(v, (str, int)) or hasattr(v, "hex"))

# Same acronym in other atlases: keeps the real ambiguity agents must handle.
region_route = routes["taxonomies.anatomicalregion"]
acronyms = {r["acronym"] for r in records["anatomicalregion"].values() if r.get("acronym")}
for acronym in sorted(acronyms):
    for obj in AnatomicalRegion.objects.filter(acronym=acronym)[:MAX_REGIONS_PER_ACRONYM]:
        records["anatomicalregion"].setdefault(str(obj.pk), serialize(region_route[2], obj))



def drop_dangling(resource, record):
    """Remove relation ids that point at records left out of the fixture."""
    for field, target in relation_targets[resource].items():
        value = record.get(field)
        included = records.get(target, {})
        # Some relations are rendered as embedded objects rather than ids; keep those as they are.
        if isinstance(value, list):
            record[field] = [v for v in value if isinstance(v, dict) or str(v) in included]
        elif value is not None and not isinstance(value, dict) and str(value) not in included:
            record[field] = None


for resource, by_id in records.items():
    for record in by_id.values():
        drop_dangling(resource, record)


def scrub(value):
    if isinstance(value, dict):
        return {scrub(k) if isinstance(k, str) else k: scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, str):
        return EMAIL.sub("member@example.org", value)
    return value


resource_apps = {resource: app for app, resource, _vs in routes.values()}
payload = {
    "dataset": DATASET,
    "project": str(project.pk),
    "resources": {
        resource: {"app": resource_apps[resource], "records": sorted(by_id.values(), key=lambda r: str(r["id"]))}
        for resource, by_id in sorted(records.items())
    },
}
text = json.dumps(scrub(json.loads(json.dumps(payload, cls=JSONEncoder))), indent=1, ensure_ascii=False, sort_keys=True)
with open(os.environ["FIXTURE_OUT"], "w", encoding="utf-8") as handle:
    handle.write(text + "\n")
print("fixture:", {resource: len(by_id) for resource, by_id in sorted(records.items())})
