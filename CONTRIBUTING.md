# Contributing

Please read [AGENTS.md](AGENTS.md) first; it holds the rules for this repository (they apply to people
and coding agents alike).

## What goes where

| Change | Where |
|---|---|
| A BrainSTEM fact (field, relation, required flag, schema, type code, route, permission, guide text) is wrong or missing | the BrainSTEM server (`shared/agent_reference/`); then refresh the fixtures here |
| How an agent connects, stays safe, or confirms writes | `references/connection.md`, `safety.md`, `write-protocol.md` |
| The workflow of a task | the skill's `SKILL.md` |
| A new skill | `skills/<name>/SKILL.md`, an entry in `tools/skill_manifest.json`, scenarios in `tests/scenarios/` |
| A new evaluation case | `tests/scenarios/*.yaml`, with ground truth in `tests/harness/oracles.py` |

## Fixtures

The tests need a server's agent reference and schema URLs. They belong to BrainSTEM and are not committed,
so download them first (no token needed; takes a few minutes):

```bash
python3 tools/fetch_fixtures.py https://www.brainstem.org     # or http://127.0.0.1:8000
```

The demo project fixtures are committed. To refresh them, and to rebuild the reference and schemas
locally, from a server checkout with the demo project loaded (read-only on the server):

```bash
tools/update_fixtures.sh <path to brainstem server checkout> <python with the server's dependencies>
```

The static tests then show whether the skills still cite pages that exist. Never commit
`agent_reference.json` or `schemas.json.gz`.

## Checks

```bash
python3 -m pytest tests/static tests/mock_api tests/harness/test_grade.py -q        # always (CI)
BRAINSTEM_CONTRACT_URL=http://127.0.0.1:8000 python3 -m pytest tests/contract -q        # mock vs a real server
python3 tools/check_server.py <server url>                                             # skills vs a live reference
```

Agent evaluations run a real agent and cost tokens, so they are not part of CI:

```bash
python3 tests/harness/run.py --allow-bash --claude-bin "$(which claude)" [--only <scenario id>]
```

Pass `--python-bin-dir` to put a virtual environment with the Python client first on the agent's PATH.
Run the scenarios touched by your change before opening a pull request, and paste the summary line.

## Writing guidance

- Keep `SKILL.md` short and task-oriented; cite reference pages instead of restating them.
- Write for the agent that will follow the text literally: explicit steps, no ambiguity about when to
  ask the user.
