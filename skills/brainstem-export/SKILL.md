---
name: brainstem-export
description: Export a BrainSTEM project's or session's metadata as versioned JSON, or convert it to Neurodata Without Borders (NWB) files with the brainstem-nwb converter, for backups, analysis pipelines or DANDI. Use when the user asks to export, download, back up or archive a BrainSTEM project or session, or wants NWB files or DANDI-ready metadata from BrainSTEM. Reads only; never writes NWB conversion code itself.
license: MIT
metadata:
  version: "0.3.0"
---

# BrainSTEM export

Read-only on the server: an export changes no records.

## Before you start

1. Follow `references/connection.md`, and read `guides/export.md` from the agent reference: it gives the
   access needed, the methods, the file format and its limitations on this server.
2. Follow `references/safety.md`. An export contains a whole project or session; save it only where
   the user asks, and do not send it elsewhere.

## Which output

| The user wants | Do |
|---|---|
| a JSON backup, or records for their own pipeline | JSON export (below) |
| NWB files, or metadata ready for DANDI | NWB export with `brainstem-nwb`: follow `references/nwb-export.md` |
| tables (CSV) | build them from a JSON export or API queries only when asked; keep ids and units in the columns |

## JSON export

1. **Identify the project or session** by name or id; ask if several match.
2. **Choose the method** the guide recommends for its size (direct, or a background job for large ones).
3. **Run it** and check the result against the guide: format version, and record counts that add up.
4. **Save** the JSON where the user asked. Do not print the whole file into the conversation.
5. **Report** the file path, format version, record counts per model, and the limitations the guide
   lists.

## NWB export

Follow `references/nwb-export.md`: check the converter is installed, collect the experimenter, lab and
institution from the user (never invent them), run a dry run and report the manifest, then export and
report the files, unit errors and validation results. The files hold metadata only.
