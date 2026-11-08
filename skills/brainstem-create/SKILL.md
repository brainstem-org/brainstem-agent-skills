---
name: brainstem-create
description: Create new BrainSTEM records through the API, such as projects, subjects, sessions, procedures, data acquisitions, manipulations, behaviors, experimental interfaces, material usages, specimen sets, specimens and logs, reusing existing records and shared taxonomies. Use when the user asks to add, register, record, log or document new experimental metadata in BrainSTEM. Every write is shown as a change plan and needs the user's explicit approval first.
license: MIT
metadata:
  version: "0.3.0"
---

# BrainSTEM create

## Before you start

1. Follow `references/connection.md`: writes need a token, the private portal, and a supported
   `data_model` in the agent reference's `index.md`. Read `rules.md`.
2. Follow `references/safety.md`.
3. Follow `references/write-protocol.md` for every write: plan → confirm → execute → verify.

## Steps

1. **Identify the records.** Map the request to resources (`data-model.md`, `vocabulary.md`) and read
   each resource's page (`resources/<resource>.md`). For typed records, pick the type code from
   `schemas/<Family>.md` and read `schemas/<Family>/<Type>.md`, including its material policy.
2. **Resolve and reuse.** Look up every referenced record and taxonomy entry by name and keep the ids
   (`guides/taxonomies.md`). Search for an existing record before creating one; if a match exists, ask
   whether to use or update it. Check that new names are free.
3. **Collect required values** from the resource page and the type's required properties, in the
   formats of `guides/validation.md`. Ask for anything missing; never invent scientific values.
4. **Show the change plan** (`references/write-protocol.md`) and wait for an explicit yes. Label plans
   that touch experimental schema families (`rules.md`). Name side effects the reference describes,
   such as records created automatically.
5. **Execute** in dependency order, checking every response. Stop at the first error and report what
   exists so far.
6. **Verify** by re-reading each new record, then report names, ids and links.

For several records that belong together (a lab, a project, a series of sessions), use
`brainstem-project-setup` and its guide `guides/project-setup.md`.
