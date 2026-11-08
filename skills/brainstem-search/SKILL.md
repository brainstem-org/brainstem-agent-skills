---
name: brainstem-search
description: Search BrainSTEM experimental metadata to answer natural-language questions such as "find sessions with hippocampal Neuropixels recordings", "which subjects received optogenetic stimulation of the medial septum" or "experiments combining running behavior with CA1 recordings". Use when the user asks to find, list, count or compare BrainSTEM projects, subjects, sessions, specimens, procedures, recordings, interfaces, materials or behaviors by species, brain region, probe, equipment, acquisition type, procedure, behavioral paradigm, date or a numeric parameter. Read-only.
license: MIT
metadata:
  version: "0.3.0"
---

# BrainSTEM search

Read-only. Never create, change or delete records in this skill.

## Before you start

1. Follow `references/connection.md`: read the server's agent reference (`index.md`, `rules.md`).
2. Follow `references/safety.md`.

## Method

Follow `guides/query-planning.md` from the agent reference: plan, resolve, compile, verify, report. In
short:

1. **Plan.** Name the result resource and write one criterion per requirement. Keep qualifiers that
   describe the same thing in one criterion (they must hold on the same record). Keep negations. Add
   no filters the user did not state. Choose routes from `relationships.md`.
2. **Resolve** every term to ids or type codes by lookup (`guides/taxonomies.md`, `vocabulary.md`,
   `schemas.md`). When a term is ambiguous, show the candidates and ask, or state exactly which ones
   you included.
3. **Compile and run** from the evidence toward the result (`query-syntax.md`, `guides/api-guide.md`;
   which relations can be traversed is on each `resources/<resource>.md` page). Run every branch of a
   multi-branch route. Page through all results. When comparing values inside type-specific details,
   read each record's details with the schema version it stores (`*_schema_version`, `guides/validation.md`;
   every version is at
   `<server>/schemas/<Family>/<Type>/<version>.json`).
4. **Verify** each result's evidence chain and re-read the records you report.
5. **Report** (format below).

## Report format

```
Found N sessions (scope: private portal, project "…"; regions: CA1 [atlas …]; types: ExtracellularEphys)

| Session | Date | Evidence |
|---|---|---|
| [name](<server>/private/stem/session/<uuid>/) `<uuid>` | 2026-03-02 | ephys acquisition `<uuid>` via interface `<uuid>` in CA1 |

Not enforced: <requirements no route supports>
Incomplete: <failed, forbidden or truncated queries>
```

- Every record mentioned comes from a tool result, with its id.
- Say "no matching records you can read", not "none exist". Name the portal.
- If the question cannot be answered with the available data or routes, say what is missing.
