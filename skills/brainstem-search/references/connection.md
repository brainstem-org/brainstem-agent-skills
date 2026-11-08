# Connecting to BrainSTEM and its agent reference

Run these checks once per session, before the first BrainSTEM operation. Do not assume a tool, a
login, or a permission level exists.

Everything BrainSTEM-specific (resources, fields, relationships, schemas, rules, guides) comes from the
server's **agent reference**, generated from the server's own code. In these skills, a page named
without a `references/` prefix (for example `rules.md` or `guides/query-planning.md`) is a page of
that reference.

## 1. Which server

- Default: `https://www.brainstem.org`.
- If `BRAINSTEM_API_URL` is set, use it (for example a local server `http://127.0.0.1:8000`). Ask the
  user if they mention another server.

## 2. Read the agent reference (public, no token)

The reference lives at `<server>/reference/`. Read a page with the first method that works:

```bash
brainstem reference index.md          # Python client 2.1.0 or later
```

```python
client.agent_reference("index.md")    # same, from Python (client as in section 4)
```

```bash
curl -sSf --compressed "${BRAINSTEM_API_URL:-https://www.brainstem.org}/reference/index.md"
```

Then:

1. **Check compatibility** in the *Versions* section of `index.md`: these skills support
   `format_version` **1.x** and `data_model` **`specimen-1`**.
   - Different major format or data model: tell the user the skills do not match this server; offer
     read-only help and do not write.
   - 404 on `index.md`: the server predates the agent reference; same as above.
2. **Read `rules.md`**, then the guide for the task (listed in `index.md`).
3. **Load other pages only when needed** (`resources/<resource>.md`, `schemas/<Family>/<Type>.md`,
   `relationships.md`, `vocabulary.md`), and do not fetch the same page twice in a session.
4. Treat the reference as the authority on this server. If it contradicts these skills on a BrainSTEM
   fact, follow the reference and mention the difference.

The JSON Schemas behind type-specific payloads are public too, at stable URLs:
`<server>/schemas/<Family>/<Type>.json` (current version), `<server>/schemas/<Family>/<Type>/` (version
list) and `<server>/schemas/<Family>/<Type>/<version>.json` (one exact version). Schema pages in the
reference link the exact version they describe.

## 3. Credentials for data (never expose them)

Reading or writing records needs a token, except public data under `/api/public/...`. Check that a token
exists without reading or printing it:

```bash
[ -n "$BRAINSTEM_API_TOKEN" ] && echo "token in environment"
test -s ~/.config/brainstem/token && echo "cached token present"
```

- Never print, echo, log or paste a token, and never put one in a file you create.
- Never run `brainstem login` yourself: it opens a browser login meant for the user. If there is no
  token and the task needs private data, ask the user to run `brainstem login` in their own terminal,
  or to create a token at `<server>/private/users/tokens/` and export it as `BRAINSTEM_API_TOKEN`. Then
  continue.
- Do not construct a logged-in `BrainstemClient()` or call data commands of the `brainstem` CLI when
  neither check passed: they start a browser login and wait up to 15 minutes. `BrainstemClient(anonymous=True)`
  and `brainstem reference` never log in.
- Without a token you can still answer from public data (`/api/public/...`); say that only public
  projects were searched. When the user asks for public data only, send data requests only to
  `/api/public/...`, not to private endpoints, not even to test access.

## 4. Which tool for data

Use the first one available:

1. **A BrainSTEM MCP server**, if the environment lists tools for it.
2. **The Python client** `brainstem_python_api_tools`
   (`python -c "import importlib.metadata as m; print(m.version('brainstem_python_api_tools'))"`):

   ```python
   import os
   from brainstem_api_tools import BrainstemClient

   client = BrainstemClient(
       token=os.environ.get("BRAINSTEM_API_TOKEN"),   # None -> the cached token
       url=os.environ.get("BRAINSTEM_API_URL"),       # None -> https://www.brainstem.org/
   )
   ```

   Install it with `pip install brainstem_python_api_tools` only if the user agrees.
3. **The `brainstem` CLI** (installed with the client), for single-record reads and writes.
4. **Plain HTTPS** with the header `Authorization: Bearer <token>`.

How to use each one on this server, and the known limits of each client version, is in
`guides/client-usage.md`.

## 5. Report what you found

Before the first operation, tell the user in one line: server, data model, tool, whether you are
authenticated, and (for writes) that changes will be shown for approval first.
