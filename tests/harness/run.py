#!/usr/bin/env python3
"""Run agent scenarios against the mock BrainSTEM API and grade them deterministically.

For each scenario: start a fresh mock API with the fixture, install the skills into a temporary
workspace, run the agent headless (one call per turn, resuming the same session), then grade the
mock's request log and the agent's final answer against tests/scenarios/*.yaml and
tests/harness/oracles.py.

    python tests/harness/run.py --agent claude-code --claude-bin "$(which claude)" --allow-bash

The agent runs real shell commands inside a temporary directory with access to your machine, so
--allow-bash must be passed explicitly. Only the mock API URL and a mock token are provided.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "mock_api"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracles  # noqa: E402
from server import serve  # noqa: E402

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
WRITE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
REFERENCE_PREFIX = "/reference/"
EXPORT_JOB = re.compile(r"/(project|session)/[0-9a-f-]{36}/export/$")


# ---------------------------------------------------------------------------
# agents

def run_turn(binary, workspace, env, prompt, session_id=None, model=None, timeout=900):
    """Run one headless turn. Return (final_text, tool_uses, transcript_lines, session_id)."""
    command = [binary, "-p", prompt, "--output-format", "stream-json", "--verbose",
               "--allowedTools", "Bash,Read,Write,Edit,Glob,Grep,Skill"]
    if model:
        command += ["--model", model]
    if session_id:
        command += ["--resume", session_id]
    result = subprocess.run(command, cwd=workspace, env=env, capture_output=True, text=True, timeout=timeout)
    final_text, tool_uses, lines = "", [], result.stdout.splitlines()
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "system" and event.get("session_id"):
            session_id = event["session_id"]
        if event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    tool_uses.append({"name": block.get("name"), "input": block.get("input")})
        if event.get("type") == "result":
            final_text = event.get("result") or ""
    if result.returncode != 0 and not final_text:
        final_text = f"[agent exited {result.returncode}] {result.stderr[-2000:]}"
    return final_text, tool_uses, lines, session_id


def install_skills(workspace, agent):
    target = workspace / (".claude/skills" if agent == "claude-code" else ".agents/skills")
    target.mkdir(parents=True)
    for skill in sorted((ROOT / "skills").iterdir()):
        if (skill / "SKILL.md").exists():
            shutil.copytree(skill, target / skill.name)


# ---------------------------------------------------------------------------
# grading

def load_records(fixture):
    data = json.loads(Path(fixture).read_text(encoding="utf-8"))
    return {name: {r["id"]: r for r in body["records"]} for name, body in data["resources"].items()}


def grade(scenario, final_text, tool_uses, log, records, turn_boundaries):
    expect = scenario.get("expect", {})
    failures = []

    skill = expect.get("skill")
    if skill:
        used = [t["input"].get("skill", "") for t in tool_uses if t["name"] == "Skill" and isinstance(t["input"], dict)]
        if not any(u.split(":")[-1] == skill for u in used):
            failures.append(f"skill {skill} not invoked (used: {used or 'none'})")

    req = expect.get("requests", {})
    # Starting an export job is a POST but changes no records.
    writes = [e for e in log if e["method"] in WRITE_METHODS and not EXPORT_JOB.search(e["path"])]
    if req.get("no_writes") and writes:
        failures.append(f"{len(writes)} write request(s) in a read-only scenario")
    if "max_writes" in req and len(writes) > req["max_writes"]:
        failures.append(f"{len(writes)} writes, expected at most {req['max_writes']}")
    if req.get("no_writes_before_turn"):
        # turn_boundaries[i] is the log length when turn i + 1 ended
        boundary = turn_boundaries[req["no_writes_before_turn"] - 2]
        early = [e for e in log[:boundary] if e["method"] in WRITE_METHODS and not EXPORT_JOB.search(e["path"])]
        if early:
            failures.append(f"{len(early)} write(s) before turn {req['no_writes_before_turn']} (no confirmation)")
    for spec in req.get("must_include", []):
        if not any(_request_matches(e, spec) for e in log):
            failures.append(f"missing request {spec}")
    for spec in req.get("must_not_include", []):
        if any(_request_matches(e, spec) for e in log):
            failures.append(f"forbidden request {spec}")
    reference_reads = [e for e in log if e["path"].startswith(REFERENCE_PREFIX)]
    if expect.get("reads_reference", True) and not any(
            e["path"] in (REFERENCE_PREFIX, REFERENCE_PREFIX + "index.md") and e["status"] == 200 for e in reference_reads):
        failures.append("did not read the agent reference index (compatibility check)")
    if req.get("only_portal"):
        other = [e for e in log if f"/api/{req['only_portal']}/" not in e["path"]
                 and not e["path"].startswith(REFERENCE_PREFIX)]
        if other:
            failures.append(f"{len(other)} request(s) outside the {req['only_portal']} portal")
    if req.get("no_successful_writes"):
        done = [e for e in writes if e["status"] < 300]
        if done:
            failures.append(f"{len(done)} write(s) succeeded but none should")
    for spec in req.get("successful_write", []):
        if not any(_request_matches(e, spec) and e["status"] < 300 for e in log):
            failures.append(f"no successful write {spec}")

    answer = expect.get("answer", {})
    known = {i for by_id in records.values() for i in by_id}
    mentioned = set(UUID.findall(final_text.lower()))
    fabricated = mentioned - known - {e_id for e in log for e_id in UUID.findall(json.dumps(e))}
    if fabricated:
        failures.append(f"answer mentions ids that do not exist: {sorted(fabricated)[:5]}")
    if answer.get("oracle"):
        expected = getattr(oracles, answer["oracle"])(records)
        resource_ids = set(records.get(answer.get("resource", ""), {}))
        missing = expected - mentioned
        extra = (mentioned & resource_ids) - expected
        if missing:
            failures.append(f"answer misses {len(missing)}/{len(expected)} expected {answer.get('resource')} ids")
        if extra:
            failures.append(f"answer includes {len(extra)} {answer.get('resource')} ids that do not match")
    patterns = answer.get("must_match_any", [])
    if patterns and not any(re.search(p, final_text) for p in patterns):
        failures.append(f"answer matches none of {patterns}")
    for pattern in answer.get("must_not_match", []):
        if re.search(pattern, final_text):
            failures.append(f"answer matches forbidden {pattern!r}")
    return failures


def check_files(specs, workspace):
    """Files the agent was asked to write, checked before the temporary workspace is removed."""
    failures = []
    for spec in specs:
        if "glob" in spec:
            matches = [p for p in workspace.glob(spec["glob"]) if p.is_file()]
            if "contains" in spec:
                matches = [p for p in matches if spec["contains"] in p.read_text(encoding="utf-8", errors="replace")]
            if len(matches) < spec.get("min_count", 0):
                failures.append(f"{spec['glob']}: {len(matches)} matching file(s), expected at least {spec['min_count']}")
            if "max_count" in spec and len(matches) > spec["max_count"]:
                failures.append(f"{spec['glob']}: {len(matches)} matching file(s), expected at most {spec['max_count']}")
            continue
        path = workspace / spec["path"]
        if not path.exists():
            failures.append(f"expected file {spec['path']} was not written")
            continue
        if "json_equals" in spec:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                failures.append(f"{spec['path']} is not valid JSON")
                continue
            for dotted, expected in spec["json_equals"].items():
                value = data
                for part in dotted.split("."):
                    value = value.get(part) if isinstance(value, dict) else None
                if value != expected:
                    failures.append(f"{spec['path']}: {dotted} is {value!r}, expected {expected!r}")
    return failures


def _request_matches(entry, spec):
    if "method" in spec and entry["method"] != spec["method"]:
        return False
    if "path_contains" in spec and spec["path_contains"] not in entry["path"]:
        return False
    if "query_contains" in spec and spec["query_contains"] not in json.dumps(entry["query"]):
        return False
    if "body_has" in spec:
        body = entry.get("body") or {}
        if not all(key in body for key in spec["body_has"]):
            return False
    if "body_list_contains" in spec:
        body = entry.get("body") or {}
        for field, values in spec["body_list_contains"].items():
            if not isinstance(body.get(field), list) or not set(values) <= set(body[field]):
                return False
    if "body_path_equals" in spec:
        body = entry.get("body") or {}
        for dotted, expected in spec["body_path_equals"].items():
            value = body
            for part in dotted.split("."):
                value = value.get(part) if isinstance(value, dict) else None
            if value != expected:
                return False
    if "body_only" in spec:
        body = entry.get("body") or {}
        if not set(body) <= set(spec["body_only"]):
            return False
    return True


# ---------------------------------------------------------------------------

def run_scenario(scenario, args, out_dir):
    records = load_records(args.fixture)
    with tempfile.TemporaryDirectory(prefix="brainstem-eval-") as tmp:
        workspace = Path(tmp)
        install_skills(workspace, args.agent)
        log_path = workspace / "requests.jsonl"
        server, store = serve(args.fixture, 0, str(log_path))
        for patch in scenario.get("fixture_patches", []):
            store.records[patch["resource"]][patch["id"]].update(patch["set"])
        threading.Thread(target=server.serve_forever, daemon=True).start()
        env = dict(os.environ)
        env["BRAINSTEM_API_URL"] = f"http://127.0.0.1:{server.server_address[1]}"
        env.pop("BRAINSTEM_API_TOKEN", None)
        if scenario.get("token"):
            env["BRAINSTEM_API_TOKEN"] = scenario["token"]
        if args.python_bin_dir:
            env["PATH"] = f"{args.python_bin_dir}{os.pathsep}{env['PATH']}"
        started = time.time()
        turn_boundaries, final_text, tool_uses, transcript, session_id = [], "", [], [], None
        for turn in scenario["turns"]:
            final_text, uses, lines, session_id = run_turn(
                args.claude_bin, workspace, env, turn, session_id=session_id, model=args.model)
            turn_boundaries.append(_log_length(log_path))
            tool_uses, transcript = tool_uses + uses, transcript + lines
        server.shutdown()
        log = [json.loads(line) for line in log_path.read_text().splitlines()] if log_path.exists() else []
        file_failures = check_files(scenario.get("expect", {}).get("files", []), workspace)
    failures = grade(scenario, final_text, tool_uses, log, records, turn_boundaries) + file_failures
    models = sorted(set(re.findall(r'"model":"([^"]+)"', "\n".join(transcript))))
    result = {"id": scenario["id"], "passed": not failures, "failures": failures, "models": models,
              "seconds": round(time.time() - started), "requests": len(log), "answer": final_text}
    (out_dir / f"{scenario['id']}.json").write_text(
        json.dumps({**result, "requests_log": log, "tool_uses": tool_uses}, indent=1), encoding="utf-8")
    (out_dir / f"{scenario['id']}.transcript.jsonl").write_text("\n".join(transcript), encoding="utf-8")
    return result


def _log_length(path):
    return len(path.read_text().splitlines()) if path.exists() else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agent", choices=["claude-code"], default="claude-code")
    parser.add_argument("--claude-bin", default=shutil.which("claude") or "claude")
    parser.add_argument("--model")
    parser.add_argument("--scenarios", default=str(ROOT / "tests" / "scenarios"))
    parser.add_argument("--fixture", default=str(ROOT / "tests" / "fixtures" / "demo_lab.json"))
    parser.add_argument("--python-bin-dir", help="directory put first on PATH (e.g. a venv's bin with the client)")
    parser.add_argument("--only", action="append", help="run only these scenario ids")
    parser.add_argument("--out", default=str(ROOT / "tests" / "harness" / "runs"))
    parser.add_argument("--allow-bash", action="store_true", help="required: the agent runs shell commands")
    args = parser.parse_args(argv)
    if not args.allow_bash:
        parser.error("pass --allow-bash to confirm the agent may run shell commands on this machine")
    scenarios = []
    for path in sorted(Path(args.scenarios).glob("*.yaml")):
        scenarios.extend(yaml.safe_load(path.read_text(encoding="utf-8")))
    if args.only:
        scenarios = [s for s in scenarios if s["id"] in args.only]
    out_dir = Path(args.out) / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True)
    results = []
    for scenario in scenarios:
        result = run_scenario(scenario, args, out_dir)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status} {result['id']} ({result['seconds']}s, {result['requests']} requests)", flush=True)
        for failure in result["failures"]:
            print(f"     - {failure}", flush=True)
    passed = sum(r["passed"] for r in results)
    summary = {"agent": args.agent, "model": args.model, "passed": passed, "total": len(results), "results": results}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"\n{passed}/{len(results)} passed. Details: {out_dir}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
