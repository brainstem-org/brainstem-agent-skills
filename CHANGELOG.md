# Changelog

This project uses semantic versioning. Compatibility with BrainSTEM servers and clients is recorded in
[COMPATIBILITY.md](COMPATIBILITY.md).

## 0.3.0 (unreleased)

- Licensed: MIT for the skills, references and tools (`LICENSE`, and `license: MIT` in every `SKILL.md`,
  since a skill is installed without the repository); the demo project fixtures under CC BY 4.0
  (`LICENSE-DATA`).
- The agent reference and schema fixtures are no longer committed: they belong to BrainSTEM (see the
  server's `license.md`). `tools/fetch_fixtures.py` downloads them from a server before the tests; CI
  fetches from www.brainstem.org (or `BRAINSTEM_FIXTURE_URL`) and caches them for a week.
- Examples and the change-plan illustration send the session's required `status`.
- `SECURITY.md` describes how to report vulnerabilities.
- Demo fixtures refreshed from the server build www.brainstem.org runs (reference format 1.4, export format 2.2).
  Tests no longer hard-code the export format (they read it from the reference) and send the now-required
  `interfaces` when creating a data acquisition. The mock lists the valid fields after an invalid filter
  field, as the server does, and leaves fields the reference marks private-only out of public records. `build_schema_fixture.py` turns off the server's per-IP limit on `/schemas/`
  in the local shell.
- `nwb-export.md` explains an unsupported export format (exit code 2): offer an upgrade and the JSON export.
- The Python client 2.1.0, `brainstem-nwb` 0.1.0 and `ndx-brainstem` 0.2.0 are on PyPI: `nwb-export.md`
  installs the converter from PyPI (with the `extensions` extra for `--extension`) and lists every exit code.
- `brainstem-export` converts projects and sessions to NWB with the `brainstem-nwb` converter
  (`references/nwb-export.md`): checks the tool, asks for experimenter, lab and institution instead of
  inventing them, runs a dry run, then exports and reports the manifest and validation.
- The mock API serves the demo project's real export (direct and background jobs); new scenarios
  `nwb-export-project` and `nwb-asks-for-experimenter`.
- The agent reference moved to the public `/reference/` (format 1.1): agents read it without a token, and
  `tools/check_server.py` needs no token.
- Typed payloads are checked against the exact JSON Schema served at `/schemas/<Family>/<Type>.json`
  before a write is proposed; stored details are read with the schema version the record names. The mock
  serves the schema URLs from a server export (`tests/fixtures/schemas.json.gz`), and the contract test
  checks that reference pages and schemas are identical to the server's.

## 0.2.0 (unreleased)

- BrainSTEM knowledge moved to the server: the skills read each server's agent reference
  (`/api/private/agent-reference/`) at run time instead of carrying generated copies. The snapshot, the
  generated references and the server-specific guides were removed (about 2,700 files down to about 80).
- `references/connection.md` checks the reference's `format_version` (1.x) and `data_model`
  (`specimen-1`) before any write.
- Test fixtures are exports of a server (`tools/update_fixtures.sh`); static tests check that every cited
  reference page exists; `tools/check_server.py` checks a live server.
- The mock API serves the agent reference and follows the server's paging, tag filters and nestable
  relations.
- Not yet licensed; the repository is private.

## 0.1.0 (unreleased, superseded)

- Six skills with references generated from a server snapshot, mock API, contract tests and agent
  evaluation harness.
