# Exporting BrainSTEM records to NWB with `brainstem-nwb`

`brainstem-nwb` is BrainSTEM's converter from project and session exports to Neurodata Without Borders
(NWB) files. It writes one metadata-only NWB file per session and subject, a conversion manifest that
accounts for every exported field, and a validation report (pynwb, NWB Inspector with the DANDI
configuration, BrainSTEM checks). Never write NWB conversion code yourself; use this tool.

The tool describes itself; prefer it over memory: `brainstem-nwb --help`, `brainstem-nwb <command> --help`,
`brainstem-nwb mapping` (how each BrainSTEM field maps to NWB) and `brainstem-nwb mapping --warnings`
(what each manifest warning means).

## 1. Check the tool

```bash
brainstem-nwb --version
```

If it is missing, ask before installing (Python 3.10 or later):

```bash
pip install brainstem-nwb                 # also installs the Python client
pip install 'brainstem-nwb[extensions]'   # only for --extension (adds the ndx-brainstem NWB extension)
```

If it cannot be installed, say so and offer the JSON export (`guides/export.md`) instead.

## 2. Collect what BrainSTEM does not record

NWB and DANDI expect an experimenter, a lab and an institution. BrainSTEM exports do not hold them, and
the tool never guesses them. Ask the user, then write their answers to a configuration file:

```toml
# brainstem-nwb.toml
[nwbfile]
experimenter = ["Last, First"]
lab = "<lab>"
institution = "<institution>"
```

Never fill these with placeholders or inferred names. If the user does not know them, export without
them and report that the files will lack these fields (`experimenter_source = "session_creator"` in
`[nwbfile]` is the documented alternative; offer it, do not apply it unasked). Subject label and species
format are also configuration keys (`[subject]` table); `brainstem-nwb export --help` lists the flags,
among them `--extension brainstem|localization` (needs `brainstem-nwb[extensions]`) and `--herd` for
ontology terms.

## 3. Choose the source

- A project: `--project <uuid>`, fetched with the user's token.
- Some sessions of a project: add `--session <uuid or name>` (repeatable).
- One session on its own: `--session <uuid>` alone fetches the session export, if the server and client
  support it; otherwise use `--project <uuid> --session <uuid>`.
- An export file the user downloaded: `--export-file <file>` (works offline, no token).

Always pass `--no-device-flow`, so the tool fails instead of waiting for a browser login. It reads the
token from `BRAINSTEM_API_TOKEN` or the cached login, and the server from `--url` (use the user's
server, from `BRAINSTEM_API_URL`).

## 4. Dry run first

```bash
brainstem-nwb export --project <uuid> --output <dir> --config brainstem-nwb.toml --no-device-flow --dry-run --json
```

This writes only `brainstem-nwb-manifest.json`. Report to the user: how many sessions and files would be
written, unit errors (sessions that cannot be exported, with their codes), and warnings by severity.
Ask before writing the files, and before overwriting an existing output directory. A re-export into a
directory that already holds NWB files needs `--overwrite` to replace files that changed; unchanged
files are reported as up to date. Pass it only after the user agrees.

## 5. Export

Run the same command without `--dry-run`. With `--json` the tool prints a summary with `exit_code`,
the counts of written, up-to-date and failed files, and validation results. Exit code 0 is success,
1 means some sessions failed, 2 means invalid options, configuration or export file, 3 means no token
was available (with `--no-device-flow`) or the export could not be fetched, 4 means validation failed.
If exit code 2 says the export format is not supported, the server writes a newer format than this
release reads: tell the user, offer to upgrade (`pip install -U brainstem-nwb`, with their agreement),
and offer the JSON export meanwhile. Read the summary, then report:

- the output directory and the number of NWB files;
- sessions not exported, with the reason and the fix the tool's troubleshooting suggests (often a
  missing value in BrainSTEM, such as a session date or a subject link);
- validation errors and warnings, from `validation-report.txt`;
- that the files hold metadata only: recordings, video and imaging data are described, not converted.

If a fix needs a change in BrainSTEM (for example setting a session's date), offer it through the
update workflow, with its own change plan and confirmation. Never change records to make an export pass
without asking.

## 6. DANDI

The files follow DANDI conventions and are validated with the DANDI configuration. Uploading to DANDI is
not part of this workflow; if asked, point the user to the DANDI CLI and the validation report, and do
not upload on their behalf.
