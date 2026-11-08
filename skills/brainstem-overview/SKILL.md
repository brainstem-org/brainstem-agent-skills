---
name: brainstem-overview
description: Orientation for BrainSTEM (brainstem.org), the electronic lab notebook and metadata platform for experimental neuroscience. Use when the user asks what BrainSTEM is, how its data are organized (projects, subjects, sessions, specimen sets, procedures, data acquisitions, experimental interfaces, material usages, taxonomies), which record type holds a piece of information, how permissions and sharing work, or how to connect an agent to BrainSTEM. Routes concrete tasks to brainstem-search, brainstem-create, brainstem-update, brainstem-project-setup and brainstem-export.
license: MIT
metadata:
  version: "0.3.0"
---

# BrainSTEM overview

## Before you start

1. Follow `references/connection.md`: find the server, check credentials without exposing them, and read
   the server's agent reference (`index.md`, then `rules.md`).
2. Follow `references/safety.md` throughout.

## Answering questions about BrainSTEM

Answer from the agent reference of the user's server, not from memory: it is generated from that
server's code.

- **What BrainSTEM is and how data are organized**: `index.md` and `data-model.md`.
- **Where something is recorded**: map the user's words with `vocabulary.md`, find the resource in
  `data-model.md`, then read `resources/<resource>.md` for its fields.
- **How two things connect** (for example "which brain region was this recording in"): give the route
  from `relationships.md`, not a field that does not exist.
- **Types and their details** (a procedure type, a recording type): `schemas.md`, then
  `schemas/<Family>/<Type>.md`.
- **Who can see or change what**: `guides/permissions.md`.
- **How to call the API or the Python client**: `guides/api-guide.md`, `guides/client-usage.md`.

Say plainly when something is not recorded in BrainSTEM, and quote the page you relied on.

## Which skill does the task

| The user wants to | Use |
|---|---|
| find, list, count or compare records | `brainstem-search` |
| add new records | `brainstem-create` |
| change, link or fix existing records | `brainstem-update` |
| set up a lab or a new project | `brainstem-project-setup` |
| export a project or session | `brainstem-export` |

If a skill is not installed, say so and describe what it would do; do not improvise writes.
