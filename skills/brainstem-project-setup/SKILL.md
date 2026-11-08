---
name: brainstem-project-setup
description: Guide a lab or researcher through setting up BrainSTEM for a new project, covering the project, setups and equipment, inventories and stocks, behavioral assays, protocols and licenses, subjects or specimen sets, procedures with their implanted interfaces, and first sessions. Use when the user wants to onboard a lab, start or organize a project in BrainSTEM, or migrate an experiment's structure into it. Reuses existing shared resources first, and asks approval for each batch of new records.
license: MIT
metadata:
  version: "0.3.0"
---

# BrainSTEM project setup

## Before you start

1. Follow `references/connection.md`: setup needs a token, the private portal, and a supported
   `data_model` in the agent reference's `index.md`. Read `rules.md`.
2. Follow `references/safety.md`.
3. Every write follows `references/write-protocol.md`.

## Steps

Follow `guides/project-setup.md` from the agent reference, stage by stage:

1. **Interview** the user about the project, modality, species, rigs, stocks, licenses and protocols.
   Write down the answers; ask about gaps instead of guessing.
2. **Inventory what exists.** Search the user's projects and lab resources, and the shared catalog and
   taxonomies (`guides/taxonomies.md`). Show what can be reused.
3. **Plan one stage at a time**, in the guide's dependency order, each as a change plan with only the
   records still missing. Wait for approval per stage.
4. **Create** each approved stage in order, checking every response. Where the reference says a record
   is created automatically (for example by a procedure), look it up instead of creating a duplicate.
5. **Check consistency** as the guide describes, and report what was reused, what was created (ids and
   links), and what is still missing.

## Keep in mind

- Different labs work differently. Adapt to the modalities the user named and skip stages that do not
  apply.
- Shared catalog entries go through approval. Propose one only when the user confirms nothing existing
  fits.
- Say so when a plan includes experimental schema families (`rules.md`).
- Field requirements are on `resources/<resource>.md`; type schemas and material policies on
  `schemas/<Family>/<Type>.md`; access rules in `guides/permissions.md`. If the user lacks the role a
  stage needs, stop and say which role is required.
