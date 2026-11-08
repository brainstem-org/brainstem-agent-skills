# Writing to BrainSTEM: plan → confirm → execute → verify

BrainSTEM holds shared research records. Every write follows these steps, with no exceptions.
Pages named without `references/` are pages of the server's agent reference (`references/connection.md`).

## 1. Understand the request

- Name each record to create or change and its resource (`data-model.md`, `resources/<resource>.md`).
- For typed records, find the type code and its schema (`schemas/<Family>/<Type>.md`), including
  required properties, units, allowed codes and, for procedures, specimen procedures and interfaces,
  the material policy.

## 2. Resolve and reuse

- Resolve every reference to an id by lookup: projects, subjects, sessions, specimen sets, setups,
  equipment, stocks, protocols, licenses, regions, species, strains, consumables. Ask when a name
  matches several records.
- Reuse existing records. Before creating, search for an existing one:
  - named records: `filter{name.iexact}=<name>` (`query-syntax.md`). The resource page lists which names must be unique and
    where. A name unique across all of BrainSTEM also covers records you cannot see, so a create can
    still fail with a uniqueness error; report it and ask for another name.
  - unnamed records (procedures, recordings, logs): look for the same parent, type and date, and the
    same file name or key details. If one exists, ask whether to update it instead.
- Never create a taxonomy or catalog entry when an existing one fits (`guides/taxonomies.md`).

## 3. Find missing information

- List every required field (`resources/<resource>.md`, *Required*, plus any form inputs it lists as
  required on create; formats in `guides/validation.md`)
  and every required schema property that has no value yet.
- Ask the user for them. Never invent scientific values (coordinates, doses, dates, sex, species,
  sampling rates, file names) to complete a record. Omit optional fields you do not know.
- For a type-specific payload, check it against the type's JSON Schema before showing the plan:
  fetch `<server>/schemas/<Family>/<Type>.json` (public) and validate with a JSON Schema validator if one
  is available (for example Python `jsonschema`). Fix what it reports with the user; the server
  validates again on write.

## 4. Show a change plan

Present the plan and wait for an explicit yes. Use this shape (an illustration checked against the
reference by `tests/static`; take field names and requirements from the resource and schema pages):

```yaml
change_plan:
  summary: "Create 1 session with 2 data acquisitions in project 'Place cells'"
  experimental: false            # true if any record is in an experimental schema family
  operations:
    - step: 1
      op: create                 # create | update | delete
      resource: session
      request: POST /api/private/stem/session/
      payload: {name: "M03_2026-03-02", status: performed, projects: ["<uuid>"], session_type: subject,
                subjects: ["<uuid>"], date_time: "2026-03-02T10:00:00Z"}
      references: {projects: "Place cells <uuid>", subjects: "M03 <uuid>"}
    - step: 2
      op: create
      resource: dataacquisition
      payload: {session: "<from step 1>", type: ExtracellularEphys, interfaces: ["<uuid>"],
                details: {sr: {value: 30000, unit: Hz}, nChannels: 64}}
  reused: ["interface 'M03 silicon probe' <uuid>"]
  side_effects: ["none"]         # e.g. an implant procedure creates an experimental interface
  missing: []                    # anything still unknown; the plan cannot run until this is empty
```

- For updates, show the current value next to the new one for every changed field.
- **Deletes and bulk changes** (more than 5 records): list every affected record by name and id, say
  that deletion cannot be undone from the API, and ask for a second, explicit confirmation naming the
  count ("yes, delete these 3 records").
- **Experimental families** (`rules.md`): label the plan `experimental: true` and say so in one
  sentence.
- If the user changes anything, show the revised plan and ask again.

## 5. Execute

- Run the steps in dependency order (parents before the records that link to them; the order for a
  new project is in `guides/project-setup.md`).
- Check the status code of every response. Stop at the first failure.
- On failure, report exactly what was created before it (ids) and what was not. Do not retry with
  altered scientific values. Offer to clean up only what you created, and only with confirmation.
- A response with an `*_approval` key means an approval request was filed, not that the record exists
  (`guides/api-guide.md`).

## 6. Verify and report

- Re-read every created or changed record by id and compare it with the plan. Report any difference.
- Report each record's name, id and link, in the form `guides/query-planning.md` gives
  (`<server>/private/<app>/<resource>/<uuid>/`).
- Never say a write succeeded without a 2xx response and the re-read.
