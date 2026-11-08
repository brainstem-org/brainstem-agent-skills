"""Write the demo project's real export (format 2.x) for tests/fixtures/demo_export.json.gz.

Run inside the server's Django shell; tools/update_fixtures.sh then scrubs it with scrub_export.py:

    cd <brainstem server> && EXPORT_OUT=<path>.json python manage.py shell < build_demo_export.py
"""

import json
import os

from guardian.shortcuts import get_users_with_perms
from rest_framework.utils.encoders import JSONEncoder

from brainstem.models import DemoDatasetRecord
from stem.models.Project import Project
from stem.services.project_export import build_project_export

project_id = DemoDatasetRecord.objects.get(dataset_id="brainstem_rich_demo_v1", model_label__iexact="stem.project").object_id
project = Project.objects.get(pk=project_id)
user = get_users_with_perms(project, only_with_perms_in=["own_project"]).first()
if user is None:
    raise SystemExit("The demo project has no owner; run generate_demo_project with --user-email first.")
with open(os.environ["EXPORT_OUT"], "w", encoding="utf-8") as handle:
    json.dump(build_project_export(user, project), handle, cls=JSONEncoder)
