# BrainSTEM Agent Skills

Agent Skills that let AI agents work with [BrainSTEM](https://www.brainstem.org), the electronic lab
notebook and metadata platform for experimental neuroscience, through its REST API. Ask in plain
language ("find sessions with hippocampal silicon-probe recordings", "add a virus injection for
mouse M04") and the agent finds the right records, builds valid API calls, and shows every change for
your approval before writing.

The skills follow the open [Agent Skills](https://agentskills.io) format. They hold agent behavior only:
how to connect, stay safe and confirm writes. Everything about BrainSTEM itself (resources, fields,
relationships, schemas, guides) comes from the **agent reference** that each BrainSTEM server publishes
at `/reference/` (public), generated from its own code. An agent therefore always works from
the description of the exact server it talks to, and nothing in this repository can drift from it.

> **Status: 0.3.0 (preview).** The skills need a server whose agent reference has format 1.x and the
`specimen-1` data model, and the Python client 2.1.0 or later for writes and exports.
www.brainstem.org meets these requirements. See [COMPATIBILITY.md](COMPATIBILITY.md).

## Skills

| Skill | Use it to |
|---|---|
| `brainstem-overview` | learn how BrainSTEM organizes data, where something is recorded, how permissions work |
| `brainstem-search` | find, list and compare records by species, brain region, probe, acquisition type, procedure, behavior, date or numeric parameters (read-only) |
| `brainstem-create` | add projects, subjects, sessions, procedures, recordings, interfaces, materials, specimens and logs |
| `brainstem-update` | correct, link, tag or delete existing records safely |
| `brainstem-project-setup` | onboard a lab or set up a new project, reusing existing resources |
| `brainstem-export` | export a project or session as JSON, or convert it to NWB files with [`brainstem-nwb`](https://github.com/brainstem-org/brainstem-nwb) |

## Install

**Claude Code** (plugin marketplace):

```text
/plugin marketplace add brainstem-org/brainstem-agent-skills
/plugin install brainstem@brainstem
```

Skills then appear as `/brainstem:brainstem-search` and so on, and load automatically when relevant.

**Copying the skill folders** (Claude Code personal or project skills, Codex, other environments that
read `<skill>/SKILL.md` folders):

```bash
git clone https://github.com/brainstem-org/brainstem-agent-skills
cd brainstem-agent-skills
tools/install.sh claude            # ~/.claude/skills
tools/install.sh codex             # ~/.agents/skills
tools/install.sh <directory>       # anywhere else
```

Which environments are tested is listed in [COMPATIBILITY.md](COMPATIBILITY.md).

## Connect to BrainSTEM

1. Install the Python client: `pip install brainstem_python_api_tools` (2.1.0 or later). For NWB
   exports, also `pip install brainstem-nwb`.
2. Authenticate **in your own terminal**, not through the agent: `brainstem login` (opens the browser;
   supports two-factor authentication). Or create a token at
   <https://www.brainstem.org/private/users/tokens/> and `export BRAINSTEM_API_TOKEN=...` before starting
   the agent.
3. For another server (for example a local development instance): `export BRAINSTEM_API_URL=http://127.0.0.1:8000`.

The agent reads the agent reference without a token; it needs the token only for private records.
Agents never ask for your password and are instructed never to print or store your token. You can read
the reference yourself at `<server>/reference/` or with `brainstem reference index.md`, and the JSON
Schemas of every type and version at `<server>/schemas/`.

## Use

Ask naturally; the matching skill loads on its own:

- "Which subjects in project X received optogenetic stimulation of the medial septum?"
- "Create a session for rat R02 on 2 March 2026 with a 64-channel recording at 30 kHz."
- "Add the tag 'reviewed' to session Y."
- "Help me set up BrainSTEM for our new two-photon project."
- "Export project X."
- "Convert project X to NWB files."

Every write is shown first as a change plan; nothing is written until you say yes. Deletes and bulk
changes ask twice. More walkthroughs: [examples/](examples/README.md).

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| "the skills do not match this server" | the server has no agent reference, or a different data model; the skills stay read-only there |
| 401 | token missing or expired: run `brainstem login` in your terminal |
| 403 | your role does not allow it (see the server's `guides/permissions.md`) |
| results look incomplete | the agent reports truncation and unreadable scopes; public-portal searches only see public projects |

## How it works

- **Skills** (`skills/`) describe the workflow for each task and cite pages of the server's agent
  reference (for example `guides/query-planning.md`, `resources/session.md`).
- **Behavior files** (`references/`): connecting and checking compatibility, safety, the
  plan → confirm → execute → verify protocol for writes, and the NWB export workflow with `brainstem-nwb`. `tools/vendor_references.py` copies them into
  each skill, so each skill works when installed alone.
- **Tests** (`tests/`): static checks that every cited reference page exists on the server, a mock API
  that serves the server's reference and schema URLs (downloaded with `tools/fetch_fixtures.py`, not
  committed) and the demo project, contract tests that compare the mock with a real server, and agent
  scenarios graded on the API calls made (`tests/harness/run.py`).
- **Server check** (`tools/check_server.py`): confirms a live server's reference format, data model and
  pages match what the skills cite.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

The skills, references and tools are released under the [MIT License](LICENSE). The demo project fixtures
listed in [LICENSE-DATA](LICENSE-DATA) are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The BrainSTEM agent reference and JSON Schemas are not part of this repository. They belong to BrainSTEM, and
their terms are on each server at `/reference/license.md`; the tests download them with
`tools/fetch_fixtures.py`.
