#!/usr/bin/env python3
"""Copy the references each skill needs into skills/<skill>/references/.

Agent environments install skills one directory at a time, so a skill can only read files
inside its own directory. tools/skill_manifest.json lists, per skill, glob patterns relative
to references/. The copies are byte-identical; edit references/ and re-run this script.

    python tools/vendor_references.py           # write
    python tools/vendor_references.py --check   # exit 1 if any skill's copies are out of date
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCES = ROOT / "references"
SKILLS = ROOT / "skills"
MANIFEST = ROOT / "tools" / "skill_manifest.json"


def expected_files(patterns):
    files = {}
    for pattern in patterns:
        matches = sorted(p for p in REFERENCES.glob(pattern) if p.is_file())
        if not matches:
            raise SystemExit(f"skill_manifest.json: pattern {pattern!r} matches no file in references/")
        for path in matches:
            files[path.relative_to(REFERENCES).as_posix()] = path.read_bytes()
    return files


def current_files(target):
    if not target.exists():
        return {}
    return {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if vendored copies are out of date")
    args = parser.parse_args(argv)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["skills"]
    problems = []
    written = removed = 0
    for skill, patterns in sorted(manifest.items()):
        skill_dir = SKILLS / skill
        if not (skill_dir / "SKILL.md").exists():
            problems.append(f"{skill}: skills/{skill}/SKILL.md does not exist")
            continue
        target = skill_dir / "references"
        expected = expected_files(patterns)
        current = current_files(target)
        changed = [name for name, data in expected.items() if current.get(name) != data]
        stale = [name for name in current if name not in expected]
        if args.check:
            problems += [f"{skill}: out of date references/{name}" for name in sorted(changed)]
            problems += [f"{skill}: stale references/{name}" for name in sorted(stale)]
            continue
        for name in changed:
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected[name])
        for name in stale:
            (target / name).unlink()
        for directory in sorted((p for p in target.rglob("*") if p.is_dir()), reverse=True):
            if not any(directory.iterdir()):
                directory.rmdir()
        written += len(changed)
        removed += len(stale)
    if problems:
        print("\n".join(problems))
        if args.check:
            print("Run: python tools/vendor_references.py")
        return 1
    if args.check:
        print(f"vendored references are up to date for {len(manifest)} skills")
    else:
        print(f"wrote {written} files, removed {removed} stale files across {len(manifest)} skills")
    return 0


if __name__ == "__main__":
    sys.exit(main())
