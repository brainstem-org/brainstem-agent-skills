# Examples

Representative workflows, using the demo lab that ships with the BrainSTEM server
(`manage.py generate_demo_project`; the same records are in `tests/fixtures/demo_lab.json`). Each shows
what you ask, what the agent does, and what it calls. The agent takes field names and rules from the
server's agent reference; the JSON payloads in `payloads/` are checked in CI against the reference of a live server.

## 1. Search by brain region and acquisition type

> "Find the sessions with extracellular electrophysiology recordings in CA1."

1. Resolves CA1 in the anatomical regions: 12 regions across 11 atlases; reports which it used.
2. `GET /api/private/modules/experimentalinterface/?filter{target_regions.in}=<CA1 ids>` → interfaces.
3. `GET /api/private/modules/dataacquisition/?filter{type}=ExtracellularEphys&filter{interfaces.in}=<ids>`.
4. Reads `session` on each acquisition, fetches the sessions, and reports them with the evidence chain.

## 2. Find subjects with a particular procedure

> "Which subjects received a virus injection targeting primary visual cortex?"

1. Resolves VISp (three atlases).
2. `GET /api/private/modules/procedure/?filter{type}=VirusInjection&filter{target_regions.in}=<VISp ids>`.
3. Fetches the subjects with `filter{id.in}` and lists them with the injection procedure ids.

## 3. Create a session with a data acquisition

> "Create a session 'R02 linear track 2026-03-02' for SAMPLE Rat R02 - Steve with a 64-channel,
> 30 kHz extracellular recording through R02's silicon probe."

The agent resolves the project, the subject and the probe interface, checks the name is free, and
shows a change plan with two operations. After approval:

- `POST /api/private/stem/session/` with [payloads/create-session.json](payloads/create-session.json)
- `POST /api/private/modules/dataacquisition/` with
  [payloads/create-dataacquisition.json](payloads/create-dataacquisition.json): note the sampling rate as
  `{"value": 30000, "unit": "Hz"}` and the reused interface id.

It then re-reads both records and reports their ids and links.

## 4. Associate metadata with existing resources

> "Register a new mouse, M10, in the project."

The agent looks up the species (*Mus musculus*, from the common name), confirms there is no subject
named M10 yet, asks for the sex and status if not given, then posts
[payloads/create-subject.json](payloads/create-subject.json). It reuses the existing species record
instead of proposing a new one.

## 5. Update a procedure

> "Add a note to R02's silicon probe implant: probe track verified in CA1 and CA3 by histology."

The agent reads the procedure, shows the current and new `notes`, and after approval sends
`PATCH /api/private/modules/procedure/<id>/` with only the changed field
([payloads/update-procedure.json](payloads/update-procedure.json)). Had the user asked to change the
target regions, it would have sent the full new `target_regions` list, because lists are replaced.

## 6. Set up a new project

> "Set up BrainSTEM for our new two-photon project in mice."

The agent interviews for project name, species, rigs, stocks and licenses, lists what already exists
(setups, inventories, assays, species, strains), and proposes one stage at a time: project → setup and
equipment → stocks → subjects → procedures (each implant creates its interface) → sessions. See
the server's `guides/project-setup.md`.

## 7. Export a project

> "Back up the demo project."

The agent checks access, runs `client.export_project(<id>, background=True)` for a large project,
saves the file where asked, and reports the format version, record counts and the export's
limitations as listed in the server's `guides/export.md`.

## 8. Convert a project to NWB

> "Convert the demo project to NWB files in ./nwb."

The agent checks that `brainstem-nwb` is installed, asks for the experimenter, lab and institution
(BrainSTEM does not record them), runs a dry run and reports what would be written, then exports. It
reports the 57 files written, the manifest, and the validation results (pynwb, NWB Inspector with the
DANDI configuration), and says that the files hold metadata only.
