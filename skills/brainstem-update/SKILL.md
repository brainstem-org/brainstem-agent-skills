---
name: brainstem-update
description: Safely change existing BrainSTEM records through the API, such as correcting a procedure, adding notes, tags or links, attaching subjects or interfaces to sessions, editing type-specific details, or deleting records. Use when the user asks to edit, fix, correct, rename, link, unlink, tag or delete BrainSTEM metadata. Reads the current record first, preserves unrelated data, shows a before/after change plan for approval, and verifies the result.
license: MIT
metadata:
  version: "0.3.0"
---

# BrainSTEM update

## Before you start

1. Follow `references/connection.md`: writes need a token, the private portal, and a supported
   `data_model` in the agent reference's `index.md`. Read `rules.md`.
2. Follow `references/safety.md`.
3. Follow `references/write-protocol.md` for every write: plan → confirm → execute → verify.

## Steps

1. **Identify the exact record.** Resolve it by id or by an unambiguous lookup. If several records
   match, list them and ask. Never update "the most likely" record.
2. **Read its current state** (`GET .../<resource>/<uuid>/`).
3. **Check the change is possible** on the resource page (`resources/<resource>.md`: which fields are
   writable, which are locked) and, for type-specific details, on `schemas/<Family>/<Type>.md`.
   `guides/validation.md` describes how updates behave. A record stores the schema version its details
   were validated against (`*_schema_version`); read its details with that version
   (`<server>/schemas/<Family>/<Type>/<version>.json`) and build the new details against the current one.
4. **Build the minimal change.**
   - Send only changed fields.
   - When a list or a JSON payload is replaced as a whole (`guides/validation.md`), start from the
     current value, change only what was asked, and send the complete value.
   - Keep values and units exactly as the user gave them.
5. **Show a before/after change plan** with each changed field's current and new value, and wait for
   an explicit yes. Deletes and bulk changes (more than 5 records) need an itemised list and a second
   confirmation that names the count.
6. **Execute** with PATCH (or DELETE), checking the response. Report 403 as "no permission" and
   stop; do not retry another way.
7. **Verify** by re-reading the record and comparing every planned field; report anything that
   differs, plus the record's id and link.

## Deleting

- Prefer correcting over deleting. Delete only when the user asks for it explicitly.
- Before deleting, read the resource page's *Deleting* line: it says which linked records are deleted
  with it and which links block the deletion. List those records in the plan.
- Deletion cannot be undone through the API.
