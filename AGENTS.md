# AGENTS.md: working on brainstem-agent-skills

This repository holds Agent Skills that teach AI agents how to *behave* when they work with BrainSTEM:
how to connect, stay safe, and confirm writes. Everything that *describes* BrainSTEM (resources, fields,
relationships, schemas, rules, guides) is served by each BrainSTEM server at
`/reference/` (public), generated from its code, and read by the agent at run time. The JSON Schemas of
every type and version are public at `/schemas/`.

## Layout

- `skills/<name>/SKILL.md`: the skills. Each skill's `references/` folder is a copy made by
  `tools/vendor_references.py`; never edit it.
- `references/`: the behavior files shared by the skills (`connection.md`, `safety.md`,
  `write-protocol.md`, `nwb-export.md`). `nwb-export.md` describes how to drive the `brainstem-nwb`
  converter; its options come from `brainstem-nwb --help`, not from this repository.
- `tests/fixtures/agent_reference.json` and `tests/fixtures/schemas.json.gz`: a server's agent reference and
  public schema URLs, used by the mock API and the static tests. They belong to BrainSTEM and must not be
  committed (`.gitignore`); download them with `tools/fetch_fixtures.py <server url>` before running the
  tests. `tests/fixtures/demo_lab.json`: the server's demo project as the private API returns it.
  `tests/fixtures/demo_export.json.gz`: the demo project's real export, with user names replaced. Refresh
  the demo files with `tools/update_fixtures.sh` (which also rebuilds the two local files); never edit any
  of them by hand.
- `tests/`: static checks, the mock API, contract tests against a real server, and the agent evaluation
  harness.

## Rules

- Do not write BrainSTEM facts (field names, required fields, routes, type codes, uniqueness, permission
  rules) into this repository. Cite the reference page that holds them instead, as a backticked path
  (`resources/session.md`, `guides/validation.md`). If a fact is missing or wrong, fix it in the server
  (`shared/agent_reference/` on the BrainSTEM server).
- Every reference page a skill cites must exist; `tests/static` checks it against the fixture.
- Keep `SKILL.md` frontmatter to the spec keys (`name`, `description`, `license`, `compatibility`,
  `metadata`, `allowed-tools`); other keys break some agent environments.
- Keep each `SKILL.md` short and task-oriented.
- Never mention BrainSTEM portals other than the private and public ones.

## After changing anything

```bash
python3 tools/vendor_references.py
python3 tools/fetch_fixtures.py https://www.brainstem.org   # once, or when the server changes
python3 -m pytest tests/static tests/mock_api tests/harness/test_grade.py -q
```
