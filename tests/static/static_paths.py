from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def skill_dirs():
    return sorted(p for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").exists())
