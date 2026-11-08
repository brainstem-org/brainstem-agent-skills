# Compatibility

## BrainSTEM server

The skills read the server's public agent reference at `/reference/` and need:

| Item | Supported |
|---|---|
| Agent reference `format_version` | 1.x |
| `data_model` | `specimen-1` |

They also use the public schema URLs at `/schemas/` when they validate a payload. Servers without the
agent reference, or with another format or data model, get read-only help only.
`tools/check_server.py <url>` checks a live server (no token needed).

### www.brainstem.org

Checked 2026-11-08 with `tools/check_server.py https://www.brainstem.org`: OK.

| Item | Status |
|---|---|
| Agent reference | served: format 1.4, data model `specimen-1`, every page the skills cite |
| JSON Schemas at `/schemas/` | served |
| Project export format | 2.2 |

### Test fixtures

The tests download the agent reference and the schemas from a server with `tools/fetch_fixtures.py`; CI
uses www.brainstem.org unless the repository variable `BRAINSTEM_FIXTURE_URL` names another server. The
demo project fixtures (`demo_lab.json`, `demo_export.json.gz`) come from a local build of the
server and are refreshed with `tools/update_fixtures.sh`; refresh them when the server's data model
changes, so the mock serves records that match the reference. They were last refreshed on 2026-11-08
from the build www.brainstem.org runs (reference format 1.4, export format 2.2); with the reference and
schemas fetched from www.brainstem.org, the static, mock and contract tests all pass.

## Python client

| Version | Status |
|---|---|
| 2.0.0 | works for data on the pre-specimen data model; read the reference with `curl` (see `references/connection.md`); no exports, no specimen routes |
| 2.1.0 (on PyPI) | adds `agent_reference()` and `brainstem reference <page>` (public, no login), anonymous mode, `export_project()`/`export_session()`, routes for the specimen model. Required for writes and exports |

## NWB converter

| Tool | Status |
|---|---|
| `brainstem-nwb` 0.1.0 (on PyPI, Python 3.10 or later) | used by `brainstem-export`; reads project export format 2.x. Tested end to end against the mock API: 57 files from the demo project's 2.1 export and 58 from its 2.2 export, validation clean. On 2.2 it adds one info message (`EXPORT_MINOR_NEWER`) |
| `ndx-brainstem` 0.2.0 (on PyPI) | optional NWB extension, installed with `brainstem-nwb[extensions]`; needed only for `--extension` |

## Agent environments

Only environments that ran the evaluation suite (`tests/harness/run.py`) are listed as tested.

| Environment | Status | Evidence |
|---|---|---|
| Claude Code 2.1.296, model `claude-opus-5-5` | tested | 2026-10-16: 20/20 scenarios passed in one full run (search 8, create/update/safety 8, setup 1, JSON export 1, NWB export 2) against the mock API serving the public reference, the schema URLs, the demo lab and its real export |
| Claude Code plugin install (`/plugin marketplace add`) | install tested | 2026-11-08, Claude Code 2.1.318: `marketplace add brainstem-org/brainstem-agent-skills` and `plugin install brainstem@brainstem` from GitHub install version 0.3.0 with all six skills and their references |
| OpenAI Codex | not tested | skills follow the Agent Skills format Codex reads from `.agents/skills/` |
| Other Agent Skills environments | not tested | |

Evaluation runs are single runs of a non-deterministic agent: rerun scenarios after changing skills, and
treat a single pass as evidence, not proof.
